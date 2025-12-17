from __future__ import annotations

import io
import time
from pathlib import Path

import pytest

from app.services.embedding_queue import EmbeddingQueue
from app.services.ingest_storage import IngestStorage
from app.utils.config import IngestConfig

MAX_UPLOAD_AND_ENQUEUE_SECONDS = 1.0

pytestmark = pytest.mark.performance


@pytest.fixture()
def storage(tmp_path: Path) -> IngestStorage:
    return IngestStorage(
        IngestConfig(
            storage_root=tmp_path,
            max_bytes=1024 * 1024,
            allowed_types=("csv",),
            reembed_concurrency=3,
        )
    )


def test_upload_and_reembed_latency(
    storage: IngestStorage, benchmark: pytest.BenchmarkFixture
) -> None:
    """Measure upload + re-embed enqueue against budget to catch regressions early."""
    payload = io.BytesIO(b"a,b\n1,2\n")

    def upload_and_enqueue() -> float:
        start = time.perf_counter()
        payload.seek(0)
        saved = storage.save_upload(
            "perf-group", payload, filename="perf.csv", mime_type="text/csv"
        )
        queue = EmbeddingQueue(concurrency=2)
        job = queue.enqueue("perf-group", [saved.id], triggered_by="perf")
        assert queue.get_status("perf-group", job.id) is not None
        return time.perf_counter() - start

    duration = benchmark(upload_and_enqueue)
    benchmark.extra_info["upload_and_enqueue_seconds"] = duration
    assert (
        duration < MAX_UPLOAD_AND_ENQUEUE_SECONDS
    ), f"Upload + enqueue exceeded budget: {duration}"
