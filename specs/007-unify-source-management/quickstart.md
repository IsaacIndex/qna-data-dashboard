# Quickstart: Unified Source Management

## Prereqs
- Python 3.11
- Poetry installed

## Setup
```bash
cd /Users/isaacibm/GitHub/qna-data-dashboard
poetry install
```

## Run dashboard
```bash
poetry run streamlit run app/main.py
```

## Run API (if split)
```bash
poetry run uvicorn app.api.main:app --reload
```

## Tests
```bash
poetry run pytest           # unit/integration
poetry run pytest tests/performance -k ingest  # performance smoke
poetry run ruff check .
poetry run black --check .
poetry run mypy app
```

## Feature-specific checks
- Unified list: open the ingest tab → “Unified source inventory”; filters default to “All” for dataset/type/status/group. Scroll with “Load more sources” to confirm server-backed pagination stays under the 600ms/page budget.
- Re-embed selector: options list `label (dataset, type)` only. Queue a job and confirm status overrides flow back into the list without exposing UUIDs.
- Legacy reconcile dry-run: call `/sources/reconcile-legacy` with `{"dry_run": true}` and verify conflicts are returned before any files are written.

## Unified source API quick calls
Use these from another shell after starting `uvicorn`:

```bash
# List sources with filters and pagination
curl "http://localhost:8000/sources?limit=25&dataset=analytics&type=sheet"

# Bulk status/groups update
curl -X POST http://localhost:8000/sources/bulk \
  -H "Content-Type: application/json" \
  -d '{"uuids":["<uuid-1>","<uuid-2>"],"status":"archived","groups":["finance","reviewed"]}'

# Re-embed by UUID (label stays in UI)
curl -X POST http://localhost:8000/sources/reembed \
  -H "Content-Type: application/json" \
  -d '{"uuid":"<source-uuid>"}'

# Legacy reconcile (writes restored placeholders when dry_run=false)
curl -X POST http://localhost:8000/sources/reconcile-legacy \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```
