from __future__ import annotations

from datetime import datetime

import pytest

from app.db.schema import FileType, IngestionStatus
from app.services.preferences import (
    ColumnPreferenceService,
    DisplayableColumn,
    PreferenceSnapshot,
    SelectedColumn,
)


class FakePreferenceRecord:
    def __init__(
        self,
        *,
        dataset_id: str,
        user_id: str | None,
        selected_columns: list[dict[str, object]],
        max_columns: int,
        updated_at: datetime | None = None,
    ) -> None:
        self.data_file_id = dataset_id
        self.user_id = user_id
        self.selected_columns = selected_columns
        self.max_columns = max_columns
        self.updated_at = updated_at or datetime.now()


class FakeMetadataRepository:
    def __init__(self) -> None:
        self.catalog = [
            {"column_name": "question", "column_label": "Question", "is_available": True},
            {"column_name": "response", "column_label": "Response", "is_available": True},
            {"column_name": "notes", "column_label": "Notes", "is_available": True},
        ]
        self.saved_payload: dict[str, object] | None = None
        self.preference: FakePreferenceRecord | None = None

    def list_displayable_column_catalog(self, dataset_id: str) -> list[dict[str, object]]:
        return list(self.catalog)

    def save_column_preference(
        self,
        *,
        data_file_id: str,
        user_id: str | None,
        selected_columns: list[dict[str, object]],
        max_columns: int,
        allowed_columns: set[str] | None = None,
        actor_user_id: str | None = None,
    ) -> FakePreferenceRecord:
        self.saved_payload = {
            "data_file_id": data_file_id,
            "user_id": user_id,
            "selected_columns": selected_columns,
            "max_columns": max_columns,
            "actor_user_id": actor_user_id,
        }
        record = FakePreferenceRecord(
            dataset_id=data_file_id,
            user_id=user_id,
            selected_columns=selected_columns,
            max_columns=max_columns,
        )
        self.preference = record
        return record

    def get_column_preference(
        self,
        *,
        data_file_id: str,
        user_id: str | None,
        include_inactive: bool = False,
    ) -> FakePreferenceRecord | None:
        return self.preference


def _snapshot(columns: list[tuple[str, str, int]], *, dataset_id: str = "dataset-123", max_columns: int = 10):
    return PreferenceSnapshot(
        dataset_id=dataset_id,
        user_id=None,
        selected_columns=[
            SelectedColumn(column_name=name, display_label=label, position=position)
            for name, label, position in columns
        ],
        max_columns=max_columns,
        updated_at=datetime.now(),
    )


def test_save_preference_orders_columns_and_normalizes_positions() -> None:
    repository = FakeMetadataRepository()
    service = ColumnPreferenceService(repository)
    snapshot = _snapshot(
        [
            ("response", "Response", 5),
            ("question", "Question", 2),
        ]
    )

    saved = service.save_preference(snapshot)

    assert [item["column_name"] for item in repository.saved_payload["selected_columns"]] == [
        "question",
        "response",
    ]
    assert [item["position"] for item in repository.saved_payload["selected_columns"]] == [0, 1]
    assert [column.column_name for column in saved.selected_columns] == ["question", "response"]
    assert [column.position for column in saved.selected_columns] == [0, 1]


def test_save_preference_rejects_unknown_columns() -> None:
    repository = FakeMetadataRepository()
    service = ColumnPreferenceService(repository)
    snapshot = _snapshot(
        [
            ("question", "Question", 0),
            ("unknown", "Unknown", 1),
        ]
    )

    with pytest.raises(ValueError, match="Unknown columns"):
        service.save_preference(snapshot)


def test_save_preference_rejects_duplicate_columns() -> None:
    repository = FakeMetadataRepository()
    service = ColumnPreferenceService(repository)
    snapshot = _snapshot(
        [
            ("question", "Question", 0),
            ("question", "Duplicate", 1),
        ]
    )

    with pytest.raises(ValueError, match="Duplicate columns"):
        service.save_preference(snapshot)


