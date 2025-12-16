from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Sequence


class SourceStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
    EMBEDDING = "embedding"
    EMBEDDED = "embedded"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DocumentGroup:
    id: str
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SourceFile:
    id: str
    document_group_id: str
    filename: str
    version_label: str
    size_bytes: int
    mime_type: str
    storage_path: str
    added_by: str | None
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: SourceStatus = SourceStatus.UPLOADED
    last_updated_at: datetime | None = None
    validation_error: str | None = None
    audit_log_ref: str | None = None
    extracted_columns: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ColumnPreferenceSet:
    id: str
    document_group_id: str
    selected_columns: Sequence[str]
    contextual_fields: Sequence[str] | None
    updated_by: str | None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0


@dataclass(frozen=True)
class EmbeddingJob:
    id: str
    document_group_id: str
    source_file_ids: Sequence[str]
    status: JobStatus
    triggered_by: str | None
    queue_position: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None
    run_duration_ms: int | None = None
