from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.db.metadata import MetadataRepository, session_scope
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService
from app.services.preferences import ColumnPreferenceService, PreferenceSnapshot, SelectedColumn


class PreferencesEmbeddingStub:
    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
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


def _write_dataset(path: Path) -> None:
    rows = [
        {
            "question": "How do I reset my password?",
            "response": "Use the password recovery flow.",
            "owner": "Support",
            "stage": "Active",
        },
        {
            "question": "Where do I update MFA settings?",
            "response": "Security page → Settings.",
            "owner": "",
            "stage": "Draft",
        },
    ]
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_preferences_persist_across_sessions_and_reset(
    tmp_path: Path,
    temp_data_root: Path,
    session_factory,
) -> None:
    embedding_service = PreferencesEmbeddingStub()
    dataset_path = tmp_path / "preferences_dataset.csv"
    _write_dataset(dataset_path)

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        ingestion = IngestionService(
            metadata_repository=repo,
            embedding_service=embedding_service,
            data_root=temp_data_root,
        )
        dataset = ingestion.ingest_file(
            source_path=dataset_path,
            display_name="Preferences Dataset",
            options=IngestionOptions(selected_columns=["question", "response"]),
        ).data_file
        dataset_id = dataset.id

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        service = ColumnPreferenceService(repo)
        snapshot = PreferenceSnapshot(
            dataset_id=dataset_id,
            user_id=None,
            selected_columns=[
                SelectedColumn(column_name="owner", display_label="Owner", position=0),
                SelectedColumn(column_name="stage", display_label="Stage", position=1),
            ],
            max_columns=5,
            updated_at=datetime.now(UTC),
        )
        saved = service.save_preference(snapshot)
        assert [column.column_name for column in saved.selected_columns] == ["owner", "stage"]

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        service = ColumnPreferenceService(repo)
        loaded = service.load_preference(dataset_id)
        assert loaded is not None
        assert [column.column_name for column in loaded.selected_columns] == ["owner", "stage"]
        service.reset_preference(dataset_id)

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        service = ColumnPreferenceService(repo)
        assert service.load_preference(dataset_id) is None
