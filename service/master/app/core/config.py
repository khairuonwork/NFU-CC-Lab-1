from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration read from environment variables."""

    master_name: str = "cc-master"
    master_host: str = "0.0.0.0"
    master_port: int = 8000

    redis_url: str = "redis://localhost:6379/0"

    rustfs_endpoint_url: str = "http://localhost:9000"
    rustfs_access_key: str = ""
    rustfs_secret_key: str = ""
    rustfs_region: str = "ap-east-1"
    rustfs_bucket: str = "cc-lab"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CC_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
