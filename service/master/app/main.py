import asyncio

from fastapi import FastAPI

from app.api.routes.inference import router as inference_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.services.redis_client import create_redis_client
from app.services.object_storage import run_upload_cleanup_loop
from app.services.rustfs_client import create_rustfs_client, ensure_bucket

class ApplicationLifespan:
    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self.upload_cleanup_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> None:
        settings = get_settings()

        self.app.state.redis = create_redis_client(settings.redis_url)
        self.app.state.rustfs = create_rustfs_client(settings)
        ensure_bucket(self.app.state.rustfs, settings.rustfs_bucket)
        self.upload_cleanup_task = asyncio.create_task(
            run_upload_cleanup_loop(self.app.state.rustfs, settings),
            name="inference-upload-cleanup",
        )

    async def __aexit__(self, *_: object) -> None:
        if self.upload_cleanup_task:
            self.upload_cleanup_task.cancel()
            try:
                await self.upload_cleanup_task
            except asyncio.CancelledError:
                pass
        await self.app.state.redis.aclose()

def lifespan(app: FastAPI) -> ApplicationLifespan:
    return ApplicationLifespan(app)

settings = get_settings()

app = FastAPI(
    title=settings.master_name,
    description="Controller API for the distributed AI lab.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(system_router)
app.include_router(inference_router)
