# QnA Data Dashboard

Local-first Streamlit dashboard for exploring query coverage, semantic search quality, and ingestion health across spreadsheet datasets. Everything runs on your machine: datasets are stored on disk, embeddings resolve locally, and analytics rely on the bundled SQLite metadata store.

## Features
- Local ingestion pipeline for CSV and Excel bundles with per-sheet visibility controls and column selection that now deduplicates headers across all sheets for quicker trial setup.
- Dual-mode search that runs semantic embeddings (Chroma-backed) alongside lexical SequenceMatcher results with per-mode pagination.
- Query Builder that previews joined sheets, flags conflicts, and helps analysts validate trial joins before committing.
- Coverage Analytics page that materializes redundancy metrics, cluster summaries, and diversity scores with one-click refreshes.
- FastAPI backend exposing ingestion, search, and analytics endpoints for automation-friendly workflows.

## Quick Start
### Prerequisites
- Python 3.11
- Optional: [Poetry](https://python-poetry.org/) for environment management (recommended)
- Optional: `chromadb`, `sentence-transformers`, and `openpyxl` for advanced features (already listed in `requirements.txt`)

### Install dependencies
Using Poetry:
```bash
poetry install
```

Using virtualenv + pip:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Launch the dashboard
```bash
# via Poetry
poetry run streamlit run app/main.py

# or with the bundled entry point
poetry run qna-dashboard
```

On first launch the app ensures `./data/` exists with subdirectories for raw uploads, logs, and (optionally) embeddings. Use the left sidebar to navigate between ingestion, search, query builder, and analytics.

## Recommended Workflow
1. **Ingest Datasets** – upload CSV/Excel files, choose relevant columns (unique across all sheets), and kick off embeddings. Hidden sheets can be opted in per bundle.
2. **Search** – run semantic and keyword filters against the ingested corpus, preview matching records, and inspect embeddings.
3. **Query Builder** – assemble sheet combinations, configure joins, and validate projections before exporting.
4. **Coverage Analytics** – refresh redundancy/diversity metrics, review cluster stability, and export insights for stakeholder reviews.

## How Search Works
- Corpus is built during ingestion: selected columns are normalized (trimmed, whitespace-collapsed, numbers dropped) into `QueryRecord` rows that retain dataset, sheet, column, and row offsets.
- Each search loads up to 5k recent candidates (optionally filtered by dataset or column), runs lexical similarity via `difflib.SequenceMatcher`, and in parallel computes semantic scores using embeddings persisted in Chroma with `EMBEDDING_MODEL_ID`.
- Responses return separate `semantic_results` and `lexical_results` lists plus `pagination.semantic` and `pagination.lexical` objects that track `limit`, `offset`, and `next_offset` (default `limitPerMode` is 10, capped at 50).
- Dataset-specific contextual columns come from saved analyst preferences; missing fields are tolerated and logged so searches still return even when a sheet schema drifts.
- Search latency and per-sheet metrics are recorded to SQLite for the analytics view with a target P95 under 2s; if embeddings are unavailable, the API falls back to lexical results with a banner in the UI.

## Configuration
Key environment variables (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_ROOT` | `./data` | Root directory for raw uploads, caches, and logs. |
| `CHROMA_PERSIST_DIR` | `<DATA_ROOT>/embeddings` | Preferred Chroma persistence directory for semantic vectors. |
| `CHROMA_DB_DIR` | `<DATA_ROOT>/chromadb` | Legacy alias for the Chroma persistence path (still honored). |
| `QNA_USE_CHROMADB` | `1` | Prefer the persistent Chroma client (`0` forces the bundled in-memory adapter). |
| `EMBEDDING_MODEL_ID` | `nomic-embed-text` | Embedding model used for semantic search and stored in Chroma metadata. |
| `EMBEDDING_MODEL_VERSION` | `<EMBEDDING_MODEL_ID>-v1` | Version tag persisted with embeddings to track refresh cadence. |
| `SENTENCE_TRANSFORMER_MODEL` | `all-MiniLM-L6-v2` | Legacy model env that also feeds `EMBEDDING_MODEL_ID` when set. |
| `SQLITE_URL` | `sqlite:///data/metadata.db` | Location of the metadata store that tracks bundles, sheets, queries, and metrics. |
| `QNA_LOG_DIR` | `<DATA_ROOT>/logs` | Directory for structured app logs. |
| `QNA_LOG_LEVEL` | `INFO` | Logging verbosity across Streamlit and FastAPI components. |

Set variables inline when launching, for example:
```bash
DATA_ROOT=~/qna-data poetry run streamlit run app/main.py
```

## API Server (Optional)
Start the FastAPI service when you need programmatic ingestion or analytics refreshes:
```bash
poetry run uvicorn app.api.router:create_app --factory --reload
```

Endpoints cover bundle uploads, sheet metadata, search, query previews, and analytics jobs. The service shares the same configuration options as the Streamlit app.

## Embedding Persistence & Refresh
- Chroma vectors persist under `CHROMA_PERSIST_DIR` (preferred) or `CHROMA_DB_DIR` (legacy). Persistent mode is on by default; set `QNA_USE_CHROMADB=0` to force the in-memory adapter. The ingest page surfaces the active mode plus per-sheet embedding readiness so you can confirm vectors exist before searching.
- Embeddings carry `EMBEDDING_MODEL_ID` and `EMBEDDING_MODEL_VERSION` tags so stale vectors can be detected and refreshed.
- Target same-day refresh (≤15 minutes per batch) when datasets change or the embedding model is updated; if persistence is missing, searches continue lexically with a fallback banner until embeddings are rebuilt.

## Project Layout
- `app/main.py` – Streamlit entry point and sidebar navigation.
- `app/pages/` – Multi-page Streamlit views (`1_ingest`, `2_search`, `3_analytics`, `4_query_builder`).
- `app/services/` – Domain services for ingestion, embeddings, analytics, search, and query orchestration.
- `app/db/` – SQLAlchemy metadata models, repositories, and Alembic-style migrations.
- `app/api/` – FastAPI factory and dependency wiring for automation scenarios.
- `tests/` – Unit, integration, contract, and performance suites (pytest).
- `docs/` – Operational and performance playbooks.

## Testing & Tooling
```bash
# Run the test suite with coverage
poetry run pytest

# Linting & formatting
poetry run ruff check .
poetry run black .

# Static typing
poetry run mypy
```

## Troubleshooting
- **SentenceTransformer unavailable** – the app automatically falls back to hash-based embeddings so searches remain functional without downloading models.
- **ChromaDB not installed** – either install `chromadb` to keep the default persistent experience, or set `QNA_USE_CHROMADB=0` to run the in-memory adapter (vectors reset between runs).
- **Database locked errors** – ensure no stray processes hold `data/metadata.db`; the repository uses SQLite with relaxed thread checks for Streamlit compatibility.

## Contributing
1. Fork the repository and create a feature branch.
2. Add or update tests alongside code changes.
3. Run the quality gates (`ruff`, `black`, `mypy`, `pytest`) before opening a PR.
4. Document user-facing changes in the README or relevant Streamlit page to keep analysts unblocked.
