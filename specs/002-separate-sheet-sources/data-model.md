# Data Model — Sheet-Level Data Sources

## Entity Overview

| Entity | Purpose | Key Relationships |
|--------|---------|-------------------|
| `SourceBundle` | Represents an uploaded Excel workbook or CSV file; tracks ownership, hash, ingestion status, and refresh cadence. | One-to-many with `SheetSource`; one-to-many with `BundleAudit`; aggregate metrics roll up here. |
| `SheetSource` | Logical dataset mapped to a single sheet (Excel) or entire CSV file; encapsulates sheet-specific schema, row metrics, and activation state. | Belongs to `SourceBundle`; referenced by `QueryRecord`, `EmbeddingVector`, dashboards, and queries. |
| `BundleAudit` | Records ingestion attempts for a `SourceBundle`, including hidden sheet selections, duration metrics, and user actions. | Belongs to `SourceBundle`; summarizes sheet-level outcomes. |
| `SheetMetric` | Captures performance metrics (ingestion duration, query latency) per sheet for monitoring thresholds defined in the spec. | Belongs to `SheetSource`. |
| `QueryDefinition` (existing) | Stores saved queries/dashboards linking sheet sources, join configuration, and derived metrics. | Many-to-many with `SheetSource` via `QuerySheetLink`. |
| `QuerySheetLink` | Junction table that tracks which sheets participate in a query, including role (primary, join) and last validation timestamp. | Links `QueryDefinition` and `SheetSource`. |
| `QueryRecord` (existing) | Row-level textual data produced during ingestion for embeddings/search. | Now references `SheetSource` instead of `DataFile`. |
| `EmbeddingVector` (existing) | Vector representation for semantic search; unchanged structure but foreign key swaps to `SheetSource`. | Belongs to `QueryRecord`. |

> Note: The current `DataFile` table will be decomposed into `SourceBundle` + `SheetSource`. Migration steps are captured in the implementation plan.

## Entity Details

### SourceBundle

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key. |
| `display_name` | String(255) | Analyst-friendly name, typically original filename without extension. |
| `original_path` | Text | Absolute path recorded for traceability. |
| `file_hash` | String(64) | Unique SHA256 hash of the full workbook/CSV bytes; deduplicates re-uploads. |
| `file_type` | Enum(csv, excel) | Determines parsing strategy. |
| `delimiter` | String(8) | Populated for CSV bundles. |
| `refresh_cadence` | Interval/Enum | Inherits from existing metadata; used for scheduling rescans. |
| `ingestion_status` | Enum(pending, processing, ready, failed) | Roll-up state across sheet ingestions. |
| `sheet_count` | Integer | Derived metric for monitoring. |
| `created_at` / `updated_at` | DateTime | Audit timestamps. |
| `owner_user_id` | UUID | References user/owner concept if available; required for permissions inheritance. |

**State transitions**: `pending → processing → ready` on successful ingestion; `processing → failed` on errors. Any sheet failure bubbles status to `partial_failed` (new enum) until retried or acknowledged.

### SheetSource

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key, stable across refreshes. |
| `bundle_id` | UUID (FK) | References `SourceBundle`. |
| `sheet_name` | String(255) | Raw sheet/tab name; for CSV, set to `__csv__`. |
| `display_label` | String(255) | Computed `{bundle.display_name}:{sheet_name}`; editable by users. |
| `visibility_state` | Enum(visible, hidden_opt_in) | Tracks whether the sheet was hidden and explicitly enabled. |
| `row_count` | Integer | Total ingested rows. |
| `column_schema` | JSON | Array of column descriptors (name, inferred type, nullable flag). |
| `status` | Enum(active, inactive, deprecated) | Drives dashboard availability. |
| `last_refreshed_at` | DateTime | Updated per sheet on successful rescan. |
| `checksum` | String(64) | Hash of sheet-level data to detect renames/content shifts. |
| `position_index` | Integer | Original sheet order for UI sorting. |
| `description` | Text | Editable metadata for catalog search. |

**State transitions**: `active` remains until sheet removed → `inactive`; can be set to `deprecated` when dashboards migrate away. Reactivation path requires re-validation to `active`.

### BundleAudit

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key. |
| `bundle_id` | UUID (FK) | Parent bundle. |
| `initiated_by` | UUID | User performing ingestion/refresh. |
| `started_at` / `completed_at` | DateTime | Timing metrics. |
| `sheet_summary` | JSON | Captures counts of created/updated/inactive sheets. |
| `hidden_sheets_enabled` | JSON | Array of sheet names opted in during run. |
| `status` | Enum(succeeded, failed, partial) | Aligns with existing audit semantics. |

### SheetMetric

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key. |
| `sheet_id` | UUID (FK) | References `SheetSource`. |
| `metric_type` | Enum(ingestion_duration_ms, query_p95_ms) | Focus on ingestion and query latency budgets. |
| `p50` / `p95` | Float | Captured per run. |
| `recorded_at` | DateTime | Timestamp for metric. |

### QueryDefinition (updates)

- Store relationships via `QuerySheetLink` rather than implicit dataset references.
- Add `validation_checksum` to ensure involved sheets remain schema-compatible; update on refresh.

### QuerySheetLink (new)

| Field | Type | Notes |
|-------|------|-------|
| `query_id` | UUID (FK) | References `QueryDefinition`. |
| `sheet_id` | UUID (FK) | References `SheetSource`. |
| `role` | Enum(primary, join, union) | Indicates usage in query. |
| `join_keys` | JSON | Stores join columns when applicable. |
| `last_validated_at` | DateTime | Updated after compatibility check. |

Composite primary key: (`query_id`, `sheet_id`, `role`).

## Validation Rules

- `SheetSource.sheet_name` must be unique per `SourceBundle` (case-insensitive) to avoid collisions during refresh.
- `SheetSource.column_schema` entries require `name`, `inferred_type`, and `nullable` flags; ingestion fails if headers missing or duplicate.
- Hidden sheet opt-ins must be recorded in `BundleAudit.hidden_sheets_enabled`; ingestion rejects hidden sheets without explicit opt-in flag.
- `SheetMetric` entries breaching thresholds (ingestion >120,000 ms or query >5,000 ms) trigger monitoring alerts propagated to performance dashboards.
- Refresh process must compare `SheetSource.checksum` + `column_schema` to detect renames; if checksum matches but sheet name differs, reassign existing `SheetSource.id` and update `sheet_name`.
- Queries referencing `inactive` sheets must produce pre-execution warnings; execution only allowed after user acknowledgment or sheet reactivation.

## Relationships Diagram (textual)

- `SourceBundle 1 — * SheetSource`  
- `SheetSource 1 — * QueryRecord`  
- `SheetSource 1 — 1..* SheetMetric`  
- `SourceBundle 1 — * BundleAudit`  
- `QueryDefinition * — * SheetSource` via `QuerySheetLink`

## Migration Considerations

1. Create `SourceBundle`, `SheetSource`, `QuerySheetLink`, and `SheetMetric` tables; backfill existing `DataFile` rows into the new schema (each `DataFile` becomes bundle + sheet for CSV).  
2. Update foreign keys in `QueryRecord`, `EmbeddingVector`, and related services to reference `SheetSource`.  
3. Populate `SheetSource.position_index` using workbook ordering on first migration; defaults to 0 for CSV.  
4. Drop deprecated `DataFile.sheet_name` column after migration to avoid confusion.  
5. Update repositories/services to expose bundle + sheet APIs, maintaining backwards compatibility via shims until consumers migrate.
