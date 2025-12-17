from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.embeddings.service import ReembedJob, ReembedService
from app.services.source_repository import SourceRepository

router = APIRouter(prefix="/sources", tags=["sources"])
default_repository = SourceRepository()
default_reembed_service = ReembedService(repository=default_repository)


def get_repository() -> SourceRepository:
    return default_repository


def get_reembed_service(
    repo: Annotated[SourceRepository, Depends(get_repository)]
) -> ReembedService:
    default_reembed_service.repository = repo  # allow override injection
    return default_reembed_service


class ReembedRequest(BaseModel):
    uuid: str = Field(min_length=1)


class ReembedResponse(BaseModel):
    job_id: Annotated[str, Field(alias="job_id")]
    uuid: str
    dataset: str
    status: str

    model_config = ConfigDict(populate_by_name=True)


@router.post("/reembed", status_code=status.HTTP_202_ACCEPTED, response_model=ReembedResponse)
async def reembed_source(
    payload: ReembedRequest, service: Annotated[ReembedService, Depends(get_reembed_service)]
) -> ReembedResponse:
    try:
        job = service.enqueue(payload.uuid)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _job_response(job)


@router.get("/reembed/{job_id}", status_code=status.HTTP_200_OK, response_model=ReembedResponse)
async def reembed_status(
    job_id: str, service: Annotated[ReembedService, Depends(get_reembed_service)]
) -> ReembedResponse:
    job = service.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_response(job)


def _job_response(job: ReembedJob) -> ReembedResponse:
    return ReembedResponse(job_id=job.id, uuid=job.uuid, dataset=job.dataset, status=job.status)
