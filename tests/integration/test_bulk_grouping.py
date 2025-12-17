from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import ingest
from app.services.audit_log import AuditLogService
from app.services.source_repository import SourceRepository
from tests.fixtures.sources_mixed import seed_mixed_source_indexes


def _build_client(tmp_path: Path) -> tuple[TestClient, SourceRepository]:
    repository = SourceRepository(data_root=tmp_path)
    audit = AuditLogService(data_root=tmp_path)
    app = FastAPI()
    app.include_router(ingest.router)
    app.dependency_overrides[ingest.get_repository] = lambda: repository
    app.dependency_overrides[ingest.get_audit_log] = lambda: audit
    return TestClient(app), repository


def test_bulk_updates_status_and_groups(tmp_path: Path, monkeypatch) -> None:
    seed = seed_mixed_source_indexes(tmp_path, include_conflict=True)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    client, repository = _build_client(tmp_path)

    target_uuids = [seed["uuids"]["ready"], seed["uuids"]["ingesting"]]
    payload = {"uuids": target_uuids, "status": "archived", "groups": ["finance", "reviewed"]}

    resp = client.post("/sources/bulk", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert all(item["error"] is None for item in body["results"])

    updated = {source.uuid: source for source in repository.list_sources()}
    for uuid in target_uuids:
        assert updated[uuid].status.value == "archived"
        assert set(updated[uuid].groups) == {"finance", "reviewed"}


def test_bulk_update_reports_missing_items(tmp_path: Path, monkeypatch) -> None:
    seed = seed_mixed_source_indexes(tmp_path)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    client, repository = _build_client(tmp_path)

    unknown = "00000000-0000-0000-0000-000000000000"
    resp = client.post(
        "/sources/bulk",
        json={"uuids": [seed["uuids"]["ready"], unknown], "groups": ["tagged"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2

    results = {item["uuid"]: item for item in body["results"]}
    assert results[unknown]["error"]
    assert results[seed["uuids"]["ready"]]["error"] is None

    refreshed = repository.get(seed["uuids"]["ready"])
    assert refreshed is not None
    assert set(refreshed.groups) == {"tagged"}
