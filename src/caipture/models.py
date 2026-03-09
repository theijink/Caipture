from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATION_FAILED = "validation_failed"
    QUEUED = "queued"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(slots=True)
class FileRef:
    path: str
    sha256: str
    mime_type: str | None = None
    bytes: int | None = None


@dataclass(slots=True)
class JobRecord:
    job_id: str
    item_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    front_input: str
    back_input: str
    context_inputs: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    cv_done: bool = False
    ocr_done: bool = False
    metadata_done: bool = False
    review_done: bool = False
    export_done: bool = False


@dataclass(slots=True)
class ServiceContext:
    config_path: Path
    runtime_name: str
    data: dict[str, Any]
