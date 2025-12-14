from __future__ import annotations

from pathlib import Path

from app.db.metadata import MetadataRepository
from app.db.schema import QuerySheetRole, SheetStatus
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from app.services.ingestion import (
    BundleIngestionOptions,
    HiddenSheetPolicy,
    IngestionService,
)
from app.services.query_builder import (
    QueryBuilderService,
    QueryFilter,
    QueryPreviewRequest,
    QueryProjection,
    QuerySheetSelection,
)


class SheetEmbeddingStub:
    def __init__(self) -> None:
        self.jobs: list[EmbeddingJob] = []

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        if job.sheet is None:
            raise AssertionError("Expected sheet-scoped embedding job.")
        self.jobs.append(job)
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub", model_dimension=1)


def test_preview_query_sums_revenue_against_budget(
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    workbook_builder,
    csv_builder,
) -> None:
    workbook_path = workbook_builder(filename="integration_queries.xlsx")
    csv_path = csv_builder(
        filename="integration_budget.csv",
        headers=("region", "category", "budget"),
        rows=(
            ("north", "hardware", 130000),
            ("north", "software", 95000),
            ("south", "hardware", 88000),
            ("south", "software", 101000),
        ),
    )

    embedding_stub = SheetEmbeddingStub()
    ingestion_service = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_stub,
        data_root=temp_data_root,
    )

    workbook_options = BundleIngestionOptions(
        selected_columns=["region", "category", "revenue"],
        hidden_sheet_policy=HiddenSheetPolicy(default_action="exclude"),
    )
    csv_options = BundleIngestionOptions(
        selected_columns=["region", "category", "budget"],
        hidden_sheet_policy=HiddenSheetPolicy(default_action="exclude"),
    )

    ingestion_service.ingest_bundle(
        source_path=workbook_path,
        display_name="Integration Workbook",
        options=workbook_options,
    )
    ingestion_service.ingest_bundle(
        source_path=csv_path,
        display_name="Integration Budget",
        options=csv_options,
    )

    north_sheet = next(
        sheet for sheet in metadata_repository.list_sheet_sources() if sheet.sheet_name == "North"
    )
    csv_sheet = next(
        sheet for sheet in metadata_repository.list_sheet_sources() if sheet.sheet_name == "__csv__"
    )

    query_service = QueryBuilderService(metadata_repository=metadata_repository)

    request = QueryPreviewRequest(
        sheets=[
            QuerySheetSelection(
                sheet_id=north_sheet.id,
                alias="sales",
                role=QuerySheetRole.PRIMARY,
                join_keys=[],
            ),
            QuerySheetSelection(
                sheet_id=csv_sheet.id,
                alias="budget",
                role=QuerySheetRole.JOIN,
                join_keys=["region", "category"],
            ),
        ],
        filters=[
            QueryFilter(sheet_alias="sales", column="region", operator="eq", value="north"),
        ],
        projections=[
            QueryProjection(expression="sum(sales.revenue)", label="total_revenue"),
            QueryProjection(expression="sum(budget.budget)", label="total_budget"),
        ],
    )

    result = query_service.preview_query(request)

    assert result.headers == ["total_revenue", "total_budget"]
    assert result.rows == [["223500", "225000"]]
    assert result.warnings == []
    assert result.row_count == 1


def test_preview_warns_for_inactive_sheet(
    temp_data_root: Path,
    metadata_repository: MetadataRepository,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="integration_warning.xlsx")
    embedding_stub = SheetEmbeddingStub()
    ingestion_service = IngestionService(
        metadata_repository=metadata_repository,
        embedding_service=embedding_stub,
        data_root=temp_data_root,
    )

    options = BundleIngestionOptions(
        selected_columns=["region", "category", "revenue"],
        hidden_sheet_policy=HiddenSheetPolicy(default_action="exclude"),
    )

    bundle_result = ingestion_service.ingest_bundle(
        source_path=workbook_path,
        display_name="Inactive Preview",
        options=options,
    )

    sheet = metadata_repository.list_sheet_sources(bundle_id=bundle_result.bundle.id)[0]
    metadata_repository.update_sheet_source(sheet, status=SheetStatus.INACTIVE)

    query_service = QueryBuilderService(metadata_repository=metadata_repository)

    request = QueryPreviewRequest(
        sheets=[
            QuerySheetSelection(sheet_id=sheet.id, alias="sales", role=QuerySheetRole.PRIMARY),
        ],
        projections=[
            QueryProjection(expression="sales.region", label="region"),
        ],
        limit=10,
    )

    result = query_service.preview_query(request)

    assert result.warnings
    assert any("inactive" in warning for warning in result.warnings)
    assert result.rows
