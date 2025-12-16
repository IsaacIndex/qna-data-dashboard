# Research: Ingest Page Source Management

## Decisions & Rationale

### Upload persistence and retention
- **Decision**: Store uploaded sources under `data/ingest_sources/{group}/` with versioned filenames; retain until explicitly deleted through the ingest UI/API.  
- **Rationale**: Aligns with existing local-first data footprint, avoids new infra approvals, and supports auditability/version history.  
- **Alternatives considered**: Object storage (adds dependency/ops overhead), temp storage (breaks audit/rehydration and conflicts with deletion controls).

### Upload size and MIME enforcement
- **Decision**: Enforce max 50 MB per file; allow CSV, XLSX/XLS, and Parquet; reject others with pre-upload validation and clear messaging.  
- **Rationale**: Keeps ingestion within Streamlit/FastAPI payload comfort and pandas/openpyxl/parquet capabilities while meeting typical analyst file sizes.  
- **Alternatives considered**: Higher limits (risk timeouts/latency), narrower types (hurts usability and current ingest behavior).

### Re-embed concurrency and queueing
- **Decision**: Cap re-embed execution to 3 concurrent jobs per document group; queue additional jobs FIFO with visible per-source status updates.  
- **Rationale**: Protects embedding/Chroma resources, keeps UI responsive, and aligns with success criteria for completion times.  
- **Alternatives considered**: Unbounded concurrency (resource contention, failures), single-threaded (unacceptably slow for batches), per-source hard cap (less flexible than per-group pooling).
