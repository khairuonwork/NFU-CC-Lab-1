from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.services.redis_client import create_redis_client
from app.services.rustfs_client import create_rustfs_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    app.state.redis = create_redis_client(settings.redis_url)
    app.state.rustfs = create_rustfs_client(settings)

    yield

    await app.state.redis.aclose()


settings = get_settings()

app = FastAPI(
    title=settings.master_name,
    description="Controller API for the distributed AI lab.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(system_router)
