from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import group_preferences
from app.services.ingest_storage import default_storage


def build_client(tmp_path) -> TestClient:
    default_storage.storage_root = tmp_path  # type: ignore[attr-defined]
    app = FastAPI()
    app.include_router(group_preferences.router)
    return TestClient(app)


def test_save_and_load_preferences(tmp_path) -> None:
    client = build_client(tmp_path)
    save = client.put(
        "/api/groups/pref-group/preferences",
        json={"selected_columns": ["a", "b"], "contextual_fields": ["ctx"]},
    )
    assert save.status_code == 200
    loaded = client.get("/api/groups/pref-group/preferences")
    assert loaded.status_code == 200
    body = loaded.json()
    assert body["selected_columns"] == ["a", "b"]
    assert body["contextual_fields"] == ["ctx"]
