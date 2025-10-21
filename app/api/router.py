from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status

from app.db.metadata import (
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionOptions, IngestionService


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

    return app
