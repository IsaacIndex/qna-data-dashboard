from __future__ import annotations

from pathlib import Path

from app.ingest.status_sync import apply_status_overrides
from app.ingest.unified_list import format_source_row
from app.models.source import SourceStatus
from app.services.source_repository import SourceRepository
from app.services.source_service import SourceService
from tests.fixtures.sources_mixed import seed_mixed_source_indexes


def test_unified_list_deduplicates_and_syncs_statuses(tmp_path: Path, monkeypatch) -> None:
    seed = seed_mixed_source_indexes(tmp_path, include_conflict=True)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    repository = SourceRepository(data_root=tmp_path)
    service = SourceService(repository=repository)

    page = service.list_sources(limit=10, sort="label")
    uuids = [source.uuid for source in page.items]
    assert len(uuids) == len(set(uuids))

    conflict_uuid = seed["uuids"]["conflict"]
    conflict_source = next(source for source in page.items if source.uuid == conflict_uuid)
    assert conflict_source.status is SourceStatus.ready

    rows = [format_source_row(source) for source in page.items]
    conflict_row = next(row for row in rows if row["uuid"] == conflict_uuid)
    assert "sales" in conflict_row["displayLabel"]
    assert "tmp_file" in conflict_row["displayLabel"]
    assert any(row["legacy"] is True for row in rows)

    synced = apply_status_overrides(page.items, {conflict_uuid: SourceStatus.archived})
    assert (
        next(source for source in synced if source.uuid == conflict_uuid).status
        is SourceStatus.archived
    )

    filters = service.build_filter_options(page.items)
    assert set(filters["datasets"]) == {"sales", "ml"}
    assert set(filters["types"]) == {"tmp_file", "sheet", "embedding"}
    assert "ready" in filters["statuses"]
