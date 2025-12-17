from __future__ import annotations

import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime

from app.services.ingest_models import EmbeddingJob, JobStatus
from app.utils.config import load_ingest_config
from app.utils.logging import get_logger

LOGGER = get_logger(__name__)


class EmbeddingQueue:
    """In-memory embedding queue with per-group concurrency caps."""

    def __init__(self, concurrency: int | None = None) -> None:
        config = load_ingest_config()
        self.concurrency = concurrency or config.reembed_concurrency
        self._queues: dict[str, deque[EmbeddingJob]] = defaultdict(deque)
        self._processing: dict[str, dict[str, EmbeddingJob]] = defaultdict(dict)
        self._completed: dict[str, dict[str, EmbeddingJob]] = defaultdict(dict)

    def enqueue(
        self, group_id: str, source_ids: list[str], triggered_by: str | None
    ) -> EmbeddingJob:
        job_id = str(uuid.uuid4())
        job = EmbeddingJob(
            id=job_id,
            document_group_id=group_id,
            source_file_ids=tuple(source_ids),
            status=JobStatus.QUEUED,
            triggered_by=triggered_by,
            queue_position=len(self._queues[group_id]),
        )
        self._queues[group_id].append(job)
        LOGGER.info("Queued embed job %s for group %s", job_id, group_id)
        self._drain(group_id)
        return job

    def retry(self, group_id: str, job_id: str) -> EmbeddingJob | None:
        existing = self.get_job(group_id, job_id)
        if existing is None:
            return None
        retried = EmbeddingJob(
            id=str(uuid.uuid4()),
            document_group_id=group_id,
            source_file_ids=existing.source_file_ids,
            status=JobStatus.QUEUED,
            triggered_by=existing.triggered_by,
            queue_position=len(self._queues[group_id]),
        )
        self._queues[group_id].append(retried)
        self._drain(group_id)
        return retried

    def get_job(self, group_id: str, job_id: str) -> EmbeddingJob | None:
        for container in (
            self._queues[group_id],
            self._processing[group_id].values(),
            self._completed[group_id].values(),
        ):
            for job in container:
                if job.id == job_id:
                    return job
        return None

    def is_source_busy(self, group_id: str, source_id: str) -> bool:
        for job in self._processing[group_id].values():
            if source_id in job.source_file_ids:
                return True
        return False

    def _drain(self, group_id: str) -> None:
        """Move queued jobs into processing respecting concurrency, then complete synchronously."""
        processing = self._processing[group_id]
        while self._queues[group_id] and len(processing) < self.concurrency:
            job = self._queues[group_id].popleft()
            start = datetime.now(UTC)
            processing[job.id] = EmbeddingJob(
                **{
                    **job.__dict__,
                    "status": JobStatus.PROCESSING,
                    "started_at": start,
                    "queue_position": 0,
                }
            )
            self._complete_job(group_id, processing[job.id])

    def _complete_job(self, group_id: str, job: EmbeddingJob) -> None:
        now = datetime.now(UTC)
        duration_ms = int((now - (job.started_at or now)).total_seconds() * 1000)
        finished = EmbeddingJob(
            **{
                **job.__dict__,
                "status": JobStatus.COMPLETED,
                "completed_at": now,
                "run_duration_ms": duration_ms,
                "queue_position": 0,
            }
        )
        self._completed[group_id][finished.id] = finished
        self._processing[group_id].pop(finished.id, None)
        LOGGER.info(
            "Completed embed job %s for group %s in %sms", finished.id, group_id, duration_ms
        )

    def get_status(self, group_id: str, job_id: str) -> EmbeddingJob | None:
        return self.get_job(group_id, job_id)


default_queue = EmbeddingQueue()
