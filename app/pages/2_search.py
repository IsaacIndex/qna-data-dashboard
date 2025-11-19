from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
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
from app.services.preferences import (  # noqa: E402
    ColumnPreferenceService,
    PreferenceSnapshot,
    SelectedColumn,
)
from app.services.search import SearchResult, SearchService  # noqa: E402
from app.utils.caching import cache_resource  # noqa: E402
from app.utils.logging import get_logger, log_event, log_timing  # noqa: E402

LOGGER = get_logger(__name__)
PLACEHOLDER_VALUE = "—"  # Accessibility-friendly placeholder for missing values
MAX_CONTEXTUAL_COLUMNS = 10


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


def _build_preference_service(repo: MetadataRepository) -> ColumnPreferenceService:
    return ColumnPreferenceService(metadata_repository=repo)


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


def _build_editor_rows(
    selection: Sequence[str],
    saved: PreferenceSnapshot | None,
    option_labels: dict[str, str],
) -> list[dict[str, object]]:
    saved_lookup = {
        column.column_name: column for column in (saved.selected_columns if saved else [])
    }
    rows: list[dict[str, object]] = []
    for index, column_name in enumerate(selection, start=1):
        saved_column = saved_lookup.get(column_name)
        label = saved_column.display_label if saved_column else option_labels.get(column_name, column_name)
        rows.append(
            {
                "columnName": column_name,
                "displayLabel": label,
                "position": index,
            }
        )
    return rows


def _render_preference_panel(
    repo: MetadataRepository,
    dataset_options: Sequence[dict[str, object]],
) -> None:
    st.subheader("Result Columns")
    st.caption("Configure dataset-specific contextual fields rendered with each search result.")

    if not dataset_options:
        st.info("Ingest a dataset to configure contextual columns.")
        return

    dataset_map = {item["label"]: item for item in dataset_options}
    dataset_key = "column_preference_dataset"
    if dataset_key not in st.session_state or st.session_state[dataset_key] not in dataset_map:
        st.session_state[dataset_key] = next(iter(dataset_map))

    selected_label = st.selectbox(
        "Dataset preferences",
        options=list(dataset_map.keys()),
        key=dataset_key,
    )
    dataset = dataset_map[selected_label]

    preference_service = _build_preference_service(repo)
    snapshot = preference_service.load_preference(dataset["id"])
    catalog = preference_service.fetch_catalog(dataset["id"])

    available_columns = [entry for entry in catalog if entry.is_available]
    option_labels = {
        entry.column_name: entry.display_label or entry.column_name for entry in available_columns
    }
    unavailable = [
        entry.display_label or entry.column_name for entry in catalog if not entry.is_available
    ]
    if unavailable:
        st.info(
            "Unavailable columns currently filtered from selection: " + ", ".join(sorted(unavailable))
        )

    default_selection = [column.column_name for column in snapshot.selected_columns] if snapshot else []
    selection = st.multiselect(
        "Select contextual columns",
        options=list(option_labels.keys()),
        default=default_selection,
        format_func=lambda column: option_labels.get(column, column),
        help="Choose the supplemental fields analysts should see alongside each search hit.",
        key=f"column_preference_selection_{dataset['id']}",
    )

    selection_list = list(selection)

    max_default = snapshot.max_columns if snapshot else min(MAX_CONTEXTUAL_COLUMNS, max(3, len(option_labels) or 1))
    max_columns = st.slider(
        "Maximum contextual columns",
        min_value=1,
        max_value=MAX_CONTEXTUAL_COLUMNS,
        value=max_default,
        key=f"column_preference_max_{dataset['id']}",
    )

    rows = _build_editor_rows(selection_list, snapshot, option_labels)
    editor_key = f"column_preference_editor_{dataset['id']}"
    if rows:
        editor_df = pd.DataFrame(rows)
        editor_df = st.data_editor(
            editor_df,
            hide_index=True,
            num_rows="fixed",
            key=editor_key,
            column_config={
                "columnName": st.column_config.Column("Column", disabled=True),
                "displayLabel": st.column_config.TextColumn("Display label"),
                "position": st.column_config.NumberColumn(
                    "Order",
                    min_value=1,
                    max_value=len(rows),
                    step=1,
                ),
            },
        )
    else:
        st.caption("Select one or more contextual columns to customize order and labels.")
        editor_df = pd.DataFrame(columns=["columnName", "displayLabel", "position"])

    exceed_limit = len(selection_list) > max_columns
    if exceed_limit:
        st.error(f"Selection exceeds the maximum allowed columns ({max_columns}). Remove columns or raise the limit.")

    reset_key = f"column_preference_reset_{dataset['id']}"
    if st.button(
        "Reset to Defaults",
        type="secondary",
        key=reset_key,
    ):
        try:
            preference_service.reset_preference(dataset["id"])
        except ValueError as error:
            repo.session.rollback()
            st.error(str(error))
        else:
            repo.session.commit()
            st.session_state.pop(f"column_preference_selection_{dataset['id']}", None)
            st.session_state.pop(editor_key, None)
            st.success("Restored default column view for this dataset.")
            st.experimental_rerun()

    save_disabled = not selection_list or exceed_limit
    if st.button(
        "Save Preferences",
        disabled=save_disabled,
        type="primary",
        key=f"column_preference_save_{dataset['id']}",
    ):
        ordered_records = (
            editor_df.sort_values("position").to_dict(orient="records")
            if not editor_df.empty
            else []
        )
        selected_columns: list[SelectedColumn] = []
        for index, record in enumerate(ordered_records):
            column_name = str(record["columnName"])
            raw_label = record.get("displayLabel")
            if isinstance(raw_label, str):
                label_value = raw_label.strip() or option_labels.get(column_name, column_name)
            else:
                label_value = option_labels.get(column_name, column_name)
            selected_columns.append(
                SelectedColumn(
                    column_name=column_name,
                    display_label=label_value,
                    position=index,
                )
            )
        snapshot_request = PreferenceSnapshot(
            dataset_id=dataset["id"],
            user_id=None,
            selected_columns=selected_columns,
            max_columns=max_columns,
            updated_at=datetime.now(timezone.utc),
        )
        try:
            saved = preference_service.save_preference(snapshot_request)
        except ValueError as error:
            repo.session.rollback()
            st.error(str(error))
        else:
            repo.session.commit()
            st.success(
                "Saved contextual columns: "
                + ", ".join(column.column_name for column in saved.selected_columns),
            )
