from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    master_name: str = "cc-master"
    master_host: str = "0.0.0.0"
    master_port: int = 8000

    redis_url: str = "redis://localhost:6379/0"
    worker_ids_csv: str = "node1,node2"
    worker_reservation_ttl_seconds: int = Field(default=30, ge=5)
    job_ttl_seconds: int = Field(default=300, ge=30)

    rustfs_endpoint_url: str = "http://localhost:9000"
    rustfs_access_key: str = ""
    rustfs_secret_key: str = ""
    rustfs_region: str = "tw-taipei-1"
    rustfs_bucket: str = "cc-lab"

    @property
    def worker_id_list(self) -> tuple[str, ...]:
        return tuple(
            worker_id.strip()
            for worker_id in self.worker_ids_csv.split(",")
            if worker_id.strip()
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CC_",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
