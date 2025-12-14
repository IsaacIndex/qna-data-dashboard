from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.schema import SheetStatus
from app.services.ingestion import ColumnCatalogEntry, aggregate_column_catalog


@dataclass
class _SheetStub:
    id: str
    display_label: str
    status: SheetStatus
    column_schema: list[dict[str, object]]
    last_refreshed_at: datetime | None = None


def test_catalog_dedupes_and_merges_availability() -> None:
    now = datetime.now(UTC)
    sheets = [
        _SheetStub(
            id="s1",
            display_label="Sheet A",
            status=SheetStatus.ACTIVE,
            column_schema=[
                {"name": "Title", "inferredType": "string", "availability": "available"}
            ],
            last_refreshed_at=now,
        ),
        _SheetStub(
            id="s2",
            display_label="Sheet B",
            status=SheetStatus.ACTIVE,
            column_schema=[
                {"name": " title ", "availability": "missing"},
            ],
            last_refreshed_at=now + timedelta(days=1),
        ),
    ]

    catalog = aggregate_column_catalog(sheets, include_unavailable=True)
    assert len(catalog) == 1
    entry = catalog[0]
    assert isinstance(entry, ColumnCatalogEntry)
    assert entry.column_name == "Title"
    assert entry.availability == "available"
    assert entry.sheet_ids == ("s1", "s2")
    assert entry.sheet_labels == ("Sheet A", "Sheet B")
    assert entry.last_seen_at == sheets[1].last_refreshed_at
    assert entry.normalized_key == "title"


def test_catalog_skips_unavailable_when_not_requested() -> None:
    sheets = [
        _SheetStub(
            id="s1",
            display_label="Sheet A",
            status=SheetStatus.ACTIVE,
            column_schema=[{"name": "Ghost", "availability": "unavailable"}],
        )
    ]

    assert aggregate_column_catalog(sheets, include_unavailable=False) == []
