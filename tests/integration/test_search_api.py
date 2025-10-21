from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

import pytest

from app.db.metadata import MetadataRepository
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService
from app.services.search import SearchService


class SearchEmbeddingStub:
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


def _write_csv(path: Path, *, first: str, second: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "response"])
        writer.writeheader()
        writer.writerow({"question": first, "response": f"Details about {first.lower()}"})
        writer.writerow({"question": second, "response": f"Details about {second.lower()}"})


def test_search_service_filters_and_thresholds(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    chroma_client,
) -> None:
    embedding_service = SearchEmbeddingStub()
    ingestion = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        data_root=temp_data_root,
    )

    dataset_a_path = tmp_path / "dataset_a.csv"
    _write_csv(
        dataset_a_path,
        first="Reset password workflow",
        second="Download invoices instructions",
    )
    dataset_a = ingestion.ingest_file(
        source_path=dataset_a_path,
        display_name="Dataset A",
        options=IngestionOptions(selected_columns=["question", "response"]),
    ).data_file

    dataset_b_path = tmp_path / "dataset_b.csv"
    _write_csv(
        dataset_b_path,
        first="Update billing address",
        second="Change payment method",
    )
    dataset_b = ingestion.ingest_file(
        source_path=dataset_b_path,
        display_name="Dataset B",
        options=IngestionOptions(selected_columns=["question"]),
    ).data_file

    service = SearchService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        chroma_client=chroma_client,
    )

    results = service.search(query="reset password workflow")
    assert results, "Expected search results for similar content"
    assert all(result.dataset_id in {dataset_a.id, dataset_b.id} for result in results)

    filtered = service.search(query="reset password workflow", dataset_ids=[dataset_a.id], column_names=["question"])
    assert filtered, "Expected filtered results"
    assert all(result.dataset_id == dataset_a.id for result in filtered)
    assert all(result.column_name == "question" for result in filtered)

    strict = service.search(query="reset password workflow", dataset_ids=[dataset_b.id], min_similarity=0.95)
    assert strict == [], "Unrelated dataset should not meet high similarity threshold"
