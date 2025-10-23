from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.schema import (
    DataFile,
    FileType,
    IngestionStatus,
    SheetSource,
    SheetStatus,
    SheetVisibilityState,
    SourceBundle,
)


def run(engine: Engine) -> None:
    """
    002_sheet_sources: Backfill legacy DataFile rows into SourceBundle/SheetSource tables.

    The migration is idempotent: if bundles already exist the routine exits early.
    """

    with Session(engine) as session:
        existing_bundles = session.execute(
            select(func.count(SourceBundle.id))  # type: ignore[arg-type]
        ).scalar_one()
        if existing_bundles:
            return

        data_files = session.execute(select(DataFile)).scalars().all()
        if not data_files:
            return

        for index, data_file in enumerate(data_files):
            bundle = SourceBundle(
                display_name=data_file.display_name,
                original_path=data_file.original_path,
                file_hash=data_file.file_hash,
                file_type=data_file.file_type,
                delimiter=data_file.delimiter,
                ingestion_status=data_file.ingestion_status,
                sheet_count=1,
                created_at=data_file.ingested_at,
                updated_at=data_file.processed_at or data_file.ingested_at,
            )
            session.add(bundle)

            sheet_name = _derive_sheet_name(data_file)
            display_label = f"{bundle.display_name}:{sheet_name}"
            status = (
                SheetStatus.ACTIVE
                if data_file.ingestion_status == IngestionStatus.READY
                else SheetStatus.INACTIVE
            )

            sheet = SheetSource(
                bundle=bundle,
                sheet_name=sheet_name,
                display_label=display_label,
                visibility_state=SheetVisibilityState.VISIBLE,
                status=status,
                row_count=data_file.row_count,
                column_schema=[],
                last_refreshed_at=data_file.processed_at,
                checksum=data_file.file_hash,
                position_index=index,
            )
            session.add(sheet)

        session.commit()


def _derive_sheet_name(data_file: DataFile) -> str:
    if data_file.sheet_name:
        return data_file.sheet_name
    if data_file.file_type == FileType.CSV:
        return "__csv__"
    return "Sheet1"
