import asyncio

from app.core.config import get_settings
from app.services.control_consumer import consume_worker_controls
from app.services.heartbeat import WorkerRuntime, run_heartbeat_loop
from app.services.job_consumer import consume_inference_jobs
from app.services.model_runtime import create_model_runtime
from app.services.redis_client import create_redis_client
from app.services.rustfs_client import create_rustfs_client

# Run one worker heartbeat and its dedicated Redis Stream consumer
async def run_worker() -> None:
    settings = get_settings()
    runtime = WorkerRuntime()
    redis = create_redis_client(settings.redis_url)
    rustfs = create_rustfs_client(settings)
    classifier = await create_model_runtime(rustfs, settings)
    heartbeat_task = asyncio.create_task(
        run_heartbeat_loop(redis, settings, runtime),
        name="worker-heartbeat",
    )
    control_task = asyncio.create_task(
        consume_worker_controls(redis, settings, runtime),
        name="worker-control-consumer",
    )

    try:
        await consume_inference_jobs(
            redis,
            settings,
            runtime,
            rustfs,
            classifier,
        )
    finally:
        heartbeat_task.cancel()
        control_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        try:
            await control_task
        except asyncio.CancelledError:
            pass
        await redis.aclose()

if __name__ == "__main__":
    asyncio.run(run_worker())
