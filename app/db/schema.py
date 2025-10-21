from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class QueryRecord(Base):
    __tablename__ = "query_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    data_file_id: Mapped[str] = mapped_column(ForeignKey("data_files.id", ondelete="CASCADE"))
    column_name: Mapped[str] = mapped_column(String(255))
    row_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    original_text: Mapped[str] = mapped_column(Text)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    data_file: Mapped[DataFile] = relationship(back_populates="records")
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
