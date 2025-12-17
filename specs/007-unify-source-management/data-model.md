# Data Model: Unified Source Management

## Entities

### Source
- **Fields**: `uuid` (canonical, immutable), `label` (human-readable name), `dataset` (string), `type` (tmp_file | sheet | embedding), `status` (new | ingesting | ready | archived | error), `groups` (list of tags), `last_updated` (timestamp), `legacy` (bool), `metadata` (dict: headers_present, path, size, checksum optional).
- **Constraints**: `uuid` unique across all sources; `label+dataset+type` must not collide once normalized; statuses follow canonical set; legacy true requires recorded remap or placeholder defaults.
- **Relationships**: May have zero or more `EmbeddingJob` records; belongs to zero or more `Group` tags.

### Legacy Source
- **Fields**: Inherits Source plus `legacy_reason` (missing_headers | prior_format | missing_uuid), `remap_status` (pending | mapped | failed), `original_id` (string optional).
- **Constraints**: Must map to `uuid`; remap failure requires audit entry and surfacing in UI.

### EmbeddingJob
- **Fields**: `job_id`, `source_uuid`, `status` (queued | running | success | failed), `started_at`, `completed_at`, `error` (optional).
- **Constraints**: `source_uuid` references Source; only one active running job per source; re-embed requests queue if job already running.

### Group
- **Fields**: `name` (string), `applied_by` (user), `applied_at` (timestamp).
- **Constraints**: Names case-insensitive; applied per source.

### Status
- **Values**: `new`, `ingesting`, `ready`, `archived`, `error`.
- **Transitions**: new → ingesting → ready | error; ready → archived; archived → ready (restore) permitted; error → ingesting allowed after remediation.

## Validation Rules
- Source records must include human-readable `label` and canonical `uuid`; legacy items missing data must be remapped before actions.
- Bulk updates must validate each source individually; partial failures reported per item.
- Re-embed operations must validate target `source_uuid` and deny archived unless explicitly confirmed.

## State & Lifecycle
- Legacy detection: when missing `uuid` or absent in `data/ingest_sources`, attempt remap; on success mark `legacy=false`; on failure mark `remap_status=failed` and block destructive actions until resolved.
- Status propagation: updates reflected across Source Management, Sheet Source Catalog, and Re-embed views within one refresh cycle.
- Infinite scroll: server returns batches with stable ordering and cursor for next page; filter/sort applied server-side.
