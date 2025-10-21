from __future__ import annotations

import csv
from pathlib import Path
import pytest

from app.db.metadata import MetadataRepository
from app.db.schema import EmbeddingVector, IngestionStatus
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService


class ChromaEmbeddingStub:
    def __init__(self, chroma_client) -> None:
        self.client = chroma_client
        self.latest_collection = None
        self.call_count = 0

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        collection = self.client.get_or_create_collection(name=f"dataset_{job.data_file.id}")
        self.latest_collection = collection
        self.call_count += 1
        texts = [record.text for record in job.records]
        vectors = [[float(len(text))] for text in texts]
        collection.add(
            ids=[f"{job.data_file.id}-{idx}" for idx in range(len(texts))],
            documents=list(texts),
            embeddings=vectors,
        )
        for idx, record in enumerate(job.records):
            job.metadata_repository.upsert_embedding(
                record_id=record.id,
                model_name="stub-model",
                model_version="test",
                vector_path=f"{job.data_file.id}-{idx}",
                embedding_dim=1,
            )
        return EmbeddingSummary(vector_count=len(texts), model_name="stub-model", model_dimension=1)


def _write_csv(path: Path) -> None:
    rows = [
        {"question": "Reset password", "response": "Use reset flow"},
        {"question": "Find invoices", "response": "Check billing tab"},
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "response"])
        writer.writeheader()
        writer.writerows(rows)


def test_ingestion_pipeline_persists_embeddings_before_search(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    chroma_client,
    db_session,
) -> None:
    source = tmp_path / "dataset.csv"
    _write_csv(source)
    orchestrator = ChromaEmbeddingStub(chroma_client)
    service = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=orchestrator,
        data_root=temp_data_root,
    )

    result = service.ingest_file(
        source_path=source,
        display_name="Integration Dataset",
        options=IngestionOptions(selected_columns=["question"]),
    )

    assert result.data_file.ingestion_status == IngestionStatus.READY
    assert orchestrator.call_count == 1
    assert orchestrator.latest_collection is not None
    assert orchestrator.latest_collection.count() == 2

    vectors = db_session.query(EmbeddingVector).all()
    assert len(vectors) == 2, "Embedding metadata should be persisted for search services"
