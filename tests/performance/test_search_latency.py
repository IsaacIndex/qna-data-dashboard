from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

import pytest

pytest.importorskip("pytest_benchmark", reason="pytest-benchmark plugin not available")

from app.db.metadata import MetadataRepository
from app.db.schema import ColumnPreference, MetricType, PerformanceMetric
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService
from app.services.search import SearchService


class BenchmarkEmbeddingStub:
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


def _write_csv(path: Path, rows: int = 1000, extra_columns: int = 0) -> None:
    fieldnames = ["question"] + [f"context_{index}" for index in range(extra_columns)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(rows):
            row = {"question": f"How to reset password #{index}?"}
            for column_index in range(extra_columns):
                row[f"context_{column_index}"] = f"value_{column_index}_{index}"
            writer.writerow(row)


def _save_preference(repo: MetadataRepository, dataset_id: str, *, column_count: int) -> None:
    selected_columns = [
        {"column_name": f"context_{index}", "display_label": f"Context {index}", "position": index}
        for index in range(column_count)
    ]
    preference = ColumnPreference(
        data_file_id=dataset_id,
        user_id=None,
        selected_columns=selected_columns,
        max_columns=column_count,
        is_active=True,
    )
    repo.session.add(preference)
    repo.session.commit()


@pytest.mark.benchmark(group="search")
def test_search_latency_under_budget(
    benchmark,
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    chroma_client,
    db_session,
) -> None:
    embedding_service = BenchmarkEmbeddingStub()
    ingestion = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        data_root=temp_data_root,
    )

    dataset_path = tmp_path / "search.csv"
    _write_csv(dataset_path, rows=1500, extra_columns=10)
    dataset = ingestion.ingest_file(
        source_path=dataset_path,
        display_name="Benchmark Dataset",
        options=IngestionOptions(selected_columns=["question"]),
    ).data_file
    _save_preference(metadata_repository, dataset_id=dataset.id, column_count=10)

    service = SearchService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        chroma_client=chroma_client,
    )

    def run_search():
        return service.search(query="reset password", dataset_ids=[dataset.id])

    results = benchmark(run_search)
    assert results, "Expected search results from benchmark run"
    assert all(len(result.contextual_columns) == 10 for result in results)

    metric = (
        db_session.query(PerformanceMetric)
        .filter(PerformanceMetric.metric_type == MetricType.SEARCH)
        .order_by(PerformanceMetric.recorded_at.desc())
        .first()
    )
    assert metric is not None, "Search service should record performance metrics"
    assert metric.p95_ms <= 1000.0
