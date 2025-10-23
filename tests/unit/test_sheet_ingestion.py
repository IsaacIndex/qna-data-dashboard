from __future__ import annotations

from app.services.ingestion import (
    DiscoveredSheet,
    HiddenSheetPolicy,
    apply_hidden_sheet_policy,
    build_sheet_summary,
    discover_workbook_sheets,
)


def test_discover_workbook_sheets_marks_hidden(workbook_builder) -> None:
    workbook_path = workbook_builder(filename="unit_discovery.xlsx")
    discovered = discover_workbook_sheets(workbook_path)

    sheet_names = [sheet.name for sheet in discovered]
    assert sheet_names == ["North", "South", "HiddenStrategic"]

    hidden_names = [sheet.name for sheet in discovered if sheet.hidden]
    assert hidden_names == ["HiddenStrategic"]


def test_apply_hidden_policy_tracks_opt_ins() -> None:
    discovered = [
        DiscoveredSheet(name="North", position=0, hidden=False),
        DiscoveredSheet(name="South", position=1, hidden=False),
        DiscoveredSheet(name="HiddenStrategic", position=2, hidden=True),
    ]

    policy = HiddenSheetPolicy(default_action="exclude", overrides=["HiddenStrategic"])
    included, hidden_opt_ins, _ = apply_hidden_sheet_policy(discovered, policy)

    assert {sheet.name for sheet in included} == {"North", "South", "HiddenStrategic"}
    assert {sheet.name for sheet in hidden_opt_ins} == {"HiddenStrategic"}

    exclude_all_policy = HiddenSheetPolicy(default_action="exclude")
    excluded_included, excluded_opt_ins, excluded_hidden = apply_hidden_sheet_policy(
        discovered, exclude_all_policy
    )
    assert {sheet.name for sheet in excluded_included} == {"North", "South"}
    assert not excluded_opt_ins
    assert {sheet.name for sheet in excluded_hidden} == {"HiddenStrategic"}


def test_build_sheet_summary_counts_created_and_hidden_opt_ins() -> None:
    included = [
        DiscoveredSheet(name="North", position=0, hidden=False),
        DiscoveredSheet(name="South", position=1, hidden=False),
        DiscoveredSheet(name="HiddenStrategic", position=2, hidden=True),
    ]
    hidden_opt_ins = [
        DiscoveredSheet(name="HiddenStrategic", position=2, hidden=True),
    ]

    summary = build_sheet_summary(included, hidden_opt_ins, inactive=0)
    assert summary == {"created": 3, "hidden_opt_ins": 1, "inactive": 0}
