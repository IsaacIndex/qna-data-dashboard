from __future__ import annotations

from pathlib import Path

from app.db.metadata import MetadataRepository
from app.db.schema import SheetStatus
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import (
    BundleIngestionOptions,
    HiddenSheetPolicy,
    IngestionService,
)
from tests.fixtures.sheet_sources.factory import SheetDefinition


class SheetEmbeddingStub:
    def __init__(self) -> None:
        self.jobs: list[EmbeddingJob] = []

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        if job.sheet is None:
            raise AssertionError("Expected sheet-scoped embedding job.")
        self.jobs.append(job)
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub", model_dimension=1)


def test_refresh_bundle_reconciles_changes(
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    workbook_builder,
) -> None:
    initial_workbook = workbook_builder(filename="integration_refresh.xlsx")
    embedding_stub = SheetEmbeddingStub()
    service = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_stub,
        data_root=temp_data_root,
    )

    options = BundleIngestionOptions(
        selected_columns=["region", "category", "revenue"],
        hidden_sheet_policy=HiddenSheetPolicy(default_action="exclude"),
    )
    bundle_result = service.ingest_bundle(
        source_path=initial_workbook,
        display_name="Integration Refresh",
        options=options,
    )

    bundle = metadata_repository.get_source_bundle(bundle_result.bundle.id)
    assert bundle is not None
    original_sheets = metadata_repository.list_sheet_sources(bundle_id=bundle.id)
    north_sheet = next(sheet for sheet in original_sheets if sheet.sheet_name == "North")
    south_sheet = next(sheet for sheet in original_sheets if sheet.sheet_name == "South")

    updated_workbook = workbook_builder(
        sheets=[
            SheetDefinition(
                name="SouthEast",
                headers=("region", "category", "revenue"),
                rows=(
                    ("south", "hardware", 89200),
                    ("south", "software", 102750),
                ),
            ),
            SheetDefinition(
                name="West",
                headers=("region", "category", "revenue"),
                rows=(
                    ("west", "hardware", 78000),
                    ("west", "software", 90500),
                ),
            ),
        ],
        filename="integration_refresh_updated.xlsx",
    )

    stored_path = temp_data_root / "bundles" / bundle.id / initial_workbook.name
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    updated_workbook.replace(stored_path)

    refresh_result = service.refresh_bundle(
        bundle_id=bundle.id,
        hidden_sheet_policy=HiddenSheetPolicy(default_action="exclude"),
        rename_tolerance="allow_same_schema",
    )

    assert len(refresh_result.updated) == 1
    assert len(refresh_result.created) == 1
    assert len(refresh_result.deactivated) == 1

    refreshed_sheets = metadata_repository.list_sheet_sources(bundle_id=bundle.id)
    southeast = next(sheet for sheet in refreshed_sheets if sheet.sheet_name == "SouthEast")
    west_sheet = next(sheet for sheet in refreshed_sheets if sheet.sheet_name == "West")
    north_after = next(sheet for sheet in refreshed_sheets if sheet.sheet_name == "North")

    assert southeast.id == south_sheet.id
    assert southeast.status == SheetStatus.ACTIVE
    assert west_sheet.status == SheetStatus.ACTIVE
    assert west_sheet.id not in {north_sheet.id, south_sheet.id}
    assert north_after.status == SheetStatus.INACTIVE

    refreshed_bundle = metadata_repository.get_source_bundle(bundle.id)
    assert refreshed_bundle is not None
    assert refreshed_bundle.sheet_count == 2
