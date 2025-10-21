# Quickstart: Local Query Coverage Analytics

## Prerequisites
- Python 3.11 installed locally.
- [Poetry](https://python-poetry.org/docs/) ≥ 1.8.
- Git LFS not required (datasets remain local and excluded from repo).

## Environment Setup
1. Install dependencies:
   ```bash
   poetry install
   ```
2. Activate the virtual environment:
   ```bash
   poetry shell
   ```
3. Configure local paths (optional overrides in `.env`):
   ```
   DATA_ROOT=./data
   CHROMA_DB_DIR=./data/chromadb
   SQLITE_URL=sqlite:///data/metadata.db
   SENTENCE_TRANSFORMER_MODEL=all-MiniLM-L6-v2
   ```

## Running the Streamlit App
```bash
poetry run streamlit run app/main.py
```

The app exposes three primary pages:
1. **Ingest Datasets** – upload CSV/Excel, map columns, start embedding jobs.
2. **Search** – execute semantic queries, apply dataset/column filters, export results.
3. **Coverage Analytics** – explore cluster charts, redundancy ratios, and diversity metrics.

## Test & Quality Gates
- Lint:
  ```bash
  poetry run ruff check .
  poetry run black --check .
  ```
- Type check:
  ```bash
  poetry run mypy app
  ```
- Unit & integration tests with coverage:
  ```bash
  poetry run pytest --cov=app --cov-report=term-missing
  ```
- Performance smoke tests (stores baselines under `tests/performance/benchmarks/`):
  ```bash
  poetry run pytest tests/performance --benchmark-only
  ```

## Benchmark & Audit Review
- View latest ingestion audits inside the app or via API:
  ```bash
  curl http://localhost:8502/api/datasets/{dataset_id}/audits/latest
  ```
- Benchmark history persists in SQLite (`performance_metrics` table); review via `sqlite3 data/metadata.db`.

## Accessibility & UX Checks
- Run Streamlit accessibility inspector (`Ctrl+Shift+A`) per page.
- Validate color contrast and keyboard navigation for custom components before merge.

## Data Management
- Raw uploads stored under `data/raw/` (one subfolder per dataset).
- ChromaDB vector store persists in `data/chromadb/`; embeddings can be rebuilt via re-ingest.
- Audit logs, labeling metadata, clustering parameters, and benchmark metrics live in `data/metadata.db`.
- Derived analytics rely on persisted metadata (SQLite and ChromaDB) so user-applied labels reappear on restart without producing intermediary processed files.
- Use the in-app maintenance page (planned in Phase 2) to purge datasets, drop embeddings, or reprocess on demand.
