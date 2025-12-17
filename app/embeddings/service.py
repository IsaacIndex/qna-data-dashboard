from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.models.source import SourceStatus
from app.services.source_repository import SourceRepository
from app.utils.metrics import emit_ingest_metric, emit_ingest_timing


@dataclass
class ReembedJob:
    id: str
    uuid: str
    dataset: str
    status: str
    queued_at: datetime
    completed_at: datetime | None = None


class ReembedService:
    """Queue and track re-embed jobs by canonical source UUID."""

    def __init__(self, repository: SourceRepository | None = None) -> None:
        self.repository = repository or SourceRepository()
        self.status_overrides: dict[str, SourceStatus] = {}
        self._jobs: dict[str, ReembedJob] = {}

    def enqueue(self, uuid: str) -> ReembedJob:
        source = self.repository.get(uuid)
        if source is None:
            raise LookupError(f"Source '{uuid}' not found")
        job = ReembedJob(
            id=str(uuid4()),
            uuid=uuid,
            dataset=source.dataset,
            status="queued",
            queued_at=datetime.now(UTC),
        )
        self._jobs[job.id] = job
        self.status_overrides[uuid] = SourceStatus.ingesting
        emit_ingest_metric("reembed.enqueue", uuid=uuid, dataset=source.dataset, status=job.status)
        return job

    def get(self, job_id: str, *, advance: bool = True) -> ReembedJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if advance and job.status == "queued":
            job.status = "processing"
            self._jobs[job_id] = job
            job = self.complete(job_id) or job
        return job

    def complete(self, job_id: str) -> ReembedJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status == "completed":
            return job
        finished = ReembedJob(
            **{**job.__dict__, "status": "completed", "completed_at": datetime.now(UTC)}
        )
        self._jobs[job_id] = finished
        self.status_overrides[job.uuid] = SourceStatus.ready
        emit_ingest_timing(
            "reembed.complete",
            elapsed_ms=(finished.completed_at - finished.queued_at).total_seconds() * 1000,
            uuid=finished.uuid,
            dataset=finished.dataset,
            job_id=job_id,
        )
        return finished
