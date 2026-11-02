import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import Settings

# Download one input object into this worker's local temporary cache.
async def download_inference_image(
    rustfs: Any,
    settings: Settings,
    job_id: UUID,
    image_key: str,
) -> Path:
    suffix = Path(image_key).suffix.lower()
    local_path = settings.worker_cache_dir / f"{job_id}{suffix}"
    await asyncio.to_thread(settings.worker_cache_dir.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(
        rustfs.download_file,
        settings.rustfs_bucket,
        image_key,
        str(local_path),
    )
    return local_path

# Remove the local copy after the worker has produced its result.
def delete_cached_image(local_path: Path) -> None:
    local_path.unlink(missing_ok=True)

# Download the configured ONNX model once and keep it in the persistent model cache.
async def download_model(
    rustfs: Any,
    settings: Settings,
) -> Path:
    local_path = settings.model_cache_dir / Path(settings.model_key).name
    temporary_path = local_path.with_suffix(f"{local_path.suffix}.partial")

    if local_path.is_file():
        return local_path

    await asyncio.to_thread(settings.model_cache_dir.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(
        rustfs.download_file,
        settings.rustfs_bucket,
        settings.model_key,
        str(temporary_path),
    )
    await asyncio.to_thread(temporary_path.replace, local_path)
    return local_path
