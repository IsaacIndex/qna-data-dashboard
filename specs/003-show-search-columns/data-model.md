# Data Model: Search Result Column Selections

## Entities

### ColumnPreference
- **Purpose**: Stores the ordered list of supplemental columns an analyst wants to display for a given dataset in search results.
- **Key Fields**:
  - `id` (UUID, primary key)
  - `data_file_id` (FK → `DataFile.id`, cascades on delete)
  - `user_id` (nullable string; `NULL` represents global default for all analysts)
  - `selected_columns` (JSON array of `{column_name, display_label, position}`)
  - `max_columns` (integer, default 10, enforces selection cap)
  - `is_active` (boolean, default `true`)
  - `created_at`, `updated_at` (UTC timestamps)
- **Constraints**:
  - Unique composite index on `(data_file_id, user_id)` to ensure one active preference per analyst-dataset pair.
  - `selected_columns` length validated against `max_columns`.

### ColumnPreferenceChange
- **Purpose**: Audit trail capturing preference updates to satisfy FR-007 governance logging.
- **Key Fields**:
  - `id` (UUID, primary key)
  - `preference_id` (FK → `ColumnPreference.id`, cascade on delete)
  - `user_id` (string, required)
  - `dataset_display_name` (string snapshot for reporting)
  - `selected_columns_snapshot` (JSON array mirroring persisted selection)
  - `changed_at` (UTC timestamp)
- **Constraints**:
  - Append-only table ordered by `changed_at DESC`.

### DisplayableColumnCatalog (logical view)
- **Purpose**: Derived representation combining `DataFile.selected_columns`, `SheetSource.column_schema`, and ingestion metadata to enumerate selectable fields.
- **Fields**:
  - `data_file_id`
  - `column_name`
  - `column_label`
  - `data_type`
  - `is_available` (boolean indicating presence across latest ingestion)
  - `last_seen_at`
- **Population**: Materialized at runtime via repository helper; no dedicated persistence beyond existing tables.

### SearchResultView (logical view)
- **Purpose**: Response model used by API/UI to render each search match with supplemental columns.
- **Fields**:
  - `record_id`
  - `dataset_id`
  - `baseline_metadata` (dataset name, column, row id)
  - `contextual_columns` (ordered mapping of column → value or placeholder)
  - `missing_columns` (list of columns not available for this row)
- **Population**: Constructed from `QueryRecord` joins during search execution.

## Relationships

- `DataFile 1─* ColumnPreference`
- `ColumnPreference 1─* ColumnPreferenceChange`
- `ColumnPreference` references logical `DisplayableColumnCatalog` to validate `selected_columns`.
- `SearchResultView` consumes `ColumnPreference` + `QueryRecord` to render contextual columns.

## Validation Rules

- On save, `selected_columns` must:
  - Only include column names flagged `is_available=True` in the current catalog snapshot.
  - Contain ≤ `max_columns` entries and maintain unique column names.
- During search rendering:
  - Missing values replace with localized placeholder text (e.g., `"—"`).
  - Deprecated columns trigger a warning banner and log entry while remaining rows fall back gracefully.
- Audit entries must record every change (create/update/delete) with responsible `user_id` and timestamp.

## State Considerations

- Preference lifecycle:
  1. `create` when analyst first customizes columns.
  2. `update` when selections reorder or change.
  3. `deactivate` (set `is_active=False`) if analyst resets to defaults or dataset is removed.
- When a dataset is deleted or re-imported with new ID, cascading delete removes orphaned preferences; re-import triggers user notification to reconfigure columns.
