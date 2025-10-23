from __future__ import annotations

from pathlib import Path

from app.db.metadata import MetadataRepository
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import (
    BundleIngestionOptions,
    HiddenSheetPolicy,
    IngestionService,
)


class SheetEmbeddingStub:
    def __init__(self) -> None:
        self.jobs: list[EmbeddingJob] = []

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        if job.sheet is None:
            raise AssertionError("Expected sheet-scoped embedding job.")
        self.jobs.append(job)
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub", model_dimension=1)


def test_ingest_workbook_registers_sheet_sources(
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="integration_catalog.xlsx")
    embedding_stub = SheetEmbeddingStub()
    service = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_stub,
        data_root=temp_data_root,
    )

    options = BundleIngestionOptions(
        selected_columns=["region", "category"],
        hidden_sheet_policy=HiddenSheetPolicy(default_action="exclude"),
    )

    result = service.ingest_bundle(
        source_path=workbook_path,
        display_name="Workbook Catalog",
        options=options,
    )

    assert result.bundle.sheet_count == 2
    assert {sheet.sheet.sheet_name for sheet in result.sheets} == {"North", "South"}

    bundle = metadata_repository.get_source_bundle(result.bundle.id)
    assert bundle is not None
    assert bundle.sheet_count == 2
    assert {sheet.sheet_name for sheet in bundle.sheets} == {"North", "South"}

    audit = metadata_repository.get_latest_bundle_audit(bundle.id)
    assert audit is not None
    assert (audit.hidden_sheets_enabled or []) == []
    assert audit.sheet_summary == {"created": 2, "hidden_opt_ins": 0, "inactive": 0}

    assert len(embedding_stub.jobs) == 2
    assert {job.sheet.sheet_name for job in embedding_stub.jobs} == {"North", "South"}
