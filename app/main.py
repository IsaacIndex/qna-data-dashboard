from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure package imports work when launched as a file via `streamlit run app/main.py`.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.config import get_chroma_persist_dir, get_data_root  # noqa: E402

APP_TITLE = "Local Query Coverage Analytics"


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def prepare_data_directories() -> Path:
    data_root = get_data_root()
    chroma_dir = get_chroma_persist_dir(data_root)
    logs_dir = Path(os.getenv("QNA_LOG_DIR", data_root / "logs")).expanduser()

    _ensure_directory(data_root)
    _ensure_directory(data_root / "raw")
    _ensure_directory(chroma_dir)
    _ensure_directory(logs_dir)
    return data_root


def render_home(data_root: Path) -> None:
    st.title(APP_TITLE)
    st.caption("Offline insights for query coverage, semantic search, and analytics.")

    st.subheader("Getting Started")
    st.write(
        "Use the sidebar to open ingestion, search, or coverage analytics pages. "
        "Uploaded datasets stay on disk under the configured data root."
    )
    st.info(f"Current data root: `{data_root}`")

    st.divider()
    st.markdown(
        """
        ### Workflow
        1. Upload CSV or Excel files on **Ingest Datasets** and choose text columns.
        2. Explore the corpus with semantic filtering on **Search**.
        3. Build cross-sheet previews and validate joins in **Query Builder**.
        4. Review redundancy and diversity metrics on **Coverage Analytics**.
        """
    )


def run() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🧭", layout="wide")
    data_root = prepare_data_directories()

    with st.sidebar:
        st.header("Navigation")
        st.markdown(
            "- **Ingest Datasets**: Upload files, map columns, build embeddings.\n"
            "- **Search**: Query the corpus with semantic filters.\n"
            "- **Query Builder**: Combine sheet sources, configure joins, and preview results.\n"
            "- **Coverage Analytics**: Visualize redundancy and cluster health."
        )
        st.divider()
        st.caption("All computations run locally. No data leaves your machine.")

    render_home(data_root)


if __name__ == "__main__":
    run()
