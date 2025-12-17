from __future__ import annotations

from collections.abc import Sequence

from app.models.source import Source, SourceStatus, SourceType


def build_filter_options(sources: Sequence[Source]) -> dict[str, list[str]]:
    """Derive unique filter options from a set of sources for UI controls."""
    datasets = sorted({source.dataset for source in sources})
    types = sorted({source.type.value for source in sources})
    statuses = sorted({source.status.value for source in sources})
    groups = sorted({group for source in sources for group in source.groups})
    return {"datasets": datasets, "types": types, "statuses": statuses, "groups": groups}


def summarize_filters(
    *,
    dataset: str | None = None,
    source_type: str | SourceType | None = None,
    status: str | SourceStatus | None = None,
    group: str | None = None,
    search: str | None = None,
) -> str:
    """Human-readable summary of active filters for display above result lists."""
    parts: list[str] = []
    if dataset:
        parts.append(f"dataset={dataset}")
    if source_type:
        value = source_type.value if isinstance(source_type, SourceType) else source_type
        parts.append(f"type={value}")
    if status:
        value = status.value if isinstance(status, SourceStatus) else status
        parts.append(f"status={value}")
    if group:
        parts.append(f"group={group}")
    if search:
        parts.append(f'search="{search}"')
    return ", ".join(parts) if parts else "No filters applied"
