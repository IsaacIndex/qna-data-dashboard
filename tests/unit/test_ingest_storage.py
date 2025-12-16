from __future__ import annotations

import io
import tempfile
from pathlib import Path

from app.services.ingest_storage import IngestStorage
from app.utils.config import IngestConfig


def make_storage(tmpdir: Path, max_bytes: int = 1024 * 1024) -> IngestStorage:
    config = IngestConfig(
        storage_root=tmpdir,
        max_bytes=max_bytes,
        allowed_types=("csv", "xlsx", "xls", "parquet"),
        reembed_concurrency=3,
    )
    return IngestStorage(config)


def test_versioned_filenames(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    payload = io.BytesIO(b"col1,col2\n1,2\n")
    storage.save_upload("group-a", payload, filename="file.csv", mime_type="text/csv")
    payload2 = io.BytesIO(b"col1,col2\n3,4\n")
    second = storage.save_upload("group-a", payload2, filename="file.csv", mime_type="text/csv")
    assert second.version_label != "file.csv"
    assert second.version_label.startswith("file (")


def test_rejects_large_files(tmp_path: Path) -> None:
    storage = make_storage(tmp_path, max_bytes=4)
    payload = io.BytesIO(b"12345")
    try:
        storage.save_upload("group-a", payload, filename="big.csv", mime_type="text/csv")
    except ValueError as exc:
        assert "File too large" in str(exc)
    else:
        assert False, "expected ValueError for large file"


def test_skips_missing_headers(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    payload = io.BytesIO(b",col2,col3\n1,2,3\n")
    saved = storage.save_upload("group-a", payload, filename="headers.csv", mime_type="text/csv")
    assert saved.extracted_columns == ("col2", "col3")
