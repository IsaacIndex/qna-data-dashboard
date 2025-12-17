from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import reembed
from app.embeddings.service import ReembedService
from app.models.source import SourceStatus
from app.services.source_repository import SourceRepository
from tests.fixtures.sources_mixed import seed_mixed_source_indexes


def _build_client(tmp_path: Path) -> tuple[TestClient, ReembedService]:
    repository = SourceRepository(data_root=tmp_path)
    service = ReembedService(repository=repository)
    app = FastAPI()
    app.include_router(reembed.router)
    app.dependency_overrides[reembed.get_repository] = lambda: repository
    app.dependency_overrides[reembed.get_reembed_service] = lambda: service
    return TestClient(app), service


def test_reembed_queues_job_and_tracks_status(tmp_path: Path) -> None:
    seed = seed_mixed_source_indexes(tmp_path)
    client, service = _build_client(tmp_path)
    target_uuid = seed["uuids"]["ready"]

    resp = client.post("/sources/reembed", json={"uuid": target_uuid})
    assert resp.status_code == 202, resp.text
    payload = resp.json()
    assert payload["uuid"] == target_uuid
    assert payload["job_id"]
    assert payload["status"] in {"queued", "processing", "completed"}
    assert service.status_overrides[target_uuid] == SourceStatus.ingesting

    status_resp = client.get(f"/sources/reembed/{payload['job_id']}")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["uuid"] == target_uuid
    assert status_body["status"] in {"queued", "processing", "completed"}


def test_reembed_returns_not_found_for_unknown_uuid(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)
    resp = client.post("/sources/reembed", json={"uuid": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 404
