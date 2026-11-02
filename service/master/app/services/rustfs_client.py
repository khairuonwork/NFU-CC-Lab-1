from typing import Any

import boto3
from botocore.exceptions import ClientError

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


# Create the application bucket once before the Controller accepts uploads.
def ensure_bucket(client: Any, bucket_name: str) -> None:
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError as error:
        error_code = error.response["Error"].get("Code")
        if error_code not in {"404", "NoSuchBucket", "NotFound"}:
            raise

        client.create_bucket(Bucket=bucket_name)
