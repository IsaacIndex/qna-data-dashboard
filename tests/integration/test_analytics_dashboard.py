from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.metadata import MetadataRepository
from app.db.schema import ClusterMembership, SimilarityCluster
from app.services.analytics import AnalyticsService
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService


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
        return EmbeddingSummary(
            vector_count=len(job.records), model_name="stub-model", model_dimension=1
        )

    def embed_texts(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        vectors = [[float(len(text))] for text in texts]
        return vectors, 1, "stub-model"


def _write_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "response"])
        writer.writeheader()
        writer.writerow(
            {"question": "Reset password workflow", "response": "Steps to reset passwords"}
        )
        writer.writerow(
            {"question": "Download invoices", "response": "Download from billing portal"}
        )


def test_analytics_service_persists_clusters(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    db_session: Session,
) -> None:
    embedding_service = AnalyticsEmbeddingStub()
    ingestion = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        data_root=temp_data_root,
    )

    dataset_path = tmp_path / "dataset.csv"
    _write_csv(dataset_path)
    dataset = ingestion.ingest_file(
        source_path=dataset_path,
        display_name="Dataset",
        options=IngestionOptions(selected_columns=["question", "response"]),
    ).data_file

    service = AnalyticsService(metadata_repository=metadata_repository)

    clusters = service.build_clusters(dataset_ids=[dataset.id])
    assert clusters, "Expected clusters to be generated"
    assert all(dataset.id in cluster.dataset_scope for cluster in clusters)

    persisted_clusters = db_session.query(SimilarityCluster).all()
    assert persisted_clusters, "Clusters should be persisted to the database"
    member_rows = db_session.query(ClusterMembership).all()
    assert member_rows, "Cluster memberships should be persisted"

    summary = service.summarize_coverage(dataset_ids=[dataset.id])
    assert summary.total_queries >= 2
    assert summary.unique_topics_estimate == len(clusters)
    assert 0 <= summary.redundancy_ratio <= 1
