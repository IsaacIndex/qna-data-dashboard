from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary


class ContextualEmbeddingStub:
    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
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
    app = create_app(embedding_service=ContextualEmbeddingStub())
    return TestClient(app)


def _csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response", "owner", "stage"])
    writer.writeheader()
    writer.writerow(
        {
            "question": "Reset password workflow",
            "response": "Visit the security page and request a password reset link.",
            "owner": "Support Ops",
            "stage": "Active",
        }
    )
    writer.writerow(
        {
            "question": "Reset security preferences",
            "response": "Adjust MFA settings inside the privacy section.",
            "owner": "",
            "stage": "Draft",
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
            ("selected_columns", (None, "owner")),
            ("selected_columns", (None, "stage")),
        ],
    )
    assert response.status_code == 202
    return response.json()["dataset_id"]


def _save_preferences(client: TestClient, dataset_id: str) -> None:
    response = client.put(
        "/preferences/columns",
        json={
            "datasetId": dataset_id,
            "selectedColumns": [
                {"columnName": "owner", "displayLabel": "Owner", "position": 0},
                {"columnName": "stage", "displayLabel": "Stage", "position": 1},
            ],
            "maxColumns": 10,
            "userId": None,
        },
    )
    assert response.status_code == 200


def test_contextual_columns_propagate_across_modes(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client, "Context Dataset")
    _save_preferences(client, dataset_id)

    response = client.get(
        "/search",
        params={
            "q": "reset",
            "min_similarity": 0.0,
            "limitPerMode": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    semantic = payload.get("semantic_results", [])
    lexical = payload.get("lexical_results", [])
    assert semantic, "Expected semantic results to be present"
    assert lexical, "Expected lexical results to be present"

    for result in semantic + lexical:
        assert result["dataset_id"] == dataset_id
        columns = result["contextual_columns"]
        assert set(columns.keys()) >= {"owner", "stage"}
        labels = result["metadata"].get("contextual_labels", {})
        assert labels.get("owner") == "Owner"
        assert labels.get("stage") == "Stage"

    semantic_missing = {item["row_index"]: item["missing_columns"] for item in semantic}
    lexical_missing = {item["row_index"]: item["missing_columns"] for item in lexical}
    assert 1 in semantic_missing and 1 in lexical_missing
    assert "owner" in semantic_missing[1] and "owner" in lexical_missing[1]
