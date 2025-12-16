from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import group_preferences, ingest_sources


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ingest_sources.router)
    app.include_router(group_preferences.router)
    return TestClient(app)


def test_group_preferences_persist() -> None:
    client = build_client()
    save = client.put(
        "/api/groups/group-a/preferences",
        json={"selected_columns": ["c1", "c2"], "contextual_fields": ["ctx"]},
    )
    assert save.status_code == 200
    loaded = client.get("/api/groups/group-a/preferences")
    assert loaded.status_code == 200
    body = loaded.json()
    assert body["selected_columns"] == ["c1", "c2"]
    assert body["contextual_fields"] == ["ctx"]
