from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.audit_log import AuditLogService
from app.services.source_repository import SourceRepository
from app.services.source_service import SourcePage, SourceService
from app.models.source import Source

router = APIRouter(prefix="/sources", tags=["sources"])


def get_repository() -> SourceRepository:
    return SourceRepository()


def get_source_service(repo: Annotated[SourceRepository, Depends(get_repository)]) -> SourceService:
    return SourceService(repository=repo)


def get_audit_log() -> AuditLogService:
    return AuditLogService()


class BulkUpdateRequest(BaseModel):
    uuids: list[str] = Field(min_length=1)
    status: str | None = None
    groups: list[str] | None = None


class SourceListResponse(BaseModel):
    items: list[Source]
    next_cursor: str | None = None


@router.get("", status_code=status.HTTP_200_OK, response_model=SourceListResponse)
async def list_sources(
    service: Annotated[SourceService, Depends(get_source_service)],
    cursor: str | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    group: str | None = Query(None),
    dataset: str | None = Query(None),
    sort: str | None = Query(None),
) -> SourcePage:
    try:
        page = service.list_sources(
            cursor=cursor,
            limit=limit,
            status_filter=status_filter,
            type_filter=type_filter,
            group=group,
            dataset=dataset,
            sort=sort,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return SourceListResponse(items=page.items, next_cursor=page.next_cursor)


@router.post("/bulk", status_code=status.HTTP_200_OK)
async def bulk_update(
    repo: Annotated[SourceRepository, Depends(get_repository)],
    audit_log: Annotated[AuditLogService, Depends(get_audit_log)],
    request: BulkUpdateRequest,
) -> dict[str, list[dict[str, object]]]:
    try:
        results = repo.bulk_update(request.uuids, status=request.status, groups=request.groups)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    audit_log.record_bulk_action(uuids=request.uuids, outcome="completed", details=request.model_dump())
    return {"results": results}
