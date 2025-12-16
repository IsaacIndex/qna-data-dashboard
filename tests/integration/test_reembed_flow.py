from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ingest_sources
from app.services.ingest_storage import default_storage


def build_client(tmp_path: Path) -> TestClient:
    default_storage.storage_root = tmp_path  # type: ignore[attr-defined]
    app = FastAPI()
    app.include_router(ingest_sources.router)
    return TestClient(app)


def _upload(client: TestClient, name: str, content: bytes) -> str:
    resp = client.post(
        "/api/groups/default/sources",
        files={"files": (name, content, "text/csv")},
    )
    assert resp.status_code == 202
    listed = client.get("/api/groups/default/sources").json()
    return listed[-1]["id"]


def test_batch_reembed_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    first = _upload(client, "r1.csv", b"a,b\n1,2\n")
    second = _upload(client, "r2.csv", b"a,b\n3,4\n")
    resp = client.post(
        "/api/groups/default/sources/reembed",
        json={"source_ids": [first, second]},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_ids"][0]
    status = client.get(f"/api/groups/default/embedding-jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] in {"queued", "processing", "completed"}
