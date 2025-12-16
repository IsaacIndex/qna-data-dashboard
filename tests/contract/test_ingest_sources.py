from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ingest_sources


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ingest_sources.router)
    return TestClient(app)


def test_upload_list_delete_sources(tmp_path: Path) -> None:
    client = build_client()
    fixture = Path("tests/fixtures/ingest/sample.csv")
    with fixture.open("rb") as handle:
        resp = client.post(
            "/api/groups/default/sources",
            files={"files": ("sample.csv", handle, "text/csv")},
        )
    assert resp.status_code == 202, resp.text
    sources = resp.json()
    assert sources and sources[0]["version_label"].startswith("sample")

    list_resp = client.get("/api/groups/default/sources")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert len(listed) >= 1

    source_id = listed[0]["id"]
    delete_resp = client.delete(f"/api/groups/default/sources/{source_id}")
    assert delete_resp.status_code == 200
