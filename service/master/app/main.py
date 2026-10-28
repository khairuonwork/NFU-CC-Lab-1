from fastapi import FastAPI

from app.api.routes.inference import router as inference_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.services.redis_client import create_redis_client
from app.services.rustfs_client import create_rustfs_client

class ApplicationLifespan:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def __aenter__(self) -> None:
        settings = get_settings()

        self.app.state.redis = create_redis_client(settings.redis_url)
        self.app.state.rustfs = create_rustfs_client(settings)

    async def __aexit__(self, *_: object) -> None:
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
