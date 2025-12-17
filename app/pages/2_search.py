from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session, sessionmaker

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
from app.services.analytics import AnalyticsClient  # noqa: E402
from app.services.embeddings import EmbeddingService  # noqa: E402
from app.services.preferences import (  # noqa: E402
    ColumnPreferenceService,
    PreferenceSnapshot,
    SelectedColumn,
    hydrate_local_preferences,
)
from app.services.search import (  # noqa: E402
    SearchResult,
    SearchService,
    build_contextual_defaults,
    build_similarity_legend,
)
from app.utils.caching import cache_resource  # noqa: E402
from app.utils.logging import get_logger, log_event, log_timing  # noqa: E402
from app.utils.session_state import (
    confirm_reset,
    ensure_session_defaults,
    request_reset,
)  # noqa: E402

LOGGER = get_logger(__name__)
PLACEHOLDER_VALUE = "—"  # Accessibility-friendly placeholder for missing values
MAX_CONTEXTUAL_COLUMNS = 10


@cache_resource
def _get_session_factory() -> sessionmaker[Session]:
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


def build_similarity_legend_table() -> pd.DataFrame:
    legend = build_similarity_legend()
    rows = [
        {
            "Label": band["label"],
            "Range": f"{band['min']}-{band['max']}%",
            "Color": band["color"],
        }
        for band in legend["palette"]
    ]
    return pd.DataFrame(rows)


def _text_color_for_hex(color: str) -> str:
    """Pick legible text color (dark vs light) for a hex background."""
    try:
        stripped = color.lstrip("#")
        red, green, blue = (int(stripped[index : index + 2], 16) for index in (0, 2, 4))
    except Exception:
        return "#0F172A"
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return "#0F172A" if luminance >= 0.6 else "#FFFFFF"


def _style_similarity_legend(df: pd.DataFrame) -> pd.DataFrame | pd.io.formats.style.Styler:
    if df.empty or "Color" not in df.columns:
        return df
    palette = df["Color"].tolist()

    def _apply(_: pd.Series) -> list[str]:
        return [
            f"background-color: {color}; color: {_text_color_for_hex(color)}; font-weight: 600;"
            for color in palette
        ]

    return df.style.apply(_apply, axis=0, subset=["Color"])


