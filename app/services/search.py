from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable, Sequence

from app.db.metadata import MetadataRepository
from app.db.schema import MetricType, QueryRecord, SheetMetricType, SheetSource
from app.utils.constants import SIMILARITY_BANDS, SIMILARITY_SCALE_LABEL
from app.utils.logging import get_logger, log_missing_columns

LOGGER = get_logger(__name__)


def similarity_to_percent(value: float) -> float:
    """Convert a 0-1 similarity ratio to a clamped 0-100 percentage."""
    if math.isnan(value):  # pragma: no cover - defensive path
        return 0.0
    clamped = max(0.0, min(value, 1.0))
    return round(clamped * 100.0, 2)


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
        preference = metadata_repository.get_column_preference(data_file_id=dataset_id, user_id=None)
        columns: list[dict[str, str]] = []
        source = "dataset"
        if preference and preference.selected_columns:
            for entry in sorted(preference.selected_columns, key=lambda item: item.get("position", 0)):
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
        scored, sheet_lookup, record_lookup = self._score_candidates(
            text, candidates, min_similarity=min_similarity
        )
        scored.sort(key=lambda entry: entry.similarity, reverse=True)
        results = scored[: max(1, limit)]
        selected_records = {
            result.record_id: record_lookup[result.record_id]
            for result in results
            if result.record_id in record_lookup
        }
        self._hydrate_contextual_columns(results, selected_records)

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
            dataset_label = pairs[0][1].data_file.display_name if pairs[0][1].data_file else dataset_id

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
        if math.isnan(ratio):  # pragma: no cover - defensive path
            return 0.0
        return round(ratio, 4)
