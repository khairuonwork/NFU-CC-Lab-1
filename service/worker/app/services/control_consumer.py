from redis.asyncio import Redis
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.inference_contract import WorkerControlMessage
from app.services.heartbeat import WorkerRuntime, publish_heartbeat
from app.services.job_consumer import ensure_consumer_group


async def consume_worker_controls(
    redis: Redis,
    settings: Settings,
    runtime: WorkerRuntime,
) -> None:
    stream_key = f"cc:control:{settings.worker_id}"
    await ensure_consumer_group(
        redis,
        stream_key,
        settings.control_consumer_group_name,
    )

    while True:
        stale_message = await _claim_stale_control(redis, settings, stream_key)
        if stale_message:
            message_id, fields = stale_message
            await _process_control_message(
                redis,
                settings,
                runtime,
                stream_key,
                message_id,
                fields,
            )
            continue

        records = await redis.xreadgroup(
            settings.control_consumer_group_name,
            settings.worker_id,
            {stream_key: ">"},
            count=1,
            block=settings.stream_block_ms,
        )

        for _, messages in records:
            for message_id, fields in messages:
                await _process_control_message(
                    redis,
                    settings,
                    runtime,
                    stream_key,
                    message_id,
                    fields,
                )


async def _claim_stale_control(
    redis: Redis,
    settings: Settings,
    stream_key: str,
) -> tuple[str, dict[str, str]] | None:
    _, messages, _ = await redis.xautoclaim(
        stream_key,
        settings.control_consumer_group_name,
        settings.worker_id,
        settings.pending_job_reclaim_idle_ms,
        start_id="0-0",
        count=1,
    )

    if not messages:
        return None

    return messages[0]


async def _process_control_message(
    redis: Redis,
    settings: Settings,
    runtime: WorkerRuntime,
    stream_key: str,
    message_id: str,
    fields: dict[str, str],
) -> None:
    try:
        message = WorkerControlMessage.model_validate_json(fields["payload"])
    except (KeyError, ValidationError):
        await redis.xack(
            stream_key,
            settings.control_consumer_group_name,
            message_id,
        )
        return

    await publish_heartbeat(redis, settings, runtime)
    await redis.set(
        f"cc:heartbeat-refresh:{message.request_id}:{settings.worker_id}",
        "acknowledged",
        ex=settings.control_ack_ttl_seconds,
    )
    await redis.xack(
        stream_key,
        settings.control_consumer_group_name,
        message_id,
    )
