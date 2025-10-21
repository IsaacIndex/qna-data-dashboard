from __future__ import annotations

import csv
import hashlib
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

try:  # Optional dependency for Excel ingestion
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - optional path
    load_workbook = None

from app.db.metadata import MetadataRepository
from app.db.schema import (
    AuditStatus,
    DataFile,
    FileType,
    IngestionStatus,
    MetricType,
    QueryRecord,
)
from app.services.embeddings import EmbeddingJob, EmbeddingService, EmbeddingSummary
from app.utils.logging import get_logger, log_timing

LOGGER = get_logger(__name__)


@dataclass
class IngestionOptions:
    selected_columns: Sequence[str]
    delimiter: Optional[str] = None
    sheet_name: Optional[str] = None
    encoding: str = "utf-8"
    allow_duplicate_import: bool = False


@dataclass
class IngestionResult:
    data_file: DataFile
    embedding_summary: EmbeddingSummary
    processed_rows: int
    skipped_rows: int


class IngestionService:
    def __init__(
        self,
        *,
        metadata_repository: MetadataRepository,
        embedding_service: EmbeddingService,
        data_root: Path | str,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.embedding_service = embedding_service
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        (self.data_root / "raw").mkdir(parents=True, exist_ok=True)

    def ingest_file(
        self,
        *,
        source_path: Path,
        display_name: str,
        options: IngestionOptions,
    ) -> IngestionResult:
        if not options.selected_columns:
            raise ValueError("At least one column must be selected for ingestion.")
        if not source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {source_path}")

        start_time = datetime.now(timezone.utc)
        timer = time.perf_counter()

        file_hash = self._hash_file(source_path)
        existing = self.metadata_repository.get_data_file_by_hash(file_hash)
        if existing and not options.allow_duplicate_import:
            raise ValueError("Dataset with identical content already ingested.")

        file_type = self._infer_file_type(source_path)
        data_file = self.metadata_repository.create_data_file(
            display_name=display_name,
            original_path=str(source_path.resolve()),
            file_hash=file_hash,
            file_type=file_type,
            delimiter=options.delimiter,
            sheet_name=options.sheet_name,
            selected_columns=options.selected_columns,
            status=IngestionStatus.PROCESSING,
        )
        self.metadata_repository.session.flush()  # type: ignore[attr-defined]

        copied_path = self._copy_raw_file(source_path, data_file)

        try:
            with log_timing(LOGGER, "ingestion.load_records", dataset_id=data_file.id):
                columns, rows = self._load_rows(copied_path, file_type, options)
            records, skipped_rows = self._materialize_records(
                rows=rows,
                columns=columns,
                data_file=data_file,
                selected_columns=options.selected_columns,
            )
            processed_rows = len(records)
            if processed_rows == 0:
                raise ValueError("No valid textual rows found for the selected columns.")

            embedding_summary = self.embedding_service.run_embedding(
                EmbeddingJob(
                    data_file=data_file,
                    records=records,
                    metadata_repository=self.metadata_repository,
                )
            )

            self.metadata_repository.update_data_file_status(
                data_file,
                status=IngestionStatus.READY,
                row_count=processed_rows,
                error_summary=None,
                processed_at=datetime.now(timezone.utc),
            )

            elapsed_ms = (time.perf_counter() - timer) * 1000.0
            records_per_second = processed_rows / (elapsed_ms / 1000.0) if elapsed_ms else None

            self.metadata_repository.create_audit(
                data_file_id=data_file.id,
                status=AuditStatus.SUCCEEDED,
                processed_rows=processed_rows,
                skipped_rows=skipped_rows,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
            )

            self.metadata_repository.record_performance_metric(
                metric_type=MetricType.INGESTION,
                data_file_id=data_file.id,
                cluster_id=None,
                benchmark_run_id=None,
                p50_ms=elapsed_ms,
                p95_ms=elapsed_ms,
                records_per_second=records_per_second,
            )

            self.metadata_repository.session.commit()  # type: ignore[attr-defined]

            return IngestionResult(
                data_file=data_file,
                embedding_summary=embedding_summary,
                processed_rows=processed_rows,
                skipped_rows=skipped_rows,
            )
        except Exception as error:
            LOGGER.exception("Ingestion failed for dataset %s: %s", data_file.id, error)
            self.metadata_repository.update_data_file_status(
                data_file,
                status=IngestionStatus.FAILED,
                error_summary=str(error),
            )
            self.metadata_repository.create_audit(
                data_file_id=data_file.id,
                status=AuditStatus.FAILED,
                processed_rows=0,
                skipped_rows=0,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
            )
            self.metadata_repository.session.commit()  # type: ignore[attr-defined]
            raise

    def _hash_file(self, path: Path) -> str:
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _infer_file_type(self, path: Path) -> FileType:
        extension = path.suffix.lower()
        if extension in {".csv", ".tsv"}:
            return FileType.CSV
        if extension in {".xls", ".xlsx"}:
            return FileType.EXCEL
        raise ValueError(f"Unsupported file type: {extension}")

    def _copy_raw_file(self, source: Path, data_file: DataFile) -> Path:
        destination_dir = self.data_root / "raw" / data_file.id
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        shutil.copy2(source, destination)
        return destination

    def _load_rows(
        self,
        path: Path,
        file_type: FileType,
        options: IngestionOptions,
    ) -> tuple[list[str], list[dict[str, object]]]:
        if file_type == FileType.CSV:
            delimiter = options.delimiter or ","
            with path.open("r", encoding=options.encoding, newline="") as handle:
                reader = csv.DictReader(handle, delimiter=delimiter)
                rows = [dict(row) for row in reader]
                columns = reader.fieldnames or []
            return columns, rows

        if load_workbook is None:
            raise RuntimeError("Excel ingestion requires the 'openpyxl' dependency.")

        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet_name = options.sheet_name or workbook.sheetnames[0]
        if sheet_name not in workbook.sheetnames:
            raise ValueError(f"Sheet '{sheet_name}' not found in workbook.")

        sheet = workbook[sheet_name]
        iterator = sheet.iter_rows(values_only=True)
        try:
            headers_row = next(iterator)
        except StopIteration:
            return [], []

        columns = [str(value) if value is not None else "" for value in headers_row]
        rows: list[dict[str, object]] = []
        for values in iterator:
            row_map: dict[str, object] = {}
            for index, column in enumerate(columns):
                if not column:
                    continue
                cell_value = None
                if values is not None and index < len(values):
                    cell_value = values[index]
                row_map[column] = cell_value
            rows.append(row_map)
        workbook.close()
        return columns, rows

    def _materialize_records(
        self,
        *,
        rows: list[dict[str, object]],
        columns: Sequence[str],
        data_file: DataFile,
        selected_columns: Sequence[str],
    ) -> tuple[list[QueryRecord], int]:
        missing = [column for column in selected_columns if column not in columns]
        if missing:
            raise ValueError(f"Selected columns not found in source: {missing}")

        records: list[QueryRecord] = []
        skipped = 0

        for index, row in enumerate(rows):
            for column in selected_columns:
                original_value = row.get(column)
                text = self._normalize_text(original_value)
                if not text:
                    skipped += 1
                    continue
                record = self.metadata_repository.create_query_record(
                    data_file_id=data_file.id,
                    column_name=str(column),
                    row_index=int(index),
                    text=text,
                    original_text=str(original_value) if original_value is not None else "",
                    tags=None,
                )
                records.append(record)
        self.metadata_repository.session.flush()  # type: ignore[attr-defined]
        return records, skipped

    def _normalize_text(self, value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.isnumeric():
            return None
        text = " ".join(text.split())
        return text
