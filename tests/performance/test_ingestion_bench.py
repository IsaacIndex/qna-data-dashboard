from __future__ import annotations

import csv
from pathlib import Path

import pytest

pytest.importorskip("pytest_benchmark", reason="pytest-benchmark plugin not available")

from app.db.metadata import MetadataRepository
from app.db.schema import PerformanceMetric
from app.services.ingestion import IngestionOptions, IngestionService


from app.services.embeddings import EmbeddingJob, EmbeddingSummary


class NoOpEmbeddingService:
    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        # Simulate minimal embedding overhead for benchmark focus.
        return EmbeddingSummary(vector_count=len(job.records), model_name="noop", model_dimension=1)


def _write_csv(path: Path, rows: int = 1000) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query", "column_b"])
        writer.writeheader()
        for i in range(rows):
            writer.writerow({"query": f"Query #{i}", "column_b": f"Aux #{i}"})


@pytest.mark.benchmark(group="ingestion")
def test_ingestion_benchmark_under_budget(
    benchmark,
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    db_session,
) -> None:
    source = tmp_path / "bench.csv"
    _write_csv(source, rows=2000)
    service = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=NoOpEmbeddingService(),
        data_root=temp_data_root,
    )

    def run_ingestion():
        return service.ingest_file(
            source_path=source,
            display_name="Benchmark Dataset",
            options=IngestionOptions(selected_columns=["query"]),
        )

    result = benchmark(run_ingestion)
    assert result.data_file.row_count == 2000

    metric = db_session.query(PerformanceMetric).order_by(PerformanceMetric.recorded_at.desc()).first()
    assert metric is not None
    assert metric.p95_ms <= 300_000
