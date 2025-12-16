# Quickstart: Ingest Page Source Management

## Setup
1) Install deps: `poetry install`  
2) Run linters/type checks: `poetry run ruff check . && poetry run black --check . && poetry run mypy`  
3) Start app (Streamlit + API): `poetry run qna-dashboard`

## Feature Flows to Verify
- Upload single/multi-file sources (CSV/XLS/XLSX/Parquet, <=50 MB each) into a selected document group; verify auto-versioning on duplicate names and status/column extraction display.
- Delete a source with confirmation; ensure deletion blocked or warned during active embedding; confirm removal from list and downstream search/index.
- Trigger re-embed for single and batch selections; observe queued/processing/completed/failed states, retry failures, and preserved prior embeddings until success.
- Switch document groups; ensure lists/preferences refresh within budget (<3s) and saved column/context selections persist per group.

## Tests
- Unit: `poetry run pytest tests/unit`
- Integration/contract: `poetry run pytest tests/integration tests/contract`
- Performance smoke: `poetry run pytest tests/performance`
- Coverage target: >=85% overall; 100% on ingest critical paths (upload/delete/re-embed/group switch handlers).
- Ingest-specific: `poetry run pytest tests/contract/test_ingest_sources.py tests/contract/test_reembed.py tests/unit/test_ingest_storage.py tests/unit/test_embedding_queue.py tests/unit/test_preferences.py`

## Observability & Performance
- Capture timings for upload readiness, delete propagation, re-embed duration, and group switch latency; report in CI artifacts.
- Ensure logs include audit metadata (who/when/action/outcome) for add/delete/re-embed.
