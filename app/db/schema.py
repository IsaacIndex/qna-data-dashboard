from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for application metadata models."""


class FileType(str, enum.Enum):
    CSV = "csv"
    EXCEL = "excel"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class AuditStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricType(str, enum.Enum):
    INGESTION = "ingestion"
    EMBEDDING = "embedding"
    SEARCH = "search"
    DASHBOARD_RENDER = "dashboard_render"


class SheetVisibilityState(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN_OPT_IN = "hidden_opt_in"


class SheetStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class SheetMetricType(str, enum.Enum):
    INGESTION_DURATION_MS = "ingestion_duration_ms"
    QUERY_P95_MS = "query_p95_ms"


class QuerySheetRole(str, enum.Enum):
    PRIMARY = "primary"
    JOIN = "join"
    UNION = "union"


class ClusteringAlgorithm(str, enum.Enum):
    HDBSCAN = "hdbscan"
    KMEANS = "kmeans"
    CUSTOM = "custom"


class DataFile(Base):
    __tablename__ = "data_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    display_name: Mapped[str] = mapped_column(String(255))
    original_path: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType, name="file_type"))
    delimiter: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    selected_columns: Mapped[list[str]] = mapped_column(JSON, default=list)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status"), default=IngestionStatus.PENDING
    )
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    records: Mapped[list[QueryRecord]] = relationship(
        back_populates="data_file", cascade="all, delete-orphan"
    )
    audits: Mapped[list[IngestionAudit]] = relationship(
        back_populates="data_file",
        cascade="all, delete-orphan",
        order_by="IngestionAudit.started_at.desc()",
    )
    column_preferences: Mapped[list["ColumnPreference"]] = relationship(
        back_populates="data_file",
        cascade="all, delete-orphan",
        order_by="ColumnPreference.updated_at.desc()",
    )


class SourceBundle(Base):
    __tablename__ = "source_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    display_name: Mapped[str] = mapped_column(String(255))
    original_path: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType, name="bundle_file_type"))
    delimiter: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    refresh_cadence: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="bundle_ingestion_status"), default=IngestionStatus.PENDING
    )
    sheet_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    owner_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    sheets: Mapped[list["SheetSource"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan", order_by="SheetSource.position_index"
    )
    audits: Mapped[list["BundleAudit"]] = relationship(
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="BundleAudit.started_at.desc()",
    )


class SheetSource(Base):
    __tablename__ = "sheet_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    bundle_id: Mapped[str] = mapped_column(ForeignKey("source_bundles.id", ondelete="CASCADE"))
    sheet_name: Mapped[str] = mapped_column(String(255))
    display_label: Mapped[str] = mapped_column(String(255))
    visibility_state: Mapped[SheetVisibilityState] = mapped_column(
        Enum(SheetVisibilityState, name="sheet_visibility_state"), default=SheetVisibilityState.VISIBLE
    )
    status: Mapped[SheetStatus] = mapped_column(
        Enum(SheetStatus, name="sheet_status"), default=SheetStatus.ACTIVE
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_schema: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_index: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)

    bundle: Mapped[SourceBundle] = relationship(back_populates="sheets")
    records: Mapped[list["QueryRecord"]] = relationship(back_populates="sheet")
    metrics: Mapped[list["SheetMetric"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan", order_by="SheetMetric.recorded_at.desc()"
    )
    query_links: Mapped[list["QuerySheetLink"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("bundle_id", "sheet_name", name="uq_sheet_unique_per_bundle"),
    )


class BundleAudit(Base):
    __tablename__ = "bundle_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    bundle_id: Mapped[str] = mapped_column(ForeignKey("source_bundles.id", ondelete="CASCADE"))
    status: Mapped[AuditStatus] = mapped_column(Enum(AuditStatus, name="bundle_audit_status"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sheet_summary: Mapped[Optional[dict[str, int]]] = mapped_column(JSON, nullable=True)
    hidden_sheets_enabled: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    initiated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    bundle: Mapped[SourceBundle] = relationship(back_populates="audits")


class SheetMetric(Base):
    __tablename__ = "sheet_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    sheet_id: Mapped[str] = mapped_column(ForeignKey("sheet_sources.id", ondelete="CASCADE"))
    metric_type: Mapped[SheetMetricType] = mapped_column(
        Enum(SheetMetricType, name="sheet_metric_type")
    )
    p50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p95: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    sheet: Mapped[SheetSource] = relationship(back_populates="metrics")


class QueryDefinition(Base):
    __tablename__ = "query_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    definition: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    validation_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    sheet_links: Mapped[list["QuerySheetLink"]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )


class QuerySheetLink(Base):
    __tablename__ = "query_sheet_links"

    query_id: Mapped[str] = mapped_column(
        ForeignKey("query_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    sheet_id: Mapped[str] = mapped_column(
        ForeignKey("sheet_sources.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[QuerySheetRole] = mapped_column(
        Enum(QuerySheetRole, name="query_sheet_role"), default=QuerySheetRole.PRIMARY
    )
    join_keys: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    query: Mapped[QueryDefinition] = relationship(back_populates="sheet_links")
    sheet: Mapped[SheetSource] = relationship(back_populates="query_links")


class QueryRecord(Base):
    __tablename__ = "query_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    data_file_id: Mapped[str] = mapped_column(ForeignKey("data_files.id", ondelete="CASCADE"))
    sheet_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sheet_sources.id", ondelete="SET NULL"), nullable=True
    )
    column_name: Mapped[str] = mapped_column(String(255))
    row_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    original_text: Mapped[str] = mapped_column(Text)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    data_file: Mapped[DataFile] = relationship(back_populates="records")
    sheet: Mapped[Optional[SheetSource]] = relationship(back_populates="records")
    embedding: Mapped["EmbeddingVector"] = relationship(
        back_populates="record", uselist=False, cascade="all, delete-orphan"
    )
    clusters: Mapped[list["ClusterMembership"]] = relationship(
        back_populates="record", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("data_file_id", "column_name", "row_index", name="uq_record_index"),
    )


class EmbeddingVector(Base):
    __tablename__ = "embedding_vectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    query_record_id: Mapped[str] = mapped_column(
        ForeignKey("query_records.id", ondelete="CASCADE"), unique=True
    )
    model_name: Mapped[str] = mapped_column(String(255))
    model_version: Mapped[str] = mapped_column(String(255))
    vector_path: Mapped[str] = mapped_column(String(255))
    embedding_dim: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    record: Mapped[QueryRecord] = relationship(back_populates="embedding")


class SimilarityCluster(Base):
    __tablename__ = "similarity_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    cluster_label: Mapped[str] = mapped_column(String(255))
    algorithm: Mapped[ClusteringAlgorithm] = mapped_column(
        Enum(ClusteringAlgorithm, name="cluster_algorithm")
    )
    dataset_scope: Mapped[list[str]] = mapped_column(JSON)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    centroid_similarity: Mapped[float] = mapped_column(Float)
    diversity_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    threshold: Mapped[float] = mapped_column(Float)

    memberships: Mapped[list["ClusterMembership"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class ClusterMembership(Base):
    __tablename__ = "cluster_memberships"

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey("similarity_clusters.id", ondelete="CASCADE"), primary_key=True
    )
    query_record_id: Mapped[str] = mapped_column(
        ForeignKey("query_records.id", ondelete="CASCADE"), primary_key=True
    )
    similarity: Mapped[float] = mapped_column(Float)

    cluster: Mapped[SimilarityCluster] = relationship(back_populates="memberships")
    record: Mapped[QueryRecord] = relationship(back_populates="clusters")


class IngestionAudit(Base):
    __tablename__ = "ingestion_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    data_file_id: Mapped[str] = mapped_column(ForeignKey("data_files.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[AuditStatus] = mapped_column(Enum(AuditStatus, name="audit_status"))
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_log_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    data_file: Mapped[DataFile] = relationship(back_populates="audits")


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType, name="metric_type"))
    data_file_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("data_files.id", ondelete="SET NULL"), nullable=True
    )
    cluster_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("similarity_clusters.id", ondelete="SET NULL"), nullable=True
    )
    benchmark_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    p50_ms: Mapped[float] = mapped_column(Float)
    p95_ms: Mapped[float] = mapped_column(Float)
    records_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    data_file: Mapped[Optional[DataFile]] = relationship()
    cluster: Mapped[Optional[SimilarityCluster]] = relationship()


class ColumnPreference(Base):
    __tablename__ = "column_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    data_file_id: Mapped[str] = mapped_column(ForeignKey("data_files.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    selected_columns: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    max_columns: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    data_file: Mapped[DataFile] = relationship(back_populates="column_preferences")
    changes: Mapped[list["ColumnPreferenceChange"]] = relationship(
        back_populates="preference",
        cascade="all, delete-orphan",
        order_by="ColumnPreferenceChange.changed_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint("data_file_id", "user_id", name="uq_column_preference_dataset_user"),
    )


class ColumnPreferenceChange(Base):
    __tablename__ = "column_preference_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    preference_id: Mapped[str] = mapped_column(
        ForeignKey("column_preferences.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(64))
    dataset_display_name: Mapped[str] = mapped_column(String(255))
    selected_columns_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    preference: Mapped[ColumnPreference] = relationship(back_populates="changes")
