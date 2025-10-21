from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.metadata import (  # noqa: E402
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.services.embeddings import EmbeddingService  # noqa: E402
from app.services.search import SearchResult, SearchService  # noqa: E402
from app.utils.caching import cache_resource  # noqa: E402
from app.utils.logging import get_logger, log_event, log_timing  # noqa: E402

LOGGER = get_logger(__name__)


@cache_resource
def _get_session_factory():
    engine = build_engine()
    init_database(engine)
    return create_session_factory(engine)


def _build_search_service(repo: MetadataRepository) -> SearchService:
    embedding = EmbeddingService(metadata_repository=repo)
    return SearchService(
        metadata_repository=repo,
        embedding_service=embedding,
    )


def _list_dataset_options(repo: MetadataRepository) -> list[dict[str, object]]:
    datasets = repo.list_data_files()
    options: list[dict[str, object]] = []
    for dataset in datasets:
        options.append(
            {
                "id": dataset.id,
                "label": f"{dataset.display_name} ({dataset.row_count} rows)",
                "columns": list(dataset.selected_columns or []),
            }
        )
    return options


def _format_results(results: Sequence[SearchResult]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(
            columns=["Dataset", "Column", "Row", "Similarity", "Text", "Tags"],
        )
    rows = []
    for result in results:
        rows.append(
            {
                "Dataset": result.dataset_name or result.dataset_id,
                "Column": result.column_name,
                "Row": result.row_index,
                "Similarity": f"{result.similarity:.2f}",
                "Text": result.text,
                "Tags": ", ".join(result.metadata.get("tags", [])),
            }
        )
    return pd.DataFrame(rows)


def _run_search(
    *,
    query: str,
    dataset_ids: list[str],
    columns: list[str],
    min_similarity: float,
    limit: int,
) -> list[SearchResult]:
    session_factory = _get_session_factory()
    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        service = _build_search_service(repo)
        with log_timing(
            LOGGER,
            "streamlit.search.execute",
            dataset_count=len(dataset_ids) if dataset_ids else "all",
        ):
            results = service.search(
                query=query,
                dataset_ids=dataset_ids or None,
                column_names=columns or None,
                min_similarity=min_similarity,
                limit=limit,
            )
        log_event(
            LOGGER,
            "streamlit.search.completed",
            result_count=len(results),
            min_similarity=min_similarity,
        )
        return results


def main() -> None:
    st.title("Search Corpus")
    st.caption("Run semantic search across ingested datasets with optional filters.")

    query = st.text_input("Search prompt", placeholder="e.g. reset password workflow")
    min_similarity = st.slider("Minimum similarity", min_value=0.0, max_value=1.0, value=0.6, step=0.05)
    limit = st.slider("Maximum results", min_value=1, max_value=100, value=20, step=1)

    with session_scope(_get_session_factory()) as session:
        repo = MetadataRepository(session)
        dataset_options = _list_dataset_options(repo)

    dataset_labels = {item["label"]: item for item in dataset_options}
    selection = st.multiselect(
        "Datasets",
        options=list(dataset_labels.keys()),
    )
    selected_dataset_ids = [dataset_labels[item]["id"] for item in selection]

    available_columns: set[str] = set()
    for item in dataset_options:
        if not selection or item["id"] in selected_dataset_ids:
            available_columns.update(item["columns"])
    sorted_columns = sorted(available_columns)
    selected_columns = st.multiselect(
        "Columns",
        options=sorted_columns,
    )

    run_disabled = not query.strip()
    if st.button("Run Search", disabled=run_disabled, type="primary"):
        try:
            results = _run_search(
                query=query,
                dataset_ids=selected_dataset_ids,
                columns=list(selected_columns),
                min_similarity=min_similarity,
                limit=limit,
            )
        except Exception as error:  # pragma: no cover - streamlit UI feedback
            LOGGER.exception("Search failed: %s", error)
            st.error(f"Search failed: {error}")
        else:
            if not results:
                st.warning("No results matched the current filters.")
            else:
                st.success(f"Found {len(results)} matching queries.")
                st.dataframe(_format_results(results), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
