from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(tags=["System"])


@router.get("/")
async def root() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.master_name,
        "status": "running",
        "documentation": "/docs",
    }


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(request: Request) -> JSONResponse:
    dependencies: dict[str, Literal["ready", "not_ready"]] = {}

    try:
        await request.app.state.redis.ping()
        dependencies["redis"] = "ready"
    except Exception:
        dependencies["redis"] = "not_ready"

    try:
        request.app.state.rustfs.list_buckets()
        dependencies["rustfs"] = "ready"
    except Exception:
        dependencies["rustfs"] = "not_ready"

    is_ready = all(state == "ready" for state in dependencies.values())
    response_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=response_status,
        content={
            "service": get_settings().master_name,
            "status": "ready" if is_ready else "not_ready",
            "dependencies": dependencies,
        },
    )
