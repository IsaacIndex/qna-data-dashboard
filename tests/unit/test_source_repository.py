from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models.source import LegacyReason, LegacySource, SourceStatus, SourceType
from app.services.source_repository import SourceRepository


def _write_index(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, indent=2, default=str))


def test_list_sources_maps_existing_and_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path
    ingest_root = data_root / "ingest_sources" / "group1"
    ingest_root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    _write_index(
        ingest_root / "_index.json",
        [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "document_group_id": "group1",
                "filename": "file.csv",
                "version_label": "file.csv",
                "size_bytes": 10,
                "mime_type": "text/csv",
                "storage_path": str(ingest_root / "file.csv"),
                "added_at": now,
                "status": "ready",
                "extracted_columns": ["a", "b"],
            },
            {
                "document_group_id": "group1",
                "filename": "legacy.csv",
                "version_label": "legacy.csv",
                "size_bytes": 5,
                "mime_type": "text/csv",
                "storage_path": str(ingest_root / "missing.csv"),
                "added_at": now,
                "extracted_columns": [],
            },
        ],
    )
    (ingest_root / "file.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    monkeypatch.setenv("DATA_ROOT", str(data_root))
    repo = SourceRepository()
    sources = repo.list_sources()

    assert len(sources) == 2
    current = next(src for src in sources if src.label == "file.csv")
    assert current.uuid == "123e4567-e89b-12d3-a456-426614174000"
    assert current.dataset == "group1"
    assert current.type is SourceType.sheet
    assert current.status is SourceStatus.ready
    assert current.metadata["path"].endswith("file.csv")
    assert current.metadata["headers_present"] is True

    legacy = next(src for src in sources if src.label == "legacy.csv")
    assert isinstance(legacy, LegacySource)
    assert legacy.legacy_reason is LegacyReason.missing_uuid
    assert legacy.remap_status.value == "pending"


def test_record_legacy_mapping_is_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    repo = SourceRepository()
    uuid_one = repo.record_legacy_mapping(
        original_id="legacy-123",
        label="Old Upload",
        dataset="group1",
        source_type=SourceType.tmp_file,
    )
    uuid_two = repo.record_legacy_mapping(
        original_id="legacy-123",
        label="Old Upload",
        dataset="group1",
        source_type=SourceType.tmp_file,
    )

    assert uuid_one == uuid_two
    map_path = repo.uuid_map_path
    assert map_path.exists()
    mapping = json.loads(map_path.read_text())
    assert mapping["legacy:legacy-123"] == uuid_one