def test_save_preference_respects_max_columns_limit() -> None:
    repository = FakeMetadataRepository()
    service = ColumnPreferenceService(repository)
    snapshot = _snapshot(
        [
            ("question", "Question", 0),
            ("response", "Response", 1),
        ],
        max_columns=1,
    )

    with pytest.raises(ValueError, match="exceeds the maximum allowed"):
        service.save_preference(snapshot)


def test_save_preference_records_audit_change(
    metadata_repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = metadata_repository.create_data_file(
        display_name="Audit Dataset",
        original_path="ignored.csv",
        file_hash="audit-hash",
        file_type=FileType.CSV,
        delimiter=",",
        sheet_name=None,
        selected_columns=["owner", "stage"],
        status=IngestionStatus.READY,
    )
    metadata_repository.session.commit()

    service = ColumnPreferenceService(metadata_repository)
    monkeypatch.setattr(
        service,
        "fetch_catalog",
        lambda dataset_id: [
            DisplayableColumn(
                column_name="owner",
                display_label="Owner",
                data_type="text",
                is_available=True,
                last_seen_at=None,
            ),
            DisplayableColumn(
                column_name="stage",
                display_label="Stage",
                data_type="text",
                is_available=True,
                last_seen_at=None,
            ),
        ],
    )
    snapshot = PreferenceSnapshot(
        dataset_id=dataset.id,
        user_id=None,
        selected_columns=[
            SelectedColumn(column_name="owner", display_label="Owner", position=0),
            SelectedColumn(column_name="stage", display_label="Stage", position=1),
        ],
        max_columns=5,
        updated_at=datetime.now(),
    )
    service.save_preference(snapshot)
    metadata_repository.session.commit()

    preference = metadata_repository.get_column_preference(data_file_id=dataset.id, user_id=None)
    assert preference is not None
    changes = metadata_repository.list_column_preference_changes(preference.id)
    assert changes, "Expected audit log entry after saving preference"


def test_update_preference_appends_audit_change(
    metadata_repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = metadata_repository.create_data_file(
        display_name="Audit Dataset",
        original_path="ignored.csv",
        file_hash="audit-hash-2",
        file_type=FileType.CSV,
        delimiter=",",
        sheet_name=None,
        selected_columns=["owner", "stage", "region"],
        status=IngestionStatus.READY,
    )
    metadata_repository.session.commit()

    service = ColumnPreferenceService(metadata_repository)
    monkeypatch.setattr(
        service,
        "fetch_catalog",
        lambda dataset_id: [
            DisplayableColumn(
                column_name="owner",
                display_label="Owner",
                data_type="text",
                is_available=True,
                last_seen_at=None,
            ),
            DisplayableColumn(
                column_name="stage",
                display_label="Stage",
                data_type="text",
                is_available=True,
                last_seen_at=None,
            ),
            DisplayableColumn(
                column_name="region",
                display_label="Region",
                data_type="text",
                is_available=True,
                last_seen_at=None,
            ),
        ],
    )
    initial = PreferenceSnapshot(
        dataset_id=dataset.id,
        user_id=None,
        selected_columns=[
            SelectedColumn(column_name="owner", display_label="Owner", position=0),
            SelectedColumn(column_name="stage", display_label="Stage", position=1),
        ],
        max_columns=5,
        updated_at=datetime.now(),
    )
    service.save_preference(initial)
    metadata_repository.session.commit()

    updated = PreferenceSnapshot(
        dataset_id=dataset.id,
        user_id=None,
        selected_columns=[
            SelectedColumn(column_name="region", display_label="Region", position=0),
            SelectedColumn(column_name="owner", display_label="Owner", position=1),
        ],
        max_columns=5,
        updated_at=datetime.now(),
    )
    service.save_preference(updated)
    metadata_repository.session.commit()

    preference = metadata_repository.get_column_preference(data_file_id=dataset.id, user_id=None)
    assert preference is not None
    changes = metadata_repository.list_column_preference_changes(preference.id)
    assert len(changes) >= 2, "Expected audit history to append entries on update"
