# Phase 0 Research: Local Query Coverage Analytics

## Python Runtime & Dependency Management
- **Decision**: Standardize on Python 3.11 managed with Poetry for dependency locking and reproducible Streamlit deployments.  
- **Rationale**: Python 3.11 offers performance gains for async I/O and aligns with modern Streamlit support; Poetry provides deterministic local installs and clean script entry points.  
- **Alternatives considered**: `pip` + `requirements.txt` (lacks lockfile and environment isolation); `uv` (fast but not yet standard in org, would require governance approval).

## Code Quality Tooling Baseline
- **Decision**: Enforce `ruff` (lint), `black` (format), `mypy` (type checking), and `pytest` with coverage gates in CI.  
- **Rationale**: These tools satisfy Code Quality Rigor, integrate with Poetry, and cover linting, formatting, typing, and testing needs for Python data apps.  
- **Alternatives considered**: `flake8` + plugins (overlaps with `ruff`), `isort` (redundant due to `ruff`/`black`), skipping types (violates constitution expectations).

## Testing & Coverage Approach
- **Decision**: Target >=85% line coverage overall and 100% on ingestion + search critical paths; combine `pytest` unit/integration suites with fixture datasets and `pytest-benchmark` for performance smoke tests.  
- **Rationale**: Meets constitution thresholds, exercises embeddings and search flows end-to-end, and provides measurable evidence for performance budgets.  
- **Alternatives considered**: Separate benchmark harness (adds maintenance overhead); manual timing via ad-hoc scripts (less repeatable, no CI integration).

## Excel/CSV Ingestion Libraries
- **Decision**: Use `pandas` for unified CSV/Excel parsing with `pyarrow` acceleration for CSV and `openpyxl` backend for XLSX ingestion.  
- **Rationale**: Pandas handles delimiter variations, schema inference, and integrates with Streamlit file uploader; `pyarrow` boosts CSV performance and `openpyxl` is stable for Excel.  
- **Alternatives considered**: `polars` (faster but Streamlit support less mature); `xlrd` (deprecated for modern XLSX).

## Visualization Toolkit for Coverage Analytics
- **Decision**: Adopt Plotly Express within Streamlit for interactive cluster, distribution, and overlap visualizations.  
- **Rationale**: Plotly provides rich interactive charts, works seamlessly with Streamlit, and supports hover tooltips critical for interpreting clusters.  
- **Alternatives considered**: Altair (less interactive for cluster drill-down); Matplotlib (static, requires more manual work for interactivity).

## Local Storage & Audit Logging Architecture
- **Decision**: Organize storage under `data/` with subdirectories `raw/` and `chromadb/`, persist ingestion metadata, labeling, clustering parameters, and audit logs in a local SQLite database, keeping derived outputs as structured metadata rather than intermediary files.  
- **Rationale**: Meets the requirement to avoid duplicate processed files while ensuring labels and analytics context survive across sessions for consistent UX.  
- **Alternatives considered**: Adding a `processed/` directory for normalized data (rejected to comply with no intermediary output requirement); relying solely on in-memory caches (fails persistence expectations); flat JSON log files (harder to query/aggregate); external databases (violates offline requirement).

## Performance Benchmarking Strategy
- **Decision**: Implement repeatable benchmarks via `pytest-benchmark` scenarios for ingestion (embedding throughput) and search (latency) and store baseline JSON under `tests/performance/benchmarks/`.  
- **Rationale**: Provides automated regression checks, integrates with pytest, and generates artifacts suitable for CI comparison.  
- **Alternatives considered**: Custom timing scripts (less standardized); relying solely on manual testing (no evidence trail).

## Streamlit Implementation Practices
- **Decision**: Structure Streamlit app with multipage layout, stateful session management, and cached embedding/search calls using `st.cache_resource` to avoid recomputation.  
- **Rationale**: Multipage flow aligns with ingestion → search → analytics journey; caching ensures responsive UX and meets performance budgets.  
- **Alternatives considered**: Single-page app (harder to maintain complex interactions); manual caching via global variables (less predictable).

## ChromaDB Usage Patterns
- **Decision**: Run ChromaDB in persistent client mode with on-disk storage, use collection per dataset, and index embeddings with metadata fields for file, column, row, and tags.  
- **Rationale**: Collection-per-dataset simplifies filtering, on-disk mode honors local persistence, and metadata enables targeted search/analytics.  
- **Alternatives considered**: Single collection for all data (complex filtering); in-memory mode (data loss risk between sessions).

## SentenceTransformers Embedding Strategy
- **Decision**: Use the `all-MiniLM-L6-v2` model via `SentenceTransformer`, batching inputs with deterministic preprocessing (lowercasing, whitespace trim) and allow model path override for air-gapped setups.  
- **Rationale**: Model balances accuracy/performance, small footprint suits offline laptops, and override supports custom domain models.  
- **Alternatives considered**: Larger models (slower, exceed performance budgets); OpenAI-hosted embeddings (violates offline requirement).