def build_contextual_guidance(
    *,
    defaults: Sequence[dict[str, object]],
    has_preferences: bool,
) -> str:
    if has_preferences:
        return ""
    if not defaults:
        return "No contextual columns saved yet. Configure preferences to show helpful fields."

    parts: list[str] = []
    for entry in defaults:
        dataset_label = str(entry.get("dataset_name") or entry.get("dataset_id") or "Dataset")
        columns = [
            str(column.get("display_label") or column.get("name"))
            for column in entry.get("columns", [])
            if column.get("name") or column.get("display_label")
        ]
        if columns:
            parts.append(f"{dataset_label}: {', '.join(columns)}")
    if not parts:
        return "No contextual columns saved yet. Configure preferences to show helpful fields."
    return "No saved contextual columns yet. Start with: " + "; ".join(parts)


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
        label = (
            saved_column.display_label
            if saved_column
            else option_labels.get(column_name, column_name)
        )
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
    state = ensure_session_defaults(st.session_state)
    with st.expander("Result Columns", expanded=False):
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
            entry.column_name: entry.display_label or entry.column_name
            for entry in available_columns
        }
        unavailable = [
            entry.display_label or entry.column_name for entry in catalog if not entry.is_available
        ]
        if unavailable:
            st.info(
                "Unavailable columns currently filtered from selection: "
                + ", ".join(sorted(unavailable))
            )

        default_selection = (
            [column.column_name for column in snapshot.selected_columns] if snapshot else []
        )
        payload = (
            state.get("local_preference_payload")
            if isinstance(state.get("local_preference_payload"), dict)
            else None
        )
        payload = payload if payload and payload.get("datasetId") == dataset["id"] else None
        hydrated = hydrate_local_preferences(
            state,
            dataset_id=dataset["id"],
            payload=payload,
            defaults=default_selection,
        )
        selection_default = (
            [column.column_name for column in hydrated.selected_columns]
            or state.get("selected_columns")
            or default_selection
        )
        state["selected_columns"] = selection_default
        selection = st.multiselect(
            "Select contextual columns",
            options=list(option_labels.keys()),
            default=selection_default,
            format_func=lambda column: option_labels.get(column, column),
            help="Choose the supplemental fields analysts should see alongside each search hit.",
            key=f"column_preference_selection_{dataset['id']}",
        )

        selection_list = list(selection)

        max_default = (
            snapshot.max_columns
            if snapshot
            else min(MAX_CONTEXTUAL_COLUMNS, max(3, len(option_labels) or 1))
        )
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
            st.error(
                f"Selection exceeds the maximum allowed columns ({max_columns}). "
                "Remove columns or raise the limit."
            )

        reset_key = f"column_preference_reset_{dataset['id']}"
        reset_flag_key = f"{reset_key}_pending"
        if st.button(
            "Reset to Defaults",
            type="secondary",
            key=reset_key,
        ):
            request_reset(state, reason=f"reset:{dataset['id']}")
            st.session_state[reset_flag_key] = True

        if st.session_state.get(reset_flag_key):
            st.warning(
                "Reset clears saved contextual columns; confirm to restore defaults.",
                icon="⚠️",
            )
            if st.button("Confirm Reset", type="primary", key=f"{reset_key}_confirm"):
                try:
                    preference_service.reset_preference(dataset["id"])
                except ValueError as error:
                    repo.session.rollback()
                    st.error(str(error))
                else:
                    repo.session.commit()
                    confirm_reset(state, keys=("selected_columns", "filters", "preference_status"))
                    state["preference_status"] = "ready"
                    st.session_state.pop(f"column_preference_selection_{dataset['id']}", None)
                    st.session_state.pop(editor_key, None)
                    st.session_state.pop("local_preference_payload", None)
                    st.session_state.pop(reset_flag_key, None)
                    st.success("Restored default column view for this dataset.")
                    st.rerun()

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
                updated_at=datetime.now(UTC),
            )
            try:
                saved = preference_service.save_preference(snapshot_request)
            except ValueError as error:
                repo.session.rollback()
                st.error(str(error))
            else:
                repo.session.commit()
                state["selected_columns"] = [
                    column.column_name for column in saved.selected_columns
                ]
                state["preference_status"] = "ready"
                st.session_state["local_preference_payload"] = {
                    "datasetId": saved.dataset_id,
                    "deviceId": saved.user_id,
                    "version": saved.version,
                    "selectedColumns": [
                        {
                            "name": column.column_name,
                            "displayLabel": column.display_label,
                            "position": column.position,
                        }
                        for column in saved.selected_columns
                    ],
                    "maxColumns": saved.max_columns,
                    "updatedAt": saved.updated_at.isoformat(),
                    "source": "preference",
                }
                try:
                    preference_service.mirror_preference(saved)
                except Exception as error:
                    LOGGER.warning("Failed to mirror preference: %s", error, exc_info=True)
                st.success(
                    "Saved contextual columns: "
                    + ", ".join(column.column_name for column in saved.selected_columns),
                )


def _format_results(results: Sequence[SearchResult]) -> tuple[pd.DataFrame, list[str]]:
    if not results:
        return (
            pd.DataFrame(
                columns=["Dataset", "Column", "Row", "Similarity", "Text", "Tags"],
            ),
            [],
        )
    contextual_order: list[str] = []
    contextual_labels: dict[str, str] = {}
    for result in results:
        labels = result.metadata.get("contextual_labels", {})
        for column, label in labels.items():
            if column not in contextual_order:
                contextual_order.append(column)
            contextual_labels[column] = label

    colors: list[str] = []
    rows = []
    for result in results:
        row = {
            "Dataset": result.dataset_name or result.dataset_id,
            "Column": result.column_name,
            "Row": result.row_index,
            "Similarity": f"{result.similarity_score:.0f}% ({result.similarity_label})",
            "Text": result.text,
            "Tags": ", ".join(result.metadata.get("tags", [])),
        }
        colors.append(result.color_stop)
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
    return pd.DataFrame(rows), colors


