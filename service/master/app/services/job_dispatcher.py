import json
import random
from datetime import datetime, timezone
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas.inference_contract import ExecutionMode, InferenceJob, InferenceOrder

# Returned when the requested mode cannot reserve enough workers.
class WorkerUnavailableError(Exception):
    def __init__(
        self,
        required_workers: int,
        available_workers: int,
        worker_states: dict[str, str],
    ) -> None:
        self.required_workers = required_workers
        self.available_workers = available_workers
        self.worker_states = worker_states
        super().__init__("Not enough idle workers are available")

# Turn UI orders into explicit worker jobs.
class JobDispatcher:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    # Read the chosen mode then hand the order to its explicit operation.
    async def accept_order(
        self,
        order: InferenceOrder,
    ) -> tuple[InferenceJob, list[str]]:
        if order.execution_mode is ExecutionMode.LOAD_BALANCE:
            return await self.load_balance(order)

        return await self.ensemble_inference(order)

    # Send one job to one idle worker.
    async def load_balance(
        self,
        order: InferenceOrder,
    ) -> tuple[InferenceJob, list[str]]:
        return await self._queue_order(order, required_workers=1)

    # Send the same job to both idle workers for probability averaging.
    async def ensemble_inference(
        self,
        order: InferenceOrder,
    ) -> tuple[InferenceJob, list[str]]:
        return await self._queue_order(order, required_workers=2)

    # Return current worker availability and execution-mode capability for the UI.
    async def read_worker_statuses(self) -> dict[str, object]:
        worker_ids = list(self.settings.worker_id_list)
        workers = await self._read_worker_status_details(worker_ids)
        available_workers = sum(
            1
            for worker in workers
            if worker["available"] is True
        )

        return {
            "workers": workers,
            "available_workers": available_workers,
            "execution_modes": {
                "load_balance": {
                    "enabled": available_workers >= 1,
                    "required_workers": 1,
                    "available_workers": available_workers,
                },
                "ensemble": {
                    "enabled": available_workers >= 2,
                    "required_workers": 2,
                    "available_workers": available_workers,
                },
            },
        }

    # Create one job, reserve enough workers, then send the Stream messages.
    async def _queue_order(
        self,
        order: InferenceOrder,
        required_workers: int,
    ) -> tuple[InferenceJob, list[str]]:
        job = InferenceJob(
            job_id=uuid4(),
            execution_mode=order.execution_mode,
            image_key=order.image_key,
            submitted_at=datetime.now(timezone.utc),
        )
        worker_ids = await self._reserve_workers(job.job_id, required_workers)

        try:
            # Store before XADD so a fast worker cannot overwrite its status.
            await self._store_job_metadata(job, worker_ids)
            await self._publish_job(job, worker_ids)
        except Exception:
            await self.redis.delete(f"cc:job:{job.job_id}")
            await self._release_workers(job.job_id, worker_ids)
            raise

        return job, worker_ids

    # Write one copy of the job into each reserved worker Stream.
    async def _publish_job(
        self,
        job: InferenceJob,
        worker_ids: list[str],
    ) -> None:
        payload = json.dumps(job.model_dump(mode="json"))
        for worker_id in worker_ids:
            await self.redis.xadd(
                f"cc:queue:{worker_id}",
                {"payload": payload},
            )

    # Read heartbeat hashes and short reservation locks in one Redis round trip.
    async def _read_worker_status_details(
        self,
        worker_ids: list[str],
    ) -> list[dict[str, object]]:
        async with self.redis.pipeline(transaction=False) as pipeline:
            for worker_id in worker_ids:
                pipeline.hgetall(f"cc:worker:{worker_id}")
                pipeline.get(f"cc:reservation:{worker_id}")
            records = await pipeline.execute()

        workers: list[dict[str, object]] = []
        for index, worker_id in enumerate(worker_ids):
            heartbeat = records[index * 2]
            reservation_job_id = records[(index * 2) + 1]
            reported_state = heartbeat.get("state", "offline")
            state = (
                "reserved"
                if reservation_job_id and reported_state == "idle"
                else reported_state
            )

            workers.append(
                {
                    "worker_id": worker_id,
                    "state": state,
                    "available": state == "idle",
                    "last_seen_at": heartbeat.get("last_seen_at"),
                    "current_job_id": heartbeat.get("current_job_id") or None,
                }
            )

        return workers

    # Store short-lived job state for UI polling.
    async def _store_job_metadata(
        self,
        job: InferenceJob,
        worker_ids: list[str],
    ) -> None:
        job_key = f"cc:job:{job.job_id}"
        await self.redis.hset(
            job_key,
            mapping={
                "status": "queued",
                "image_key": job.image_key,
                "execution_mode": job.execution_mode,
                "worker_ids": json.dumps(worker_ids),
                "submitted_at": job.submitted_at.isoformat(),
            },
        )
        await self.redis.expire(job_key, self.settings.job_ttl_seconds)

    # Reserve only workers whose latest heartbeat says idle.
    async def _reserve_workers(self, job_id: UUID, worker_count: int) -> list[str]:
        candidates = list(self.settings.worker_id_list)
        worker_states = await self._read_worker_states(candidates)
        random.shuffle(candidates)
        reserved: list[str] = []

        for worker_id in candidates:
            if worker_states[worker_id] != "idle":
                continue

            acquired = await self.redis.set(
                f"cc:reservation:{worker_id}",
                str(job_id),
                nx=True,
                ex=self.settings.worker_reservation_ttl_seconds,
            )
            if acquired:
                reserved.append(worker_id)
            else:
                worker_states[worker_id] = "reserved"

            if len(reserved) == worker_count:
                return reserved

        await self._release_workers(job_id, reserved)
        raise WorkerUnavailableError(
            required_workers=worker_count,
            available_workers=len(reserved),
            worker_states=worker_states,
        )

    # Read only the state needed while selecting workers for an order.
    async def _read_worker_states(self, worker_ids: list[str]) -> dict[str, str]:
        states: dict[str, str] = {}

        for worker_id in worker_ids:
            worker = await self.redis.hgetall(f"cc:worker:{worker_id}")
            states[worker_id] = worker.get("state", "offline")

        return states

    # Release only reservations owned by this job.
    async def _release_workers(self, job_id: UUID, worker_ids: list[str]) -> None:
        for worker_id in worker_ids:
            reservation_key = f"cc:reservation:{worker_id}"
            if await self.redis.get(reservation_key) == str(job_id):
                await self.redis.delete(reservation_key)
