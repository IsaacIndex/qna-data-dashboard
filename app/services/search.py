from __future__ import annotations

import math
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher

from app.db.metadata import MetadataRepository
from app.db.schema import MetricType, QueryRecord, SheetMetricType, SheetSource
from app.utils.constants import SIMILARITY_BANDS, SIMILARITY_SCALE_LABEL
from app.utils.logging import get_logger, log_missing_columns

LOGGER = get_logger(__name__)

DEFAULT_RESULTS_PER_MODE = 10
MAX_RESULTS_PER_MODE = 50


def normalize_similarity_ratio(value: float, *, scale_max: float = 1.0) -> float:
    """Normalize a similarity value to a 0-1 ratio regardless of original scale."""
    if math.isnan(value):  # pragma: no cover - defensive path
        return 0.0
    if scale_max <= 0:  # pragma: no cover - guard against misconfiguration
        return 0.0
    clamped = max(0.0, min(value, scale_max))
    return round(clamped / scale_max, 4)


def similarity_to_percent(value: float) -> float:
    """Convert a 0-1 similarity ratio to a clamped 0-100 percentage."""
    return round(normalize_similarity_ratio(value) * 100.0, 2)


def normalize_lexical_similarity(value: float) -> float:
    """Normalize SequenceMatcher scores to the shared 0-1 scale."""
    return normalize_similarity_ratio(value, scale_max=1.0)


def normalize_embedding_similarity(value: float, *, is_distance: bool = False) -> float:
    """Normalize embedding scores (distance or similarity) to the shared 0-1 scale."""
    score = 1.0 - value if is_distance else value
    return normalize_similarity_ratio(score, scale_max=1.0)


def describe_similarity_score(score_percent: float) -> tuple[str, str]:
    """Return the band label and color stop for a 0-100 similarity score."""
    clamped = max(0.0, min(score_percent, 100.0))
    for band in SIMILARITY_BANDS:
        if band.min_score <= clamped <= band.max_score:
            return band.label, band.color
    fallback = SIMILARITY_BANDS[-1]
    return fallback.label, fallback.color


def build_similarity_legend() -> dict[str, object]:
    return {
        "palette": [
            {"label": band.label, "min": band.min_score, "max": band.max_score, "color": band.color}
            for band in SIMILARITY_BANDS
        ],
        "scale": SIMILARITY_SCALE_LABEL,
    }


def build_contextual_defaults(
    metadata_repository: MetadataRepository,
    dataset_ids: Sequence[str],
) -> list[dict[str, object]]:
    defaults: list[dict[str, object]] = []
    for dataset_id in dataset_ids:
        dataset = metadata_repository.get_data_file(dataset_id)
        if dataset is None:
            continue
        preference = metadata_repository.get_column_preference(
            data_file_id=dataset_id, user_id=None
        )
        columns: list[dict[str, str]] = []
        source = "dataset"
        if preference and preference.selected_columns:
            for entry in sorted(
                preference.selected_columns, key=lambda item: item.get("position", 0)
            ):
                name = str(entry.get("column_name") or "").strip()
                if not name:
                    continue
                label = str(entry.get("display_label") or name).strip() or name
                columns.append({"name": name, "display_label": label})
            source = "preference"
        else:
            for name in dataset.selected_columns or []:
                if not name:
                    continue
                columns.append({"name": name, "display_label": name})
        defaults.append(
            {
                "dataset_id": dataset_id,
                "dataset_name": dataset.display_name,
                "columns": columns,
                "source": source,
            }
        )
    return defaults


def resolve_limit_per_mode(limit_per_mode: int | None, fallback_limit: int | None = None) -> int:
    base_limit = limit_per_mode if limit_per_mode is not None else fallback_limit
    if base_limit is None:
        base_limit = DEFAULT_RESULTS_PER_MODE
    return max(1, min(base_limit, MAX_RESULTS_PER_MODE))