def _style_similarity_scores(
    df: pd.DataFrame,
    colors: Sequence[str],
) -> pd.DataFrame | pd.io.formats.style.Styler:
    if df.empty or not colors:
        return df
    palette = list(colors)

    def _apply(_: pd.Series) -> list[str]:
        return [
            f"background-color: {color}; color: {_text_color_for_hex(color)}; font-weight: 700;"
            for color in palette
        ]

    return df.style.apply(_apply, axis=0, subset=["Similarity"])


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


def _load_contextual_defaults(
    repo: MetadataRepository,
    dataset_ids: Sequence[str],
) -> list[dict[str, object]]:
    scope = list(dict.fromkeys(dataset_ids)) if dataset_ids else []
    if not scope:
        return []
    return build_contextual_defaults(repo, scope)


def _run_search(
    *,
    query: str,
    dataset_ids: list[str],
    columns: list[str],
    min_similarity: float,
    limit_per_mode: int,
    offset_semantic: int,
    offset_lexical: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    session_factory = _get_session_factory()
    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        service = _build_search_service(repo)
        start = time.perf_counter()
        with log_timing(
            LOGGER,
            "streamlit.search.execute",
            dataset_count=len(dataset_ids) if dataset_ids else "all",
        ):
            response = service.search_dual(
                query=query,
                dataset_ids=dataset_ids or None,
                column_names=columns or None,
                min_similarity=min_similarity,
                limit_per_mode=limit_per_mode,
                offset_semantic=offset_semantic,
                offset_lexical=offset_lexical,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        all_results: list[SearchResult] = [
            *response.get("semantic_results", []),
            *response.get("lexical_results", []),
        ]
        log_event(
            LOGGER,
            "streamlit.search.completed",
            result_count=len(all_results),
            min_similarity=min_similarity,
        )
        defaults = _load_contextual_defaults(
            repo,
            dataset_ids or [result.dataset_id for result in all_results],
        )
        try:
            analytics = AnalyticsClient()
            contextual_labels = sorted(
                {
                    label
                    for result in all_results
                    for label in result.metadata.get("contextual_labels", {}).values()
                }
            )
            detail = f"contextual:{','.join(contextual_labels)}" if contextual_labels else None
            dataset_hint = dataset_ids[0] if dataset_ids else None
            analytics.search_latency(elapsed_ms, dataset_id=dataset_hint, detail=detail)
            analytics.flush()
        except Exception as error:
            LOGGER.warning("Failed to record search analytics: %s", error, exc_info=True)
        return response, defaults


def main() -> None:
    state = ensure_session_defaults(st.session_state)
    st.title("Search Corpus")
    st.caption(
        "Run semantic (embeddings) and lexical search side by side with per-mode pagination "
        "and contextual columns."
    )

    state.setdefault("semantic_offset", 0)
    state.setdefault("lexical_offset", 0)
    state.setdefault("auto_search", False)

    with st.form("search_prompt_form", clear_on_submit=False):
        st.markdown("Search prompt")
        prompt_col, action_col = st.columns([4, 1], gap="medium")
        with prompt_col:
            query = st.text_input(
                "Search prompt",
                placeholder="e.g. reset password workflow",
                key="search_prompt",
                label_visibility="collapsed",
            )
        with action_col:
            form_submitted = st.form_submit_button("Run Search", type="primary", width="stretch")
    min_similarity = st.slider(
        "Minimum similarity", min_value=0.0, max_value=1.0, value=0.6, step=0.05
    )
    limit_per_mode = st.slider("Results per mode", min_value=1, max_value=50, value=10, step=1)
    with st.expander("Similarity Legend", expanded=False):
        st.markdown(
            "Semantic and lexical tabs share this scale. Use the load-more buttons on each tab to "
            "page results independently without resetting filters."
        )
        st.dataframe(
            _style_similarity_legend(build_similarity_legend_table()),
            hide_index=True,
            width="stretch",
        )

    with session_scope(_get_session_factory()) as session:
        repo = MetadataRepository(session)
        dataset_options = _list_dataset_options(repo)
        _render_preference_panel(repo, dataset_options)

    st.divider()

    dataset_labels = {item["label"]: item for item in dataset_options}
    dataset_key = "search_dataset_selection"
    if dataset_key in state:
        state[dataset_key] = [label for label in state[dataset_key] if label in dataset_labels]
    selection = st.multiselect(
        "Datasets",
        options=list(dataset_labels.keys()),
        default=state.get(dataset_key, []),
        key=dataset_key,
    )
    selected_dataset_ids = [dataset_labels[item]["id"] for item in selection]

    available_columns: set[str] = set()
    for item in dataset_options:
        if not selection or item["id"] in selected_dataset_ids:
            available_columns.update(item["columns"])
    sorted_columns = sorted(available_columns)
    column_key = "search_column_selection"
    if column_key in state:
        state[column_key] = [column for column in state[column_key] if column in sorted_columns]
    selected_columns = st.multiselect(
        "Columns",
        options=sorted_columns,
        default=state.get(column_key, []),
        key=column_key,
    )

    if form_submitted:
        state["semantic_offset"] = 0
        state["lexical_offset"] = 0
    run_disabled = not query.strip()
    should_search = (form_submitted or state.get("auto_search", False)) and not run_disabled

    if form_submitted and run_disabled:
        st.warning("Enter a search prompt before running a search.")
    elif should_search:
        try:
            response, defaults = _run_search(
                query=query,
                dataset_ids=selected_dataset_ids,
                columns=list(selected_columns),
                min_similarity=min_similarity,
                limit_per_mode=limit_per_mode,
                offset_semantic=state["semantic_offset"],
                offset_lexical=state["lexical_offset"],
            )
        except Exception as error:  # pragma: no cover - streamlit UI feedback
            LOGGER.exception("Search failed: %s", error)
            st.error(f"Search failed: {error}")
        else:
            state["auto_search"] = False
            semantic_results: list[SearchResult] = response.get("semantic_results", [])
            lexical_results: list[SearchResult] = response.get("lexical_results", [])
            pagination = response.get("pagination", {})
            fallback = response.get("fallback", {}) or {}
            combined = semantic_results + lexical_results

            if not combined:
                st.warning("No results matched the current filters.")
            else:
                st.success(f"Found {len(combined)} matching queries across modes.")
                if not fallback.get("semantic_available", True):
                    st.warning(
                        fallback.get("message")
                        or "Semantic results unavailable; showing lexical results only.",
                        icon="⚠️",
                    )
                missing_columns = _collect_missing_columns(combined)
                for dataset, columns in missing_columns.items():
                    st.info(
                        f"{dataset}: missing contextual columns {', '.join(columns)}. "
                        "Values are shown with placeholders.",
                        icon="ℹ️",
                    )
                guidance = build_contextual_guidance(
                    defaults=defaults,
                    has_preferences=any(
                        result.metadata.get("contextual_labels") for result in combined
                    ),
                )
                if guidance:
                    st.info(guidance)

                tabs = st.tabs(["Semantic", "Lexical"])
                mode_map = [
                    ("semantic", semantic_results, tabs[0]),
                    ("lexical", lexical_results, tabs[1]),
                ]
                for mode, results, container in mode_map:
                    with container:
                        if mode == "semantic" and not fallback.get("semantic_available", True):
                            st.info(
                                fallback.get("message")
                                or "Semantic results unavailable; showing lexical only."
                            )
                        if not results:
                            st.write("No results in this mode yet.")
                            continue
                        df, colors = _format_results(results)
                        styled = _style_similarity_scores(df, colors)
                        st.dataframe(styled, width="stretch", hide_index=True)
                        page = pagination.get(mode, {})
                        next_offset = page.get("next_offset")
                        if next_offset is not None:
                            label = f"Load more {mode} results"
                            if st.button(label, key=f"{mode}_load_more"):
                                state[f"{mode}_offset"] = next_offset
                                state["auto_search"] = True
                                st.rerun()

    if not should_search:
        state["auto_search"] = False


if __name__ == "__main__":
    main()
