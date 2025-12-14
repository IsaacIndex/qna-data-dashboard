from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary


class FlakyEmbeddingStub:
    def __init__(self) -> None:
        self.available = False

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        # Ingestion should continue to work even when query-time availability is toggled.
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
        if not self.available:
            raise RuntimeError("Embeddings temporarily unavailable")
        vectors = [[float(len(text))] for text in texts]
        return vectors, 1, "stub-model"


@pytest.fixture
def flaky_stub() -> FlakyEmbeddingStub:
    return FlakyEmbeddingStub()


@pytest.fixture
def client(
    sqlite_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flaky_stub: FlakyEmbeddingStub,
) -> TestClient:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    app = create_app(embedding_service=flaky_stub)
    return TestClient(app)


def _csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response"])
    writer.writeheader()
    writer.writerow({"question": "Reset password workflow", "response": "Reset password workflow"})
    writer.writerow(
        {"question": "Reset billing integration", "response": "Reset billing integration"}
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


def test_semantic_fallback_and_recovery(client: TestClient, flaky_stub: FlakyEmbeddingStub) -> None:
    _ingest_dataset(client, "Fallback Dataset")

    first = client.get(
        "/search",
        params={"q": "reset", "min_similarity": 0.0, "limitPerMode": 5},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["lexical_results"], "Lexical results should still be returned during fallback"
    assert payload["semantic_results"] == []
    fallback = payload["fallback"]
    assert fallback["semantic_available"] is False
    assert "unavailable" in (fallback["message"] or "").lower()

    flaky_stub.available = True

    recovered = client.get(
        "/search",
        params={"q": "reset", "min_similarity": 0.0, "limitPerMode": 5},
    )
    assert recovered.status_code == 200
    recovered_payload = recovered.json()
    assert recovered_payload[
        "semantic_results"
    ], "Semantic results should resume once embeddings recover"
    assert recovered_payload["fallback"]["semantic_available"] is True
