from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ingest_sources


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ingest_sources.router)
    return TestClient(app)


def test_empty_group_returns_empty_list() -> None:
    client = build_client()
    resp = client.get("/api/groups/empty-group/sources")
    assert resp.status_code == 200
    assert resp.json() == []