def _format_results(results: Sequence[SearchResult]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(
            columns=["Dataset", "Column", "Row", "Similarity", "Text", "Tags"],
        )
    contextual_order: list[str] = []
    contextual_labels: dict[str, str] = {}
    for result in results:
        labels = result.metadata.get("contextual_labels", {})
        for column, label in labels.items():
            if column not in contextual_order:
                contextual_order.append(column)
            contextual_labels[column] = label

    rows = []
    for result in results:
        row = {
            "Dataset": result.dataset_name or result.dataset_id,
            "Column": result.column_name,
            "Row": result.row_index,
            "Similarity": f"{result.similarity:.2f}",
            "Text": result.text,
            "Tags": ", ".join(result.metadata.get("tags", [])),
        }
        for column in contextual_order:
            label = contextual_labels.get(column, column)
            value = result.contextual_columns.get(column)
            if value is None:
                row[label] = PLACEHOLDER_VALUE
            elif isinstance(value, str) and not value.strip():
                row[label] = PLACEHOLDER_VALUE
            else:
                row[label] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _collect_missing_columns(results: Sequence[SearchResult]) -> dict[str, list[str]]:
    notices: dict[str, set[str]] = {}
    for result in results:
        if not result.missing_columns:
            continue
        dataset_label = result.dataset_name or result.dataset_id
        labels = result.metadata.get("contextual_labels", {})
        target = notices.setdefault(dataset_label, set())
        for column in result.missing_columns:
            target.add(labels.get(column, column))
    return {dataset: sorted(values) for dataset, values in notices.items()}


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
        _render_preference_panel(repo, dataset_options)

    st.divider()

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
                missing_columns = _collect_missing_columns(results)
                for dataset, columns in missing_columns.items():
                    st.info(
                        f"{dataset}: missing contextual columns {', '.join(columns)}. "
                        "Values are shown with placeholders.",
                        icon="ℹ️",
                    )
                st.dataframe(_format_results(results), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
