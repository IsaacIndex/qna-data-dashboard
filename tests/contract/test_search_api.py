from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Sequence

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary


class ApiEmbeddingStub:
    def __init__(self) -> None:
        self.run_count = 0

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        self.run_count += 1
        for idx, record in enumerate(job.records):
            job.metadata_repository.upsert_embedding(
                record_id=record.id,
                model_name="stub-model",
                model_version="test",
                vector_path=f"{job.data_file.id}-{idx}",
                embedding_dim=1,
            )
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub-model", model_dimension=1)

    def embed_texts(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        vectors = [[float(len(text))] for text in texts]
        return vectors, 1, "stub-model"


@pytest.fixture
def client(
    sqlite_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    app = create_app(embedding_service=ApiEmbeddingStub())
    return TestClient(app)


def _csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response"])
    writer.writeheader()
    writer.writerow(
        {
            "question": "How to reset password?",
            "response": "Use account recovery flow.",
        }
    )
    writer.writerow(
        {
            "question": "Where can I download invoices?",
            "response": "Invoices live on the billing portal.",
        }
    )
    return buffer.getvalue().encode("utf-8")


def _ingest_dataset(client: TestClient, display_name: str) -> str:
    response = client.post(
        "/datasets/import",
        files=[
            ("upload", ("faq.csv", _csv_bytes(), "text/csv")),
            ("display_name", (None, display_name)),
            ("selected_columns", (None, "question")),
            ("selected_columns", (None, "response")),
        ],
    )
    assert response.status_code == 202
    return response.json()["dataset_id"]


def test_search_returns_ranked_results(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client, "FAQ Dataset")

    response = client.get("/search", params={"q": "reset password"})
    assert response.status_code == 200
    payload = response.json()
    assert "results" in payload
    assert payload["results"], "Expected at least one search result"

    first = payload["results"][0]
    assert first["dataset_id"] == dataset_id
    assert first["record_id"]
    assert first["column_name"] in {"question", "response"}
    assert first["similarity"] >= 0.0
    assert first["text"]


def test_search_honors_filters(client: TestClient) -> None:
    dataset_a = _ingest_dataset(client, "FAQ Dataset A")
    dataset_b = _ingest_dataset(client, "FAQ Dataset B")

    filtered = client.get(
        "/search",
        params={
            "q": "reset password",
            "dataset_ids": dataset_a,
            "column_names": "question",
        },
    )
    assert filtered.status_code == 200
    results = filtered.json()["results"]
    assert results, "Expected filtered results"
    assert all(result["dataset_id"] == dataset_a for result in results)
    assert all(result["column_name"] == "question" for result in results)

    high_threshold = client.get(
        "/search",
        params={
            "q": "reset password",
            "dataset_ids": dataset_b,
            "min_similarity": 0.99,
        },
    )
    assert high_threshold.status_code == 200
    assert high_threshold.json()["results"] == []
