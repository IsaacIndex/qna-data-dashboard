from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.db.metadata import MetadataRepository
from app.db.schema import ColumnPreference, PreferenceMirror
from app.utils.logging import get_logger, log_event
from app.utils.session_state import SessionStore, ensure_session_defaults


@dataclass(frozen=True)
class SelectedColumn:
    column_name: str
    display_label: str
    position: int


@dataclass(frozen=True)
class DisplayableColumn:
    column_name: str
    display_label: str
    data_type: str | None
    is_available: bool
    last_seen_at: datetime | None


@dataclass(frozen=True)
class PreferenceSnapshot:
    dataset_id: str
    user_id: str | None
    selected_columns: Sequence[SelectedColumn]
    max_columns: int
    updated_at: datetime
    version: int = 0
    source: str | None = None


def _dedupe_selected_columns(columns: Sequence[SelectedColumn]) -> list[SelectedColumn]:
    ordered = sorted(columns, key=lambda column: column.position)
    seen: set[str] = set()
    deduped: list[SelectedColumn] = []
    for column in ordered:
        if column.column_name in seen:
            continue
        seen.add(column.column_name)
        deduped.append(
            SelectedColumn(
                column_name=column.column_name,
                display_label=column.display_label,
                position=len(deduped),
            )
        )
    return deduped


def _parse_selected_columns(entries: Sequence[dict[str, Any]]) -> list[SelectedColumn]:
    parsed: list[SelectedColumn] = []
    for index, entry in enumerate(entries):
        raw_name = entry.get("name") or entry.get("columnName") or entry.get("column_name")
        name = str(raw_name or "").strip()
        if not name:
            continue
        raw_label = entry.get("displayLabel") or entry.get("display_label") or name
        label = str(raw_label or name).strip() or name
        position_raw = entry.get("position", index)
        try:
            position = int(position_raw)
        except (TypeError, ValueError):
            position = index
        parsed.append(
            SelectedColumn(
                column_name=name,
                display_label=label,
                position=position,
            )
        )
    return _dedupe_selected_columns(parsed)


def persist_column_selection(
    store: SessionStore | None,
    *,
    dataset_id: str,
    selected_columns: Sequence[str],
    active_tab: str,
) -> SessionStore:
    """
    Persist column selections in session state without blocking UI interactions.
    Returns the updated session store for convenience.
    """

    state = ensure_session_defaults(store)
    state["selected_columns"] = list(selected_columns)
    state["active_tab"] = active_tab
    state["last_saved_at"] = datetime.now(UTC)
    state["preference_status"] = "ready"
    log_event(
        get_logger(__name__),
        "column.selection.persist",
        dataset_id=dataset_id,
        tab=active_tab,
        column_count=len(selected_columns),
    )
    return state


def hydrate_local_preferences(
    store: SessionStore | None,
    *,
    dataset_id: str,
    payload: dict[str, Any] | None,
    defaults: Sequence[str] | None = None,
) -> PreferenceSnapshot:
    """
    Apply preferences loaded from device-local storage into session state with safe fallbacks.
    Returns a snapshot representation for downstream use.
    """

    state = ensure_session_defaults(store)
    state["preference_status"] = "loading"

    device_id = None
    version = 0
    source = "defaults"
    updated_at = datetime.now(UTC)
    default_selection = [name for name in defaults or [] if name]

    selected_columns: list[SelectedColumn] = [
        SelectedColumn(column_name=name, display_label=name, position=index)
        for index, name in enumerate(default_selection)
    ]
    max_columns = max(len(selected_columns), 1)
    success = True

    if payload:
        device_id_raw = payload.get("deviceId") or payload.get("device_id")
        device_id = str(device_id_raw).strip() if device_id_raw else None
        max_candidate = payload.get("maxColumns") or payload.get("max_columns")
        try:
            max_columns = int(max_candidate) if max_candidate is not None else max_columns
        except (TypeError, ValueError):
            max_columns = max_columns
        max_columns = max(max_columns, 1)
        source = str(payload.get("source") or "localStorage")
        version_value = payload.get("version")
        try:
            version = int(version_value) if version_value is not None else 0
        except (TypeError, ValueError):
            version = 0
        updated_raw = payload.get("updatedAt") or payload.get("updated_at")
        if isinstance(updated_raw, str):
            try:
                updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
            except ValueError:
                updated_at = datetime.now(UTC)

        entries = payload.get("selectedColumns") or payload.get("selected_columns") or []
        try:
            selected_columns = _parse_selected_columns(entries)
        except Exception:
            success = False
            selected_columns = []

        if not selected_columns and default_selection:
            selected_columns = [
                SelectedColumn(column_name=name, display_label=name, position=index)
                for index, name in enumerate(default_selection)
            ]
            source = "defaults"

    trimmed = _dedupe_selected_columns(selected_columns)[:max_columns]
    state["selected_columns"] = [column.column_name for column in trimmed]
    state["preference_status"] = "ready"
    state["preference_source"] = source
    state["preference_version"] = version
    state["last_saved_at"] = updated_at

    log_event(
        get_logger(__name__),
        "preference.load",
        dataset_id=dataset_id,
        success=success,
        source=source,
        version=version,
    )

    return PreferenceSnapshot(
        dataset_id=dataset_id,
        user_id=device_id,
        selected_columns=trimmed,
        max_columns=max_columns,
        updated_at=updated_at,
        version=version,
        source=source,
    )


