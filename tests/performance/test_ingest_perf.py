from __future__ import annotations

import io
import time
from pathlib import Path

from app.services.embedding_queue import EmbeddingQueue
from app.services.ingest_storage import IngestStorage
from app.utils.config import IngestConfig


def test_upload_and_reembed_latency(tmp_path: Path) -> None:
    storage = IngestStorage(
        IngestConfig(
            storage_root=tmp_path,
            max_bytes=1024 * 1024,
            allowed_types=("csv",),
            reembed_concurrency=3,
        )
    )
    payload = io.BytesIO(b"a,b\n1,2\n")
    start = time.perf_counter()
    saved = storage.save_upload("perf-group", payload, filename="perf.csv", mime_type="text/csv")
    queue = EmbeddingQueue(concurrency=2)
    job = queue.enqueue("perf-group", [saved.id], triggered_by="perf")
    duration = time.perf_counter() - start
    assert duration < 1.5, f"Upload + enqueue took too long: {duration}"
    assert queue.get_status("perf-group", job.id) is not None
