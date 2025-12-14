from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.schema import SheetStatus
from app.services.ingestion import (
    aggregate_column_catalog,
    build_column_picker_options,
)
from app.services.preferences import persist_column_selection


@dataclass
class _SheetStub:
    id: str
    display_label: str
    status: SheetStatus
    column_schema: list[dict[str, object]]
    last_refreshed_at: datetime | None = None


def test_column_picker_builds_deduped_options_with_sheet_chips() -> None:
    now = datetime.now(UTC)
    sheets = [
        _SheetStub(
            id="s1",
            display_label="Sheet A",
            status=SheetStatus.ACTIVE,
            column_schema=[
                {"name": "Region", "availability": "available", "inferredType": "string"},
                {"name": "Category", "availability": "available"},
                {"name": "Ghost", "availability": "missing"},
            ],
            last_refreshed_at=now,
        ),
        _SheetStub(
            id="s2",
            display_label="Sheet B",
            status=SheetStatus.ACTIVE,
            column_schema=[
                {"name": "region", "availability": "missing"},
                {"name": "Revenue", "availability": "available", "inferredType": "number"},
                {"name": "Ghost", "availability": "missing"},
            ],
            last_refreshed_at=now + timedelta(minutes=5),
        ),
    ]

    catalog = aggregate_column_catalog(sheets, include_unavailable=True)
    options = build_column_picker_options(catalog)

    names = {option["column_name"] for option in options}
    assert {"Region", "Category", "Revenue", "Ghost"}.issubset(names)

    region = next(option for option in options if option["column_name"].lower() == "region")
    assert region["availability"] == "available"
    assert set(region["sheet_chips"]) == {"Sheet A", "Sheet B"}
    assert region["data_type"] == "string"

    missing = next(option for option in options if option["availability"] == "missing")
    assert missing["column_name"] == "Ghost"
    assert set(missing["sheet_chips"]) == {"Sheet A", "Sheet B"}


def test_column_selection_persists_across_tab_switches() -> None:
    store: dict[str, object] = {}
    state = persist_column_selection(
        store,
        dataset_id="ds-1",
        selected_columns=["Region", "Revenue"],
        active_tab="ingest",
    )
    assert state["selected_columns"] == ["Region", "Revenue"]
    assert state["active_tab"] == "ingest"
    first_saved = state["last_saved_at"]

    updated = persist_column_selection(
        store,
        dataset_id="ds-1",
        selected_columns=["Region"],
        active_tab="search",
    )
    assert updated["selected_columns"] == ["Region"]
    assert updated["active_tab"] == "search"
    assert updated["last_saved_at"] >= first_saved
    assert updated["reset_requested"] is False
