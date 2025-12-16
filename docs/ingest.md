# Ingest Page Source Management

- Manage document groups locally under `data/ingest_sources/`, with auto-versioned filenames and audit logging for uploads and deletions.
- Supported source types: CSV, XLS/XLSX, Parquet (50 MB max per file by default, configurable via env).
- Re-embed sources individually or in batches with a per-group concurrency cap (default 3) and job status visibility.
- Preferences for contextual columns are saved per group and restored when switching groups.
- Use the Streamlit ingest page to upload, delete, queue re-embeds, and switch groups without restarting the app.
