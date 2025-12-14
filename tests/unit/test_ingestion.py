from __future__ import annotations

import csv
from pathlib import Path

import pytest

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover - optional path
    Workbook = None

from app.db.metadata import MetadataRepository
from app.db.schema import IngestionStatus
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import IngestionOptions, IngestionService


class DummyEmbeddingService:
    def __init__(self) -> None:
        self.jobs: list[EmbeddingJob] = []

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        self.jobs.append(job)
        texts: list[str] = [record.text for record in job.records]
        return EmbeddingSummary(vector_count=len(texts), model_name="dummy", model_dimension=1)


def _write_csv(path: Path) -> None:
    rows = [
        {"question": "How to reset password?", "response": "Use the reset link.", "notes": 1},
        {"question": "Where to find invoices?", "response": "Navigate to billing.", "notes": 2},
        {"question": "", "response": "", "notes": 3},
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "response", "notes"])
        writer.writeheader()
        writer.writerows(rows)


if Workbook is not None:

    def _write_excel(path: Path, sheet_name: str = "Sheet1") -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = sheet_name
        worksheet.append(["prompt", "category"])
        worksheet.append(["Draft refund email", "support"])
        worksheet.append(["Clarify warranty coverage", "legal"])
        workbook.save(path)

else:  # pragma: no cover - fallback when dependency missing

    def _write_excel(path: Path, sheet_name: str = "Sheet1") -> None:  # type: ignore[return-value]
        raise RuntimeError("openpyxl not available")


@pytest.fixture
def embedding_service() -> DummyEmbeddingService:
    return DummyEmbeddingService()


def _build_service(
    metadata_repository: MetadataRepository,
    embedding_service: DummyEmbeddingService,
    temp_data_root: Path,
) -> IngestionService:
    return IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_service,
        data_root=temp_data_root,
    )


def test_ingest_csv_creates_records_and_embeddings(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    embedding_service: DummyEmbeddingService,
) -> None:
    source = tmp_path / "faq.csv"
    _write_csv(source)

    service = _build_service(metadata_repository, embedding_service, temp_data_root)
    result = service.ingest_file(
        source_path=source,
        display_name="FAQ Import",
        options=IngestionOptions(
            selected_columns=["question", "response"],
            delimiter=",",
        ),
    )

    assert result.data_file.display_name == "FAQ Import"
    assert result.data_file.ingestion_status == IngestionStatus.READY
    assert embedding_service.jobs, "Expected embeddings orchestration to run"

    job = embedding_service.jobs[0]
    assert job.data_file.id == result.data_file.id
    assert len(job.records) == 4  # 2 columns * 2 non-empty rows
    assert all(record.text for record in job.records)

    raw_dir = temp_data_root / "raw" / result.data_file.id
    assert raw_dir.exists()
    assert any(raw_dir.iterdir()), "Raw dataset copy should exist for auditability"


@pytest.mark.skipif(Workbook is None, reason="openpyxl not installed")
def test_ingest_excel_sheet_selection(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    embedding_service: DummyEmbeddingService,
) -> None:
    source = tmp_path / "workbook.xlsx"
    _write_excel(source, sheet_name="Queries")

    service = _build_service(metadata_repository, embedding_service, temp_data_root)
    result = service.ingest_file(
        source_path=source,
        display_name="Workbook Import",
        options=IngestionOptions(
            selected_columns=["prompt"],
            sheet_name="Queries",
        ),
    )

    assert result.data_file.row_count == 2
    job = embedding_service.jobs[0]
    assert job.data_file.id == result.data_file.id
    assert [record.text for record in job.records] == [
        "Draft refund email",
        "Clarify warranty coverage",
    ]


def test_ingest_missing_column_skips_but_continues(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    embedding_service: DummyEmbeddingService,
) -> None:
    source = tmp_path / "faq.csv"
    _write_csv(source)
    service = _build_service(metadata_repository, embedding_service, temp_data_root)

    result = service.ingest_file(
        source_path=source,
        display_name="FAQ Import",
        options=IngestionOptions(selected_columns=["question", "missing"]),
    )

    assert result.data_file.ingestion_status == IngestionStatus.READY
    assert result.data_file.selected_columns == ["question"]

    job = embedding_service.jobs[0]
    assert len(embedding_service.jobs) == 1
    assert {record.column_name for record in job.records} == {"question"}
    assert len(job.records) == 2


def test_ingest_all_missing_columns_raises_error(
    tmp_path: Path,
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    embedding_service: DummyEmbeddingService,
) -> None:
    source = tmp_path / "faq.csv"
    _write_csv(source)
    service = _build_service(metadata_repository, embedding_service, temp_data_root)

    with pytest.raises(ValueError):
        service.ingest_file(
            source_path=source,
            display_name="FAQ Import",
            options=IngestionOptions(selected_columns=["missing"]),
        )
