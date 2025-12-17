from __future__ import annotations

from pathlib import Path

from app.embeddings.service import ReembedService
from app.ingest.reembed_panel import build_reembed_options
from app.models.source import SourceStatus
from app.services.source_repository import SourceRepository
from app.services.source_service import SourceService
from tests.fixtures.sources_mixed import seed_mixed_source_indexes


def test_reembed_selector_uses_human_labels(tmp_path: Path, monkeypatch) -> None:
    seed = seed_mixed_source_indexes(tmp_path)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    repository = SourceRepository(data_root=tmp_path)
    service = SourceService(repository=repository)
    reembed = ReembedService(repository=repository)

    sources = service.list_sources(limit=10, sort="label").items
    options = build_reembed_options(sources)
    assert options

    for option in options:
        label = option["displayLabel"]
        assert option["uuid"]  # value should still use the UUID
        assert option["uuid"] not in label  # hide raw IDs from the label
        assert "(" in label and "," in label  # dataset/type context shown

    target_uuid = seed["uuids"]["embedding"]
    job = reembed.enqueue(target_uuid)
    assert job.status in {"queued", "processing", "completed"}

    refreshed = service.list_sources(status_overrides=reembed.status_overrides)
    target = next(source for source in refreshed.items if source.uuid == target_uuid)
    assert target.status is SourceStatus.ingesting
