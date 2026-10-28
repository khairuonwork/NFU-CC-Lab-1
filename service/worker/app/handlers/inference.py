from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.schemas.inference_contract import InferenceJob, InferenceResult
from app.services.object_storage import delete_cached_image, download_inference_image

# Download the image first. ONNX Runtime classification is added next.
async def run_inference(
    job: InferenceJob,
    worker_id: str,
    rustfs: Any,
    settings: Settings,
) -> InferenceResult:
    local_path = await download_inference_image(
        rustfs,
        settings,
        job.job_id,
        job.image_key,
    )

    try:
        raise NotImplementedError(
            "ONNX inference is not configured yet"
        )
    finally:
        delete_cached_image(local_path)
