# Quickstart: Q&A Dashboard UX Refresh

1. **Install & run** (Python 3.11):  
   ```bash
   poetry install
   poetry run streamlit run app/main.py
   ```
   Optional: start FastAPI for automation/tests  
   ```bash
   poetry run uvicorn app.api.router:create_app --factory --reload
   ```

2. **Ingest a multi-sheet file** to exercise deduped column picker: upload CSV/XLSX on the Ingest page, keep hidden sheets excluded by default, and confirm missing headers are skipped.

3. **Pick columns for trial embeddings**: open the column picker to see unique column names with sheet chips; select columns with keyboard/mouse, notice unavailable badges for missing headers, and confirm selections persist when switching tabs.

4. **Run a search** on the Search page: execute a query and verify contextual columns render per saved/default preferences plus a similarity legend (0–100%, neutral→teal palette) with text labels and numeric values on each row.

5. **Save/reset preferences (device-local)**: adjust contextual columns, save, refresh the browser, and confirm localStorage rehydrates the view without blocking; use reset to restore defaults and confirm a reset confirmation message appears.

6. **Check analytics events**: inspect `data/logs/analytics.jsonl` for `search.latency`, `tab.switch.latency`, `preference.load/save`, and `column.selection.persist` records after interactions; ensure durations stay under the 2s P95 budget for search/tab switches.