@dataclass
class SearchResult:
    record_id: str
    dataset_id: str
    dataset_name: str
    sheet_id: str | None
    sheet_label: str | None
    column_name: str
    row_index: int
    text: str
    similarity: float
    metadata: dict[str, object]
    contextual_columns: dict[str, object] = field(default_factory=dict)
    missing_columns: list[str] = field(default_factory=list)
    mode: str = "lexical"
    similarity_score: float = field(init=False)
    similarity_label: str = field(init=False)
    color_stop: str = field(init=False)

    def __post_init__(self) -> None:
        percent = similarity_to_percent(self.similarity)
        self.similarity_score = percent
        label, color = describe_similarity_score(percent)
        self.similarity_label = label
        self.color_stop = color

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "sheet_id": self.sheet_id,
            "sheet_label": self.sheet_label,
            "column_name": self.column_name,
            "row_index": self.row_index,
            "text": self.text,
            "similarity": self.similarity,
            "similarity_score": self.similarity_score,
            "similarity_label": self.similarity_label,
            "color_stop": self.color_stop,
            "metadata": self.metadata,
            "contextual_columns": self.contextual_columns,
            "missing_columns": self.missing_columns,
            "mode": self.mode,
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
        self.chroma_client = chroma_client or getattr(embedding_service, "chroma_client", None)
        self.candidate_limit = candidate_limit

    def search_dual(
        self,
        *,
        query: str,
        dataset_ids: Sequence[str] | None = None,
        column_names: Sequence[str] | None = None,
        min_similarity: float = 0.6,
        limit_per_mode: int | None = None,
        offset_semantic: int = 0,
        offset_lexical: int = 0,
    ) -> dict[str, object]:
        text = query.strip()
        limit = resolve_limit_per_mode(limit_per_mode, fallback_limit=None)
        if not text:
            return {
                "semantic_results": [],
                "lexical_results": [],
                "pagination": {
                    "semantic": self._build_pagination(limit, offset_semantic, 0, 0),
                    "lexical": self._build_pagination(limit, offset_lexical, 0, 0),
                },
                "fallback": {"semantic_available": False, "message": "Empty query"},
            }

        start = time.perf_counter()
        candidates = self._load_candidates(dataset_ids=dataset_ids, column_names=column_names)
        scored, sheet_lookup, record_lookup = self._score_candidates(
            text, candidates, min_similarity=min_similarity
        )
        scored.sort(key=lambda entry: entry.similarity, reverse=True)
        lexical_total = len(scored)
        lexical_results = self._slice_results(scored, offset_lexical, limit, mode="lexical")
        candidate_records = [
            record_lookup[result.record_id]
            for result in scored
            if result.record_id in record_lookup
        ]

        semantic_results: list[SearchResult] = []
        semantic_total = 0
        semantic_available = False
        semantic_message: str | None = None
        try:
            semantic_ranked = self._semantic_rank(
                query=text,
                candidates=candidate_records,
                limit=limit + offset_semantic,
                min_similarity=min_similarity,
            )
            semantic_total = len(semantic_ranked)
            semantic_results = self._slice_results(
                semantic_ranked, offset_semantic, limit, mode="semantic"
            )
            semantic_available = True
        except Exception as error:  # pragma: no cover - ensure lexical path survives
            semantic_available = False
            semantic_message = str(error) or "Semantic results unavailable"

        combined_results = lexical_results + semantic_results
        selected_records = {
            result.record_id: record_lookup[result.record_id]
            for result in combined_results
            if result.record_id in record_lookup
        }
        self._hydrate_contextual_columns(combined_results, selected_records)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms <= 0:
            elapsed_ms = 0.01
        records_per_second = len(candidates) / (elapsed_ms / 1000.0) if candidates else None

        self._record_metrics(
            elapsed_ms=elapsed_ms,
            records_per_second=records_per_second,
            results=lexical_results + semantic_results,
            sheet_lookup=sheet_lookup,
        )

        return {
            "semantic_results": semantic_results,
            "lexical_results": lexical_results,
            "pagination": {
                "semantic": self._build_pagination(
                    limit, offset_semantic, semantic_total, len(semantic_results)
                ),
                "lexical": self._build_pagination(
                    limit, offset_lexical, lexical_total, len(lexical_results)
                ),
            },
            "fallback": {"semantic_available": semantic_available, "message": semantic_message},
        }

    def search(
        self,
        *,
        query: str,
        dataset_ids: Sequence[str] | None = None,
        column_names: Sequence[str] | None = None,
        min_similarity: float = 0.6,
        limit: int | None = None,
        limit_per_mode: int | None = None,
    ) -> list[SearchResult]:
        """Legacy single-mode search retained for callers that have not migrated."""
        response = self.search_dual(
            query=query,
            dataset_ids=dataset_ids,
            column_names=column_names,
            min_similarity=min_similarity,
            limit_per_mode=limit_per_mode or limit,
            offset_semantic=0,
            offset_lexical=0,
        )
        return response["lexical_results"]  # type: ignore[index]

    def _semantic_rank(
        self,
        *,
        query: str,
        candidates: Sequence[QueryRecord],
        limit: int,
        min_similarity: float,
    ) -> list[SearchResult]:
        if self.embedding_service is None or not candidates:
            return []
        query_vectors, _, _ = self.embedding_service.embed_texts([query])
        if not query_vectors:
            return []
        query_vector = query_vectors[0]
        candidate_vectors, _, _ = self.embedding_service.embed_texts(
            [record.text for record in candidates]
        )
        ranked: list[tuple[float, QueryRecord]] = []
        for record, vector in zip(candidates, candidate_vectors, strict=False):
            similarity = self._cosine_similarity(query_vector, vector)
            normalized = normalize_embedding_similarity(similarity)
            if normalized < min_similarity:
                continue
            ranked.append((similarity, record))
        ranked.sort(key=lambda item: item[0], reverse=True)
        top_ranked = ranked[:limit]
        results: list[SearchResult] = []
        for similarity, record in top_ranked:
            sheet = record.sheet
            results.append(
                SearchResult(
                    record_id=record.id,
                    dataset_id=record.data_file_id,
                    dataset_name=record.data_file.display_name if record.data_file else "",
                    sheet_id=sheet.id if sheet else None,
                    sheet_label=sheet.display_label if sheet else None,
                    column_name=record.column_name,
                    row_index=record.row_index,
                    text=record.text,
                    similarity=normalize_embedding_similarity(similarity),
                    metadata={
                        "original_text": record.original_text,
                        "tags": record.tags or [],
                        "sheet_id": sheet.id if sheet else None,
                        "sheet_label": sheet.display_label if sheet else None,
                        "bundle_id": sheet.bundle_id if sheet else None,
                    },
                    mode="semantic",
                )
            )
        return results

    @staticmethod
    def _cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
        if not first or not second or len(first) != len(second):
            return 0.0
        dot = sum(a * b for a, b in zip(first, second, strict=False))
        norm_a = math.sqrt(sum(a * a for a in first))
        norm_b = math.sqrt(sum(b * b for b in second))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _slice_results(
        self,
        results: Sequence[SearchResult],
        offset: int,
        limit: int,
        *,
        mode: str,
    ) -> list[SearchResult]:
        start = max(0, offset)
        end = start + limit
        sliced = results[start:end]
        return [replace(result, mode=mode) for result in sliced]

    def _record_metrics(
        self,
        *,
        elapsed_ms: float,
        records_per_second: float | None,
        results: Sequence[SearchResult],
        sheet_lookup: dict[str, SheetSource],
    ) -> None:
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
            for result in results:
                if result.sheet_id and result.sheet_id in sheet_lookup:
                    self.metadata_repository.record_sheet_metric(
                        sheet=sheet_lookup[result.sheet_id],
                        metric_type=SheetMetricType.QUERY_P95_MS,
                        p50=elapsed_ms,
                        p95=elapsed_ms,
                    )
            self.metadata_repository.session.commit()  # type: ignore[attr-defined]
        except Exception as error:  # pragma: no cover - metrics failure should not break search
            LOGGER.warning("Failed to record search performance metric: %s", error)
            self.metadata_repository.session.rollback()  # type: ignore[attr-defined]

    def _build_pagination(
        self,
        limit: int,
        offset: int,
        total: int,
        returned: int,
    ) -> dict[str, int | None]:
        next_offset: int | None = None
        if returned + offset < total:
            next_offset = offset + limit
        return {
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }

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
    ) -> tuple[list[SearchResult], dict[str, SheetSource], dict[str, QueryRecord]]:
        results: list[SearchResult] = []
        sheet_lookup: dict[str, SheetSource] = {}
        record_lookup: dict[str, QueryRecord] = {}
        for record in candidates:
            similarity = self._compute_similarity(query, record.text)
            if similarity < min_similarity:
                continue
            dataset = record.data_file
            sheet = record.sheet
            if sheet is not None:
                sheet_lookup[sheet.id] = sheet
            record_lookup[record.id] = record
            results.append(
                SearchResult(
                    record_id=record.id,
                    dataset_id=record.data_file_id,
                    dataset_name=dataset.display_name if dataset else "",
                    sheet_id=sheet.id if sheet else None,
                    sheet_label=sheet.display_label if sheet else None,
                    column_name=record.column_name,
                    row_index=record.row_index,
                    text=record.text,
                    similarity=similarity,
                    metadata={
                        "original_text": record.original_text,
                        "tags": record.tags or [],
                        "sheet_id": sheet.id if sheet else None,
                        "sheet_label": sheet.display_label if sheet else None,
                        "bundle_id": sheet.bundle_id if sheet else None,
                    },
                )
            )
        return results, sheet_lookup, record_lookup

    def _hydrate_contextual_columns(
        self,
        results: Sequence[SearchResult],
        record_lookup: dict[str, QueryRecord],
    ) -> None:
        if not results:
            return

        grouped: dict[str, list[tuple[SearchResult, QueryRecord]]] = {}
        for result in results:
            record = record_lookup.get(result.record_id)
            if record is None:
                continue
            grouped.setdefault(result.dataset_id, []).append((result, record))

        for dataset_id, pairs in grouped.items():
            preference = self.metadata_repository.get_column_preference(
                data_file_id=dataset_id,
                user_id=None,
            )
            if preference is None or not preference.selected_columns:
                continue
            ordered = sorted(
                preference.selected_columns,
                key=lambda entry: entry.get("position", 0),
            )
            if not ordered:
                continue

            dataset_missing: set[str] = set()
            dataset_label = (
                pairs[0][1].data_file.display_name if pairs[0][1].data_file else dataset_id
            )

            for result, record in pairs:
                row_values = self.metadata_repository.get_row_values(record)
                contextual: dict[str, object] = {}
                missing: list[str] = []
                labels: dict[str, str] = {}
                for selection in ordered:
                    column = selection.get("column_name")
                    if not column:
                        continue
                    label = selection.get("display_label") or column
                    value = row_values.get(column)
                    if value is None:
                        missing.append(column)
                    elif isinstance(value, str) and not value.strip():
                        missing.append(column)
                    contextual[column] = value
                    labels[column] = label
                result.contextual_columns = contextual
                result.missing_columns = missing
                result.metadata["contextual_labels"] = labels
                for column in missing:
                    dataset_missing.add(labels.get(column, column))
            if dataset_missing:
                log_missing_columns(
                    LOGGER,
                    dataset_id=dataset_id,
                    dataset_name=dataset_label,
                    columns=sorted(dataset_missing),
                )

    def _compute_similarity(self, first: str, second: str) -> float:
        if not second:
            return 0.0
        ratio = SequenceMatcher(None, first.lower(), second.lower()).ratio()
        return normalize_lexical_similarity(ratio)
