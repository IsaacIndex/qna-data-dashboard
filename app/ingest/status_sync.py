from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from app.models.source import Source, SourceStatus


def _status_rank(status: SourceStatus) -> int:
    ordering = {
        SourceStatus.error: 5,
        SourceStatus.archived: 4,
        SourceStatus.ingesting: 3,
        SourceStatus.ready: 2,
        SourceStatus.new: 1,
    }
    return ordering.get(status, 0)


def _timestamp(source: Source) -> datetime:
    if source.last_updated is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if source.last_updated.tzinfo is None:
        return source.last_updated.replace(tzinfo=timezone.utc)
    return source.last_updated


def merge_sources_by_uuid(sources: Sequence[Source]) -> list[Source]:
    """Deduplicate sources by UUID, preferring the freshest status."""
    merged: dict[str, Source] = {}
    for candidate in sources:
        existing = merged.get(candidate.uuid)
        if existing is None:
            merged[candidate.uuid] = candidate
            continue
        merged[candidate.uuid] = _newer(candidate, existing)
    return list(merged.values())


def apply_status_overrides(
    sources: Sequence[Source], overrides: Mapping[str, SourceStatus | str] | None
) -> list[Source]:
    if not overrides:
        return list(sources)
    updated: list[Source] = []
    for source in sources:
        if source.uuid not in overrides:
            updated.append(source)
            continue
        override = overrides[source.uuid]
        status = SourceStatus(override)
        updated.append(source.model_copy(update={"status": status}))
    return merge_sources_by_uuid(updated)


def _newer(left: Source, right: Source) -> Source:
    left_score = (_timestamp(left), _status_rank(left.status))
    right_score = (_timestamp(right), _status_rank(right.status))
    return left if left_score >= right_score else right
