from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.services.legacy_reconcile import LegacyReconcileResult, LegacyReconcileService
from app.services.source_repository import SourceRepository

router = APIRouter(prefix="/sources", tags=["sources"])
default_repository = SourceRepository()
default_reconcile_service = LegacyReconcileService(repository=default_repository)


def get_repository() -> SourceRepository:
    return default_repository


def get_reconcile_service(
    repo: Annotated[SourceRepository, Depends(get_repository)],
) -> LegacyReconcileService:
    default_reconcile_service.repository = repo
    return default_reconcile_service


class LegacyReconcileRequest(BaseModel):
    dry_run: bool = Field(default=False)


class LegacyConflict(BaseModel):
    legacy_id: str
    reason: str
    suggested_action: str


class LegacyReconcileResponse(BaseModel):
    reinserted: list[str]
    conflicts: list[LegacyConflict]


@router.post(
    "/reconcile-legacy",
    status_code=status.HTTP_200_OK,
    response_model=LegacyReconcileResponse,
)
async def reconcile_legacy(
    request: LegacyReconcileRequest,
    service: Annotated[LegacyReconcileService, Depends(get_reconcile_service)],
) -> LegacyReconcileResponse:
    result: LegacyReconcileResult = service.reconcile(dry_run=request.dry_run)
    conflicts = [LegacyConflict(**conflict) for conflict in result.conflicts]
    return LegacyReconcileResponse(reinserted=result.reinserted, conflicts=conflicts)
