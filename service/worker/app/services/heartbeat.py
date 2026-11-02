import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from redis.asyncio import Redis

from app.core.config import Settings

class WorkerState(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    TRAINING = "training"

# In-memory state exposed by the worker heartbeat
@dataclass
class WorkerRuntime:
    state: WorkerState = WorkerState.IDLE
    current_job_id: str = ""

# Refresh the worker state record in Redis
async def publish_heartbeat(
    redis: Redis,
    settings: Settings,
    runtime: WorkerRuntime,
) -> None:
    key = f"cc:worker:{settings.worker_id}"
    now = datetime.now(timezone.utc).isoformat()

    async with redis.pipeline(transaction=True) as pipeline:
        pipeline.hset(
            key,
            mapping={
                "worker_id": settings.worker_id,
                "state": runtime.state,
                "last_seen_at": now,
                "current_job_id": runtime.current_job_id,
            },
        )
        pipeline.expire(key, settings.heartbeat_ttl_seconds)
        await pipeline.execute()

# Keep the worker visible while it waits for Stream messages
async def run_heartbeat_loop(
    redis: Redis,
    settings: Settings,
    runtime: WorkerRuntime,
) -> None:
    while True:
        await publish_heartbeat(redis, settings, runtime)
        await asyncio.sleep(settings.heartbeat_interval_seconds)
