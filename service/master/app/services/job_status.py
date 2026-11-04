import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas.inference_contract import InferenceResult

# Read temporary job state and any worker results from Redis
async def read_inference_job(
    redis: Redis,
    job_id: str,
    settings: Settings,
) -> dict[str, Any] | None:
    metadata = await redis.hgetall(f"cc:job:{job_id}")
    if not metadata:
        return None

    worker_ids = json.loads(metadata["worker_ids"])
    worker_results: list[dict[str, Any]] = []

    for worker_id in worker_ids:
        raw_result = await redis.get(f"cc:result:{job_id}:{worker_id}")
        if raw_result:
            result = InferenceResult.model_validate_json(raw_result)
            worker_results.append(result.model_dump(mode="json"))

    state, reason = _resolve_state(
        metadata["status"],
        metadata["submitted_at"],
        worker_ids,
        worker_results,
        settings.job_timeout_seconds,
    )
    response: dict[str, Any] = {
        "job_id": job_id,
        "status": state,
        "image_key": metadata["image_key"],
        "execution_mode": metadata["execution_mode"],
        "worker_ids": worker_ids,
        "worker_results": worker_results,
    }

    if state == "succeeded":
        response["result"] = _build_result(metadata["execution_mode"], worker_results)

    if reason:
        response["reason"] = reason
        response["missing_worker_ids"] = [
            worker_id
            for worker_id in worker_ids
            if worker_id not in {result["worker_id"] for result in worker_results}
        ]

    return response

# Resolve UI state from the job record and available worker results
def _resolve_state(
    stored_state: str,
    submitted_at: str,
    worker_ids: list[str],
    worker_results: list[dict[str, Any]],
    job_timeout_seconds: int,
) -> tuple[str, str | None]:
    if len(worker_results) < len(worker_ids):
        deadline = datetime.fromisoformat(submitted_at) + timedelta(
            seconds=job_timeout_seconds,
        )
        if datetime.now(timezone.utc) >= deadline:
            return "failed", "job_timeout"

        return stored_state, None

    if any(result["status"] == "failed" for result in worker_results):
        return "failed", "worker_failed"

    return "succeeded", None

# Return one result for load balance or averaged probabilities for ensemble
def _build_result(
    execution_mode: str,
    worker_results: list[dict[str, Any]], # label: score
) -> dict[str, Any]:
    if execution_mode == "load_balance":
        return worker_results[0]

    totals: defaultdict[str, float] = defaultdict(float)
    for result in worker_results:
        for label, score in (result["probabilities"] or {}).items():
            totals[label] += score

    probabilities = {
        label: score / len(worker_results)
        for label, score in totals.items()
    }
    label = max(probabilities, key=probabilities.get) if probabilities else None

    return {
        "label": label,
        "probabilities": probabilities,
        "worker_ids": [result["worker_id"] for result in worker_results],
    }
