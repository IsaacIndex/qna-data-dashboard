from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.models.source import SourceStatus, SourceType


def _write_index(root: Path, dataset: str, entries: list[dict[str, Any]]) -> Path:
    index_path = root / "ingest_sources" / dataset / "_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(entries, indent=2, default=str))
    return index_path


def seed_mixed_source_indexes(base: Path, *, include_conflict: bool = False) -> dict[str, Any]:
    """
    Create a mixed set of ingest index files with tmp files, sheets, embeddings, and a legacy record.
    Returns the UUIDs and labels for convenience in tests.
    """
    now = datetime.now(UTC)
    ingest_root = base / "ingest_sources"
    sales_dir = ingest_root / "sales"
    ml_dir = ingest_root / "ml"
    sales_dir.mkdir(parents=True, exist_ok=True)
    ml_dir.mkdir(parents=True, exist_ok=True)

    (sales_dir / "pipeline.xlsx").write_text("h1,h2\n1,2\n", encoding="utf-8")
    (sales_dir / "quick.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (sales_dir / "shared.csv").write_text("a\n1\n", encoding="utf-8")
    (ml_dir / "vectors.parquet").write_text("placeholder", encoding="utf-8")

    uuids = {
        "ready": "11111111-1111-1111-1111-111111111111",
        "ingesting": "22222222-2222-2222-2222-222222222222",
        "embedding": "33333333-3333-3333-3333-333333333333",
        "conflict": "44444444-4444-4444-4444-444444444444",
    }

    sales_entries: list[dict[str, Any]] = [
        {
            "id": uuids["ready"],
            "document_group_id": "sales",
            "filename": "pipeline.xlsx",
            "version_label": "pipeline.xlsx",
            "size_bytes": 1024,
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "storage_path": str(sales_dir / "pipeline.xlsx"),
            "status": SourceStatus.ready.value,
            "extracted_columns": ["h1", "h2"],
            "last_updated": now.isoformat(),
            "tags": ["finance"],
        },
        {
            "id": uuids["ingesting"],
            "document_group_id": "sales",
            "filename": "quick.csv",
            "version_label": "quick.csv",
            "size_bytes": 256,
            "mime_type": "text/csv",
            "storage_path": str(sales_dir / "quick.csv"),
            "status": SourceStatus.ingesting.value,
            "type": SourceType.tmp_file.value,
            "extracted_columns": ["a", "b"],
            "last_updated": (now - timedelta(minutes=2)).isoformat(),
            "tags": ["priority"],
        },
    ]

    shared_entry = {
        "id": uuids["conflict"],
        "document_group_id": "sales",
        "filename": "shared.csv",
        "version_label": "shared.csv",
        "size_bytes": 128,
        "mime_type": "text/csv",
        "storage_path": str(sales_dir / "shared.csv"),
        "status": SourceStatus.ingesting.value,
        "type": SourceType.tmp_file.value,
        "extracted_columns": ["a"],
        "last_updated": (now - timedelta(minutes=5)).isoformat(),
        "tags": ["shared"],
    }
    shared_latest = {
        **shared_entry,
        "status": SourceStatus.ready.value,
        "last_updated": (now - timedelta(minutes=1)).isoformat(),
        "tags": ["shared", "latest"],
    }
    if include_conflict:
        sales_entries.extend([shared_entry, shared_latest])
    else:
        sales_entries.append(shared_latest)

    ml_entries: list[dict[str, Any]] = [
        {
            "id": uuids["embedding"],
            "document_group_id": "ml",
            "filename": "vectors.parquet",
            "version_label": "vectors.parquet",
            "size_bytes": 512,
            "mime_type": "application/octet-stream",
            "storage_path": str(ml_dir / "vectors.parquet"),
            "status": SourceStatus.error.value,
            "last_updated": (now - timedelta(minutes=3)).isoformat(),
            "type": SourceType.embedding.value,
            "tags": ["ml"],
            "extracted_columns": ["embedding_vector"],
        },
        {
            "document_group_id": "ml",
            "filename": "legacy-missing.csv",
            "version_label": "legacy-missing.csv",
            "size_bytes": 0,
            "mime_type": "text/csv",
            "storage_path": str(ml_dir / "missing.csv"),
            "status": SourceStatus.new.value,
            "last_updated": (now - timedelta(minutes=10)).isoformat(),
            "extracted_columns": [],
            "tags": ["legacy"],
        },
    ]

    _write_index(base, "sales", sales_entries)
    _write_index(base, "ml", ml_entries)

    return {
        "uuids": uuids,
        "labels": [entry["version_label"] for entry in [*sales_entries, *ml_entries]],
        "datasets": ["sales", "ml"],
    }
