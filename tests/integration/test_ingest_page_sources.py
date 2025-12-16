from __future__ import annotations

import io
from pathlib import Path

from app.services.ingest_storage import IngestStorage
from app.utils.config import IngestConfig


def test_add_delete_flow(tmp_path: Path) -> None:
    storage = IngestStorage(
        IngestConfig(
            storage_root=tmp_path,
            max_bytes=1024 * 1024,
            allowed_types=("csv",),
            reembed_concurrency=3,
        )
    )
    saved = storage.save_upload("group1", io.BytesIO(b"a,b\n1,2\n"), filename="flow.csv", mime_type="text/csv")
    assert saved.status.value == "ready"
    listed = storage.list_sources("group1")
    assert len(listed) == 1
    assert listed[0].version_label == "flow.csv"

    deleted = storage.delete_source("group1", saved.id)
    assert deleted is True
    assert storage.list_sources("group1") == []
