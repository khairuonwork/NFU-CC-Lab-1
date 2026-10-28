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
