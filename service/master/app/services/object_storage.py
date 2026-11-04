import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings

ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
INFERENCE_UPLOAD_PREFIX = "uploads/inference/"
EXPECTED_IMAGE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}

logger = logging.getLogger(__name__)


# Verify the image content and rewind the upload before RustFS reads it.
def _validate_upload(file: UploadFile, suffix: str, max_bytes: int) -> None:
    stream = file.file
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)

    if size == 0:
        raise ValueError("The uploaded image is empty")

    if size > max_bytes:
        limit_megabytes = max_bytes // (1024 * 1024)
        raise ValueError(f"The uploaded image exceeds the {limit_megabytes} MB limit")

    try:
        with Image.open(stream) as image:
            image.verify()
            image_format = image.format
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as error:
        raise ValueError("The uploaded file is not a valid image") from error
    finally:
        stream.seek(0)

    if image_format != EXPECTED_IMAGE_FORMATS[suffix]:
        raise ValueError("The file extension does not match the uploaded image format")

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

    await asyncio.to_thread(_validate_upload, file, suffix, settings.upload_max_bytes)

    object_key = f"{INFERENCE_UPLOAD_PREFIX}{uuid4()}{suffix}"
    extra_args = {"ContentType": file.content_type or "application/octet-stream"}

    await asyncio.to_thread(
        rustfs.upload_fileobj,
        file.file,
        settings.rustfs_bucket,
        object_key,
        ExtraArgs=extra_args,
    )

    return object_key

# Delete an upload after it is no longer required.
async def delete_object(rustfs: Any, settings: Settings, object_key: str) -> None:
    await asyncio.to_thread(
        rustfs.delete_object,
        Bucket=settings.rustfs_bucket,
        Key=object_key,
    )


# Remove inference uploads that outlive the configured retention window.
async def delete_expired_inference_uploads(rustfs: Any, settings: Settings) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.upload_retention_seconds,
    )
    continuation_token: str | None = None

    while True:
        arguments: dict[str, str] = {
            "Bucket": settings.rustfs_bucket,
            "Prefix": INFERENCE_UPLOAD_PREFIX,
        }
        if continuation_token:
            arguments["ContinuationToken"] = continuation_token

        page = await asyncio.to_thread(rustfs.list_objects_v2, **arguments)
        for item in page.get("Contents", []):
            if item["LastModified"] < cutoff:
                await delete_object(rustfs, settings, item["Key"])

        if not page.get("IsTruncated"):
            return

        continuation_token = page.get("NextContinuationToken")
        if not continuation_token:
            return


# Continue cleanup even when the browser no longer polls its job result.
async def run_upload_cleanup_loop(rustfs: Any, settings: Settings) -> None:
    while True:
        await asyncio.sleep(settings.upload_cleanup_interval_seconds)
        try:
            await delete_expired_inference_uploads(rustfs, settings)
        except Exception:
            logger.exception("Unable to clean up expired inference uploads")
