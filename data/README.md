# Local Data Storage Policy

All datasets and derived artifacts remain on the local machine to satisfy offline and privacy requirements. Use the following directory layout when running the dashboard:

- `data/raw/` – original CSV/Excel uploads grouped by dataset identifier. Files in this directory are never modified or checked into version control.
- `data/chromadb/` – persistent storage for ChromaDB collections that back semantic search and analytics. Safe to delete to rebuild embeddings if storage needs to be reclaimed.
- `data/metadata.db` – SQLite database that stores dataset metadata, query records, clustering parameters, audits, and performance benchmarks.
- `data/logs/` – optional directory for structured logs and ingestion error exports referenced by audit records.

Do **not** create additional processed copies of data files. When re-ingesting or rebuilding embeddings, reuse the canonical files under `data/raw/` and persist new metadata to SQLite or ChromaDB. If you need to purge datasets, use the maintenance workflow in the app to remove both the raw file and associated metadata.
