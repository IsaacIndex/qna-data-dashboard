# Validation Checklist: Q&A Dashboard UX Refresh

- [x] Ingest multi-sheet dataset and deduped column picker persists selections across tab switches (`tests/integration/ingest/test_column_picker_dedupe.py`).
- [x] Search similarity legend and contextual defaults render when no saved preferences (`tests/integration/search/test_search_similarity_ui.py`).
- [x] Device-local preferences hydrate and reset across restart cycle (`tests/integration/preferences/test_local_preferences.py`).
- [x] Preference mirror endpoints accept snapshots and return the latest copy (`tests/contract/test_preferences_mirror.py`).
- [x] Latency smoke tests stay under search/tab budgets (`tests/performance/test_latency_budgets.py`).
- [x] Analytics events logged for preference load/save/column selection persistence (`tests/unit/test_analytics_client.py`).
