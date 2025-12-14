from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

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
        return EmbeddingSummary(
            vector_count=len(job.records), model_name="stub-model", model_dimension=1
        )

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


def _csv_bytes(suffix: str = "") -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response"])
    writer.writeheader()
    writer.writerow(
        {
            "question": f"How to reset password?{suffix}",
            "response": f"Use account recovery flow.{suffix}",
        }
    )
    writer.writerow(
        {
            "question": f"Where can I download invoices?{suffix}",
            "response": f"Invoices live on the billing portal.{suffix}",
        }
    )
    return buffer.getvalue().encode("utf-8")


def _ingest_dataset(client: TestClient, display_name: str, *, suffix: str = "") -> str:
    response = client.post(
        "/datasets/import",
        files=[
            ("upload", ("faq.csv", _csv_bytes(suffix), "text/csv")),
            ("display_name", (None, display_name)),
            ("selected_columns", (None, "question")),
            ("selected_columns", (None, "response")),
        ],
    )
    assert response.status_code == 202
    return response.json()["dataset_id"]


def test_search_returns_ranked_results(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client, "FAQ Dataset")

    response = client.get("/search", params={"q": "reset password", "limitPerMode": 2})
    assert response.status_code == 200
    payload = response.json()
    semantic = payload["semantic_results"]
    lexical = payload["lexical_results"]
    assert semantic, "Expected semantic results"
    assert lexical, "Expected lexical results"

    assert len(semantic) <= 2
    assert len(lexical) <= 2
    for entry in semantic + lexical:
        assert entry["dataset_id"] == dataset_id
        assert entry["record_id"]
        assert entry["column_name"] in {"question", "response"}
        assert entry["similarity"] >= 0.0
        assert entry["text"]
        assert entry["mode"] in {"semantic", "lexical"}

    pagination = payload["pagination"]
    assert pagination["semantic"]["limit"] == 2
    assert pagination["lexical"]["limit"] == 2


def test_search_honors_filters(client: TestClient) -> None:
    dataset_a = _ingest_dataset(client, "FAQ Dataset A")
    dataset_b = _ingest_dataset(client, "FAQ Dataset B", suffix="B")

    filtered = client.get(
        "/search",
        params={
            "q": "reset password",
            "dataset_ids": dataset_a,
            "column_names": "question",
            "limitPerMode": 5,
        },
    )
    assert filtered.status_code == 200
    body = filtered.json()
    for result in body["semantic_results"] + body["lexical_results"]:
        assert result["dataset_id"] == dataset_a
        assert result["column_name"] == "question"

    high_threshold = client.get(
        "/search",
        params={
            "q": "reset password",
            "dataset_ids": dataset_b,
            "min_similarity": 0.99,
            "limitPerMode": 5,
        },
    )
    assert high_threshold.status_code == 200
    assert high_threshold.json()["semantic_results"] == []
    assert high_threshold.json()["lexical_results"] == []
