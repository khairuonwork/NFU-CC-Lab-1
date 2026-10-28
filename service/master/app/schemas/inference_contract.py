from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

class ExecutionMode(StrEnum):
    LOAD_BALANCE = "load_balance"
    ENSEMBLE = "ensemble"

# Queue an exist image from RustFS
class QueueInferenceRequest(BaseModel):
    image_key: str = Field(min_length=1)
    execution_mode: ExecutionMode

# JSON payload from Master to Worker Redis Stream
class InferenceJob(BaseModel):
    schema_version: Literal[1] = 1
    job_id: UUID
    job_type: Literal["inference"] = "inference"
    execution_mode: ExecutionMode
    image_key: str
    submitted_at: datetime

# Temporary result from one worker to Redis
class InferenceResult(BaseModel):
    schema_version: Literal[1] = 1
    job_id: UUID
    worker_id: str
    status: Literal["succeeded", "failed"]
    label: str | None = None
    probabilities: dict[str, float] | None = None
    model_key: str | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    completed_at: datetime
    error: str | None = None
