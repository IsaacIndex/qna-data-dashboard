from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from app.db.metadata import MetadataRepository
from app.db.schema import ColumnPreference
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService
from app.services.search import SearchService


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
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub-model", model_dimension=1)

    def embed_texts(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        vectors = [[float(len(text))] for text in texts]
        return vectors, 1, "stub-model"


def _write_dataset_a(path: Path) -> None:
    rows = [
        {
            "question": "Reset password workflow",
            "response": "Visit the security page and request a password reset link.",
            "owner": "Support Ops",
            "stage": "Active",
        },
        {
            "question": "Reset security preferences",
            "response": "Adjust MFA settings inside the privacy section.",
            "owner": "",
            "stage": "Draft",
        },
    ]
    _write_csv(path, rows)


def _write_dataset_b(path: Path) -> None:
    rows = [
        {
            "question": "Reset billing integration",
            "response": "Roll back to the last known good configuration.",
            "region": "EU",
            "status": "",
        },
    ]
    _write_csv(path, rows)


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _save_preference(
    repo: MetadataRepository,
    *,
    dataset_id: str,
    selected: Sequence[tuple[str, str]],
    max_columns: int = 10,
) -> ColumnPreference:
    payload = [
        {"column_name": column, "display_label": label, "position": index}
        for index, (column, label) in enumerate(selected)
    ]
    preference = ColumnPreference(
        data_file_id=dataset_id,
        user_id=None,
        selected_columns=payload,
        max_columns=max_columns,
        is_active=True,
    )
    repo.session.add(preference)
    repo.session.commit()
    return preference


def test_search_results_include_contextual_columns(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    chroma_client,
) -> None:
    embedding_service = ContextualEmbeddingStub()
    ingestion = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        data_root=temp_data_root,
    )

    dataset_a_path = tmp_path / "dataset_a.csv"
    _write_dataset_a(dataset_a_path)
    dataset_a = ingestion.ingest_file(
        source_path=dataset_a_path,
        display_name="Dataset A",
        options=IngestionOptions(selected_columns=["question", "response"]),
    ).data_file

    dataset_b_path = tmp_path / "dataset_b.csv"
    _write_dataset_b(dataset_b_path)
    dataset_b = ingestion.ingest_file(
        source_path=dataset_b_path,
        display_name="Dataset B",
        options=IngestionOptions(selected_columns=["question"]),
    ).data_file

    _save_preference(
        metadata_repository,
        dataset_id=dataset_a.id,
        selected=[("owner", "Owner"), ("stage", "Stage")],
    )
    _save_preference(
        metadata_repository,
        dataset_id=dataset_b.id,
        selected=[("region", "Region"), ("status", "Status")],
    )

    service = SearchService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        chroma_client=chroma_client,
    )

    results = service.search(query="reset", limit=10, min_similarity=0.3)
    assert results, "Expected search results with contextual columns"

    grouped: dict[str, list] = defaultdict(list)
    for result in results:
        grouped[result.dataset_id].append(result)

    assert dataset_a.id in grouped and dataset_b.id in grouped

    dataset_a_rows = {item.row_index: item for item in grouped[dataset_a.id]}
    assert dataset_a_rows[0].contextual_columns == {"owner": "Support Ops", "stage": "Active"}
    assert dataset_a_rows[0].missing_columns == []

    # Missing owner should be captured while stage remains populated
    assert dataset_a_rows[1].contextual_columns.get("owner") in ("", None)
    assert "owner" in dataset_a_rows[1].missing_columns
    assert dataset_a_rows[1].contextual_columns.get("stage") == "Draft"

    dataset_b_rows = grouped[dataset_b.id]
    assert dataset_b_rows[0].contextual_columns["region"] == "EU"
    assert dataset_b_rows[0].contextual_columns.get("status") in ("", None)
    assert "status" in dataset_b_rows[0].missing_columns
