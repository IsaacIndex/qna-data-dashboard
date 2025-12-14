from __future__ import annotations

from app.services.refresh_utils import (
    DiscoveredSheetSnapshot,
    ExistingSheetSnapshot,
    match_sheets,
)


def _schema(*names: str) -> list[dict[str, object]]:
    return [{"name": name, "inferredType": "string", "nullable": False} for name in names]


def test_match_sheets_reuses_existing_by_name() -> None:
    existing = [
        ExistingSheetSnapshot(
            id="north", sheet_name="North", checksum="old", column_schema=_schema("a"), row_count=2
        )
    ]
    discovered = [
        DiscoveredSheetSnapshot(
            sheet_name="North", checksum="new", column_schema=_schema("a"), row_count=2
        )
    ]

    matches, deactivated = match_sheets(existing, discovered, tolerance="strict")

    assert len(matches) == 1
    discovered_sheet, existing_sheet = matches[0]
    assert discovered_sheet.sheet_name == "North"
    assert existing_sheet is not None and existing_sheet.id == "north"
    assert deactivated == []


def test_match_sheets_detects_rename_by_checksum() -> None:
    existing = [
        ExistingSheetSnapshot(
            id="south",
            sheet_name="South",
            checksum="hash1",
            column_schema=_schema("region"),
            row_count=2,
        )
    ]
    discovered = [
        DiscoveredSheetSnapshot(
            sheet_name="SouthEast", checksum="hash1", column_schema=_schema("region"), row_count=2
        )
    ]

    matches, deactivated = match_sheets(existing, discovered, tolerance="strict")

    assert len(matches) == 1
    discovered_sheet, existing_sheet = matches[0]
    assert discovered_sheet.sheet_name == "SouthEast"
    assert existing_sheet is not None and existing_sheet.id == "south"
    assert deactivated == []


def test_match_sheets_uses_schema_when_allowed() -> None:
    existing = [
        ExistingSheetSnapshot(
            id="south",
            sheet_name="South",
            checksum="hash1",
            column_schema=_schema("region"),
            row_count=2,
        )
    ]
    discovered = [
        DiscoveredSheetSnapshot(
            sheet_name="SouthEast", checksum="hash2", column_schema=_schema("region"), row_count=2
        )
    ]

    matches_strict, _ = match_sheets(existing, discovered, tolerance="strict")
    _, strict_existing = matches_strict[0]
    assert strict_existing is None

    matches_schema, deactivated = match_sheets(existing, discovered, tolerance="allow_same_schema")
    discovered_sheet, existing_sheet = matches_schema[0]
    assert existing_sheet is not None and existing_sheet.id == "south"
    assert not deactivated


def test_match_sheets_marks_remaining_as_deactivated() -> None:
    existing = [
        ExistingSheetSnapshot(
            id="north",
            sheet_name="North",
            checksum="hash-n",
            column_schema=_schema("a"),
            row_count=2,
        ),
        ExistingSheetSnapshot(
            id="south",
            sheet_name="South",
            checksum="hash-s",
            column_schema=_schema("a"),
            row_count=2,
        ),
    ]
    discovered = [
        DiscoveredSheetSnapshot(
            sheet_name="North", checksum="hash-x", column_schema=_schema("a"), row_count=2
        )
    ]

    matches, deactivated = match_sheets(existing, discovered, tolerance="strict")

    assert len(matches) == 1
    assert matches[0][1] is not None and matches[0][1].id == "north"
    assert len(deactivated) == 1
    assert deactivated[0].id == "south"
