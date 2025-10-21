from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Sequence

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary


class AnalyticsEmbeddingStub:
    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
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
    app = create_app(embedding_service=AnalyticsEmbeddingStub())
    return TestClient(app)


def _csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response"])
    writer.writeheader()
    writer.writerow({"question": "Reset password workflow", "response": "Steps to reset passwords"})
    writer.writerow({"question": "Download invoices", "response": "Download from billing portal"})
    return buffer.getvalue().encode("utf-8")


@pytest.fixture
def dataset_id(client: TestClient) -> str:
    response = client.post(
        "/datasets/import",
        files=[
            ("upload", ("faq.csv", _csv_bytes(), "text/csv")),
            ("display_name", (None, "FAQ Dataset")),
            ("selected_columns", (None, "question")),
            ("selected_columns", (None, "response")),
        ],
    )
    assert response.status_code == 202
    return response.json()["dataset_id"]


def test_analytics_clusters_contract(client: TestClient, dataset_id: str) -> None:
    response = client.get("/analytics/clusters", params={"dataset_ids": dataset_id})
    assert response.status_code == 200
    payload = response.json()
    assert "clusters" in payload
    clusters = payload["clusters"]
    assert clusters, "Expected analytics clusters to be returned"
    first = clusters[0]
    assert first["cluster_id"]
    assert dataset_id in first["dataset_scope"]
    assert 0 <= first["diversity_score"] <= 1
    assert first["member_count"] > 0


def test_analytics_summary_contract(client: TestClient, dataset_id: str) -> None:
    response = client.get("/analytics/summary", params={"dataset_ids": dataset_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_ids"] == [dataset_id]
    assert payload["total_queries"] >= 2
    assert 0 <= payload["redundancy_ratio"] <= 1
    assert "last_refreshed_at" in payload
