from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ingest_sources
from app.services.ingest_storage import default_storage


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ingest_sources.router)
    return TestClient(app)


def _ensure_source(client: TestClient) -> str:
    fixture = Path("tests/fixtures/ingest/sample.csv")
    with fixture.open("rb") as handle:
        resp = client.post(
            "/api/groups/default/sources",
            files={"files": ("sample.csv", handle, "text/csv")},
        )
    assert resp.status_code == 202
    listed = client.get("/api/groups/default/sources").json()
    return listed[0]["id"]


def test_reembed_queue_and_status(tmp_path: Path) -> None:
    # isolate storage root for this test
    default_storage.storage_root = tmp_path  # type: ignore[attr-defined]
    client = build_client()
    source_id = _ensure_source(client)
    resp = client.post(
        "/api/groups/default/sources/reembed",
        json={"source_ids": [source_id]},
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_ids"][0]

    status_resp = client.get(f"/api/groups/default/embedding-jobs/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] in {"processing", "completed", "queued"}
