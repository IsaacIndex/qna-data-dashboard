from __future__ import annotations

import json
import logging
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from app.api import group_preferences, ingest_sources
from app.api.routes.ingest import router as ingest_router
from app.api.routes.legacy import router as legacy_router
from app.api.routes.reembed import router as reembed_router
from app.db.metadata import (
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.db.schema import BundleAudit, QuerySheetRole, SheetSource, SheetStatus, SourceBundle
from app.services.analytics import AnalyticsClient, AnalyticsService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import (
    BundleIngestionOptions,
    HiddenSheetPolicy,
    IngestionOptions,
    IngestionService,
    aggregate_column_catalog,
)
from app.services.preferences import ColumnPreferenceService, PreferenceSnapshot, SelectedColumn
from app.services.query_builder import (
    QueryBuilderService,
    QueryConflictError,
    QueryFilter,
    QueryPreviewRequest,
    QueryProjection,
    QuerySheetSelection,
    QueryValidationError,
)
from app.services.search import SearchService, build_contextual_defaults, build_similarity_legend
from app.utils.config import get_data_root

LOGGER = logging.getLogger(__name__)


class SelectedColumnPayload(BaseModel):
    column_name: Annotated[str, Field(alias="columnName")]
    display_label: Annotated[str, Field(alias="displayLabel")]
    position: Annotated[int, Field(alias="position", ge=0)]

    model_config = ConfigDict(populate_by_name=True)


class UpdateColumnPreferenceRequest(BaseModel):
    dataset_id: Annotated[str, Field(alias="datasetId")]
    user_id: Annotated[str | None, Field(alias="userId", default=None)]
    selected_columns: Annotated[
        list[SelectedColumnPayload],
        Field(alias="selectedColumns", default_factory=list),
    ]
    max_columns: Annotated[int | None, Field(alias="maxColumns", default=None)]

    model_config = ConfigDict(populate_by_name=True)


class ColumnPreferenceResponse(BaseModel):
    dataset_id: Annotated[str, Field(alias="datasetId")]
    user_id: Annotated[str | None, Field(alias="userId", default=None)]
    selected_columns: Annotated[
        list[SelectedColumnPayload],
        Field(alias="selectedColumns", default_factory=list),
    ]
    max_columns: Annotated[int, Field(alias="maxColumns")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class MirrorSelectedColumnPayload(BaseModel):
    name: Annotated[str, Field(alias="name")]
    display_label: Annotated[str, Field(alias="displayLabel")]
    position: Annotated[int, Field(alias="position", ge=0)]

    model_config = ConfigDict(populate_by_name=True)


class PreferenceMirrorRequest(BaseModel):
    dataset_id: Annotated[str, Field(alias="datasetId")]
    device_id: Annotated[str | None, Field(alias="deviceId", default=None)]
    version: Annotated[int, Field(default=0, ge=0)]
    selected_columns: Annotated[
        list[MirrorSelectedColumnPayload],
        Field(alias="selectedColumns", default_factory=list),
    ]
    max_columns: Annotated[int | None, Field(alias="maxColumns", default=None)]
    source: Annotated[str | None, Field(alias="source", default=None)]

    model_config = ConfigDict(populate_by_name=True)


class PreferenceMirrorResponse(BaseModel):
    dataset_id: Annotated[str, Field(alias="datasetId")]
    device_id: Annotated[str | None, Field(alias="deviceId", default=None)]
    version: Annotated[int, Field(alias="version")]
    selected_columns: Annotated[
        list[MirrorSelectedColumnPayload],
        Field(alias="selectedColumns", default_factory=list),
    ]
    max_columns: Annotated[int, Field(alias="maxColumns")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class DisplayableColumnResponse(BaseModel):
    column_name: Annotated[str, Field(alias="columnName")]
    display_label: Annotated[str, Field(alias="displayLabel")]
    data_type: Annotated[str | None, Field(alias="dataType", default=None)]
    is_available: Annotated[bool, Field(alias="isAvailable")]
    last_seen_at: Annotated[datetime | None, Field(alias="lastSeenAt", default=None)]

    model_config = ConfigDict(populate_by_name=True)


class ColumnCatalogResponse(BaseModel):
    dataset_id: Annotated[str, Field(alias="datasetId")]
    columns: list[DisplayableColumnResponse]

    model_config = ConfigDict(populate_by_name=True)


class ColumnCatalogItemResponse(BaseModel):
    column_name: Annotated[str, Field(alias="columnName")]
    display_label: Annotated[str, Field(alias="displayLabel")]
    availability: Annotated[str, Field(alias="availability")]
    sheet_provenance: Annotated[list[str], Field(alias="sheetProvenance", default_factory=list)]
    data_type: Annotated[str | None, Field(alias="dataType", default=None)]
    last_seen_at: Annotated[datetime | None, Field(alias="lastSeenAt", default=None)]

    model_config = ConfigDict(populate_by_name=True)


class AggregatedColumnCatalogResponse(BaseModel):
    dataset_id: Annotated[str, Field(alias="datasetId")]
    columns: list[ColumnCatalogItemResponse]

    model_config = ConfigDict(populate_by_name=True)


def create_app(
    *,
    embedding_service: object | None = None,
) -> FastAPI:
    """Create a FastAPI instance exposing ingestion metadata endpoints."""
    app = FastAPI(
        title="Local Query Coverage Analytics API",
        version="0.1.0",
    )

    engine = build_engine()
    init_database(engine)
    SessionFactory = create_session_factory(engine)
    data_root = get_data_root()

    def get_repository() -> Iterator[MetadataRepository]:
        with session_scope(SessionFactory) as session:
            yield MetadataRepository(session)

    def embedding_factory(repo: MetadataRepository) -> EmbeddingService:
        if embedding_service is not None:
            return embedding_service
        return EmbeddingService(metadata_repository=repo)

    def get_ingestion_service(
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository)
    ) -> IngestionService:
        service = embedding_factory(repo)
        return IngestionService(
            metadata_repository=repo,
            embedding_service=service,
            data_root=data_root,
        )

    def get_search_service(
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository)
    ) -> SearchService:
        service = embedding_factory(repo)
        return SearchService(
            metadata_repository=repo,
            embedding_service=service,
        )

    def get_query_builder_service(
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository)
    ) -> QueryBuilderService:
        return QueryBuilderService(metadata_repository=repo)

    def get_preference_service(
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository)
    ) -> ColumnPreferenceService:
        return ColumnPreferenceService(metadata_repository=repo)

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
            raise HTTPException(
                status_code=400,
                detail="hiddenSheetPolicy must be valid JSON.",
            ) from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="hiddenSheetPolicy must be an object.")
        default_action = payload.get("defaultAction", "exclude")
        overrides = payload.get("overrides") or []
        if default_action not in {"exclude", "include_all"}:
            raise HTTPException(
                status_code=400,
                detail="defaultAction must be 'exclude' or 'include_all'.",
            )
        if not isinstance(overrides, list) or not all(isinstance(item, str) for item in overrides):
            raise HTTPException(status_code=400, detail="overrides must be an array of strings.")
        return HiddenSheetPolicy(
            default_action="include_all" if default_action == "include_all" else "exclude",
            overrides=overrides,
        )

    def _serialize_bundle(bundle: SourceBundle) -> dict[str, object]:
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

    def _serialize_sheet(sheet: SheetSource) -> dict[str, object]:
        return {
            "id": sheet.id,
            "bundleId": sheet.bundle_id,
            "sheetName": sheet.sheet_name,
            "displayLabel": sheet.display_label,
            "visibilityState": sheet.visibility_state.value,
            "status": sheet.status.value,
            "rowCount": sheet.row_count,
            "columnSchema": sheet.column_schema,
            "lastRefreshedAt": (
                sheet.last_refreshed_at.isoformat() if sheet.last_refreshed_at else None
            ),
            "checksum": sheet.checksum,
            "positionIndex": sheet.position_index,
            "description": sheet.description,
            "tags": sheet.tags,
        }

    def _serialize_bundle_audit(audit: BundleAudit) -> dict[str, object]:
        return {
            "id": audit.id,
            "bundleId": audit.bundle_id,
            "status": audit.status.value,
            "startedAt": audit.started_at.isoformat(),
            "completedAt": audit.completed_at.isoformat() if audit.completed_at else None,
            "sheetSummary": audit.sheet_summary,
            "hiddenSheetsEnabled": audit.hidden_sheets_enabled,
        }

    def _to_preference_response(snapshot: PreferenceSnapshot) -> ColumnPreferenceResponse:
        return ColumnPreferenceResponse(
            dataset_id=snapshot.dataset_id,
            user_id=snapshot.user_id,
            selected_columns=[
                SelectedColumnPayload(
                    column_name=column.column_name,
                    display_label=column.display_label,
                    position=column.position,
                )
                for column in snapshot.selected_columns
            ],
            max_columns=snapshot.max_columns,
            updated_at=snapshot.updated_at,
        )

    def _snapshot_from_request(payload: UpdateColumnPreferenceRequest) -> PreferenceSnapshot:
        max_columns = payload.max_columns if payload.max_columns is not None else 10
        return PreferenceSnapshot(
            dataset_id=payload.dataset_id,
            user_id=payload.user_id,
            selected_columns=[
                SelectedColumn(
                    column_name=column.column_name,
                    display_label=column.display_label,
                    position=column.position,
                )
                for column in payload.selected_columns
            ],
            max_columns=max_columns,
            updated_at=datetime.now(UTC),
            version=0,
            source="preference",
        )

    def _snapshot_from_mirror(payload: PreferenceMirrorRequest) -> PreferenceSnapshot:
        max_columns = (
            payload.max_columns
            if payload.max_columns is not None
            else max(len(payload.selected_columns), 1)
        )
        return PreferenceSnapshot(
            dataset_id=payload.dataset_id,
            user_id=payload.device_id,
            selected_columns=[
                SelectedColumn(
                    column_name=column.name,
                    display_label=column.display_label,
                    position=column.position,
                )
                for column in payload.selected_columns
            ],
            max_columns=max_columns or 1,
            updated_at=datetime.now(UTC),
            version=payload.version,
            source=payload.source or "mirror",
        )

    def _mirror_response(snapshot: PreferenceSnapshot) -> PreferenceMirrorResponse:
        return PreferenceMirrorResponse(
            dataset_id=snapshot.dataset_id,
            device_id=snapshot.user_id,
            version=snapshot.version,
            selected_columns=[
                MirrorSelectedColumnPayload(
                    name=column.column_name,
                    display_label=column.display_label,
                    position=column.position,
                )
                for column in snapshot.selected_columns
            ],
            max_columns=snapshot.max_columns,
            updated_at=snapshot.updated_at,
        )

    @app.get(
        "/preferences/columns/catalog",
        response_model=ColumnCatalogResponse,
        response_model_by_alias=True,
    )
    def list_column_catalog(
        dataset_id: Annotated[str, Query(alias="datasetId")],
        service: Annotated[ColumnPreferenceService, Depends(get_preference_service)] = Depends(
            get_preference_service
        ),
    ) -> ColumnCatalogResponse:
        catalog = service.fetch_catalog(dataset_id)
        columns = [
            DisplayableColumnResponse(
                column_name=entry.column_name,
                display_label=entry.display_label,
                data_type=entry.data_type,
                is_available=entry.is_available,
                last_seen_at=entry.last_seen_at,
            )
            for entry in catalog
        ]
        return ColumnCatalogResponse(dataset_id=dataset_id, columns=columns)

    @app.get(
        "/preferences/columns",
        response_model=ColumnPreferenceResponse,
        response_model_by_alias=True,
    )
    def load_column_preference(
        dataset_id: Annotated[str, Query(alias="datasetId")],
        service: Annotated[ColumnPreferenceService, Depends(get_preference_service)] = Depends(
            get_preference_service
        ),
        user_id: Annotated[str | None, Query(alias="userId")] = None,
    ) -> ColumnPreferenceResponse:
        snapshot = service.load_preference(dataset_id=dataset_id, user_id=user_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Preference not found.")
        return _to_preference_response(snapshot)

    @app.put(
        "/preferences/columns",
        response_model=ColumnPreferenceResponse,
        response_model_by_alias=True,
    )
    def save_column_preference(
        payload: UpdateColumnPreferenceRequest,
        service: Annotated[ColumnPreferenceService, Depends(get_preference_service)] = Depends(
            get_preference_service
        ),
    ) -> ColumnPreferenceResponse:
        snapshot = _snapshot_from_request(payload)
        try:
            saved = service.save_preference(snapshot)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _to_preference_response(saved)

    @app.delete("/preferences/columns", status_code=status.HTTP_204_NO_CONTENT)
    def delete_column_preference(
        dataset_id: Annotated[str, Query(alias="datasetId")],
        service: Annotated[ColumnPreferenceService, Depends(get_preference_service)] = Depends(
            get_preference_service
        ),
        user_id: Annotated[str | None, Query(alias="userId")] = None,
    ) -> Response:
        service.reset_preference(dataset_id, user_id=user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/preferences/columns/mirror",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=PreferenceMirrorResponse,
        response_model_by_alias=True,
    )
    def mirror_preferences(
        payload: PreferenceMirrorRequest,
        service: Annotated[ColumnPreferenceService, Depends(get_preference_service)] = Depends(
            get_preference_service
        ),
    ) -> PreferenceMirrorResponse:
        snapshot = _snapshot_from_mirror(payload)
        mirrored = service.mirror_preference(snapshot)
        return _mirror_response(mirrored)

    @app.get(
        "/preferences/columns/mirror",
        response_model=PreferenceMirrorResponse,
        response_model_by_alias=True,
    )
    def load_mirrored_preference(
        dataset_id: Annotated[str, Query(alias="datasetId")],
        service: Annotated[ColumnPreferenceService, Depends(get_preference_service)] = Depends(
            get_preference_service
        ),
        device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    ) -> PreferenceMirrorResponse | Response:
        snapshot = service.load_mirrored_preference(dataset_id=dataset_id, device_id=device_id)
        if snapshot is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return _mirror_response(snapshot)

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
            alias = (
                alias_raw.strip()
                if isinstance(alias_raw, str) and alias_raw.strip()
                else f"sheet_{index + 1}"
            )

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
                elif isinstance(raw_key, int | float):
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

    def get_analytics_service(
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository)
    ) -> AnalyticsService:
        return AnalyticsService(metadata_repository=repo)

    @app.post("/api/source-bundles/import", status_code=status.HTTP_201_CREATED)
    async def import_source_bundle(
        file: Annotated[UploadFile, File(...)],
        displayName: Annotated[str, Form(...)],
        ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)] = Depends(
            get_ingestion_service
        ),
        selectedColumns: Annotated[str | None, Form()] = None,
        hiddenSheetPolicy: Annotated[str | None, Form()] = None,
        delimiter: Annotated[str | None, Form()] = None,
        allowDuplicateImport: Annotated[bool, Form()] = False,
    ) -> dict[str, object]:
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
    def list_bundle_sheets(
        bundle_id: str,
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository),
    ) -> dict[str, object]:
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
        ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)] = Depends(
            get_ingestion_service
        ),
    ) -> dict[str, object]:
        allow_hidden = payload.get("allowHiddenSheets")
        if not isinstance(allow_hidden, list) or not all(
            isinstance(item, str) for item in allow_hidden
        ):
            raise HTTPException(
                status_code=422, detail="allowHiddenSheets must be an array of strings."
            )

        rename_tolerance = payload.get("renameTolerance", "allow_same_schema")
        if not isinstance(rename_tolerance, str) or rename_tolerance not in {
            "allow_same_schema",
            "strict",
        }:
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
        query_service: Annotated[QueryBuilderService, Depends(get_query_builder_service)] = Depends(
            get_query_builder_service
        ),
    ) -> dict[str, object]:
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
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository),
    ) -> dict[str, object]:
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
                raise HTTPException(
                    status_code=422, detail=f"Invalid sheet status '{status_value}'."
                ) from error

        tags_value = payload.get("tags")
        if tags_value is not None:
            if not isinstance(tags_value, list) or not all(
                isinstance(tag, str) for tag in tags_value
            ):
                raise HTTPException(status_code=422, detail="tags must be an array of strings.")

        repo.update_sheet_source(
            sheet,
            status=status_enum,
            description=description if isinstance(description, str) else None,
            tags=(
                [tag for tag in tags_value or [] if tag.strip()] if tags_value is not None else None
            ),
        )

        return _serialize_sheet(sheet)

    @app.get("/datasets")
    def list_datasets(
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository),
    ) -> dict[str, list[dict[str, object]]]:
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
        upload: Annotated[UploadFile, File(...)],
        display_name: Annotated[str, Form(...)],
        selected_columns: Annotated[list[str], Form(...)],
        ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)] = Depends(
            get_ingestion_service
        ),
        delimiter: Annotated[str | None, Form()] = None,
        sheet_name: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
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
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository),
    ) -> dict[str, object]:
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

    @app.get(
        "/datasets/{dataset_id}/columns/catalog",
        response_model=AggregatedColumnCatalogResponse,
        response_model_by_alias=True,
    )
    def list_dataset_column_catalog(
        dataset_id: str,
        repo: Annotated[MetadataRepository, Depends(get_repository)] = Depends(get_repository),
        include_unavailable: bool = Query(
            default=False,
            alias="includeUnavailable",
            description="Include columns marked missing/unavailable",
        ),
    ) -> AggregatedColumnCatalogResponse:
        bundle = repo.get_source_bundle(dataset_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")

        sheets = repo.list_sheet_sources(bundle_id=bundle.id, statuses=[SheetStatus.ACTIVE])
        catalog = aggregate_column_catalog(sheets, include_unavailable=include_unavailable)
        columns = [
            ColumnCatalogItemResponse(
                column_name=entry.column_name,
                display_label=entry.display_label,
                availability=entry.availability,
                sheet_provenance=(
                    list(entry.sheet_labels) if entry.sheet_labels else list(entry.sheet_ids)
                ),
                data_type=entry.data_type,
                last_seen_at=entry.last_seen_at,
            )
            for entry in catalog
        ]
        return AggregatedColumnCatalogResponse(dataset_id=bundle.id, columns=columns)

    @app.get("/search")
    def search_queries(
        search_service: Annotated[SearchService, Depends(get_search_service)] = Depends(
            get_search_service
        ),
        q: str = Query(..., description="Natural language search query"),
        dataset_ids: str | None = Query(
            default=None,
            alias="datasetIds",
            description="Comma-separated dataset IDs to filter results",
        ),
        dataset_ids_legacy: str | None = Query(
            default=None,
            alias="dataset_ids",
            description="Comma-separated dataset IDs to filter results (legacy dataset_ids)",
        ),
        column_names: str | None = Query(
            default=None,
            alias="columnNames",
            description="Comma-separated column names to filter results",
        ),
        column_names_legacy: str | None = Query(
            default=None,
            alias="column_names",
            description="Comma-separated column names to filter results (legacy column_names)",
        ),
        min_similarity_percent: float = Query(
            default=60.0,
            ge=0.0,
            le=100.0,
            description="Minimum similarity threshold (0-100)",
            alias="minSimilarityPercent",
        ),
        min_similarity: float | None = Query(
            default=None,
            ge=0.0,
            le=1.0,
            description="Minimum similarity threshold (0-1, legacy)",
            alias="min_similarity",
        ),
        limit_per_mode: int | None = Query(
            default=10,
            ge=1,
            le=50,
            description="Maximum results per mode (semantic and lexical paginate independently)",
            alias="limitPerMode",
        ),
        offset_semantic: int = Query(
            default=0,
            ge=0,
            description="Offset for semantic results pagination",
            alias="offsetSemantic",
        ),
        offset_lexical: int = Query(
            default=0,
            ge=0,
            description="Offset for lexical results pagination",
            alias="offsetLexical",
        ),
    ) -> dict[str, object]:
        dataset_filters = _split_csv(dataset_ids or dataset_ids_legacy) or None
        column_filters = _split_csv(column_names or column_names_legacy) or None
        similarity_threshold = (
            min_similarity if min_similarity is not None else (min_similarity_percent / 100.0)
        )
        start = time.perf_counter()
        response = search_service.search_dual(
            query=q,
            dataset_ids=dataset_filters,
            column_names=column_filters,
            min_similarity=similarity_threshold,
            limit_per_mode=limit_per_mode,
            offset_semantic=offset_semantic,
            offset_lexical=offset_lexical,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        legend = build_similarity_legend()
        semantic_results = response["semantic_results"]
        lexical_results = response["lexical_results"]
        dataset_scope = dataset_filters or sorted(
            {result.dataset_id for result in semantic_results + lexical_results}
        )
        contextual_defaults = build_contextual_defaults(
            search_service.metadata_repository, dataset_scope
        )
        try:
            client = AnalyticsClient()
            contextual_labels = sorted(
                {
                    label
                    for result in lexical_results + semantic_results
                    for label in result.metadata.get("contextual_labels", {}).values()
                }
            )
            detail = f"contextual:{','.join(contextual_labels)}" if contextual_labels else None
            dataset_hint = dataset_filters[0] if dataset_filters else None
            client.search_latency(elapsed_ms, dataset_id=dataset_hint, detail=detail)
            client.flush()
        except Exception as error:
            LOGGER.warning("Failed to record search latency: %s", error, exc_info=True)

        fallback = response.get("fallback") or {"semantic_available": True, "message": None}
        if fallback.get("message") is None and not fallback.get("semantic_available", True):
            fallback["message"] = "Semantic results unavailable"

        combined_results = semantic_results + lexical_results

        return {
            "legend": legend,
            "contextual_defaults": contextual_defaults,
            "semantic_results": [result.to_dict() for result in semantic_results],
            "lexical_results": [result.to_dict() for result in lexical_results],
            "results": [result.to_dict() for result in combined_results],
            "pagination": response["pagination"],
            "fallback": fallback,
        }

    @app.get("/analytics/clusters")
    def analytics_clusters(
        analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)] = Depends(
            get_analytics_service
        ),
        dataset_ids: str | None = Query(
            default=None,
            description="Comma-separated dataset IDs to scope analytics",
        ),
    ) -> dict[str, object]:
        dataset_filters = _split_csv(dataset_ids) or None
        clusters = analytics_service.list_clusters(dataset_filters)
        if not clusters:
            clusters = analytics_service.build_clusters(dataset_filters)
        return {"clusters": [cluster.to_dict() for cluster in clusters]}

    @app.get("/analytics/summary")
    def analytics_summary(
        analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)] = Depends(
            get_analytics_service
        ),
        dataset_ids: str | None = Query(
            default=None,
            description="Comma-separated dataset IDs to scope analytics",
        ),
    ) -> dict[str, object]:
        dataset_filters = _split_csv(dataset_ids) or None
        summary = analytics_service.summarize_coverage(dataset_filters)
        return summary.to_dict()

    app.include_router(ingest_sources.router)
    app.include_router(ingest_router)
    app.include_router(reembed_router)
    app.include_router(legacy_router)
    app.include_router(group_preferences.router)

    return app
