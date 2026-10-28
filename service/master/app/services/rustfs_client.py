from typing import Any

import boto3

from app.core.config import Settings


def create_rustfs_client(settings: Settings) -> Any:
    """Create an S3-compatible client for RustFS."""

    return boto3.client(
        "s3",
        endpoint_url=settings.rustfs_endpoint_url,
        aws_access_key_id=settings.rustfs_access_key,
        aws_secret_access_key=settings.rustfs_secret_key,
        region_name=settings.rustfs_region,
    )
