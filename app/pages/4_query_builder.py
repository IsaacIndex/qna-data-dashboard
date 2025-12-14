from __future__ import annotations

import re
import sys
from collections import defaultdict
from collections.abc import Iterable
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
from app.db.schema import QuerySheetRole, SheetSource  # noqa: E402
from app.services.query_builder import (  # noqa: E402
    QueryBuilderService,
    QueryConflictError,
    QueryFilter,
    QueryPreviewRequest,
    QueryProjection,
    QuerySheetSelection,
    QueryValidationError,
)
from app.utils.caching import cache_resource  # noqa: E402
from app.utils.logging import get_logger, log_event, log_timing  # noqa: E402

LOGGER = get_logger(__name__)


@cache_resource
def _get_session_factory() -> sessionmaker[Session]:
    engine = build_engine()
    init_database(engine)
    return create_session_factory(engine)


def _slugify(label: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", label.strip().lower()).strip("_")
    return cleaned or "sheet"


def _describe_sheet(sheet: SheetSource) -> dict[str, object]:
    columns = [str(column.get("name")) for column in sheet.column_schema if column.get("name")]
    numeric_columns = [col for col in columns if _is_numeric_column(sheet.column_schema, col)]
    return {
        "id": sheet.id,
        "bundle": sheet.bundle.display_name,
        "label": sheet.display_label,
        "sheet_name": sheet.sheet_name,
        "columns": columns,
        "numeric_columns": numeric_columns,
        "column_schema": sheet.column_schema,
        "status": sheet.status.value,
        "visibility": sheet.visibility_state.value,
        "last_refreshed_at": (
            sheet.last_refreshed_at.isoformat() if sheet.last_refreshed_at else None
        ),
    }


def _is_numeric_column(schema: Iterable[dict[str, object]], column_name: str) -> bool:
    for entry in schema:
        if entry.get("name") == column_name:
            inferred = str(entry.get("inferredType") or "").lower()
            return inferred in {"number", "numeric", "float", "integer"}
    return False


def _load_sheet_descriptions(repo: MetadataRepository) -> list[dict[str, object]]:
    sheets = []
    for sheet in repo.list_sheet_sources():
        sheets.append(_describe_sheet(sheet))
    alias_counts: defaultdict[str, int] = defaultdict(int)
    for sheet in sheets:
        base = _slugify(sheet["label"])
        alias_counts[base] += 1
        sheet["default_alias"] = base if alias_counts[base] == 1 else f"{base}_{alias_counts[base]}"
    return sheets


def _build_query_service(repo: MetadataRepository) -> QueryBuilderService:
    return QueryBuilderService(metadata_repository=repo)


def _coerce_filter_value(value: str, *, column: str, sheet: dict[str, object]) -> object:
    if not value:
        return value
    if column in sheet["numeric_columns"]:
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _render_table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        st.warning("Preview returned no rows for the current configuration.")
        return
    dataframe = pd.DataFrame(rows, columns=headers)
    st.dataframe(dataframe, width="stretch", hide_index=True)


def main() -> None:
    st.title("Query Builder Preview")
    st.caption(
        "Combine sheet sources, choose projections, and run join previews before saving a query."
    )

    with session_scope(_get_session_factory()) as session:
        repo = MetadataRepository(session)
        sheets = _load_sheet_descriptions(repo)

    if not sheets:
        st.info("No sheet sources available. Ingest a workbook or CSV to begin building queries.")
        return

    sheet_lookup = {sheet["label"]: sheet for sheet in sheets}
    sheet_options = sorted(sheet_lookup.keys())

    primary_label = st.selectbox("Primary sheet", options=sheet_options)
    primary_sheet = sheet_lookup[primary_label]
    primary_alias_input = st.text_input(
        "Primary alias",
        value=str(primary_sheet["default_alias"]),
        key=f"alias_{primary_sheet['id']}",
    ).strip()
    primary_alias_value = primary_alias_input or str(primary_sheet["default_alias"])

    info_message = f"Sheet **{primary_sheet['label']}** — status `{primary_sheet['status']}`"
    if primary_sheet["last_refreshed_at"]:
        info_message += f", refreshed {primary_sheet['last_refreshed_at']}"
    st.caption(info_message)
    if primary_sheet["status"] != "active":
        st.warning(
            "Primary sheet is inactive; preview results may be stale until the bundle is refreshed."
        )

    other_labels = [label for label in sheet_options if label != primary_label]
    join_labels = st.multiselect("Join sheets", options=other_labels)

    join_configurations: list[dict[str, object]] = []
    for label in join_labels:
        join_sheet = sheet_lookup[label]
        alias_input = st.text_input(
            f"Alias for {label}",
            value=str(join_sheet["default_alias"]),
            key=f"alias_{join_sheet['id']}",
        ).strip()
        alias = alias_input or str(join_sheet["default_alias"])
        join_caption = f"Sheet **{join_sheet['label']}** — status `{join_sheet['status']}`"
        if join_sheet["last_refreshed_at"]:
            join_caption += f", refreshed {join_sheet['last_refreshed_at']}"
        st.caption(join_caption)
        if join_sheet["status"] != "active":
            st.warning(
                f"Join sheet {alias} is not active. Validate data before using it in saved queries."
            )
        shared_columns = sorted(set(primary_sheet["columns"]) & set(join_sheet["columns"]))
        join_keys = st.multiselect(
            f"Join keys for {alias}",
            options=shared_columns,
            default=shared_columns[:1],
            key=f"join_{join_sheet['id']}_keys",
        )
        join_configurations.append(
            {
                "sheet": join_sheet,
                "alias": alias,
                "join_keys": join_keys,
            }
        )

    projection_mode = st.radio(
        "Projection mode",
        options=("Detail rows", "Aggregate sums"),
        horizontal=True,
    )
    limit = st.slider("Result limit", min_value=1, max_value=1000, value=100, step=10)

    columns_selection: dict[str, list[str]] = {}
    aggregate_selection: list[tuple[str, str]] = []

    if projection_mode == "Detail rows":
        st.subheader("Columns to include")
        primary_columns = st.multiselect(
            f"Columns from {primary_alias_value}",
            options=primary_sheet["columns"],
            default=primary_sheet["columns"][: min(3, len(primary_sheet["columns"]))],
            key=f"cols_{primary_sheet['id']}",
        )
        columns_selection[primary_alias_value] = primary_columns
        for config in join_configurations:
            join_sheet = config["sheet"]
            alias = config["alias"]
            join_columns = st.multiselect(
                f"Columns from {alias}",
                options=join_sheet["columns"],
                default=join_sheet["columns"][: min(2, len(join_sheet["columns"]))],
                key=f"cols_{join_sheet['id']}",
            )
            columns_selection[alias] = join_columns
    else:
        st.subheader("Numeric columns to sum")
        numeric_columns = primary_sheet["numeric_columns"]
        selected = st.multiselect(
            f"Sum columns from {primary_alias_value}",
            options=numeric_columns,
            key=f"agg_{primary_sheet['id']}",
        )
        aggregate_selection.extend((primary_alias_value, column) for column in selected)
        for config in join_configurations:
            join_sheet = config["sheet"]
            alias = config["alias"]
            selected = st.multiselect(
                f"Sum columns from {alias}",
                options=join_sheet["numeric_columns"],
                key=f"agg_{join_sheet['id']}",
            )
            aggregate_selection.extend((alias, column) for column in selected)

    with st.expander("Filters", expanded=False):
        enable_filter = st.checkbox("Filter primary sheet rows")
        filter_column = None
        filter_value: object = None
        if enable_filter:
            filter_column = st.selectbox(
                "Filter column",
                options=primary_sheet["columns"],
                key=f"filter_col_{primary_sheet['id']}",
            )
            filter_input = st.text_input("Filter value", key=f"filter_val_{primary_sheet['id']}")
            filter_value = _coerce_filter_value(
                filter_input, column=filter_column, sheet=primary_sheet
            )

    if st.button("Preview Query", type="primary"):
        try:
            if projection_mode == "Detail rows":
                if not any(columns_selection.values()):
                    raise QueryValidationError(
                        "Select at least one column to include in the preview."
                    )
            else:
                if not aggregate_selection:
                    raise QueryValidationError("Select at least one numeric column to aggregate.")

            alias_validation = primary_alias_value.strip()
            if not alias_validation:
                raise QueryValidationError("Primary alias cannot be empty.")

            sheets_payload: list[QuerySheetSelection] = [
                QuerySheetSelection(
                    sheet_id=str(primary_sheet["id"]),
                    alias=alias_validation,
                    role=QuerySheetRole.PRIMARY,
                    join_keys=(),
                )
            ]

            for config in join_configurations:
                join_keys = config["join_keys"]
                if not join_keys:
                    raise QueryValidationError(
                        f"Provide at least one join key for alias '{config['alias']}'."
                    )
                alias = config["alias"].strip()
                if not alias:
                    raise QueryValidationError("Join aliases cannot be empty.")
                sheets_payload.append(
                    QuerySheetSelection(
                        sheet_id=str(config["sheet"]["id"]),
                        alias=alias,
                        role=QuerySheetRole.JOIN,
                        join_keys=tuple(join_keys),
                    )
                )

            projections: list[QueryProjection] = []
            if projection_mode == "Detail rows":
                for alias, columns in columns_selection.items():
                    for column in columns:
                        label = f"{alias}.{column}"
                        projections.append(
                            QueryProjection(expression=f"{alias}.{column}", label=label)
                        )
            else:
                for alias, column in aggregate_selection:
                    label = f"sum_{alias}_{column}"
                    projections.append(
                        QueryProjection(expression=f"sum({alias}.{column})", label=label)
                    )

            filters: list[QueryFilter] = []
            if enable_filter and filter_column:
                filters.append(
                    QueryFilter(
                        sheet_alias=alias_validation,
                        column=filter_column,
                        operator="eq",
                        value=filter_value,
                    )
                )

            request = QueryPreviewRequest(
                sheets=tuple(sheets_payload),
                projections=tuple(projections),
                filters=tuple(filters),
                limit=limit,
            )

            with session_scope(_get_session_factory()) as session:
                repo = MetadataRepository(session)
                query_service = _build_query_service(repo)
                with log_timing(
                    LOGGER,
                    "streamlit.query_builder.preview",
                    sheet_count=len(sheets_payload),
                    projection_mode=projection_mode,
                ):
                    result = query_service.preview_query(request)
                log_event(
                    LOGGER,
                    "streamlit.query_builder.preview_completed",
                    row_count=result.row_count,
                    warnings=len(result.warnings),
                )

            st.success(
                f"Preview completed in {result.execution_ms:.1f} ms ({result.row_count} rows)."
            )
            if result.warnings:
                st.warning("\n".join(result.warnings))
            _render_table(result.rows, result.headers)
        except QueryConflictError as error:
            LOGGER.warning("Query preview conflict: %s", error)
            st.error(f"Preview cannot run: {error}")
        except QueryValidationError as error:
            st.error(f"Invalid configuration: {error}")
        except Exception as error:  # pragma: no cover - defensive UI guard
            LOGGER.exception("Preview failed: %s", error)
            st.error(f"Preview failed: {error}")


if __name__ == "__main__":
    main()
