from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid5

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.metadata import (
    FileType,
    IngestionStatus,
    MetadataRepository,
    build_engine,
    create_session_factory,
    session_scope,
)
from app.db.schema import SheetStatus, SheetVisibilityState
from app.models.source import RemapStatus, SourceStatus, SourceType
from app.services.audit_log import AuditLogService
from app.services.source_repository import SourceRepository
from app.utils.logging import get_logger
from app.utils.metrics import emit_ingest_metric
from app.utils.source_uuid import SOURCE_NAMESPACE, ensure_canonical_uuid

LOGGER = get_logger(__name__)


@dataclass
class LegacyReconcileResult:
    reinserted: list[str]
    conflicts: list[dict[str, str]]


class LegacyReconcileService:
    """Reinsert missing legacy sources and ensure canonical UUID mapping."""

    def __init__(
        self,
        repository: SourceRepository | None = None,
        audit_log: AuditLogService | None = None,
        metadata_session_factory: sessionmaker | None = None,
    ) -> None:
        self.repository = repository or SourceRepository()
        self.audit_log = audit_log or AuditLogService()
        if metadata_session_factory is None:
            sqlite_path = (self.repository.storage_root.parent / "metadata.db").resolve()
            metadata_session_factory = create_session_factory(
                build_engine(f"sqlite:///{sqlite_path}")
            )
        self.metadata_session_factory = metadata_session_factory

    def reconcile(self, *, dry_run: bool = False) -> LegacyReconcileResult:
        reinserted: list[str] = []
        conflicts: list[dict[str, str]] = []

        backfilled = self._backfill_sheet_catalog(dry_run=dry_run)
        reinserted.extend(backfilled)
        metadata_backfilled = self._backfill_catalog_metadata(dry_run=dry_run)
        reinserted.extend(metadata_backfilled)

        for index_path in self.repository._iter_index_files():
            entries = self.repository._load_index(index_path)
            dataset = index_path.parent.name
            updated = False

            for entry in entries:
                storage_path = entry.get("storage_path") or ""
                target_path = (
                    Path(storage_path)
                    if storage_path
                    else self.repository.storage_root
                    / dataset
                    / (entry.get("version_label") or entry.get("filename") or "restored.csv")
                )
                target_exists = target_path.expanduser().exists()

                label = (
                    entry.get("label")
                    or entry.get("version_label")
                    or entry.get("filename")
                    or "source"
                )
                original_id = entry.get("original_id") or entry.get("id")
                source_type = self.repository._infer_type(entry)
                canonical_uuid = ensure_canonical_uuid(
                    label=label,
                    dataset=dataset,
                    source_type=source_type,
                    original_id=original_id,
                    map_path=self.repository.uuid_map_path,
                )

                missing_uuid = not bool(entry.get("uuid") or entry.get("id"))
                needs_reinsert = not target_exists

                if needs_reinsert:
                    if target_path.exists():
                        LOGGER.warning(
                            "Skipping reinsertion for %s; file already exists at %s",
                            label,
                            target_path,
                        )
                        conflicts.append(
                            {
                                "legacy_id": original_id or label,
                                "reason": "existing_file",
                                "suggested_action": "Inspect existing file before overwrite",
                            }
                        )
                        continue
                    if not dry_run:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path.write_text("# restored legacy source\n", encoding="utf-8")
                        entry["storage_path"] = str(target_path)
                        if not entry.get("uuid"):
                            entry["uuid"] = canonical_uuid
                    reinserted.append(canonical_uuid)
                    if not dry_run:
                        updated = True
                        self._mark_mapped(entry)
                        self.audit_log.record_legacy_reinsertion(
                            source_uuid=canonical_uuid, outcome="restored", conflict=False
                        )

                elif missing_uuid:
                    reinserted.append(canonical_uuid)
                    if not dry_run:
                        entry["uuid"] = canonical_uuid
                        updated = True
                        self._mark_mapped(entry)
                        self.audit_log.record_legacy_reinsertion(
                            source_uuid=canonical_uuid, outcome="remapped", conflict=False
                        )

            if updated and not dry_run:
                self.repository._save_index(index_path, entries)

        emit_ingest_metric(
            "legacy.reconcile",
            reinserted=len(reinserted),
            conflicts=len(conflicts),
            dry_run=dry_run,
        )
        return LegacyReconcileResult(reinserted=reinserted, conflicts=conflicts)

    @staticmethod
    def _mark_mapped(entry: dict) -> None:
        entry.pop("legacy", None)
        entry["legacy"] = False
        if entry.get("legacy_reason"):
            entry["remap_status"] = RemapStatus.mapped.value

    def _backfill_sheet_catalog(self, *, dry_run: bool) -> list[str]:
        """Ensure legacy Sheet Catalog bundles appear in ingest_sources for unified listing."""
        created: list[str] = []
        dataset = "catalog"
        index_path = self.repository.storage_root / dataset / "_index.json"
        current_entries = self.repository._load_index(index_path)
        current_by_uuid = {entry.get("uuid") or entry.get("id"): entry for entry in current_entries}
        updated = False

        with session_scope(self.metadata_session_factory) as session:
            metadata = MetadataRepository(session=session)
            try:
                bundles = metadata.list_source_bundles()
            except OperationalError:
                LOGGER.warning(
                    "Skipping sheet catalog backfill: metadata tables not initialized yet."
                )
                return created
            if not bundles:
                return created

            bundle_map = {bundle.id: bundle for bundle in bundles}
            sheets = metadata.list_sheet_sources()

            for sheet in sheets:

                bundle = bundle_map.get(sheet.bundle_id)
                storage_path = (
                    Path(bundle.original_path).expanduser()
                    if bundle and bundle.original_path
                    else None
                )
                status = (
                    SourceStatus.ready
                    if getattr(sheet, "status", None) == SheetStatus.ACTIVE
                    else SourceStatus.archived
                )
                columns = []
                if sheet.column_schema:
                    columns = [
                        column.get("name")
                        for column in sheet.column_schema
                        if isinstance(column, dict) and column.get("name")
                    ]

                added_at = (
                    sheet.last_refreshed_at
                    or (bundle.updated_at if bundle else None)
                    or (bundle.created_at if bundle else None)
                )
                added_at_str = added_at.isoformat() if added_at else None
                last_updated = sheet.last_refreshed_at or (bundle.updated_at if bundle else None)
                last_updated_str = last_updated.isoformat() if last_updated else None

                entry = {
                    "uuid": sheet.id,
                    "id": sheet.id,
                    "document_group_id": dataset,
                    "filename": sheet.display_label,
                    "version_label": sheet.display_label,
                    "size_bytes": (
                        storage_path.stat().st_size if storage_path and storage_path.exists() else 0
                    ),
                    "mime_type": (
                        _mime_type(bundle.file_type) if bundle else "application/octet-stream"
                    ),
                    "storage_path": (
                        str(storage_path) if storage_path and storage_path.exists() else ""
                    ),
                    "status": status.value,
                    "added_at": added_at_str,
                    "last_updated": last_updated_str,
                    "last_updated_at": last_updated_str,
                    "extracted_columns": columns or ["legacy_sheet_catalog"],
                    "tags": ["sheet-catalog", "legacy"]
                    + (list(sheet.tags or []) if hasattr(sheet, "tags") and sheet.tags else []),
                    "type": SourceType.sheet.value,
                }

                if dry_run:
                    created.append(sheet.id)
                    continue

                existing_entry = current_by_uuid.get(sheet.id)
                if existing_entry:
                    merged = {**existing_entry, **{k: v for k, v in entry.items() if v}}
                    current_by_uuid[sheet.id] = merged
                else:
                    current_by_uuid[sheet.id] = entry
                    created.append(sheet.id)
                    self.audit_log.record_legacy_reinsertion(
                        source_uuid=sheet.id, outcome="backfilled", conflict=False
                    )
                updated = True

        if updated and not dry_run:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            self.repository._save_index(index_path, list(current_by_uuid.values()))

        return created

    def _backfill_catalog_metadata(self, *, dry_run: bool) -> list[str]:
        """Insert missing ingest entries into metadata DB so the Sheet Source Catalog
        reflects new files."""
        created: list[str] = []
        with session_scope(self.metadata_session_factory) as session:
            metadata = MetadataRepository(session=session)
            try:
                existing_sheets = {sheet.id for sheet in metadata.list_sheet_sources()}
            except OperationalError:
                LOGGER.warning("Skipping metadata backfill: metadata tables not initialized yet.")
                return created

            for index_path in self.repository._iter_index_files():
                entries = self.repository._load_index(index_path)
                for entry in entries:
                    sheet_id = entry.get("uuid") or entry.get("id")
                    if not sheet_id or sheet_id in existing_sheets:
                        continue

                    storage_path = Path(entry.get("storage_path") or "")
                    if not storage_path.exists():
                        continue

                    filename = (
                        entry.get("filename") or entry.get("version_label") or storage_path.name
                    )
                    bundle_id = str(uuid5(SOURCE_NAMESPACE, f"bundle|{storage_path}"))
                    bundle = metadata.get_source_bundle(bundle_id)
                    if bundle is None and not dry_run:
                        bundle = metadata.create_source_bundle(
                            display_name=filename.split(":")[0],
                            original_path=str(storage_path),
                            file_hash=str(storage_path),
                            file_type=_file_type(storage_path),
                            delimiter=None,
                            refresh_cadence=None,
                            ingestion_status=IngestionStatus.READY,
                        )
                        bundle.id = bundle_id  # ensure deterministic ID

                    if dry_run:
                        created.append(sheet_id)
                        continue

                    column_schema = [
                        {"name": name} for name in entry.get("extracted_columns") or []
                    ]
                    status = (
                        SheetStatus.ACTIVE
                        if entry.get("status", "ready") == "ready"
                        else SheetStatus.INACTIVE
                    )
                    sheet = metadata.create_sheet_source(
                        bundle=bundle,
                        sheet_name=filename.split(":")[-1],
                        display_label=filename,
                        visibility_state=SheetVisibilityState.VISIBLE,
                        status=status,
                        row_count=entry.get("row_count") or 0,
                        column_schema=column_schema,
                        position_index=0,
                        checksum=str(entry.get("checksum") or storage_path.name),
                        description=None,
                        tags=entry.get("tags") or [],
                        last_refreshed_at=None,
                    )
                    sheet.id = sheet_id
                    bundle.sheet_count = (bundle.sheet_count or 0) + 1
                    existing_sheets.add(sheet_id)
                    created.append(sheet_id)

        return created

    def _existing_uuids(self) -> set[str]:
        known: set[str] = set()
        for index_path in self.repository._iter_index_files():
            for entry in self.repository._load_index(index_path):
                uuid = entry.get("uuid") or entry.get("id")
                if uuid:
                    known.add(uuid)
        return known


def _mime_type(file_type: FileType) -> str:
    if file_type is FileType.CSV:
        return "text/csv"
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file_type(path: Path) -> FileType:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return FileType.CSV
    return FileType.EXCEL
