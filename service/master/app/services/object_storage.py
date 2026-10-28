import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings

ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# Upload an inference image and return its RustFS object key
async def upload_inference_image(
    rustfs: Any,
    settings: Settings,
    file: UploadFile,
) -> str:
    original_name = file.filename or ""
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("Only JPG, JPEG, PNG, and WEBP image files are accepted")

    object_key = f"uploads/inference/{uuid4()}{suffix}"
    extra_args = {"ContentType": file.content_type or "application/octet-stream"}

    await asyncio.to_thread(
        rustfs.upload_fileobj,
        file.file,
        settings.rustfs_bucket,
        object_key,
        ExtraArgs=extra_args,
    )

    return object_key

# Delete an uploaded object when the job cannot be queued
async def delete_object(rustfs: Any, settings: Settings, object_key: str) -> None:
    await asyncio.to_thread(
        rustfs.delete_object,
        Bucket=settings.rustfs_bucket,
        Key=object_key,
    )
