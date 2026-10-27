from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

CONTROLLER_DIRECTORY = Path(__file__).parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CONTROLLER_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        )

    controller_name: str = "cc-controller"

    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_db: str | None = None
    postgres_user: str | None = None 
    postgres_password: str | None = None

    redis_host: str | None = None
    redis_port: int = 6379
    redis_password: str | None = None 

    rustfs_health_url: str | None = None

    @property
    def postgres_is_configured(self) -> bool:
        return all([
            self.postgres_host,
            self.postgres_port,
            self.postgres_db,
            self.postgres_user,
            self.postgres_password
        ])

    @property
    def redis_is_configured(self) -> bool:
        return all([
            self.redis_host,
            self.redis_port,
            self.redis_password
        ])

    @property
    def rustfs_is_configured(self) -> bool:
        return bool(self.rustfs_health_url)

@lru_cache()
def get_settings() -> Settings:
    return Settings()