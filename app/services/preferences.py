from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from app.db.metadata import MetadataRepository
from app.db.schema import ColumnPreference
from app.utils.logging import get_logger, log_event


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


class ColumnPreferenceService:
    """Orchestrates catalog lookups and persistence for column preferences."""

    def __init__(self, metadata_repository: MetadataRepository):
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

    def load_preference(self, dataset_id: str, user_id: str | None = None) -> PreferenceSnapshot | None:
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
        columns.sort(key=lambda item: item.position)
        return PreferenceSnapshot(
            dataset_id=record.data_file_id,
            user_id=record.user_id,
            selected_columns=columns,
            max_columns=record.max_columns,
            updated_at=record.updated_at,
        )

    def _cache_key(self, dataset_id: str, user_id: str | None) -> tuple[str, str | None]:
        return dataset_id, user_id

    def _prepare_selection(self, snapshot: PreferenceSnapshot) -> tuple[list[dict[str, object]], set[str]]:
        if snapshot.max_columns < 1:
            raise ValueError("max_columns must be at least 1.")

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

        unknown = sorted({name for name, *_ in sanitized if name not in allowed_columns})
        if unknown:
            unknown_list = ", ".join(unknown)
            raise ValueError(f"Unknown columns for dataset {snapshot.dataset_id}: {unknown_list}.")

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

        if len(ordered) > snapshot.max_columns:
            raise ValueError(
                f"Selection exceeds the maximum allowed columns ({snapshot.max_columns})."
            )

        return ordered, allowed_columns
