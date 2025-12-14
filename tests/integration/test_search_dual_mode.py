from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app


@pytest.fixture
def client(
    sqlite_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    app = create_app()
    return TestClient(app)


def _csv_bytes(row_count: int = 12) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response"])
    writer.writeheader()
    for index in range(row_count):
        writer.writerow(
            {
                "question": f"test case {index}",
                "response": f"answer {index}",
            }
        )
    return buffer.getvalue().encode("utf-8")


def _ingest_dataset(client: TestClient, display_name: str, rows: int = 12) -> str:
    response = client.post(
        "/datasets/import",
        files=[
            ("upload", ("faq.csv", _csv_bytes(rows), "text/csv")),
            ("display_name", (None, display_name)),
            ("selected_columns", (None, "question")),
            ("selected_columns", (None, "response")),
        ],
    )
    assert response.status_code == 202
    return response.json()["dataset_id"]


def test_dual_mode_pagination_independent(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client, "Pagination Dataset", rows=12)

    first_page = client.get(
        "/search",
        params={
            "q": "test case",
            "min_similarity": 0.0,
            "limitPerMode": 5,
        },
    )
    assert first_page.status_code == 200
    payload = first_page.json()
    assert len(payload["semantic_results"]) == 5
    assert len(payload["lexical_results"]) == 5
    assert payload["pagination"]["semantic"]["offset"] == 0
    assert payload["pagination"]["lexical"]["offset"] == 0
    assert payload["pagination"]["lexical"]["next_offset"] == 5

    next_lexical = client.get(
        "/search",
        params={
            "q": "test case",
            "min_similarity": 0.0,
            "limitPerMode": 5,
            "offsetLexical": 5,
            "offsetSemantic": 0,
        },
    )
    assert next_lexical.status_code == 200
    next_payload = next_lexical.json()
    assert next_payload["pagination"]["lexical"]["offset"] == 5
    assert next_payload["pagination"]["semantic"]["offset"] == 0
    assert all(result["dataset_id"] == dataset_id for result in next_payload["lexical_results"])
    # Semantic results should remain anchored to their own pagination
    assert next_payload["semantic_results"][0]["mode"] == "semantic"
