from __future__ import annotations

import csv
import io
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
    writer = csv.DictWriter(buffer, fieldnames=["question", "column_b"])
    writer.writeheader()
    writer.writerow(
        {
            "question": "How to reset password?",
            "column_b": "Reset instructions",
        }
    )
    writer.writerow(
        {
            "question": "Where are invoices?",
            "column_b": "Billing portal",
        }
    )
    return buffer.getvalue().encode("utf-8")


def test_import_dataset_contract_flow(client: TestClient) -> None:
    response = client.post(
        "/datasets/import",
        files={
            "upload": ("faq.csv", _csv_bytes(), "text/csv"),
            "display_name": (None, "FAQ Dataset"),
            "selected_columns": (None, "question"),
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert "dataset_id" in payload
    assert payload["ingestion_status"] in {"pending", "processing", "ready"}

    datasets_resp = client.get("/datasets")
    assert datasets_resp.status_code == 200
    datasets = datasets_resp.json()["datasets"]
    assert any(ds["display_name"] == "FAQ Dataset" for ds in datasets)

    dataset_id = payload["dataset_id"]
    audit_resp = client.get(f"/datasets/{dataset_id}/audits/latest")
    assert audit_resp.status_code == 200
    audit_payload = audit_resp.json()
    assert audit_payload["dataset_id"] == dataset_id
