from __future__ import annotations

import csv
import io
import warnings
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic._internal._generate_schema import UnsupportedFieldAttributeWarning

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary

warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)


class ApiEmbeddingStub:
    def __init__(self) -> None:
        self.run_count = 0

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        self.run_count += 1
        for index, record in enumerate(job.records):
            job.metadata_repository.upsert_embedding(
                record_id=record.id,
                model_name="stub-model",
                model_version="test",
                vector_path=f"{job.data_file.id}-{index}",
                embedding_dim=1,
            )
        return EmbeddingSummary(
            vector_count=len(job.records), model_name="stub-model", model_dimension=1
        )

    def embed_texts(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        vectors = [[float(len(text))] for text in texts]
        return vectors, 1, "stub-model"


def _csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["question", "response", "notes"])
    writer.writeheader()
    writer.writerow(
        {
            "question": "How to reset password?",
            "response": "Use account recovery flow.",
            "notes": "Common support topic",
        }
    )
    writer.writerow(
        {
            "question": "Where can I download invoices?",
            "response": "Invoices live on the billing portal.",
            "notes": "Direct customers to billing portal",
        }
    )
    return buffer.getvalue().encode("utf-8")


@pytest.fixture
def client(
    sqlite_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    app = create_app(embedding_service=ApiEmbeddingStub())
    return TestClient(app)


def _ingest_dataset(client: TestClient) -> str:
    response = client.post(
        "/datasets/import",
        files=[
            ("upload", ("faq.csv", _csv_bytes(), "text/csv")),
            ("display_name", (None, "Preferences Dataset")),
            ("selected_columns", (None, "question")),
            ("selected_columns", (None, "response")),
            ("selected_columns", (None, "notes")),
        ],
    )
    assert response.status_code == 202
    return response.json()["dataset_id"]


def test_mirror_round_trip_accepts_snapshot(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client)
    payload = {
        "datasetId": dataset_id,
        "deviceId": "device-1",
        "version": 3,
        "selectedColumns": [
            {"name": "question", "displayLabel": "Question", "position": 0},
            {"name": "response", "displayLabel": "Response", "position": 1},
        ],
        "maxColumns": 4,
        "source": "localStorage",
    }

    post_response = client.post("/preferences/columns/mirror", json=payload)
    assert post_response.status_code == 202
    mirrored = post_response.json()
    assert mirrored["datasetId"] == dataset_id
    assert mirrored["deviceId"] == "device-1"
    assert mirrored["version"] == 3
    assert [entry["name"] for entry in mirrored["selectedColumns"]] == ["question", "response"]
    assert mirrored["maxColumns"] == 4

    get_response = client.get(
        "/preferences/columns/mirror",
        params={"datasetId": dataset_id, "deviceId": "device-1"},
    )
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert [entry["name"] for entry in fetched["selectedColumns"]] == ["question", "response"]
    assert fetched["version"] == 3


def test_mirror_get_returns_empty_response_when_missing(client: TestClient) -> None:
    response = client.get("/preferences/columns/mirror", params={"datasetId": "missing"})
    assert response.status_code == 204
