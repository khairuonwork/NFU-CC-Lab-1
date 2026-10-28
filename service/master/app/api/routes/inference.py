from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.schemas.inference_contract import ExecutionMode, InferenceOrder
from app.services.job_dispatcher import JobDispatcher, WorkerUnavailableError
from app.services.job_status import read_inference_job
from app.services.object_storage import delete_object, upload_inference_image

router = APIRouter(prefix="/inference", tags=["Inference"])

# Create a response the UI can use when the requested mode has no workers
def worker_unavailable_response(
    error: WorkerUnavailableError,
    execution_mode: ExecutionMode,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "unavailable",
            "reason": "not_enough_idle_workers",
            "message": str(error),
            "execution_mode": execution_mode,
            "required_workers": error.required_workers,
            "available_workers": error.available_workers,
            "workers": error.worker_states,
        },
    )

# Return worker state and enabled execution modes before the UI queues a job.
@router.get("/workers")
async def get_worker_statuses(request: Request) -> JSONResponse:
    dispatcher = JobDispatcher(request.app.state.redis, get_settings())
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=await dispatcher.read_worker_statuses(),
    )

# Accept an explicit UI order for an existing image in RustFS.
@router.post("/orders", status_code=status.HTTP_202_ACCEPTED)
async def submit_inference_order(
    body: InferenceOrder,
    request: Request,
) -> JSONResponse:
    dispatcher = JobDispatcher(request.app.state.redis, get_settings())

    try:
        job, worker_ids = await dispatcher.accept_order(body)
    except WorkerUnavailableError as error:
        return worker_unavailable_response(error, body.execution_mode)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "queued",
            "job_id": str(job.job_id),
            "execution_mode": job.execution_mode,
            "worker_ids": worker_ids,
        },
    )

# Read temporary job state and results for UI polling
@router.get("/jobs/{job_id}")
async def get_inference_job(job_id: str, request: Request) -> JSONResponse:
    job = await read_inference_job(request.app.state.redis, job_id)

    if not job:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "not_found",
                "message": "Inference job does not exist or has expired",
                "job_id": job_id,
            },
        )

    return JSONResponse(status_code=status.HTTP_200_OK, content=job)

# Upload an image to RustFS then queue it for inference
@router.post("/images", status_code=status.HTTP_202_ACCEPTED)
async def upload_and_queue_inference(
    request: Request,
    file: Annotated[UploadFile, File()],
    execution_mode: Annotated[ExecutionMode, Form()],
) -> JSONResponse:
    settings = get_settings()
    rustfs = request.app.state.rustfs
    object_key = ""

    try:
        object_key = await upload_inference_image(rustfs, settings, file)
    except ValueError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "status": "invalid_upload",
                "message": str(error),
            },
        )
    finally:
        await file.close()

    dispatcher = JobDispatcher(request.app.state.redis, settings)
    order = InferenceOrder(
        image_key=object_key,
        execution_mode=execution_mode,
    )

    try:
        job, worker_ids = await dispatcher.accept_order(order)
    except WorkerUnavailableError as error:
        await delete_object(rustfs, settings, object_key)
        return worker_unavailable_response(error, execution_mode)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "queued",
            "job_id": str(job.job_id),
            "image_key": object_key,
            "execution_mode": job.execution_mode,
            "worker_ids": worker_ids,
        },
    )
