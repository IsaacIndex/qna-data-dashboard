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
from app.services.embeddings import EmbeddingService  # noqa: E402
from app.services.ingestion import IngestionOptions, IngestionService  # noqa: E402
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


def _render_dataset_list(repo: MetadataRepository) -> None:
    datasets = repo.list_data_files()
    if not datasets:
        st.info("No datasets ingested yet. Upload a CSV or Excel file to get started.")
        return
    st.subheader("Existing Datasets")
    for dataset in datasets:
        st.write(
            f"**{dataset.display_name}** – status **{dataset.ingestion_status.value}**, "
            f"{dataset.row_count} records"
        )


def run_ingestion(uploaded_file, selected_columns: Sequence[str], delimiter: str | None, sheet: str | None):
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
                result = ingestion_service.ingest_file(
                    source_path=temp_path,
                    display_name=uploaded_file.name,
                    options=IngestionOptions(
                        selected_columns=selected_columns,
                        delimiter=delimiter or None,
                        sheet_name=sheet or None,
                    ),
                )
        finally:
            temp_path.unlink(missing_ok=True)

        log_event(LOGGER, "streamlit.ingestion.complete", dataset_id=result.data_file.id)
        return result


def main() -> None:
    st.title("Ingest Datasets")
    st.caption("Upload CSV or Excel files, select text columns, and build embeddings locally.")

    uploaded_file = st.file_uploader("Select CSV or Excel file", type=["csv", "xlsx", "xls"])
    selected_columns: list[str] = []
    delimiter: str | None = None
    sheet_name: str | None = None
    preview_headers: list[str] = []
    preview_rows: list[dict[str, str]] = []
    if uploaded_file:
        try:
            preview_headers, preview_rows = _preview_rows(uploaded_file)
            if preview_rows:
                st.table(preview_rows)
            selected_columns = st.multiselect(
                "Select text columns to embed",
                options=list(preview_headers),
            )
            if uploaded_file.name.lower().endswith(".csv"):
                delimiter = st.text_input("Delimiter", value=",")
            else:
                if load_workbook is None:
                    st.error("Excel ingestion requires installing the 'openpyxl' package.")
                else:
                    workbook = load_workbook(uploaded_file, read_only=True)
                    sheet_name = st.selectbox("Sheet name", options=workbook.sheetnames)
                    workbook.close()
                    uploaded_file.seek(0)
        except Exception as error:
            st.error(f"Failed to read file: {error}")

    disable_ingest = True
    if uploaded_file and selected_columns:
        if uploaded_file.name.lower().endswith((".xls", ".xlsx")) and load_workbook is None:
            disable_ingest = True
        else:
            disable_ingest = False

    if st.button("Start Ingestion", disabled=disable_ingest):
        try:
            result = run_ingestion(uploaded_file, selected_columns, delimiter, sheet_name)
            st.success(
                f"Ingestion complete: dataset `{result.data_file.display_name}` "
                f"ready with {result.processed_rows} records."
            )
        except Exception as error:
            st.error(f"Ingestion failed: {error}")

    with session_scope(_get_session_factory()) as session:
        repo = MetadataRepository(session)
        _render_dataset_list(repo)


if __name__ == "__main__":
    main()
