from fastapi import FastAPI, status
from fastapi.responses import JSONResponse


from controller.app.core.config import get_settings
from controller.app.services.readiness import read_dependency_health

settings = get_settings()

app = FastAPI(
    title=settings.controller_name,
    description="Controller API for the Distributed AI models for Edge Computing",
    docs_url="/docs",
    redoc_url=None
)

@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    return {"service": settings.controller_name,
            "description": app.description,
            "status": "running",
            "documentation": "/docs"
            }

@app.get("/health/live", tags=["System-Health"])
async def health_live() -> dict[str, str]:
    return {"status": "alive"}

@app.get("/health/ready", tags=["System-Health"], response_model=None)
async def health_ready()-> JSONResponse:
    checks = await read_dependency_health(settings)
    is_ready = all(check == "ready" for check in checks.values())
    response_body = {
        "service": settings.controller_name,
        "status": "ready" if is_ready else "not_ready",
        "dependencies": checks
    }

    response_status = (
        status.HTTP_200_OK
        if is_ready 
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(status_code=response_status, content=response_body)