from __future__ import annotations

import math
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Sequence

from app.db.metadata import MetadataRepository
from app.db.schema import MetricType, QueryRecord
from app.utils.logging import get_logger

LOGGER = get_logger(__name__)


@dataclass
class SearchResult:
    record_id: str
    dataset_id: str
    dataset_name: str
    column_name: str
    row_index: int
    text: str
    similarity: float
    metadata: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "column_name": self.column_name,
            "row_index": self.row_index,
            "text": self.text,
            "similarity": self.similarity,
            "metadata": self.metadata,
        }


class SearchService:
    """Lightweight semantic search using local metadata and string similarity."""

    def __init__(
        self,
        *,
        metadata_repository: MetadataRepository,
        embedding_service: object | None = None,
        chroma_client: object | None = None,
        candidate_limit: int = 5000,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.embedding_service = embedding_service
        self.chroma_client = chroma_client
        self.candidate_limit = candidate_limit

    def search(
        self,
        *,
        query: str,
        dataset_ids: Sequence[str] | None = None,
        column_names: Sequence[str] | None = None,
        min_similarity: float = 0.6,
        limit: int = 20,
    ) -> list[SearchResult]:
        text = query.strip()
        if not text:
            return []
        start = time.perf_counter()
        candidates = self._load_candidates(dataset_ids=dataset_ids, column_names=column_names)
        scored = self._score_candidates(text, candidates, min_similarity=min_similarity)
        scored.sort(key=lambda entry: entry.similarity, reverse=True)
        results = scored[: max(1, limit)]

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms <= 0:
            elapsed_ms = 0.01
        records_per_second = len(candidates) / (elapsed_ms / 1000.0) if candidates else None

        try:
            self.metadata_repository.record_performance_metric(
                metric_type=MetricType.SEARCH,
                data_file_id=None,
                cluster_id=None,
                benchmark_run_id=None,
                p50_ms=elapsed_ms,
                p95_ms=elapsed_ms,
                records_per_second=records_per_second,
            )
            self.metadata_repository.session.commit()  # type: ignore[attr-defined]
        except Exception as error:  # pragma: no cover - metrics failure should not break search
            LOGGER.warning("Failed to record search performance metric: %s", error)
            self.metadata_repository.session.rollback()  # type: ignore[attr-defined]

        return results

    def _load_candidates(
        self,
        *,
        dataset_ids: Sequence[str] | None,
        column_names: Sequence[str] | None,
    ) -> list[QueryRecord]:
        return list(
            self.metadata_repository.fetch_search_candidates(
                dataset_ids=dataset_ids,
                column_names=column_names,
                max_records=self.candidate_limit,
            )
        )

    def _score_candidates(
        self,
        query: str,
        candidates: Iterable[QueryRecord],
        *,
        min_similarity: float,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for record in candidates:
            similarity = self._compute_similarity(query, record.text)
            if similarity < min_similarity:
                continue
            dataset = record.data_file
            results.append(
                SearchResult(
                    record_id=record.id,
                    dataset_id=record.data_file_id,
                    dataset_name=dataset.display_name if dataset else "",
                    column_name=record.column_name,
                    row_index=record.row_index,
                    text=record.text,
                    similarity=similarity,
                    metadata={
                        "original_text": record.original_text,
                        "tags": record.tags or [],
                    },
                )
            )
        return results

    def _compute_similarity(self, first: str, second: str) -> float:
        if not second:
            return 0.0
        ratio = SequenceMatcher(None, first.lower(), second.lower()).ratio()
        if math.isnan(ratio):  # pragma: no cover - defensive path
            return 0.0
        return round(ratio, 4)
