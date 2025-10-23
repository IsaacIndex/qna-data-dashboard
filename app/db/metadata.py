from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from sqlalchemy import Select, create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from .migrations import run_migrations
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
    BundleAudit,
    PerformanceMetric,
    QueryDefinition,
    QueryRecord,
    QuerySheetLink,
    QuerySheetRole,
    SheetMetric,
    SheetMetricType,
    SheetSource,
    SheetStatus,
    SheetVisibilityState,
    SimilarityCluster,
    SourceBundle,
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
    run_migrations(engine)


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

    # Source bundle helpers -------------------------------------------
    def list_source_bundles(self) -> Sequence[SourceBundle]:
        stmt: Select[tuple[SourceBundle]] = select(SourceBundle).order_by(SourceBundle.created_at.desc())
        return self.session.execute(stmt).scalars().all()

    def get_source_bundle(self, bundle_id: str) -> SourceBundle | None:
        return self.session.get(SourceBundle, bundle_id)

    def get_source_bundle_by_hash(self, file_hash: str) -> SourceBundle | None:
        stmt: Select[tuple[SourceBundle]] = select(SourceBundle).where(SourceBundle.file_hash == file_hash)
        return self.session.execute(stmt).scalars().first()

    def create_source_bundle(
        self,
        *,
        display_name: str,
        original_path: str,
        file_hash: str,
        file_type: FileType,
        delimiter: str | None,
        refresh_cadence: str | None,
        owner_user_id: str | None = None,
        ingestion_status: IngestionStatus = IngestionStatus.PENDING,
    ) -> SourceBundle:
        bundle = SourceBundle(
            display_name=display_name,
            original_path=original_path,
            file_hash=file_hash,
            file_type=file_type,
            delimiter=delimiter,
            refresh_cadence=refresh_cadence,
            ingestion_status=ingestion_status,
            owner_user_id=owner_user_id,
        )
        self.session.add(bundle)
        return bundle

    def update_source_bundle(
        self,
        bundle: SourceBundle,
        *,
        ingestion_status: IngestionStatus | None = None,
        sheet_count: int | None = None,
        refresh_cadence: str | None = None,
        original_path: str | None = None,
    ) -> SourceBundle:
        if ingestion_status is not None:
            bundle.ingestion_status = ingestion_status
        if sheet_count is not None:
            bundle.sheet_count = sheet_count
        if refresh_cadence is not None:
            bundle.refresh_cadence = refresh_cadence
        if original_path is not None:
            bundle.original_path = original_path
        bundle.updated_at = datetime.now(timezone.utc)
        return bundle

    # Sheet source helpers --------------------------------------------
    def list_sheet_sources(
        self,
        *,
        bundle_id: str | None = None,
        statuses: Sequence[SheetStatus] | None = None,
    ) -> Sequence[SheetSource]:
        stmt: Select[tuple[SheetSource]] = select(SheetSource)
        if bundle_id:
            stmt = stmt.where(SheetSource.bundle_id == bundle_id)
        if statuses:
            stmt = stmt.where(SheetSource.status.in_(tuple(statuses)))
        stmt = stmt.order_by(SheetSource.position_index.asc())
        return self.session.execute(stmt).scalars().all()

    def get_sheet_source(self, sheet_id: str) -> SheetSource | None:
        return self.session.get(SheetSource, sheet_id)

    def create_sheet_source(
        self,
        *,
        bundle: SourceBundle,
        sheet_name: str,
        display_label: str,
        visibility_state: SheetVisibilityState,
        status: SheetStatus,
        row_count: int,
        column_schema: Sequence[dict[str, object]],
        position_index: int,
        checksum: str | None,
        description: str | None = None,
        tags: Sequence[str] | None = None,
        last_refreshed_at: datetime | None = None,
    ) -> SheetSource:
        sheet = SheetSource(
            bundle=bundle,
            sheet_name=sheet_name,
            display_label=display_label,
            visibility_state=visibility_state,
            status=status,
            row_count=row_count,
            column_schema=list(column_schema),
            position_index=position_index,
            checksum=checksum,
            description=description,
            tags=list(tags) if tags else None,
            last_refreshed_at=last_refreshed_at,
        )
        self.session.add(sheet)
        return sheet

    def update_sheet_source(
        self,
        sheet: SheetSource,
        *,
        sheet_name: str | None = None,
        display_label: str | None = None,
        visibility_state: SheetVisibilityState | None = None,
        status: SheetStatus | None = None,
        row_count: int | None = None,
        column_schema: Sequence[dict[str, object]] | None = None,
        checksum: str | None = None,
        description: str | None = None,
        tags: Sequence[str] | None = None,
        last_refreshed_at: datetime | None = None,
        position_index: int | None = None,
    ) -> SheetSource:
        if sheet_name is not None:
            sheet.sheet_name = sheet_name
        if display_label is not None:
            sheet.display_label = display_label
        if visibility_state is not None:
            sheet.visibility_state = visibility_state
        if status is not None:
            sheet.status = status
        if row_count is not None:
            sheet.row_count = row_count
        if column_schema is not None:
            sheet.column_schema = list(column_schema)
        if checksum is not None:
            sheet.checksum = checksum
        if description is not None:
            sheet.description = description
        if tags is not None:
            sheet.tags = list(tags)
        if last_refreshed_at is not None:
            sheet.last_refreshed_at = last_refreshed_at
        if position_index is not None:
            sheet.position_index = position_index
        return sheet

    def fetch_search_candidates(
        self,
        *,
        dataset_ids: Sequence[str] | None = None,
        column_names: Sequence[str] | None = None,
        max_records: int | None = 5000,
    ) -> Sequence[QueryRecord]:
        stmt: Select[tuple[QueryRecord]] = (
            select(QueryRecord)
            .options(
                joinedload(QueryRecord.data_file),
                joinedload(QueryRecord.sheet),
            )
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
        sheet_id: str | None = None,
    ) -> QueryRecord:
        record = QueryRecord(
            data_file_id=data_file_id,
            column_name=column_name,
            row_index=row_index,
            text=text,
            original_text=original_text,
            tags=list(tags) if tags else None,
            sheet_id=sheet_id,
        )
        self.session.add(record)
        return record

    def delete_query_records_for_sheet(self, sheet_id: str) -> None:
        stmt: Select[tuple[QueryRecord]] = select(QueryRecord).where(QueryRecord.sheet_id == sheet_id)
        for record in self.session.execute(stmt).scalars():
            self.session.delete(record)

    # Sheet lifecycle audits ------------------------------------------
    def create_bundle_audit(
        self,
        *,
        bundle: SourceBundle,
        status: AuditStatus,
        started_at: datetime,
        completed_at: datetime | None,
        sheet_summary: dict[str, int] | None = None,
        hidden_sheets_enabled: Sequence[str] | None = None,
        initiated_by: str | None = None,
    ) -> BundleAudit:
        audit = BundleAudit(
            bundle=bundle,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            sheet_summary=dict(sheet_summary) if sheet_summary else None,
            hidden_sheets_enabled=list(hidden_sheets_enabled) if hidden_sheets_enabled else None,
            initiated_by=initiated_by,
        )
        self.session.add(audit)
        return audit

    def get_latest_bundle_audit(self, bundle_id: str) -> BundleAudit | None:
        stmt = (
            select(BundleAudit)
            .where(BundleAudit.bundle_id == bundle_id)
            .order_by(BundleAudit.started_at.desc())
        )
        return self.session.execute(stmt).scalars().first()

    # Sheet metrics ----------------------------------------------------
    def record_sheet_metric(
        self,
        *,
        sheet: SheetSource,
        metric_type: SheetMetricType,
        p50: float | None,
        p95: float | None,
        recorded_at: datetime | None = None,
    ) -> SheetMetric:
        metric = SheetMetric(
            sheet=sheet,
            metric_type=metric_type,
            p50=p50,
            p95=p95,
            recorded_at=recorded_at or datetime.now(timezone.utc),
        )
        self.session.add(metric)
        return metric

    # Query definitions ------------------------------------------------
    def list_query_definitions(self) -> Sequence[QueryDefinition]:
        stmt: Select[tuple[QueryDefinition]] = select(QueryDefinition).order_by(QueryDefinition.created_at.desc())
        return self.session.execute(stmt).scalars().all()

    def get_query_definition(self, query_id: str) -> QueryDefinition | None:
        return self.session.get(QueryDefinition, query_id)

    def create_query_definition(
        self,
        *,
        name: str,
        definition: dict[str, object],
        description: str | None = None,
        validation_checksum: str | None = None,
    ) -> QueryDefinition:
        query = QueryDefinition(
            name=name,
            description=description,
            definition=dict(definition),
            validation_checksum=validation_checksum,
        )
        self.session.add(query)
        return query

    def update_query_definition(
        self,
        query: QueryDefinition,
        *,
        description: str | None = None,
        definition: dict[str, object] | None = None,
        validation_checksum: str | None = None,
    ) -> QueryDefinition:
        if description is not None:
            query.description = description
        if definition is not None:
            query.definition = dict(definition)
        if validation_checksum is not None:
            query.validation_checksum = validation_checksum
        query.updated_at = datetime.now(timezone.utc)
        return query

    def create_query_with_links(
        self,
        *,
        name: str,
        definition: dict[str, object],
        description: str | None,
        sheet_links: Sequence[tuple[str, QuerySheetRole, Sequence[str] | None, datetime | None]],
        validation_checksum: str | None = None,
    ) -> QueryDefinition:
        query = self.create_query_definition(
            name=name,
            description=description,
            definition=definition,
            validation_checksum=validation_checksum,
        )
        self.set_query_sheet_links(query=query, links=sheet_links)
        return query

    def update_query_with_links(
        self,
        *,
        query: QueryDefinition,
        definition: dict[str, object] | None,
        description: str | None,
        sheet_links: Sequence[tuple[str, QuerySheetRole, Sequence[str] | None, datetime | None]],
        validation_checksum: str | None = None,
    ) -> QueryDefinition:
        updated = self.update_query_definition(
            query,
            description=description,
            definition=definition,
            validation_checksum=validation_checksum,
        )
        self.set_query_sheet_links(query=updated, links=sheet_links)
        return updated

    def set_query_sheet_links(
        self,
        *,
        query: QueryDefinition,
        links: Sequence[tuple[str, QuerySheetRole, Sequence[str] | None, datetime | None]],
    ) -> None:
        self.session.execute(delete(QuerySheetLink).where(QuerySheetLink.query_id == query.id))
        for sheet_id, role, join_keys, last_validated_at in links:
            link = QuerySheetLink(
                query_id=query.id,
                sheet_id=sheet_id,
                role=role,
                join_keys=list(join_keys) if join_keys else None,
                last_validated_at=last_validated_at,
            )
            self.session.add(link)

    def list_query_links_for_sheet(self, sheet_id: str) -> Sequence[QuerySheetLink]:
        stmt: Select[tuple[QuerySheetLink]] = select(QuerySheetLink).where(QuerySheetLink.sheet_id == sheet_id)
        return self.session.execute(stmt).scalars().all()

    def list_query_definitions_with_links(self) -> Sequence[QueryDefinition]:
        stmt: Select[tuple[QueryDefinition]] = (
            select(QueryDefinition)
            .options(joinedload(QueryDefinition.sheet_links))
            .order_by(QueryDefinition.created_at.desc())
        )
        return self.session.execute(stmt).scalars().all()

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
