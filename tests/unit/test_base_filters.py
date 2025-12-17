from __future__ import annotations

from app.ingest.components.base_filters import build_filter_options, summarize_filters
from app.models.source import Source, SourceStatus, SourceType


def _source(label: str, dataset: str, source_type: SourceType, status: SourceStatus) -> Source:
    return Source(
        uuid=f"uuid-{label}",
        label=label,
        dataset=dataset,
        type=source_type,
        status=status,
    )


def test_build_filter_options_dedupes_and_sorts() -> None:
    sources = [
        _source("A", "ds1", SourceType.sheet, SourceStatus.ready).model_copy(update={"groups": ["north"]}),
        _source("B", "ds1", SourceType.tmp_file, SourceStatus.ingesting).model_copy(update={"groups": ["north", "east"]}),
        _source("C", "ds2", SourceType.sheet, SourceStatus.ready).model_copy(update={"groups": ["west"]}),
    ]

    options = build_filter_options(sources)

    assert options["datasets"] == ["ds1", "ds2"]
    assert options["types"] == ["sheet", "tmp_file"]
    assert options["statuses"] == ["ingesting", "ready"]
    assert options["groups"] == ["east", "north", "west"]


def test_summarize_filters_orders_labels() -> None:
    summary = summarize_filters(dataset="ds1", source_type="sheet", status="ready", group="north", search="foo")
    assert "dataset=ds1" in summary
    assert "type=sheet" in summary
    assert "status=ready" in summary
    assert "group=north" in summary
    assert "search=\"foo\"" in summary
