from typing import Any

import boto3

from app.core.config import Settings

# Create the S3-compatible RustFS client
def create_rustfs_client(settings: Settings) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.rustfs_endpoint_url,
        aws_access_key_id=settings.rustfs_access_key,
        aws_secret_access_key=settings.rustfs_secret_key,
        region_name=settings.rustfs_region,
    )
