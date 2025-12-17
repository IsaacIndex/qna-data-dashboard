from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.ingest import router as ingest_router
from app.api.routes.legacy import router as legacy_router
from app.api.routes.reembed import router as reembed_router


def test_ingest_router_exposes_stub_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    app = FastAPI()
    app.include_router(ingest_router)
    app.include_router(reembed_router)
    app.include_router(legacy_router)
    client = TestClient(app)

    resp_list = client.get("/sources")
    assert resp_list.status_code == 200
    assert resp_list.json()["items"] == []
    assert resp_list.json()["next_cursor"] is None

    resp_reembed = client.post("/sources/reembed", json={"uuid": "123"})
    assert resp_reembed.status_code == 404

    resp_reconcile = client.post("/sources/reconcile-legacy", json={})
    assert resp_reconcile.status_code == 200
    assert resp_reconcile.json()["reinserted"] == []
    assert resp_reconcile.json()["conflicts"] == []
