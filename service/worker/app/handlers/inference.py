from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from app.core.config import Settings
from app.schemas.inference_contract import InferenceJob, InferenceResult
from app.services.model_runtime import OnnxImageClassifier
from app.services.object_storage import delete_cached_image, download_inference_image

# Download one image, run the cached model, then remove the temporary input file.
async def run_inference(
    job: InferenceJob,
    worker_id: str,
    rustfs: Any,
    settings: Settings,
    classifier: OnnxImageClassifier,
) -> InferenceResult:
    local_path = await download_inference_image(
        rustfs,
        settings,
        job.job_id,
        job.image_key,
    )

    try:
        started_at = perf_counter()
        label, probabilities = await classifier.classify(local_path)
        elapsed_ms = round((perf_counter() - started_at) * 1_000)

        return InferenceResult(
            job_id=job.job_id,
            worker_id=worker_id,
            status="succeeded",
            label=label,
            probabilities=probabilities,
            model_key=settings.model_key,
            elapsed_ms=elapsed_ms,
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        delete_cached_image(local_path)
