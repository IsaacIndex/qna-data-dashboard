from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Sequence
import warnings

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from pydantic._internal._generate_schema import UnsupportedFieldAttributeWarning

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
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub-model", model_dimension=1)

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


def test_catalog_lists_available_columns(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client)

    response = client.get("/preferences/columns/catalog", params={"datasetId": dataset_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["datasetId"] == dataset_id
    columns = payload["columns"]
    names = {column["columnName"] for column in columns}
    assert {"question", "response", "notes"} <= names


def test_save_and_fetch_preference(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client)

    save_response = client.put(
        "/preferences/columns",
        json={
            "datasetId": dataset_id,
            "selectedColumns": [
                {"columnName": "question", "displayLabel": "Question", "position": 0},
                {"columnName": "response", "displayLabel": "Response", "position": 1},
            ],
            "maxColumns": 5,
        },
    )
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["datasetId"] == dataset_id
    assert saved["selectedColumns"][0]["columnName"] == "question"
    assert saved["selectedColumns"][1]["columnName"] == "response"

    fetch_response = client.get(
        "/preferences/columns",
        params={"datasetId": dataset_id},
    )
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["datasetId"] == dataset_id
    assert [item["columnName"] for item in fetched["selectedColumns"]] == ["question", "response"]


def test_save_rejects_unknown_columns(client: TestClient) -> None:
    dataset_id = _ingest_dataset(client)

    save_response = client.put(
        "/preferences/columns",
        json={
            "datasetId": dataset_id,
            "selectedColumns": [
                {"columnName": "question", "displayLabel": "Question", "position": 0},
                {"columnName": "nonexistent", "displayLabel": "Missing", "position": 1},
            ],
        },
    )
    assert save_response.status_code == 400
    payload = save_response.json()
    assert payload["detail"]
