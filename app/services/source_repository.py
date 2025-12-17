from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from app.models.source import LegacySource, Source, SourceStatus, SourceType
from app.utils.config import get_data_root
from app.utils.metrics import emit_ingest_metric
from app.utils.source_uuid import detect_legacy_reason, ensure_canonical_uuid


class SourceRepository:
    """File-backed repository for ingest sources and legacy mappings."""

    def __init__(self, data_root: Path | None = None) -> None:
        base = Path(data_root) if data_root is not None else get_data_root()
        self.storage_root = (base / "ingest_sources").expanduser()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.uuid_map_path = self.storage_root / "_uuid_map.json"

    # ---- public API ----
    def list_sources(
        self,
        *,
        dataset: str | None = None,
        source_type: SourceType | None = None,
        status: Sequence[SourceStatus] | None = None,
        include_legacy: bool = True,
    ) -> list[Source]:
        results: list[Source] = []
        for index_path in self._iter_index_files():
            group_id = index_path.parent.name
            for entry in self._load_index(index_path):
                source = self._hydrate_source(entry, dataset_override=group_id)
                if source is None:
                    continue
                if not include_legacy and isinstance(source, LegacySource):
                    continue
                if dataset and source.dataset != dataset:
                    continue
                if source_type and source.type is not source_type:
                    continue
                if status and source.status not in status:
                    continue
                results.append(source)
        return results

    def get(self, uuid: str) -> Source | None:
        for source in self.list_sources():
            if source.uuid == uuid:
                return source
        return None

    def record_legacy_mapping(
        self,
        *,
        original_id: str,
        label: str,
        dataset: str,
        source_type: SourceType,
    ) -> str:
        """Persist and return a canonical UUID for a legacy identifier."""
        return ensure_canonical_uuid(
            label=label,
            dataset=dataset,
            source_type=source_type,
            original_id=original_id,
            map_path=self.uuid_map_path,
        )

    def bulk_update(
        self,
        uuids: Sequence[str],
        *,
        status: str | None = None,
        groups: Sequence[str] | None = None,
    ) -> list[dict[str, object]]:
        """Apply status/group updates across ingest index files and report per-item results."""
        if not uuids:
            raise ValueError("At least one UUID is required for bulk update")

        status_value: SourceStatus | None = None
        if status:
            try:
                status_value = SourceStatus(status)
            except ValueError as error:
                raise ValueError("Unsupported status value") from error

        normalized_groups = self._normalize_groups(groups) if groups is not None else None
        targets = set(uuids)
        results: dict[str, dict[str, object]] = {
            uuid: {"uuid": uuid, "status": None, "groups": [], "error": "not found"}
            for uuid in targets
        }

        for index_path in self._iter_index_files():
            entries = self._load_index(index_path)
            updated = False
            for entry in entries:
                entry_uuid = entry.get("uuid") or entry.get("id")
                if not entry_uuid or entry_uuid not in targets:
                    continue

                if status_value:
                    entry["status"] = status_value.value
                if normalized_groups is not None:
                    entry["groups"] = normalized_groups
                    entry["tags"] = normalized_groups

                results[entry_uuid] = {
                    "uuid": entry_uuid,
                    "status": entry.get("status"),
                    "groups": entry.get("groups") or entry.get("tags") or [],
                    "error": None,
                }
                updated = True

            if updated:
                self._save_index(index_path, entries)

        successes = [payload for payload in results.values() if payload.get("error") is None]
        failures = [payload for payload in results.values() if payload.get("error")]
        emit_ingest_metric(
            "sources.bulk_update",
            requested=len(uuids),
            updated=len(successes),
            failed=len(failures),
            status=status_value.value if status_value else None,
            groups_applied=len(normalized_groups or []) if normalized_groups is not None else 0,
        )

        return [results[uuid] for uuid in uuids]

    # ---- helpers ----
    def _iter_index_files(self) -> Iterable[Path]:
        return sorted(self.storage_root.glob("*/_index.json"))

    def _load_index(self, path: Path) -> list[dict]:
        try:
            return json.loads(path.read_text())
        except Exception:
            return []

    def _save_index(self, path: Path, entries: Sequence[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(list(entries), indent=2, default=str))

    def _normalize_groups(self, groups: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for raw in groups:
            name = str(raw or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(name)
        return result

    def _hydrate_source(self, entry: dict, *, dataset_override: str) -> Source | None:
        uuid = entry.get("uuid") or entry.get("id")
        label = (
            entry.get("label") or entry.get("version_label") or entry.get("filename") or "source"
        )
        dataset = entry.get("dataset") or dataset_override
        source_type = self._infer_type(entry)
        source_status = self._map_status(entry.get("status"))
        last_updated = self._parse_datetime(
            entry.get("last_updated") or entry.get("last_updated_at")
        )
        groups = entry.get("groups") or entry.get("tags") or []
        storage_path = entry.get("storage_path") or ""
        path_exists = Path(storage_path).expanduser().exists() if storage_path else False

        legacy_reason = detect_legacy_reason({**entry, "uuid": uuid}, path_exists=path_exists)
        metadata = self._build_metadata(entry, storage_path)

        if legacy_reason:
            canonical_uuid = ensure_canonical_uuid(
                label=label,
                dataset=dataset,
                source_type=source_type,
                original_id=entry.get("original_id") or entry.get("id"),
                map_path=self.uuid_map_path,
            )
            return LegacySource(
                uuid=canonical_uuid,
                label=label,
                dataset=dataset,
                type=source_type,
                status=source_status,
                groups=groups,
                last_updated=last_updated,
                metadata=metadata,
                legacy_reason=legacy_reason,
                original_id=entry.get("original_id") or entry.get("id"),
            )

        if not uuid:
            return None

        return Source(
            uuid=uuid,
            label=label,
            dataset=dataset,
            type=source_type,
            status=source_status,
            groups=groups,
            last_updated=last_updated,
            metadata=metadata,
        )

    def _map_status(self, raw_status: str | None) -> SourceStatus:
        status_map = {
            "uploaded": SourceStatus.new,
            "new": SourceStatus.new,
            "validating": SourceStatus.ingesting,
            "ingesting": SourceStatus.ingesting,
            "ready": SourceStatus.ready,
            "active": SourceStatus.ready,
            "archived": SourceStatus.archived,
            "inactive": SourceStatus.archived,
            "failed": SourceStatus.error,
            "error": SourceStatus.error,
            "embedding": SourceStatus.ingesting,
            "embedded": SourceStatus.ready,
        }
        if raw_status:
            lowered = str(raw_status).lower()
            if lowered in status_map:
                return status_map[lowered]
        return SourceStatus.new

    def _infer_type(self, entry: dict) -> SourceType:
        raw_type = entry.get("type")
        if raw_type:
            try:
                return SourceType(raw_type)
            except ValueError:
                pass
        path = (entry.get("storage_path") or "").lower()
        if path.endswith((".csv", ".xlsx", ".xls", ".parquet")):
            return SourceType.sheet
        return SourceType.tmp_file

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _build_metadata(self, entry: dict, storage_path: str) -> dict:
        return {
            "path": storage_path,
            "size": entry.get("size_bytes"),
            "checksum": entry.get("checksum"),
            "headers_present": bool(entry.get("extracted_columns")),
        }
