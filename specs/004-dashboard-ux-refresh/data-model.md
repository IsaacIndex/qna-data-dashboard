# Data Model: Q&A Dashboard UX Refresh

## Entities

- **Dataset**
  - Fields: `id` (UUID), `display_name`, `file_type` (csv|excel), `ingestion_status` (pending|processing|ready|failed), `sheet_count`, `row_count`, `has_missing_headers` (bool), `created_at`, `updated_at`.
  - Relationships: has many `Sheet`; has many `ColumnPreference` (audit/mirror only).
  - Validation: `sheet_count` ≥1 when ready; `ingestion_status` transitions follow state machine below.

- **Sheet**
  - Fields: `id`, `dataset_id`, `sheet_name`, `display_label`, `visibility_state` (visible|hidden), `status` (pending|ingesting|ready|failed), `row_count`, `column_schema` (list of column definitions), `last_refreshed_at`.
  - Relationships: belongs to `Dataset`; contributes columns to `ColumnCatalog`.
  - Validation: `column_schema` entries must include `name`, `normalized_key`, and `availability` (available|missing|duplicate|unusable).

- **ColumnCatalog Entry**
  - Fields: `column_name`, `display_label`, `normalized_key`, `sheet_ids` (list), `availability` (available|missing|unusable), `data_type` (optional), `last_seen_at`.
  - Relationships: aggregated from `Sheet.column_schema` per dataset; consumed by embedding column picker.
  - Validation: `normalized_key` unique per dataset; mark entries with only missing headers as `availability=missing` and exclude from default selection list.

- **ColumnPreference** (device-local source of truth, optionally mirrored to backend)
  - Fields: `dataset_id`, `device_id` (browser-local identifier), `selected_columns` (ordered list of `{name, display_label, position}`), `max_columns` (int|null), `version` (int), `updated_at`.
  - Relationships: associated with `Dataset`; mirrored snapshots may be stored in metadata DB for audit/analytics.
  - Validation: positions must be consecutive starting at 0; `selected_columns` limited to available catalog entries; `max_columns` ≥ len(selected_columns).

- **SearchResult**
  - Fields: `result_id`, `dataset_id`, `sheet_id`, `row_id` (optional), `similarity_score` (float 0–100), `similarity_label` (Very Low|Low|Medium|High|Very High), `color_stop` (hex from palette), `context_columns` (list of `{name, display_label, value}`), `rank`, `query_id`.
  - Relationships: references `Sheet` and `Dataset`; decorated with `ColumnPreference` fields.
  - Validation: `similarity_score` clamped 0–100; `similarity_label` derived from score banding.

- **SessionState**
  - Fields: `dataset_id`, `active_tab`, `selected_sheets` (list), `selected_columns` (list), `filters`, `preference_status` (idle|loading|ready|error), `last_saved_at`, `reset_flag` (bool).
  - Relationships: hydrated from localStorage at load, synced to Streamlit `session_state`.
  - Validation: `active_tab` must be one of configured pages; reset must clear selections only after explicit confirmation.

- **AnalyticsEvent**
  - Fields: `event`, `duration_ms`, `dataset_id`, `tab`, `success` (bool), `detail` (optional message), `timestamp`.
  - Relationships: written to local JSONL logs; optionally mirrored to DB for audits.
  - Validation: `duration_ms` ≥0; `event` limited to known set (search.latency, tab.switch.latency, preference.load, preference.save, column.selection.persist).

## State Transitions

- Dataset ingestion: `pending -> processing -> ready` (or `failed` on error); `ready -> processing` allowed on reingest; `failed -> processing` allowed after fix.
- Sheet status: `pending|ingesting -> ready|failed`; hidden sheets remain eligible for catalog aggregation when explicitly included.
- Column preference: `draft (session/localStorage) -> saved` when commit occurs; `saved -> reset` clears selections and restores defaults; mirroring to backend is best-effort and non-blocking.
- Search flow: `idle -> running -> success|failure`; on tab switches, session state preserves selections and preferences unless `reset_flag` triggers `-> default`.

## Validation Rules

- Column picker renders only `availability=available` by default; missing/unusable columns appear with badges and cannot be selected.
- Similarity score banding: 0–20 Very Low, 21–40 Low, 41–65 Medium, 66–85 High, 86–100 Very High; color stops taken from the defined neutral→teal palette and legend shown on page.
- Preference load must resolve from localStorage within 100ms target; if unavailable, UI renders defaults and queues best-effort backend mirror retrieval without blocking search.
- Reset actions require explicit confirmation and log an `preferences.reset` analytics event.
