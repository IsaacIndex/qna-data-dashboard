# Data Model: Ingest Page Source Management

## Entities

### Document Group
- **Attributes**: `id`, `name`, `description`, `created_at`, `updated_at`.
- **Relationships**: Has many Source Files; has one Column Preference Set (latest active).
- **Notes**: Scope boundary for ingest UI, embeddings, and preferences.

### Source File
- **Attributes**: `id`, `document_group_id`, `filename`, `version_label` (e.g., "name (2).xlsx"), `size_bytes`, `mime_type`, `storage_path`, `added_by`, `added_at`, `status` (uploaded|validating|ready|failed|embedding|embedded), `last_updated_at`, `validation_error` (nullable), `audit_log_ref`.
- **Relationships**: Belongs to Document Group; referenced by Embedding Jobs.
- **Rules**: Duplicate filenames are auto-versioned; deletions blocked during active embedding unless cancelled with warning; max 50 MB; allowed types CSV/XLS/XLSX/Parquet; missing headers skipped during extraction.

### Column Preference Set
- **Attributes**: `id`, `document_group_id`, `selected_columns` (unique list), `contextual_fields`, `updated_by`, `updated_at`, `version`.
- **Relationships**: Belongs to Document Group; applied to Embedding Jobs.
- **Rules**: Saved per group; pre-populates ingest/re-embed flows; must reflect only columns available across group sources.

### Embedding Job
- **Attributes**: `id`, `document_group_id`, `source_file_ids` (list), `status` (queued|processing|completed|failed|cancelled), `started_at`, `completed_at`, `failure_reason` (nullable), `triggered_by`, `queue_position`, `run_duration_ms`.
- **Relationships**: Targets one or many Source Files within a Document Group; uses Column Preference Set snapshot.
- **Rules**: Up to 3 concurrent jobs per group; queued FIFO; prior embeddings remain active until success; failures are retryable without removing sources.

## State Transitions

- **Source File**:
  - uploaded → validating → ready | failed
  - ready → embedding → embedded | failed
  - embedded → deleted (only when no active embedding) or re-embedded via Embedding Job
- **Embedding Job**:
  - queued → processing → completed | failed | cancelled

## Identity & Uniqueness

- Document Group: unique `name`.
- Source File: unique per `(document_group_id, version_label)`.
- Column Preference Set: one active per group; version increments on change.
- Embedding Job: unique `id`; queue order per group by `queued_at`.
