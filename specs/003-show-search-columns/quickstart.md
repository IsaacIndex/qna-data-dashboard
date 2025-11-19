# Quickstart: Search Result Column Selections

## Prerequisites
- Python 3.11 with Poetry dependencies installed (`poetry install --with dev`)
- Local metadata database initialized (`poetry run qna-dashboard --setup` or run ingest workflow)
- At least one dataset ingested with contextual columns available

## Run the Dashboard
```bash
poetry run qna-dashboard
```
- Streamlit app launches at `http://localhost:8501`
- Ensure backend FastAPI workers start automatically (handled inside `app/main.py`)

## Configure Display Columns
1. Navigate to **Search** page.
2. In the **Result Columns** panel, choose a dataset.
3. Select up to 10 supplemental columns. The table below the picker lets you rename labels and adjust their `Order` value to control display sequence.
4. Click **Save Preferences** to persist the selection. A confirmation toast should list the saved fields and order.
5. To revert a dataset to baseline metadata, use **Reset to Defaults**; the panel clears the selection immediately and reloads the catalog.

## Validate Search Rendering
1. Enter a representative query.
2. Confirm each result row shows baseline metadata plus the chosen supplemental columns in order.
3. Trigger a multi-dataset search; verify each dataset’s rows honor their own saved configuration.
4. Toggle the **Show Missing Values** option to confirm placeholders (`"—"`) appear for nulls.

## Regression & Performance Checks
- Run unit/integration tests:
  ```bash
  poetry run pytest tests/unit/test_column_preferences.py tests/integration/test_search_columns.py
  ```
- Execute performance benchmark:
  ```bash
  poetry run pytest tests/performance/test_search_latency.py --benchmark-only
  ```
- Inspect generated logs for preference change entries and missing-column warnings.

## Resetting Preferences
- Use the **Reset to Defaults** button in the UI, or run:
  ```bash
  poetry run python -m app.cli.reset_preferences --dataset-id <DATA_FILE_ID>
  ```
- Confirm search results revert to baseline metadata only.
