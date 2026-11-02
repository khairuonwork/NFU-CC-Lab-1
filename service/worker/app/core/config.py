from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    worker_id: str
    redis_url: str = "redis://localhost:6379/0"
    heartbeat_ttl_seconds: int = Field(default=15, ge=2)
    heartbeat_interval_seconds: int = Field(default=5, ge=1)
    consumer_group_name: str = "cc-workers"
    stream_block_ms: int = Field(default=1000, ge=100)
    pending_job_reclaim_idle_ms: int = Field(default=60_000, ge=1_000)
    result_ttl_seconds: int = Field(default=300, ge=30)
    rustfs_endpoint_url: str = "http://localhost:9000"
    rustfs_access_key: str = ""
    rustfs_secret_key: str = ""
    rustfs_region: str = "tw-taipei-1"
    rustfs_bucket: str = "cc-lab"
    worker_cache_dir: Path = Path("/tmp/cc-worker-cache")
    model_key: str = "models/baseline-mobilenetv3-small.onnx"
    model_cache_dir: Path = Path("/tmp/cc-worker-model-cache")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CC_",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
