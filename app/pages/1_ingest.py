from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:  # Optional Excel dependency
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - optional path
    load_workbook = None

from app.db.metadata import (  # noqa: E402
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.db.schema import SheetStatus  # noqa: E402
from app.services.embeddings import EmbeddingService  # noqa: E402
from app.services.ingestion import (  # noqa: E402
    BundleIngestionOptions,
    HiddenSheetPolicy,
    IngestionService,
)
from app.utils.caching import cache_resource  # noqa: E402
from app.utils.logging import get_logger, log_event, log_timing  # noqa: E402

LOGGER = get_logger(__name__)


@cache_resource
def _get_session_factory():
    engine = build_engine()
    init_database(engine)
    return create_session_factory(engine)


def _data_root() -> Path:
    return Path(os.getenv("DATA_ROOT", "./data")).expanduser()


def _preview_rows(uploaded_file, sample_rows: int = 5) -> tuple[list[str], list[dict[str, str]]]:
    uploaded_file.seek(0)
    if uploaded_file.name.lower().endswith(".csv"):
        content = uploaded_file.read().decode("utf-8")
        uploaded_file.seek(0)
        reader = csv.DictReader(io.StringIO(content))
        rows = []
        for index, row in enumerate(reader):
            rows.append(row)
            if index + 1 >= sample_rows:
                break
        return reader.fieldnames or [], rows

    if load_workbook is None:
        uploaded_file.seek(0)
        raise RuntimeError("Excel preview requires the 'openpyxl' dependency.")

    workbook = load_workbook(uploaded_file, read_only=True)
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        headers_row = next(rows_iter)
    except StopIteration:
        workbook.close()
        uploaded_file.seek(0)
        return [], []

    headers = [str(value) if value is not None else "" for value in headers_row]
    rows: list[dict[str, str]] = []
    for index, values in enumerate(rows_iter):
        row_map: dict[str, str] = {}
        for col_index, header in enumerate(headers):
            if not header:
                continue
            cell_value = None
            if values is not None and col_index < len(values):
                cell_value = values[col_index]
            row_map[header] = "" if cell_value is None else str(cell_value)
        rows.append(row_map)
        if index + 1 >= sample_rows:
            break

    workbook.close()
    uploaded_file.seek(0)
    return headers, rows


def _collect_unique_columns(uploaded_file) -> list[str]:
    """Aggregate unique column headers across every sheet to support trial column selection."""
    uploaded_file.seek(0)
    filename = uploaded_file.name.lower()

    if filename.endswith(".csv"):
        content = uploaded_file.read().decode("utf-8")
        uploaded_file.seek(0)
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return []
        seen: set[str] = set()
        ordered: list[str] = []
        for header in reader.fieldnames:
            if not header or header in seen:
                continue
            seen.add(header)
            ordered.append(header)
        return ordered

    if load_workbook is None:
        uploaded_file.seek(0)
        raise RuntimeError("Excel preview requires the 'openpyxl' dependency.")

    workbook = load_workbook(uploaded_file, read_only=True)
    seen: set[str] = set()
    ordered: list[str] = []
    try:
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            iterator = worksheet.iter_rows(values_only=True)
            try:
                headers_row = next(iterator)
            except StopIteration:
                continue
            for value in headers_row:
                if value is None:
                    continue
                header = str(value).strip()
                if not header or header in seen:
                    continue
                seen.add(header)
                ordered.append(header)
    finally:
        workbook.close()
        uploaded_file.seek(0)
    return ordered


def _render_sheet_catalog(repo: MetadataRepository) -> None:
    bundles = repo.list_source_bundles()
    if not bundles:
        st.info("No source bundles ingested yet. Upload a workbook or CSV to begin.")
        return

    st.subheader("Sheet Source Catalog")
    for bundle in bundles:
        st.markdown(
            f"**{bundle.display_name}** — {bundle.sheet_count} sheets, "
            f"status **{bundle.ingestion_status.value}**"
        )
        sheets = repo.list_sheet_sources(bundle_id=bundle.id)
        if not sheets:
            st.write("- _No sheet sources registered yet._")
            continue
        for sheet in sheets:
            visibility = "Hidden Opt-In" if sheet.visibility_state.value == "hidden_opt_in" else "Visible"
            status = sheet.status.value
            last_refreshed = (
                sheet.last_refreshed_at.isoformat() if sheet.last_refreshed_at else "N/A"
            )
            message = (
                "- ``{label}`` ({visibility}, status {status}, "
                "{rows} rows, refreshed {refreshed})".format(
                    label=sheet.display_label,
                    visibility=visibility,
                    status=status,
                    rows=sheet.row_count,
                    refreshed=last_refreshed,
                )
            )
            if sheet.status != SheetStatus.ACTIVE:
                st.warning(message)
            else:
                st.write(message)


def run_ingestion(
    uploaded_file,
    selected_columns: Sequence[str],
    delimiter: str | None,
    hidden_sheet_overrides: Sequence[str],
):
    session_factory = _get_session_factory()

    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        embedding_service = EmbeddingService(metadata_repository=repo)
        ingestion_service = IngestionService(
            metadata_repository=repo,
            embedding_service=embedding_service,
            data_root=_data_root(),
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
            tmp.write(uploaded_file.read())
            temp_path = Path(tmp.name)
        uploaded_file.seek(0)

        try:
            with log_timing(LOGGER, "streamlit.ingestion.submit", display_name=uploaded_file.name):
                bundle_result = ingestion_service.ingest_bundle(
                    source_path=temp_path,
                    display_name=uploaded_file.name,
                    options=BundleIngestionOptions(
                        selected_columns=selected_columns,
                        delimiter=delimiter or None,
                        hidden_sheet_policy=HiddenSheetPolicy(
                            default_action="exclude",
                            overrides=list(hidden_sheet_overrides),
                        ),
                    ),
                )
        finally:
            temp_path.unlink(missing_ok=True)

        log_event(LOGGER, "streamlit.ingestion.complete", bundle_id=bundle_result.bundle.id)
        return bundle_result


def main() -> None:
    st.title("Ingest Sheet Sources")
    st.caption(
        "Upload CSV or Excel files, expose individual sheets to the catalog, and opt in hidden tabs with audit logging."
    )

    uploaded_file = st.file_uploader("Select CSV or Excel file", type=["csv", "xlsx", "xls"])
    selected_columns: list[str] = []
    delimiter: str | None = None
    preview_headers: list[str] = []
    preview_rows: list[dict[str, str]] = []
    hidden_sheet_overrides: list[str] = []
    visible_sheet_names: list[str] = []
    hidden_sheet_names: list[str] = []

    if uploaded_file:
        try:
            preview_headers, preview_rows = _preview_rows(uploaded_file)
            unique_columns = _collect_unique_columns(uploaded_file)
            column_options = unique_columns or list(preview_headers)

            if preview_rows:
                st.table(preview_rows)

            selected_columns = st.multiselect(
                "Select text columns to embed",
                options=column_options,
            )
            if unique_columns:
                st.caption("Detected columns across all sheets: " + ", ".join(unique_columns))

            filename = uploaded_file.name.lower()
            if filename.endswith(".csv"):
                delimiter = st.text_input("Delimiter", value=",")
                visible_sheet_names = ["__csv__"]
            elif filename.endswith((".xls", ".xlsx")):
                if load_workbook is None:
                    st.error("Excel ingestion requires installing the 'openpyxl' package.")
                else:
                    workbook = load_workbook(uploaded_file, read_only=True)
                    visible_sheet_names = []
                    hidden_sheet_names = []
                    for name in workbook.sheetnames:
                        worksheet = workbook[name]
                        hidden = getattr(worksheet, "sheet_state", "visible") != "visible"
                        if hidden:
                            hidden_sheet_names.append(name)
                        else:
                            visible_sheet_names.append(name)
                    workbook.close()
                    uploaded_file.seek(0)

                    if visible_sheet_names:
                        st.info("Visible sheets detected: " + ", ".join(visible_sheet_names))
                    if hidden_sheet_names:
                        st.warning(
                            "Hidden sheets remain excluded unless explicitly enabled. "
                            "Select any hidden sheets you want to include; this will be recorded in audit logs."
                        )
                        hidden_sheet_overrides = st.multiselect(
                            "Hidden sheets to include",
                            options=hidden_sheet_names,
                        )
        except Exception as error:
            st.error(f"Failed to read file: {error}")
            selected_columns = []
            hidden_sheet_overrides = []

    disable_ingest = True
    if uploaded_file and selected_columns:
        if uploaded_file.name.lower().endswith((".xls", ".xlsx")) and load_workbook is None:
            disable_ingest = True
        else:
            disable_ingest = False

    if st.button("Start Ingestion", disabled=disable_ingest):
        try:
            bundle_result = run_ingestion(
                uploaded_file,
                selected_columns,
                delimiter,
                hidden_sheet_overrides,
            )
            st.success(
                f"Ingestion complete: bundle `{bundle_result.bundle.display_name}` "
                f"ready with {bundle_result.bundle.sheet_count} sheet sources."
            )

            sheet_rows = [
                {
                    "Sheet": sheet_result.sheet.sheet_name,
                    "Visibility": sheet_result.sheet.visibility_state.value,
                    "Rows": sheet_result.sheet.row_count,
                }
                for sheet_result in bundle_result.sheets
            ]
            if sheet_rows:
                st.table(sheet_rows)

            if hidden_sheet_overrides:
                st.info(
                    "Hidden sheet opt-ins recorded: " + ", ".join(hidden_sheet_overrides)
                )
        except Exception as error:
            st.error(f"Ingestion failed: {error}")

    with session_scope(_get_session_factory()) as session:
        repo = MetadataRepository(session)
        _render_sheet_catalog(repo)


if __name__ == "__main__":
    main()
