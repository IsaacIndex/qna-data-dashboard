from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status

from app.db.metadata import (
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.db.schema import QuerySheetRole, SheetStatus
from app.services.analytics import AnalyticsService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import (
    BundleIngestionOptions,
    HiddenSheetPolicy,
    IngestionOptions,
    IngestionService,
)
from app.services.search import SearchService
from app.services.query_builder import (
    QueryBuilderService,
    QueryConflictError,
    QueryFilter,
    QueryPreviewRequest,
    QueryProjection,
    QuerySheetSelection,
    QueryValidationError,
)


def create_app(
    *,
    embedding_service: Optional[object] = None,
) -> FastAPI:
    """Create a FastAPI instance exposing ingestion metadata endpoints."""
    app = FastAPI(
        title="Local Query Coverage Analytics API",
        version="0.1.0",
    )

    engine = build_engine()
    init_database(engine)
    SessionFactory = create_session_factory(engine)
    data_root = Path(os.getenv("DATA_ROOT", "./data")).expanduser()

    def get_repository():
        with session_scope(SessionFactory) as session:
            yield MetadataRepository(session)

    def embedding_factory(repo: MetadataRepository):
        if embedding_service is not None:
            return embedding_service
        return EmbeddingService(metadata_repository=repo)

    def get_ingestion_service(repo: MetadataRepository = Depends(get_repository)):
        service = embedding_factory(repo)
        return IngestionService(
            metadata_repository=repo,
            embedding_service=service,
            data_root=data_root,
        )

    def get_search_service(repo: MetadataRepository = Depends(get_repository)):
        service = embedding_factory(repo)
        return SearchService(
            metadata_repository=repo,
            embedding_service=service,
        )

    def get_query_builder_service(repo: MetadataRepository = Depends(get_repository)):
        return QueryBuilderService(metadata_repository=repo)

    def _split_csv(value: str | None) -> list[str] | None:
        if not value:
            return None
        return [item.strip() for item in value.split(",") if item.strip()]

    def _parse_selected_columns(value: str | None) -> list[str]:
        if value is None:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [column.strip() for column in value.split(",") if column.strip()]
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            return [column.strip() for column in parsed if column.strip()]
        raise HTTPException(
            status_code=400,
            detail="selectedColumns must be a JSON array of strings or comma-separated list.",
        )

    def _parse_hidden_policy(value: str | None) -> HiddenSheetPolicy:
        if not value:
            return HiddenSheetPolicy(default_action="exclude", overrides=[])
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="hiddenSheetPolicy must be valid JSON.") from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="hiddenSheetPolicy must be an object.")
        default_action = payload.get("defaultAction", "exclude")
        overrides = payload.get("overrides") or []
        if default_action not in {"exclude", "include_all"}:
            raise HTTPException(status_code=400, detail="defaultAction must be 'exclude' or 'include_all'.")
        if not isinstance(overrides, list) or not all(isinstance(item, str) for item in overrides):
            raise HTTPException(status_code=400, detail="overrides must be an array of strings.")
        return HiddenSheetPolicy(
            default_action="include_all" if default_action == "include_all" else "exclude",
            overrides=overrides,
        )

    def _serialize_bundle(bundle) -> dict[str, object]:
        return {
            "id": bundle.id,
            "displayName": bundle.display_name,
            "fileType": bundle.file_type.value,
            "ingestionStatus": bundle.ingestion_status.value,
            "sheetCount": bundle.sheet_count,
            "refreshCadence": bundle.refresh_cadence,
            "ownerUserId": bundle.owner_user_id,
            "createdAt": bundle.created_at.isoformat(),
            "updatedAt": bundle.updated_at.isoformat(),
        }

    def _serialize_sheet(sheet) -> dict[str, object]:
        return {
            "id": sheet.id,
            "bundleId": sheet.bundle_id,
            "sheetName": sheet.sheet_name,
            "displayLabel": sheet.display_label,
            "visibilityState": sheet.visibility_state.value,
            "status": sheet.status.value,
            "rowCount": sheet.row_count,
            "columnSchema": sheet.column_schema,
            "lastRefreshedAt": sheet.last_refreshed_at.isoformat() if sheet.last_refreshed_at else None,
            "checksum": sheet.checksum,
            "positionIndex": sheet.position_index,
            "description": sheet.description,
            "tags": sheet.tags,
        }

    def _serialize_bundle_audit(audit) -> dict[str, object]:
        return {
            "id": audit.id,
            "bundleId": audit.bundle_id,
            "status": audit.status.value,
            "startedAt": audit.started_at.isoformat(),
            "completedAt": audit.completed_at.isoformat() if audit.completed_at else None,
            "sheetSummary": audit.sheet_summary,
            "hiddenSheetsEnabled": audit.hidden_sheets_enabled,
        }

    def _parse_preview_request(payload: dict[str, object]) -> QueryPreviewRequest:
        sheets_payload = payload.get("sheets")
        if not isinstance(sheets_payload, list) or not sheets_payload:
            raise QueryValidationError("'sheets' must be a non-empty array.")

        selections: list[QuerySheetSelection] = []
        for index, entry in enumerate(sheets_payload):
            if not isinstance(entry, dict):
                raise QueryValidationError("Each sheet entry must be an object.")
            sheet_id = entry.get("sheetId")
            if not isinstance(sheet_id, str) or not sheet_id.strip():
                raise QueryValidationError("sheetId is required for each sheet.")

            alias_raw = entry.get("alias")
            alias = alias_raw.strip() if isinstance(alias_raw, str) and alias_raw.strip() else f"sheet_{index + 1}"

            role_raw = entry.get("role", QuerySheetRole.PRIMARY.value)
            if not isinstance(role_raw, str):
                raise QueryValidationError("role must be a string when provided.")
            try:
                role = QuerySheetRole(role_raw)
            except ValueError as exc:
                raise QueryValidationError(f"Unsupported role '{role_raw}'.") from exc

            join_keys_raw = entry.get("joinKeys", [])
            if join_keys_raw is None:
                join_keys_raw = []
            if not isinstance(join_keys_raw, list):
                raise QueryValidationError("joinKeys must be an array of strings.")
            join_keys_list: list[str] = []
            for raw_key in join_keys_raw:
                if isinstance(raw_key, str):
                    key_value = raw_key.strip()
                elif isinstance(raw_key, (int, float)):
                    key_value = str(raw_key)
                else:
                    raise QueryValidationError("joinKeys must contain only strings or numbers.")
                if not key_value:
                    raise QueryValidationError("joinKeys entries must be non-empty strings.")
                join_keys_list.append(key_value)

            selections.append(
                QuerySheetSelection(
                    sheet_id=sheet_id,
                    alias=alias,
                    role=role,
                    join_keys=tuple(join_keys_list),
                )
            )

        projection_payload = payload.get("projections")
        if not isinstance(projection_payload, list) or not projection_payload:
            raise QueryValidationError("'projections' must be a non-empty array.")
        projections: list[QueryProjection] = []
        for entry in projection_payload:
            if not isinstance(entry, dict):
                raise QueryValidationError("Each projection must be an object.")
            expression = entry.get("expression")
            label = entry.get("label")
            if not isinstance(expression, str) or not expression.strip():
                raise QueryValidationError("Projection expression must be a non-empty string.")
            if not isinstance(label, str) or not label.strip():
                raise QueryValidationError("Projection label must be a non-empty string.")
            projections.append(QueryProjection(expression=expression, label=label))

        filters_payload = payload.get("filters", [])
        filters: list[QueryFilter] = []
        if filters_payload is None:
            filters_payload = []
        if not isinstance(filters_payload, list):
            raise QueryValidationError("'filters' must be an array when provided.")
        for entry in filters_payload:
            if not isinstance(entry, dict):
                raise QueryValidationError("Each filter must be an object.")
            sheet_alias = entry.get("sheetAlias")
            column = entry.get("column")
            operator = entry.get("operator")
            if not isinstance(sheet_alias, str) or not sheet_alias.strip():
                raise QueryValidationError("Filter sheetAlias must be a non-empty string.")
            if not isinstance(column, str) or not column.strip():
                raise QueryValidationError("Filter column must be a non-empty string.")
            if not isinstance(operator, str) or not operator.strip():
                raise QueryValidationError("Filter operator must be a non-empty string.")
            filters.append(
                QueryFilter(
                    sheet_alias=sheet_alias,
                    column=column,
                    operator=operator,
                    value=entry.get("value"),
                )
            )

        limit_raw = payload.get("limit")
        limit_value: int | None = None
        if limit_raw is not None:
            if isinstance(limit_raw, bool) or not isinstance(limit_raw, int):
                raise QueryValidationError("limit must be an integer when provided.")
            if limit_raw <= 0:
                raise QueryValidationError("limit must be greater than zero.")
            limit_value = int(limit_raw)

        return QueryPreviewRequest(
            sheets=tuple(selections),
            projections=tuple(projections),
            filters=tuple(filters),
            limit=limit_value,
        )

    def get_analytics_service(repo: MetadataRepository = Depends(get_repository)):
        return AnalyticsService(metadata_repository=repo)

    @app.post("/api/source-bundles/import", status_code=status.HTTP_201_CREATED)
    async def import_source_bundle(
        file: UploadFile = File(...),
        displayName: str = Form(...),
        selectedColumns: str | None = Form(default=None),
        hiddenSheetPolicy: str | None = Form(default=None),
        delimiter: str | None = Form(default=None),
        allowDuplicateImport: bool = Form(default=False),
        ingestion_service: IngestionService = Depends(get_ingestion_service),
    ):
        columns = _parse_selected_columns(selectedColumns)
        if not columns:
            raise HTTPException(status_code=400, detail="selectedColumns are required.")
        policy = _parse_hidden_policy(hiddenSheetPolicy)

        suffix = Path(file.filename or "upload").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            temp_path = Path(tmp_file.name)

        try:
            result = ingestion_service.ingest_bundle(
                source_path=temp_path,
                display_name=displayName,
                options=BundleIngestionOptions(
                    selected_columns=columns,
                    hidden_sheet_policy=policy,
                    delimiter=delimiter or None,
                    allow_duplicate_import=allowDuplicateImport,
                ),
            )
        finally:
            temp_path.unlink(missing_ok=True)

        bundle_payload = _serialize_bundle(result.bundle)
        bundle_payload["hiddenOptInCount"] = len(result.hidden_opt_ins)
        return bundle_payload

    @app.get("/api/source-bundles/{bundle_id}/sheets")
    def list_bundle_sheets(bundle_id: str, repo: MetadataRepository = Depends(get_repository)):
        bundle = repo.get_source_bundle(bundle_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="Source bundle not found.")
        sheets = repo.list_sheet_sources(bundle_id=bundle_id)
        return {
            "bundle": _serialize_bundle(bundle),
            "sheets": [_serialize_sheet(sheet) for sheet in sheets],
        }

    @app.post("/api/source-bundles/{bundle_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
    def refresh_bundle_endpoint(
        bundle_id: str,
        payload: dict[str, object],
        ingestion_service: IngestionService = Depends(get_ingestion_service),
    ):
        allow_hidden = payload.get("allowHiddenSheets")
        if not isinstance(allow_hidden, list) or not all(isinstance(item, str) for item in allow_hidden):
            raise HTTPException(status_code=422, detail="allowHiddenSheets must be an array of strings.")

        rename_tolerance = payload.get("renameTolerance", "allow_same_schema")
        if not isinstance(rename_tolerance, str) or rename_tolerance not in {"allow_same_schema", "strict"}:
            raise HTTPException(
                status_code=422,
                detail="renameTolerance must be 'allow_same_schema' or 'strict'.",
            )

        policy = HiddenSheetPolicy(default_action="exclude", overrides=allow_hidden)

        try:
            result = ingestion_service.refresh_bundle(
                bundle_id=bundle_id,
                hidden_sheet_policy=policy,
                rename_tolerance=rename_tolerance,
            )
        except FileNotFoundError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ValueError as error:
            message = str(error)
            status_code = 404 if "not found" in message.lower() else 422
            raise HTTPException(status_code=status_code, detail=message) from error

        return _serialize_bundle_audit(result.audit)

    @app.post("/api/queries/preview")
    def preview_query_endpoint(
        payload: dict[str, object],
        query_service: QueryBuilderService = Depends(get_query_builder_service),
    ):
        try:
            request = _parse_preview_request(payload)
        except QueryValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            result = query_service.preview_query(request)
        except QueryConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except QueryValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "headers": result.headers,
            "rows": result.rows,
            "warnings": result.warnings,
            "executionMetrics": {
                "executionMs": result.execution_ms,
                "rowCount": result.row_count,
            },
        }

    @app.patch("/api/sheet-sources/{sheet_id}")
    def update_sheet_source_endpoint(
        sheet_id: str,
        payload: dict[str, object],
        repo: MetadataRepository = Depends(get_repository),
    ):
        sheet = repo.get_sheet_source(sheet_id)
        if sheet is None:
            raise HTTPException(status_code=404, detail="Sheet source not found.")

        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise HTTPException(status_code=422, detail="description must be a string.")

        status_value = payload.get("status")
        status_enum: SheetStatus | None = None
        if status_value is not None:
            if not isinstance(status_value, str):
                raise HTTPException(status_code=422, detail="status must be a string.")
            try:
                status_enum = SheetStatus(status_value)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=f"Invalid sheet status '{status_value}'.") from error

        tags_value = payload.get("tags")
        if tags_value is not None:
            if not isinstance(tags_value, list) or not all(isinstance(tag, str) for tag in tags_value):
                raise HTTPException(status_code=422, detail="tags must be an array of strings.")

        repo.update_sheet_source(
            sheet,
            status=status_enum,
            description=description if isinstance(description, str) else None,
            tags=[tag for tag in tags_value or [] if tag.strip()] if tags_value is not None else None,
        )

        return _serialize_sheet(sheet)

    @app.get("/datasets")
    def list_datasets(repo: MetadataRepository = Depends(get_repository)):
        datasets = repo.list_data_files()
        return {
            "datasets": [
                {
                    "id": dataset.id,
                    "display_name": dataset.display_name,
                    "ingestion_status": dataset.ingestion_status.value,
                    "row_count": dataset.row_count,
                    "ingested_at": dataset.ingested_at.isoformat(),
                }
                for dataset in datasets
            ]
        }

    @app.post("/datasets/import", status_code=status.HTTP_202_ACCEPTED)
    async def import_dataset(
        upload: UploadFile = File(...),
        display_name: str = Form(...),
        selected_columns: list[str] = Form(...),
        delimiter: str | None = Form(default=None),
        sheet_name: str | None = Form(default=None),
        ingestion_service: IngestionService = Depends(get_ingestion_service),
    ):
        columns = [column for column in selected_columns if column]
        if not columns:
            raise HTTPException(status_code=400, detail="selected_columns are required.")

        suffix = Path(upload.filename or "upload").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            contents = await upload.read()
            tmp_file.write(contents)
            temp_path = Path(tmp_file.name)

        try:
            clean_delimiter = delimiter or None
            clean_sheet = sheet_name or None

            result = ingestion_service.ingest_file(
                source_path=temp_path,
                display_name=display_name,
                options=IngestionOptions(
                    selected_columns=columns,
                    delimiter=clean_delimiter,
                    sheet_name=clean_sheet,
                ),
            )
        finally:
            temp_path.unlink(missing_ok=True)

        return {
            "dataset_id": result.data_file.id,
            "ingestion_status": result.data_file.ingestion_status.value,
            "processed_rows": result.processed_rows,
        }

    @app.get("/datasets/{dataset_id}/audits/latest")
    def latest_audit(
        dataset_id: str,
        repo: MetadataRepository = Depends(get_repository),
    ):
        audit = repo.get_latest_audit(dataset_id)
        if audit is None:
            raise HTTPException(status_code=404, detail="Audit not found")
        return {
            "dataset_id": audit.data_file_id,
            "status": audit.status.value,
            "processed_rows": audit.processed_rows,
            "skipped_rows": audit.skipped_rows,
            "started_at": audit.started_at.isoformat(),
            "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
        }

    @app.get("/search")
    def search_queries(
        q: str = Query(..., description="Natural language search query"),
        dataset_ids: str | None = Query(
            default=None,
            description="Comma-separated dataset IDs to filter results",
        ),
        column_names: str | None = Query(
            default=None,
            description="Comma-separated column names to filter results",
        ),
        min_similarity: float = Query(
            default=0.6,
            ge=0.0,
            le=1.0,
            description="Minimum similarity threshold (0-1)",
        ),
        limit: int = Query(default=20, ge=1, le=100, description="Maximum results to return"),
        search_service: SearchService = Depends(get_search_service),
    ):
        dataset_filters = _split_csv(dataset_ids) or None
        column_filters = _split_csv(column_names) or None
        results = search_service.search(
            query=q,
            dataset_ids=dataset_filters,
            column_names=column_filters,
            min_similarity=min_similarity,
            limit=limit,
        )
        return {"results": [result.to_dict() for result in results]}

    @app.get("/analytics/clusters")
    def analytics_clusters(
        dataset_ids: str | None = Query(
            default=None,
            description="Comma-separated dataset IDs to scope analytics",
        ),
        analytics_service: AnalyticsService = Depends(get_analytics_service),
    ):
        dataset_filters = _split_csv(dataset_ids) or None
        clusters = analytics_service.list_clusters(dataset_filters)
        if not clusters:
            clusters = analytics_service.build_clusters(dataset_filters)
        return {"clusters": [cluster.to_dict() for cluster in clusters]}

    @app.get("/analytics/summary")
    def analytics_summary(
        dataset_ids: str | None = Query(
            default=None,
            description="Comma-separated dataset IDs to scope analytics",
        ),
        analytics_service: AnalyticsService = Depends(get_analytics_service),
    ):
        dataset_filters = _split_csv(dataset_ids) or None
        summary = analytics_service.summarize_coverage(dataset_filters)
        return summary.to_dict()

    return app
