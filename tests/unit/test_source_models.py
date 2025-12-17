from __future__ import annotations

import pytest

from app.models.source import (
    LegacyReason,
    LegacySource,
    RemapStatus,
    Source,
    SourceStatus,
    SourceType,
)


def test_source_trims_and_dedupes_groups() -> None:
    source = Source(
        uuid="123e4567-e89b-12d3-a456-426614174000",
        label="  Sales ",
        dataset=" Reports ",
        type=SourceType.sheet,
        status=SourceStatus.ready,
        groups=["north", "north", "west", " "],
    )

    assert source.label == "Sales"
    assert source.dataset == "Reports"
    assert source.groups == ["north", "west"]


def test_source_requires_label_and_dataset() -> None:
    with pytest.raises(ValueError):
        Source(
            uuid="123",
            label="",
            dataset="reports",
            type=SourceType.sheet,
        )

    with pytest.raises(ValueError):
        Source(
            uuid="123",
            label="Sales",
            dataset=" ",
            type=SourceType.sheet,
        )


def test_legacy_source_sets_flags_and_defaults() -> None:
    legacy = LegacySource(
        uuid="123e4567-e89b-12d3-a456-426614174999",
        label="Old Upload",
        dataset="legacy",
        type=SourceType.tmp_file,
        legacy_reason=LegacyReason.missing_uuid,
        original_id="upload-42",
    )

    assert legacy.legacy is True
    assert legacy.remap_status is RemapStatus.pending
    assert legacy.legacy_reason is LegacyReason.missing_uuid
