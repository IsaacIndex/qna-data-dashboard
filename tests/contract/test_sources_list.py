from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import ingest as ingest_routes
from app.services.source_repository import SourceRepository
from tests.fixtures.sources_mixed import seed_mixed_source_indexes


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ingest_routes.router)
    return TestClient(app)


def test_get_sources_supports_filters_sort_and_cursor(tmp_path: Path, monkeypatch) -> None:
    seed = seed_mixed_source_indexes(tmp_path)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    expected = sorted([source.label for source in SourceRepository(data_root=tmp_path).list_sources()])

    client = build_client()

    collected: list[str] = []
    cursor = None
    for _ in range(3):  # should converge well before this
        resp = client.get("/sources", params={"cursor": cursor, "limit": 2, "sort": "label"})
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        collected.extend(item["label"] for item in payload["items"])
        cursor = payload["next_cursor"]
        if cursor is None:
            break
    assert sorted(collected) == expected

    ready = client.get("/sources", params={"status": "ready"})
    assert ready.status_code == 200, ready.text
    assert {item["status"] for item in ready.json()["items"]} == {"ready"}

    embedded = client.get("/sources", params={"type": "embedding"})
    assert embedded.status_code == 200, embedded.text
    assert {item["type"] for item in embedded.json()["items"]} == {"embedding"}

    sales_only = client.get("/sources", params={"dataset": "sales"})
    assert sales_only.status_code == 200, sales_only.text
    assert {item["dataset"] for item in sales_only.json()["items"]} == {"sales"}

    with_groups = client.get("/sources", params={"group": "shared"})
    assert with_groups.status_code == 200, with_groups.text
    assert all("shared" in item.get("groups", []) for item in with_groups.json()["items"])

    everything = client.get("/sources", params={"limit": 50, "sort": "label"})
    assert any(item["legacy"] for item in everything.json()["items"])
    assert set(item["label"] for item in everything.json()["items"]) == set(seed["labels"])
