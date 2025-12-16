from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.services.embedding_queue import EmbeddingQueue, default_queue
from app.services.ingest_models import EmbeddingJob, SourceFile
from app.services.ingest_storage import IngestStorage, default_storage
from app.utils.audit import record_audit


def get_storage() -> IngestStorage:
    return default_storage


def get_queue() -> EmbeddingQueue:
    return default_queue


router = APIRouter(prefix="/api/groups")


@router.get("", response_model=list[dict])
def list_groups() -> list[dict]:
    # Minimal stub returning a default group for UI wiring
    return [{"id": "default", "name": "Default Group", "description": "Local ingest sources"}]


@router.get("/{group_id}/sources", response_model=list[dict])
def list_sources(
    group_id: str,
    storage: Annotated[IngestStorage, Depends(get_storage)],
) -> list[dict]:
    return [storage._serialize_source(item) for item in storage.list_sources(group_id)]  # noqa: SLF001


@router.post(
    "/{group_id}/sources",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=list[dict],
)
def upload_sources(
    group_id: str,
    files: Annotated[list[UploadFile], File(...)],
    storage: Annotated[IngestStorage, Depends(get_storage)],
) -> list[dict]:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    results: list[SourceFile] = []
    for file in files:
        try:
            results.append(
                storage.save_upload(
                    group_id,
                    file.file,
                    filename=file.filename,
                    mime_type=file.content_type or "",
                    added_by=None,
                )
            )
            record_audit("source.upload", "success", user=None, details={"group": group_id, "file": file.filename})
        except Exception as exc:
            record_audit("source.upload", "failure", user=None, details={"group": group_id, "file": file.filename})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [storage._serialize_source(item) for item in results]  # noqa: SLF001


@router.delete("/{group_id}/sources/{source_id}", status_code=status.HTTP_200_OK)
def delete_source(
    group_id: str,
    source_id: str,
    storage: Annotated[IngestStorage, Depends(get_storage)],
    queue: Annotated[EmbeddingQueue, Depends(get_queue)],
) -> dict:
    if queue.is_source_busy(group_id, source_id):
        raise HTTPException(status_code=409, detail="Embedding in progress; cannot delete")
    deleted = storage.delete_source(group_id, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    record_audit("source.delete", "success", user=None, details={"group": group_id, "source_id": source_id})
    return {"status": "deleted"}


@router.post(
    "/{group_id}/sources/reembed",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict,
)
def trigger_reembed(
    group_id: str,
    payload: dict,
    queue: Annotated[EmbeddingQueue, Depends(get_queue)],
) -> dict:
    source_ids = payload.get("source_ids") or payload.get("sourceIds") or []
    if not source_ids:
        raise HTTPException(status_code=400, detail="No source_ids provided")
    job = queue.enqueue(group_id, list(source_ids), triggered_by=None)
    record_audit("source.reembed", "queued", user=None, details={"group": group_id, "sources": len(source_ids)})
    return {"job_ids": [job.id]}


@router.get("/{group_id}/embedding-jobs/{job_id}", response_model=dict)
def get_job_status(
    group_id: str,
    job_id: str,
    queue: Annotated[EmbeddingQueue, Depends(get_queue)],
) -> dict:
    job = queue.get_status(group_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.__dict__
