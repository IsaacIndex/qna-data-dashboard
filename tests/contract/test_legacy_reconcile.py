from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import legacy
from app.models.source import SourceType
from app.services.legacy_reconcile import LegacyReconcileService
from app.services.source_repository import SourceRepository
from app.utils.source_uuid import stable_source_uuid
from tests.fixtures.sources_mixed import seed_mixed_source_indexes


def _build_client(tmp_path: Path) -> tuple[TestClient, SourceRepository]:
    repository = SourceRepository(data_root=tmp_path)
    service = LegacyReconcileService(repository=repository)
    app = FastAPI()
    app.include_router(legacy.router)
    app.dependency_overrides[legacy.get_repository] = lambda: repository
    app.dependency_overrides[legacy.get_reconcile_service] = lambda: service
    return TestClient(app), repository


def test_reconcile_reports_dry_run_and_reinserts(tmp_path: Path, monkeypatch) -> None:
    seed_mixed_source_indexes(tmp_path)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    client, repository = _build_client(tmp_path)

    missing_path = tmp_path / "ingest_sources" / "ml" / "missing.csv"
    expected_uuid = stable_source_uuid(
        label="legacy-missing.csv", dataset="ml", source_type=SourceType.sheet
    )

    dry_resp = client.post("/sources/reconcile-legacy", json={"dry_run": True})
    assert dry_resp.status_code == 200
    dry_body = dry_resp.json()
    assert expected_uuid in dry_body["reinserted"]
    assert dry_body["conflicts"] == []
    assert not missing_path.exists()

    resp = client.post("/sources/reconcile-legacy", json={"dry_run": False})
    assert resp.status_code == 200
    body = resp.json()
    assert expected_uuid in body["reinserted"]
    assert body["conflicts"] == []
    assert missing_path.exists()

    restored = repository.get(expected_uuid)
    assert restored is not None
    assert restored.uuid == expected_uuid
