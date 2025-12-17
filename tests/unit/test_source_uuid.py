from __future__ import annotations

import json
from pathlib import Path

from app.models.source import LegacyReason, SourceType
from app.utils.source_uuid import (
    canonical_source_key,
    detect_legacy_reason,
    ensure_canonical_uuid,
    stable_source_uuid,
)


def test_stable_uuid_is_deterministic() -> None:
    uuid_one = stable_source_uuid(
        label="Sales Data", dataset="analytics", source_type=SourceType.sheet
    )
    uuid_two = stable_source_uuid(
        label="Sales Data", dataset="analytics", source_type=SourceType.sheet
    )
    uuid_other = stable_source_uuid(
        label="Sales Data", dataset="other", source_type=SourceType.sheet
    )

    assert uuid_one == uuid_two
    assert uuid_one != uuid_other


def test_canonical_key_normalizes_whitespace_and_case() -> None:
    key = canonical_source_key(
        label="  Sales Data  ", dataset="ANALYTICS ", source_type=SourceType.sheet
    )
    assert key == "analytics|sheet|sales data"


def test_detect_legacy_reason_prioritizes_missing_uuid() -> None:
    reason = detect_legacy_reason({"extracted_columns": []}, path_exists=True)
    assert reason is LegacyReason.missing_uuid

    reason_missing_headers = detect_legacy_reason(
        {"uuid": "123", "extracted_columns": []}, path_exists=True
    )
    assert reason_missing_headers is LegacyReason.missing_headers


def test_ensure_canonical_uuid_persists_map(tmp_path: Path) -> None:
    map_path = tmp_path / "_uuid_map.json"
    first = ensure_canonical_uuid(
        label="Sales Data",
        dataset="analytics",
        source_type=SourceType.sheet,
        original_id="legacy-1",
        map_path=map_path,
    )
    second = ensure_canonical_uuid(
        label="Sales Data",
        dataset="analytics",
        source_type=SourceType.sheet,
        original_id="legacy-1",
        map_path=map_path,
    )

    assert first == second
    mapping = json.loads(map_path.read_text())
    assert mapping["legacy:legacy-1"] == first
