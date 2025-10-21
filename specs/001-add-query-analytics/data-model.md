# Data Model: Local Query Coverage Analytics

## Overview
The feature manages three core data domains:
1. **Ingestion metadata** for imported CSV/Excel files and column selections.
2. **Query corpus artifacts** including raw text, embeddings, and clustering outputs stored locally.
3. **Operational telemetry** that captures audit logs and performance metrics.

All artifacts remain on the user's machine under the `data/` directory, with original files stored in `data/raw/`, vector data persisted in ChromaDB, and relational metadata (including labels, clustering parameters, and audits) stored in SQLite—ensuring derived insights persist across sessions without creating separate processed file copies.

## Entities

### DataFile
- **Description**: Metadata representing an imported CSV/Excel source.
- **Fields**:
  - `id` (UUID) – primary key.
  - `display_name` (string) – friendly name shown in UI.
  - `original_path` (string) – absolute path at the time of import.
  - `file_hash` (string) – checksum used to detect re-imports.
  - `file_type` (enum: `csv`, `excel`) – drives parsing strategy.
  - `delimiter` (string, nullable) – CSV delimiter when applicable.
  - `sheet_name` (string, nullable) – selected Excel sheet.
  - `selected_columns` (json array<string>) – text columns chosen for embedding.
  - `row_count` (integer) – number of processed rows across selected columns.
  - `ingestion_status` (enum: `pending`, `processing`, `ready`, `failed`) – status exposed to UI.
  - `error_summary` (string, nullable) – failure context when status = `failed`.
  - `ingested_at` (datetime) – ingestion start timestamp.
  - `processed_at` (datetime, nullable) – completion timestamp.
- **Relationships**:
  - `DataFile` 1─* `QueryRecord`.
  - `DataFile` 1─1 `IngestionAudit` (latest record).
- **Validation Rules**:
  - `selected_columns` must contain at least one column with detected text type.
  - Files exceeding configured row/size limits are rejected before ingest.
  - Re-import triggers comparison on `file_hash` to prevent duplicates.
- **State Transitions**:
  - `pending → processing → ready` (successful pipeline).
  - `processing → failed` (on exception) with retry returning to `pending`.

### QueryRecord
- **Description**: A single textual row extracted from an imported dataset.
- **Fields**:
  - `id` (UUID) – primary key.
  - `data_file_id` (UUID) – foreign key to `DataFile`.
  - `column_name` (string) – originating column.
  - `row_index` (integer) – positional index in source file.
  - `text` (string) – normalized text used for embeddings.
  - `original_text` (string) – raw input before normalization.
  - `tags` (json array<string>, nullable) – analyst-provided labels.
  - `created_at` (datetime) – ingestion timestamp.
- **Relationships**:
  - `QueryRecord` 1─1 `EmbeddingVector`.
  - `QueryRecord` *─* `SimilarityCluster` (via membership table).
- **Validation Rules**:
  - `text` must be non-empty after normalization; null or numeric-only rows are skipped.
  - `row_index` unique per (`data_file_id`, `column_name`).

### EmbeddingVector
- **Description**: SentenceTransformers embedding associated with a query record.
- **Fields**:
  - `id` (UUID) – mirrors ChromaDB vector id.
  - `query_record_id` (UUID) – foreign key to `QueryRecord`.
  - `model_name` (string) – embedding model identifier.
  - `model_version` (string) – pinned model revision hash.
  - `vector_path` (string) – reference to ChromaDB collection/vector id.
  - `embedding_dim` (integer) – dimension size (e.g., 384).
  - `created_at` (datetime) – timestamp of embedding creation.
- **Relationships**:
  - Stored physically in ChromaDB; metadata cached in SQLite to support re-processing and auditing.
- **Validation Rules**:
  - `model_name` must match configured SentenceTransformers default unless overridden.
  - Embedding recomputation invalidates prior vector and updates `created_at`.

