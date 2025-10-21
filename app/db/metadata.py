from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from sqlalchemy import Select, create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from .schema import (
    AuditStatus,
    Base,
    ClusterMembership,
    DataFile,
    EmbeddingVector,
    FileType,
    IngestionAudit,
    IngestionStatus,
    MetricType,
    PerformanceMetric,
    QueryRecord,
    SimilarityCluster,
)

DEFAULT_SQLITE_URL = "sqlite:///data/metadata.db"


def _resolve_sqlite_url(url: str | None = None) -> str:
    resolved = url or os.getenv("SQLITE_URL", DEFAULT_SQLITE_URL)
    if resolved.startswith("sqlite:///"):
        db_path = Path(resolved.replace("sqlite:///", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def build_engine(url: str | None = None) -> Engine:
    resolved = _resolve_sqlite_url(url)
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    return create_engine(resolved, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class MetadataRepository:
    """Data access helpers for SQLite-backed metadata and analytics."""

    def __init__(self, session: Session):
        self.session = session

    # Dataset helpers -----------------------------------------------------
    def list_data_files(self) -> Sequence[DataFile]:
        stmt: Select[tuple[DataFile]] = select(DataFile)
        return self.session.execute(stmt).scalars().all()

    def get_data_file(self, data_file_id: str) -> DataFile | None:
        return self.session.get(DataFile, data_file_id)

    def get_data_file_by_hash(self, file_hash: str) -> DataFile | None:
        stmt: Select[tuple[DataFile]] = select(DataFile).where(DataFile.file_hash == file_hash)
        return self.session.execute(stmt).scalars().first()

    def create_data_file(
        self,
        *,
        display_name: str,
        original_path: str,
        file_hash: str,
        file_type: FileType,
        delimiter: str | None,
        sheet_name: str | None,
        selected_columns: Sequence[str],
        status: IngestionStatus = IngestionStatus.PENDING,
    ) -> DataFile:
        data_file = DataFile(
            display_name=display_name,
            original_path=original_path,
            file_hash=file_hash,
            file_type=file_type,
            delimiter=delimiter,
            sheet_name=sheet_name,
            selected_columns=list(selected_columns),
            ingestion_status=status,
        )
        self.session.add(data_file)
        return data_file

    def update_data_file_status(
        self,
        data_file: DataFile,
        *,
        status: IngestionStatus,
        row_count: int | None = None,
        error_summary: str | None = None,
        processed_at: datetime | None = None,
    ) -> DataFile:
        data_file.ingestion_status = status
        if row_count is not None:
            data_file.row_count = row_count
        data_file.error_summary = error_summary
        if processed_at is not None:
            data_file.processed_at = processed_at
        return data_file

    def fetch_search_candidates(
        self,
        *,
        dataset_ids: Sequence[str] | None = None,
        column_names: Sequence[str] | None = None,
        max_records: int | None = 5000,
    ) -> Sequence[QueryRecord]:
        stmt: Select[tuple[QueryRecord]] = (
            select(QueryRecord)
            .options(joinedload(QueryRecord.data_file))
            .order_by(QueryRecord.created_at.desc())
        )
        if dataset_ids:
            stmt = stmt.where(QueryRecord.data_file_id.in_(tuple(dataset_ids)))
        if column_names:
            stmt = stmt.where(QueryRecord.column_name.in_(tuple(column_names)))
        if max_records is not None:
            stmt = stmt.limit(max(1, max_records))
        return self.session.execute(stmt).scalars().all()

    # Query records -------------------------------------------------------
    def replace_query_records(
        self,
        data_file: DataFile,
        records: Iterable[QueryRecord],
    ) -> None:
        existing = select(QueryRecord).where(QueryRecord.data_file_id == data_file.id)
        for record in self.session.execute(existing).scalars():
            self.session.delete(record)
        for record in records:
            self.session.add(record)

    def create_query_record(
        self,
        *,
        data_file_id: str,
        column_name: str,
        row_index: int,
        text: str,
        original_text: str,
        tags: Sequence[str] | None = None,
    ) -> QueryRecord:
        record = QueryRecord(
            data_file_id=data_file_id,
            column_name=column_name,
            row_index=row_index,
            text=text,
            original_text=original_text,
            tags=list(tags) if tags else None,
        )
        self.session.add(record)
        return record

    # Embeddings ----------------------------------------------------------
    def upsert_embedding(
        self,
        *,
        record_id: str,
        model_name: str,
        model_version: str,
        vector_path: str,
        embedding_dim: int,
    ) -> EmbeddingVector:
        stmt = select(EmbeddingVector).where(EmbeddingVector.query_record_id == record_id)
        embedding = self.session.execute(stmt).scalars().first()
        if embedding is None:
            embedding = EmbeddingVector(
                query_record_id=record_id,
                model_name=model_name,
                model_version=model_version,
                vector_path=vector_path,
                embedding_dim=embedding_dim,
            )
            self.session.add(embedding)
        else:
            embedding.model_name = model_name
            embedding.model_version = model_version
            embedding.vector_path = vector_path
            embedding.embedding_dim = embedding_dim
        return embedding

    # Clusters ------------------------------------------------------------
    def save_similarity_clusters(
        self,
        *,
        clusters: Iterable[SimilarityCluster],
        memberships: Iterable[ClusterMembership],
        clear_existing: bool = True,
    ) -> None:
        if clear_existing:
            self.session.execute(delete(ClusterMembership))
            self.session.execute(delete(SimilarityCluster))
        for cluster in clusters:
            self.session.merge(cluster)
        for membership in memberships:
            self.session.merge(membership)

    def list_similarity_clusters(self) -> Sequence[SimilarityCluster]:
        stmt: Select[tuple[SimilarityCluster]] = select(SimilarityCluster)
        return self.session.execute(stmt).scalars().all()

    # Audits --------------------------------------------------------------
    def create_audit(
        self,
        *,
        data_file_id: str,
        status: AuditStatus,
        processed_rows: int,
        skipped_rows: int,
        error_log_path: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> IngestionAudit:
        audit = IngestionAudit(
            data_file_id=data_file_id,
            status=status,
            processed_rows=processed_rows,
            skipped_rows=skipped_rows,
            error_log_path=error_log_path,
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=completed_at,
        )
        self.session.add(audit)
        return audit

    def get_latest_audit(self, data_file_id: str) -> IngestionAudit | None:
        stmt = (
            select(IngestionAudit)
            .where(IngestionAudit.data_file_id == data_file_id)
            .order_by(IngestionAudit.started_at.desc())
        )
        return self.session.execute(stmt).scalars().first()

    # Performance metrics -------------------------------------------------
    def record_performance_metric(
        self,
        *,
        metric_type: MetricType,
        data_file_id: str | None,
        cluster_id: str | None,
        benchmark_run_id: str | None,
        p50_ms: float,
        p95_ms: float,
        records_per_second: float | None,
    ) -> PerformanceMetric:
        metric = PerformanceMetric(
            metric_type=metric_type,
            data_file_id=data_file_id,
            cluster_id=cluster_id,
            benchmark_run_id=benchmark_run_id,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            records_per_second=records_per_second,
        )
        self.session.add(metric)
        return metric
