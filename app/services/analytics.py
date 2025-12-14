from __future__ import annotations

import math
import time
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from app.db.metadata import MetadataRepository
from app.db.schema import (
    ClusteringAlgorithm,
    ClusterMembership,
    MetricType,
    QueryRecord,
    SimilarityCluster,
)
from app.utils.logging import (
    ANALYTICS_LOG_PATH,
    BufferedJsonlWriter,
    get_logger,
    log_event,
)

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class AnalyticsEvent:
    event: str
    duration_ms: float
    dataset_id: str | None = None
    tab: str | None = None
    success: bool = True
    detail: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "duration_ms": round(self.duration_ms, 3),
            "dataset_id": self.dataset_id,
            "tab": self.tab,
            "success": self.success,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
        }


class AnalyticsClient:
    """Lightweight event emitter that writes analytics JSONL with buffering."""

    def __init__(
        self,
        *,
        writer: BufferedJsonlWriter | None = None,
        log_path: str | None = None,
        buffer_size: int = 32,
    ) -> None:
        destination = Path(log_path) if log_path else ANALYTICS_LOG_PATH
        self.writer = writer or BufferedJsonlWriter(destination, buffer_size=buffer_size)
        self.logger = LOGGER

    def search_latency(
        self,
        duration_ms: float,
        *,
        dataset_id: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> AnalyticsEvent:
        return self._record(
            "search.latency",
            duration_ms,
            dataset_id=dataset_id,
            success=success,
            detail=detail,
        )

    def tab_switch_latency(
        self,
        duration_ms: float,
        *,
        tab: str | None = None,
        dataset_id: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> AnalyticsEvent:
        return self._record(
            "tab.switch.latency",
            duration_ms,
            dataset_id=dataset_id,
            tab=tab,
            success=success,
            detail=detail,
        )

    def preference_load(
        self,
        duration_ms: float,
        *,
        dataset_id: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> AnalyticsEvent:
        return self._record(
            "preference.load",
            duration_ms,
            dataset_id=dataset_id,
            success=success,
            detail=detail,
        )

    def preference_save(
        self,
        duration_ms: float,
        *,
        dataset_id: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> AnalyticsEvent:
        return self._record(
            "preference.save",
            duration_ms,
            dataset_id=dataset_id,
            success=success,
            detail=detail,
        )

    def column_selection_persist(
        self,
        duration_ms: float,
        *,
        dataset_id: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> AnalyticsEvent:
        return self._record(
            "column.selection.persist",
            duration_ms,
            dataset_id=dataset_id,
            success=success,
            detail=detail,
        )

    def flush(self) -> None:
        self.writer.flush()

    def _record(
        self,
        event: str,
        duration_ms: float,
        *,
        dataset_id: str | None,
        tab: str | None = None,
        success: bool,
        detail: str | None,
    ) -> AnalyticsEvent:
        clamped = max(0.0, float(duration_ms))
        payload = AnalyticsEvent(
            event=event,
            duration_ms=clamped,
            dataset_id=dataset_id,
            tab=tab,
            success=success,
            detail=detail,
        )
        self.writer.write(payload.to_dict())
        log_event(
            self.logger,
            event,
            duration_ms=payload.duration_ms,
            dataset_id=dataset_id,
            tab=tab,
            success=success,
            detail=detail,
            timestamp=payload.timestamp.isoformat(),
        )
        return payload


@dataclass
class ClusterAnalytics:
    cluster_id: str
    cluster_label: str
    dataset_scope: list[str]
    member_count: int
    centroid_similarity: float
    diversity_score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "cluster_id": self.cluster_id,
            "cluster_label": self.cluster_label,
            "dataset_scope": self.dataset_scope,
            "member_count": self.member_count,
            "centroid_similarity": self.centroid_similarity,
            "diversity_score": self.diversity_score,
        }


@dataclass
class CoverageSummary:
    dataset_ids: list[str]
    total_queries: int
    unique_topics_estimate: int
    redundancy_ratio: float
    last_refreshed_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_ids": self.dataset_ids,
            "total_queries": self.total_queries,
            "unique_topics_estimate": self.unique_topics_estimate,
            "redundancy_ratio": self.redundancy_ratio,
            "last_refreshed_at": self.last_refreshed_at.isoformat(),
        }


class AnalyticsService:
    """Generate local analytics for coverage diversity and cluster summaries."""

    def __init__(self, *, metadata_repository: MetadataRepository) -> None:
        self.metadata_repository = metadata_repository

    def build_clusters(self, dataset_ids: Sequence[str] | None = None) -> list[ClusterAnalytics]:
        records = self._load_records(dataset_ids=dataset_ids)
        grouped: defaultdict[tuple[str, str], list[QueryRecord]] = defaultdict(list)
        for record in records:
            scope_id = record.sheet_id or record.data_file_id
            grouped[(scope_id, record.column_name)].append(record)

        clusters: list[SimilarityCluster] = []
        memberships: list[ClusterMembership] = []
        analytics: list[ClusterAnalytics] = []

        start = time.perf_counter()
        for (scope_id, column_name), rows in grouped.items():
            dataset = rows[0].data_file
            sheet = rows[0].sheet
            cluster_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{scope_id}:{column_name}"))
            centroid_text = rows[0].text
            similarities = [self._similarity(centroid_text, row.text) for row in rows]
            average_similarity = sum(similarities) / len(similarities) if similarities else 0.0
            unique_texts = {row.text.lower().strip() for row in rows if row.text}
            diversity = len(unique_texts) / len(rows) if rows else 0.0

            cluster_label = (
                f"{sheet.display_label} · {column_name}"
                if sheet is not None
                else f"{dataset.display_name} · {column_name}" if dataset else column_name
            )

            cluster = SimilarityCluster(
                id=cluster_id,
                cluster_label=cluster_label,
                algorithm=ClusteringAlgorithm.CUSTOM,
                dataset_scope=[scope_id],
                member_count=len(rows),
                centroid_similarity=round(min(1.0, average_similarity), 4),
                diversity_score=round(min(1.0, diversity), 4),
                threshold=0.6,
            )
            clusters.append(cluster)

            for record, similarity in zip(rows, similarities, strict=False):
                memberships.append(
                    ClusterMembership(
                        cluster_id=cluster_id,
                        query_record_id=record.id,
                        similarity=round(min(1.0, similarity), 4),
                    )
                )

            analytics.append(
                ClusterAnalytics(
                    cluster_id=cluster_id,
                    cluster_label=cluster_label,
                    dataset_scope=[scope_id],
                    member_count=len(rows),
                    centroid_similarity=cluster.centroid_similarity,
                    diversity_score=cluster.diversity_score,
                )
            )

        self.metadata_repository.save_similarity_clusters(
            clusters=clusters,
            memberships=memberships,
            clear_existing=True,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        try:
            self.metadata_repository.record_performance_metric(
                metric_type=MetricType.DASHBOARD_RENDER,
                data_file_id=None,
                cluster_id=None,
                benchmark_run_id=None,
                p50_ms=elapsed_ms,
                p95_ms=elapsed_ms,
                records_per_second=None,
            )
            self.metadata_repository.session.commit()  # type: ignore[attr-defined]
        except Exception as error:  # pragma: no cover - defensive path
            LOGGER.warning("Failed to record analytics metric: %s", error)
            self.metadata_repository.session.rollback()  # type: ignore[attr-defined]
        return analytics

    def list_clusters(self, dataset_ids: Sequence[str] | None = None) -> list[ClusterAnalytics]:
        clusters = self.metadata_repository.list_similarity_clusters()
        results: list[ClusterAnalytics] = []
        for cluster in clusters:
            scope = cluster.dataset_scope or []
            if dataset_ids and not any(dataset_id in scope for dataset_id in dataset_ids):
                continue
            results.append(
                ClusterAnalytics(
                    cluster_id=cluster.id,
                    cluster_label=cluster.cluster_label,
                    dataset_scope=list(scope),
                    member_count=cluster.member_count,
                    centroid_similarity=cluster.centroid_similarity,
                    diversity_score=cluster.diversity_score,
                )
            )
        return results

    def summarize_coverage(self, dataset_ids: Sequence[str] | None = None) -> CoverageSummary:
        records = self._load_records(dataset_ids=dataset_ids)
        total = len(records)
        unique_texts = {record.text.lower().strip() for record in records if record.text}
        redundancy = 0.0
        if total:
            redundancy = 1.0 - (len(unique_texts) / total)
            redundancy = round(min(1.0, max(0.0, redundancy)), 4)

        clusters = self.list_clusters(dataset_ids=dataset_ids)
        if not clusters:
            clusters = self.build_clusters(dataset_ids=dataset_ids)

        dataset_scope = (
            list(dataset_ids)
            if dataset_ids
            else sorted({record.sheet_id or record.data_file_id for record in records})
        )
        return CoverageSummary(
            dataset_ids=dataset_scope,
            total_queries=total,
            unique_topics_estimate=len(clusters),
            redundancy_ratio=redundancy,
            last_refreshed_at=datetime.now(UTC),
        )

    def _load_records(self, dataset_ids: Sequence[str] | None) -> list[QueryRecord]:
        results = list(
            self.metadata_repository.fetch_search_candidates(
                dataset_ids=dataset_ids,
                column_names=None,
                max_records=None,
            )
        )
        if dataset_ids:
            scope = set(dataset_ids)
            results = [
                record
                for record in results
                if (record.sheet_id and record.sheet_id in scope) or (record.data_file_id in scope)
            ]
        return results

    def _similarity(self, first: str, second: str) -> float:
        if not first or not second:
            return 0.0
        ratio = SequenceMatcher(None, first.lower(), second.lower()).ratio()
        if math.isnan(ratio):  # pragma: no cover
            return 0.0
        return ratio
