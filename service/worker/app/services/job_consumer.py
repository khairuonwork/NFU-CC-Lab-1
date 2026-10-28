from datetime import datetime, timezone

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import Settings
from app.handlers.inference import run_inference
from app.schemas.inference_contract import InferenceJob, InferenceResult
from app.services.heartbeat import WorkerRuntime, WorkerState

# Create the Consumer Group once and ignore an existing group.
async def ensure_consumer_group(redis: Redis, stream_key: str, group_name: str) -> None:
    try:
        await redis.xgroup_create(stream_key, group_name, id="0-0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise

# Claim one job left pending by a previous worker process.
async def claim_stale_message(
    redis: Redis,
    settings: Settings,
    stream_key: str,
) -> tuple[str, dict[str, str]] | None:
    _, messages, _ = await redis.xautoclaim(
        stream_key,
        settings.consumer_group_name,
        settings.worker_id,
        settings.pending_job_reclaim_idle_ms,
        start_id="0-0",
        count=1,
    )

    if not messages:
        return None

    return messages[0]

# Read this worker stream, store the result, then acknowledge the entry.
async def consume_inference_jobs(
    redis: Redis,
    settings: Settings,
    runtime: WorkerRuntime,
    rustfs: object,
) -> None:
    stream_key = f"cc:queue:{settings.worker_id}"
    await ensure_consumer_group(redis, stream_key, settings.consumer_group_name)

    while True:
        stale_message = await claim_stale_message(redis, settings, stream_key)
        if stale_message:
            message_id, fields = stale_message
            await _process_message(
                redis,
                settings,
                runtime,
                rustfs,
                stream_key,
                message_id,
                fields,
            )
            continue

        records = await redis.xreadgroup(
            settings.consumer_group_name,
            settings.worker_id,
            {stream_key: ">"},
            count=1,
            block=settings.stream_block_ms,
        )
        if not records:
            continue

        for _, messages in records:
            for message_id, fields in messages:
                await _process_message(
                    redis,
                    settings,
                    runtime,
                    rustfs,
                    stream_key,
                    message_id,
                    fields,
                )

# Process one message or acknowledge it when its result already exists.
async def _process_message(
    redis: Redis,
    settings: Settings,
    runtime: WorkerRuntime,
    rustfs: object,
    stream_key: str,
    message_id: str,
    fields: dict[str, str],
) -> None:
    job = InferenceJob.model_validate_json(fields["payload"])
    result_key = f"cc:result:{job.job_id}:{settings.worker_id}"

    if await redis.get(result_key):
        await _acknowledge_job(redis, settings, stream_key, message_id, job)
        return

    runtime.state = WorkerState.BUSY
    runtime.current_job_id = str(job.job_id)
    await redis.hset(f"cc:job:{job.job_id}", mapping={"status": "processing"})

    try:
        result = await run_inference(job, settings.worker_id, rustfs, settings)
    except Exception as error:
        result = InferenceResult(
            job_id=job.job_id,
            worker_id=settings.worker_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=str(error),
        )

    try:
        await redis.set(
            result_key,
            result.model_dump_json(),
            ex=settings.result_ttl_seconds,
        )
        await _acknowledge_job(redis, settings, stream_key, message_id, job)
    finally:
        runtime.state = WorkerState.IDLE
        runtime.current_job_id = ""

# Acknowledge delivery and release the matching worker reservation.
async def _acknowledge_job(
    redis: Redis,
    settings: Settings,
    stream_key: str,
    message_id: str,
    job: InferenceJob,
) -> None:
    await redis.xack(stream_key, settings.consumer_group_name, message_id)

    reservation_key = f"cc:reservation:{settings.worker_id}"
    if await redis.get(reservation_key) == str(job.job_id):
        await redis.delete(reservation_key)
