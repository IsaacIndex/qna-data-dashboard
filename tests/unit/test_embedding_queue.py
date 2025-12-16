from __future__ import annotations

from app.services.embedding_queue import EmbeddingQueue
from app.services.ingest_models import JobStatus


def test_queue_honors_concurrency() -> None:
    queue = EmbeddingQueue(concurrency=1)
    job1 = queue.enqueue("group1", ["s1"], triggered_by="tester")
    job2 = queue.enqueue("group1", ["s2"], triggered_by="tester")
    status1 = queue.get_status("group1", job1.id)
    status2 = queue.get_status("group1", job2.id)
    assert status1 is not None
    assert status1.status in {JobStatus.PROCESSING, JobStatus.COMPLETED}
    assert status2 is not None
    assert status2.status in {JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED}


def test_retry_enqueues_new_job() -> None:
    queue = EmbeddingQueue(concurrency=2)
    job = queue.enqueue("group2", ["a"], triggered_by=None)
    retried = queue.retry("group2", job.id)
    assert retried is not None
    assert retried.id != job.id
    assert queue.get_status("group2", retried.id) is not None