class ColumnPreferenceService:
    """Orchestrates catalog lookups and persistence for column preferences."""

    def __init__(self, metadata_repository: MetadataRepository) -> None:
        self.metadata_repository = metadata_repository
        self._cache: dict[tuple[str, str | None], PreferenceSnapshot] = {}
        self._logger = get_logger(__name__)

    def fetch_catalog(self, dataset_id: str) -> Sequence[DisplayableColumn]:
        catalog = self.metadata_repository.list_displayable_column_catalog(dataset_id)
        entries: list[DisplayableColumn] = []
        for entry in catalog:
            entries.append(
                DisplayableColumn(
                    column_name=str(entry.get("column_name", "")),
                    display_label=str(entry.get("column_label", entry.get("column_name", ""))),
                    data_type=entry.get("data_type"),
                    is_available=bool(entry.get("is_available", True)),
                    last_seen_at=entry.get("last_seen_at"),
                )
            )
        return entries

    def load_preference(
        self, dataset_id: str, user_id: str | None = None
    ) -> PreferenceSnapshot | None:
        cache_key = self._cache_key(dataset_id, user_id)
        if cache_key in self._cache:
            return self._cache[cache_key]
        record = self.metadata_repository.get_column_preference(
            data_file_id=dataset_id, user_id=user_id
        )
        if record is None:
            return None
        snapshot = self._to_snapshot(record)
        self._cache[cache_key] = snapshot
        return snapshot

    def save_preference(self, snapshot: PreferenceSnapshot) -> PreferenceSnapshot:
        normalized, allowed_columns = self._prepare_selection(snapshot)
        record = self.metadata_repository.save_column_preference(
            data_file_id=snapshot.dataset_id,
            user_id=snapshot.user_id,
            selected_columns=normalized,
            max_columns=snapshot.max_columns,
            allowed_columns=allowed_columns,
            actor_user_id=snapshot.user_id,
        )
        saved = self._to_snapshot(record)
        self._cache[self._cache_key(saved.dataset_id, saved.user_id)] = saved
        log_event(
            self._logger,
            "preferences.save",
            dataset_id=saved.dataset_id,
            user_id=saved.user_id or "system",
            column_count=len(saved.selected_columns),
        )
        return saved

    def reset_preference(self, dataset_id: str, user_id: str | None = None) -> None:
        self.metadata_repository.reset_column_preference(
            data_file_id=dataset_id,
            user_id=user_id,
            actor_user_id=user_id,
        )
        self._cache.pop(self._cache_key(dataset_id, user_id), None)
        log_event(
            self._logger,
            "preferences.reset",
            dataset_id=dataset_id,
            user_id=user_id or "system",
        )

    def load_mirrored_preference(
        self, dataset_id: str, device_id: str | None = None
    ) -> PreferenceSnapshot | None:
        cache_key = self._cache_key(dataset_id, device_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        record = self.metadata_repository.get_preference_mirror(
            data_file_id=dataset_id,
            device_id=device_id,
        )
        if record is None:
            return None

        snapshot = self._mirror_to_snapshot(record)
        self._cache[cache_key] = snapshot
        return snapshot

    def mirror_preference(self, snapshot: PreferenceSnapshot) -> PreferenceSnapshot:
        try:
            normalized, _ = self._prepare_selection(snapshot, strict_validation=False)
            max_columns = max(snapshot.max_columns, len(normalized), 1)
            record = self.metadata_repository.upsert_preference_mirror(
                data_file_id=snapshot.dataset_id,
                device_id=snapshot.user_id,
                selected_columns=normalized,
                max_columns=max_columns,
                version=snapshot.version,
                source=snapshot.source or "mirror",
            )
            mirrored = self._mirror_to_snapshot(record)
            self._cache[self._cache_key(mirrored.dataset_id, mirrored.user_id)] = mirrored
            return mirrored
        except Exception as error:
            self._logger.warning(
                "Mirror preference failed for dataset %s: %s",
                snapshot.dataset_id,
                error,
            )
            fallback_columns = _dedupe_selected_columns(snapshot.selected_columns)
            return PreferenceSnapshot(
                dataset_id=snapshot.dataset_id,
                user_id=snapshot.user_id,
                selected_columns=fallback_columns,
                max_columns=max(snapshot.max_columns, len(fallback_columns), 1),
                updated_at=datetime.now(UTC),
                version=snapshot.version,
                source=snapshot.source or "mirror",
            )

    def _to_snapshot(self, record: ColumnPreference) -> PreferenceSnapshot:
        columns: list[SelectedColumn] = []
        for entry in record.selected_columns:
            columns.append(
                SelectedColumn(
                    column_name=str(entry.get("column_name", "")),
                    display_label=str(entry.get("display_label", entry.get("column_name", ""))),
                    position=int(entry.get("position", 0)),
                )
            )
        columns = _dedupe_selected_columns(columns)
        version = len(getattr(record, "changes", []) or [])
        return PreferenceSnapshot(
            dataset_id=record.data_file_id,
            user_id=record.user_id,
            selected_columns=columns,
            max_columns=record.max_columns,
            updated_at=record.updated_at,
            version=version,
            source="preference",
        )

    def _mirror_to_snapshot(self, record: PreferenceMirror) -> PreferenceSnapshot:
        columns: list[SelectedColumn] = []
        for entry in record.selected_columns:
            columns.append(
                SelectedColumn(
                    column_name=str(entry.get("column_name", "")),
                    display_label=str(entry.get("display_label", entry.get("column_name", ""))),
                    position=int(entry.get("position", 0)),
                )
            )
        columns = _dedupe_selected_columns(columns)
        return PreferenceSnapshot(
            dataset_id=record.data_file_id,
            user_id=record.device_id,
            selected_columns=columns,
            max_columns=record.max_columns,
            updated_at=record.updated_at,
            version=record.version,
            source=record.source or "mirror",
        )

    def _cache_key(self, dataset_id: str, user_id: str | None) -> tuple[str, str | None]:
        return dataset_id, user_id

    def _prepare_selection(
        self,
        snapshot: PreferenceSnapshot,
        *,
        strict_validation: bool = True,
    ) -> tuple[list[dict[str, object]], set[str]]:
        max_columns = snapshot.max_columns or len(snapshot.selected_columns) or 1
        if max_columns < 1:
            raise ValueError("max_columns must be at least 1.")

        allowed_columns: set[str] = set()
        if strict_validation:
            catalog = self.fetch_catalog(snapshot.dataset_id)
            allowed_columns = {
                entry.column_name for entry in catalog if entry.is_available and entry.column_name
            }

        sanitized: list[tuple[str, str, int]] = []
        for column in snapshot.selected_columns:
            name = column.column_name.strip()
            if not name:
                raise ValueError("Column selections must include a column name.")
            label = column.display_label.strip() if column.display_label else name
            sanitized.append((name, label, column.position))

        duplicates = [
            name for name, count in Counter(entry[0] for entry in sanitized).items() if count > 1
        ]
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate columns are not allowed: {duplicate_list}.")

        if strict_validation:
            unknown = sorted({name for name, *_ in sanitized if name not in allowed_columns})
            if unknown:
                unknown_list = ", ".join(unknown)
                raise ValueError(
                    f"Unknown columns for dataset {snapshot.dataset_id}: {unknown_list}."
                )

        ordered: list[dict[str, object]] = []
        seen: set[str] = set()
        for name, label, _ in sorted(sanitized, key=lambda item: item[2]):
            if name in seen:
                continue
            seen.add(name)
            ordered.append(
                {
                    "column_name": name,
                    "display_label": label or name,
                    "position": len(ordered),
                }
            )

        if len(ordered) > max_columns:
            raise ValueError(f"Selection exceeds the maximum allowed columns ({max_columns}).")

        return ordered, allowed_columns
