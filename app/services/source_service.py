from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping, Sequence

from app.ingest.components.base_filters import build_filter_options
from app.ingest.status_sync import apply_status_overrides, merge_sources_by_uuid
from app.models.source import Source, SourceStatus, SourceType
from app.services.source_repository import SourceRepository
from app.utils.metrics import emit_ingest_timing


@dataclass
class SourcePage:
    items: list[Source]
    next_cursor: str | None = None


class SourceService:
    """Aggregate sources across contexts, apply filters/sorting, and paginate results."""

    def __init__(self, repository: SourceRepository | None = None) -> None:
        self.repository = repository or SourceRepository()

    def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
        status_filter: str | None = None,
        type_filter: str | None = None,
        group: str | None = None,
        dataset: str | None = None,
        sort: str | None = None,
        status_overrides: Mapping[str, SourceStatus | str] | None = None,
    ) -> SourcePage:
        started = perf_counter()
        safe_limit = max(1, min(limit, 200))
        sources = merge_sources_by_uuid(self.repository.list_sources())
        sources = apply_status_overrides(sources, status_overrides)
        sources = self._apply_filters(
            sources,
            status_filter=status_filter,
            type_filter=type_filter,
            dataset=dataset,
            group=group,
        )
        sources = self._apply_sort(sources, sort or "label")
        items, next_cursor = self._paginate(sources, cursor, safe_limit)
        emit_ingest_timing(
            "sources.list",
            elapsed_ms=(perf_counter() - started) * 1000,
            total=len(items),
            requested_limit=safe_limit,
            has_next=bool(next_cursor),
            dataset=dataset,
            type=type_filter,
            status=status_filter,
            group=group,
        )
        return SourcePage(items=items, next_cursor=next_cursor)

    def build_filter_options(self, sources: Sequence[Source] | None = None) -> dict[str, list[str]]:
        pool = list(sources) if sources is not None else merge_sources_by_uuid(self.repository.list_sources())
        return build_filter_options(pool)

    # ---- helpers ----
    def _apply_filters(
        self,
        sources: Sequence[Source],
        *,
        status_filter: str | None,
        type_filter: str | None,
        dataset: str | None,
        group: str | None,
    ) -> list[Source]:
        filtered: list[Source] = []
        status_value = SourceStatus(status_filter) if status_filter else None
        type_value = SourceType(type_filter) if type_filter else None
        group_lower = group.lower() if group else None

        for source in sources:
            if dataset and source.dataset != dataset:
                continue
            if type_value and source.type is not type_value:
                continue
            if status_value and source.status is not status_value:
                continue
            if group_lower:
                normalized = [value.lower() for value in source.groups]
                if group_lower not in normalized:
                    continue
            filtered.append(source)
        return filtered

    def _apply_sort(self, sources: Sequence[Source], sort: str) -> list[Source]:
        key = sort or "label"
        valid_sorts = {"label", "dataset", "status", "last_updated", "group"}
        if key not in valid_sorts:
            raise ValueError(f"Unsupported sort '{key}'. Expected one of: {', '.join(sorted(valid_sorts))}.")

        def _sort_key(source: Source) -> tuple:
            if key == "dataset":
                return (source.dataset.lower(), source.label.lower())
            if key == "status":
                return (source.status.value, source.label.lower())
            if key == "group":
                first_group = source.groups[0].lower() if source.groups else ""
                return (first_group, source.label.lower())
            if key == "last_updated":
                return (
                    0 if source.last_updated is None else 1,
                    "" if source.last_updated is None else source.last_updated.isoformat(),
                    source.label.lower(),
                )
            return (source.label.lower(), source.dataset.lower())

        return sorted(sources, key=_sort_key)

    def _paginate(self, sources: Sequence[Source], cursor: str | None, limit: int) -> tuple[list[Source], str | None]:
        try:
            offset = int(cursor) if cursor else 0
        except ValueError as error:
            raise ValueError("cursor must be an integer offset") from error
        start = max(offset, 0)
        end = start + limit
        next_cursor = str(end) if end < len(sources) else None
        return list(sources[start:end]), next_cursor
