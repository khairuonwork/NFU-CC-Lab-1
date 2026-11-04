from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

class ExecutionMode(StrEnum):
    LOAD_BALANCE = "load_balance"
    ENSEMBLE = "ensemble"


class WorkerControlMessage(BaseModel):
    schema_version: Literal[1] = 1
    message_type: Literal["worker_control"] = "worker_control"
    command: Literal["publish_heartbeat"] = "publish_heartbeat"
    request_id: UUID
    requested_at: datetime

class InferenceJob(BaseModel):
    schema_version: Literal[1] = 1
    job_id: UUID
    job_type: Literal["inference"] = "inference"
    execution_mode: ExecutionMode
    image_key: str
    submitted_at: datetime

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