### SimilarityCluster
- **Description**: Grouping of related queries derived from clustering over embeddings.
- **Fields**:
  - `id` (UUID) – primary key.
  - `cluster_label` (string) – human-readable descriptor (e.g., Topic keyword).
  - `algorithm` (enum: `hdbscan`, `kmeans`, etc.) – clustering method used.
  - `dataset_scope` (json array<UUID>) – included `DataFile` identifiers.
  - `member_count` (integer) – number of `QueryRecord` members.
  - `centroid_similarity` (float) – average cosine similarity to centroid.
  - `diversity_score` (float) – dispersion metric for dashboard.
  - `created_at` (datetime) – generation time.
  - `threshold` (float) – similarity cutoff used for cluster assignment.
- **Relationships**:
  - `SimilarityCluster` *─* `QueryRecord` via `ClusterMembership`.
- **Validation Rules**:
  - Clusters must record algorithm and parameters to reproduce analytics.
  - `diversity_score` normalized between 0 and 1.

### ClusterMembership
- **Description**: Join table linking queries to similarity clusters.
- **Fields**:
  - `cluster_id` (UUID) – foreign key to `SimilarityCluster`.
  - `query_record_id` (UUID) – foreign key to `QueryRecord`.
  - `similarity` (float) – similarity score for membership.
- **Validation Rules**:
  - Composite primary key (`cluster_id`, `query_record_id`).
  - `similarity` must meet or exceed cluster `threshold`.

### IngestionAudit
- **Description**: Audit entry summarizing ingestion outcomes.
- **Fields**:
  - `id` (UUID) – primary key.
  - `data_file_id` (UUID) – foreign key to `DataFile`.
  - `started_at` (datetime) – ingestion start time.
  - `completed_at` (datetime, nullable) – completion time.
  - `status` (enum: `succeeded`, `failed`, `cancelled`).
- **Fields (continued)**:
  - `processed_rows` (integer) – count of records attempted.
  - `skipped_rows` (integer) – count skipped due to validation.
  - `error_log_path` (string, nullable) – pointer to detailed error CSV.
- **Validation Rules**:
  - On failure, `error_log_path` must be populated with a readable log file.
  - `completed_at` required when status = `succeeded` or `failed`.

### PerformanceMetric
- **Description**: Captures ingestion, embedding, search, and visualization timing results.
- **Fields**:
  - `id` (UUID) – primary key.
  - `metric_type` (enum: `ingestion`, `embedding`, `search`, `dashboard_render`).
  - `data_file_id` (UUID, nullable) – associated dataset when relevant.
- **Fields (continued)**:
  - `p50_ms` / `p95_ms` (float) – latency measurements.
  - `records_per_second` (float, nullable) – throughput for ingestion/embedding.
  - `benchmark_run_id` (UUID) – links to benchmark execution metadata.
  - `recorded_at` (datetime) – timestamp for release reporting.
- **Validation Rules**:
  - `p95_ms` must be <= configured budget thresholds; exceedances flagged for review.

## Relationships Summary
- `DataFile` 1─* `QueryRecord` 1─1 `EmbeddingVector`.
- `QueryRecord` *─* `SimilarityCluster` via `ClusterMembership`.
- `DataFile` 1─* `IngestionAudit`.
- `PerformanceMetric` optionally references `DataFile` or `SimilarityCluster` for scoped measurements.

## State & Workflow Notes
1. **Ingestion**: File metadata captured in `DataFile`, audit entry created (status `pending`). After processing, `QueryRecord` + `EmbeddingVector` rows generated, audit updated to `succeeded` or `failed`.
2. **Search**: Queries resolved via ChromaDB using metadata filters (`DataFile`, `column`, similarity threshold). Results hydrate from SQLite + Chroma metadata.
3. **Analytics**: Clustering jobs produce `SimilarityCluster` and `ClusterMembership` entries; metrics logged for dashboard summarization.
4. **Reprocessing**: When files change, previous records soft-deleted or versioned via new `DataFile` row keyed by `file_hash`, enabling comparison and rollback.
