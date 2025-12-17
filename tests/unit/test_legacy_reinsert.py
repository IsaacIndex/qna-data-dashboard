from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.db.metadata import (
    FileType,
    IngestionStatus,
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.db.schema import SheetStatus, SheetVisibilityState
from app.models.source import Source, SourceStatus, SourceType
from app.services.audit_log import AuditLogService
from app.services.legacy_reconcile import LegacyReconcileService
from app.services.source_repository import SourceRepository


def _write_index(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, indent=2, default=str))


def test_reconcile_creates_missing_file_and_updates_index(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path
    ingest_root = data_root / "ingest_sources" / "legacy"
    ingest_root.mkdir(parents=True, exist_ok=True)
    index_path = ingest_root / "_index.json"

    _write_index(
        index_path,
        [
            {
                "document_group_id": "legacy",
                "filename": "legacy-missing.csv",
                "version_label": "legacy-missing.csv",
                "size_bytes": 5,
                "mime_type": "text/csv",
                "storage_path": str(ingest_root / "legacy-missing.csv"),
                "status": "new",
                "extracted_columns": ["a", "b"],
            }
        ],
    )

    monkeypatch.setenv("DATA_ROOT", str(data_root))
    repository = SourceRepository(data_root=data_root)
    audit = AuditLogService(data_root=data_root)
    service = LegacyReconcileService(repository=repository, audit_log=audit)

    result = service.reconcile(dry_run=False)
    assert result.reinserted

    restored_path = ingest_root / "legacy-missing.csv"
    assert restored_path.exists()

    # find the legacy record (exclude any catalog backfill)
    legacy_uuid = next(
        uuid
        for uuid in result.reinserted
        if repository.get(uuid)
        and str(restored_path) in str(repository.get(uuid).metadata.get("path", ""))
    )
    source = repository.get(legacy_uuid)
    assert isinstance(source, Source)
    assert source.type is SourceType.sheet
    assert source.status is SourceStatus.new
    assert source.metadata["path"] == str(restored_path)
    assert source.legacy is False

    map_path = data_root / "ingest_sources" / "_uuid_map.json"
    assert map_path.exists()
    mapping = json.loads(map_path.read_text())
    assert mapping

    audit_log = data_root / "logs" / "ingest_audit.jsonl"
    assert audit_log.exists()
    assert "legacy.reinsert" in audit_log.read_text()


def test_reconcile_backfills_sheet_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path
    bundle_dir = data_root / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    workbook = bundle_dir / "book.xlsx"
    workbook.write_text("dummy", encoding="utf-8")

    sqlite_url = f"sqlite:///{data_root}/metadata.db"
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("SQLITE_URL", sqlite_url)

    engine = build_engine(sqlite_url)
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session=session)
        bundle = repo.create_source_bundle(
            display_name="book.xlsx",
            original_path=str(workbook),
            file_hash="abc123",
            file_type=FileType.EXCEL,
            delimiter=None,
            refresh_cadence=None,
            ingestion_status=IngestionStatus.READY,
        )
        repo.create_sheet_source(
            bundle=bundle,
            sheet_name="Sheet1",
            display_label="book.xlsx:Sheet1",
            visibility_state=SheetVisibilityState.VISIBLE,
            status=SheetStatus.ACTIVE,
            row_count=10,
            column_schema=[{"name": "col1"}],
            position_index=0,
            checksum="abc123",
            description=None,
            tags=["foo"],
            last_refreshed_at=None,
        )

    repository = SourceRepository(data_root=data_root)
    audit = AuditLogService(data_root=data_root)
    service = LegacyReconcileService(
        repository=repository,
        audit_log=audit,
        metadata_session_factory=session_factory,
    )

    result = service.reconcile(dry_run=False)
    assert result.reinserted

    backfilled_uuid = next(uuid for uuid in result.reinserted if repository.get(uuid))
    indexed = repository.get(backfilled_uuid)
    assert indexed is not None
    assert indexed.dataset == "catalog"
    assert "sheet-catalog" in indexed.groups
    assert indexed.status is SourceStatus.ready

    audit_log = data_root / "logs" / "ingest_audit.jsonl"
    assert "backfilled" in audit_log.read_text()


def test_ingest_entries_backfill_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path
    ingest_root = data_root / "ingest_sources" / "catalog"
    ingest_root.mkdir(parents=True, exist_ok=True)
    stored = ingest_root / "stored.csv"
    stored.write_text("a,b\n1,2\n", encoding="utf-8")
    index_path = ingest_root / "_index.json"

    entry_uuid = "123e4567-e89b-12d3-a456-426614174000"
    _write_index(
        index_path,
        [
            {
                "uuid": entry_uuid,
                "document_group_id": "catalog",
                "filename": "stored.csv",
                "version_label": "stored.csv",
                "size_bytes": stored.stat().st_size,
                "mime_type": "text/csv",
                "storage_path": str(stored),
                "status": "ready",
                "extracted_columns": ["a", "b"],
            }
        ],
    )

    sqlite_url = f"sqlite:///{data_root}/metadata.db"
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("SQLITE_URL", sqlite_url)

    engine = build_engine(sqlite_url)
    init_database(engine)
    session_factory = create_session_factory(engine)

    repository = SourceRepository(data_root=data_root)
    audit = AuditLogService(data_root=data_root)
    service = LegacyReconcileService(
        repository=repository,
        audit_log=audit,
        metadata_session_factory=session_factory,
    )

    result = service.reconcile(dry_run=False)
    assert entry_uuid in result.reinserted

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session=session)
        sheets = repo.list_sheet_sources()
        assert any(sheet.id == entry_uuid for sheet in sheets)
