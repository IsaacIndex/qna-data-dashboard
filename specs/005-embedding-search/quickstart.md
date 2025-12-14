# Quickstart: Embeddings-based Search Upgrade

1) Install deps: `poetry install` (Python 3.11). Ensure `chromadb` and `sentence-transformers` are present (already in deps).
2) Set data roots (optional): `export DATA_ROOT=./data` (default) and `export CHROMA_PERSIST_DIR=./data/embeddings` (preferred). Set `QNA_USE_CHROMADB=1` to force persisted Chroma; `CHROMA_DB_DIR` remains supported for legacy setups.
3) Model: Ensure HuggingFace access (if needed) and allow download of `nomic-embed-text` via `EMBEDDING_MODEL_ID` (or legacy `SENTENCE_TRANSFORMER_MODEL`); optionally pin `EMBEDDING_MODEL_VERSION` to tag persisted vectors.
4) Launch API/Streamlit:
   - API: `poetry run uvicorn app.api.router:create_app --factory --reload`
   - UI: `poetry run streamlit run app/main.py`
5) Run tests: `poetry run pytest` (includes coverage via `--cov=app --cov-report=term-missing`). Performance smoke: `poetry run pytest tests/performance/test_search_latency.py --benchmark-only` (skips if pytest-benchmark is missing).
6) Lint/typecheck/format: `poetry run ruff check`, `poetry run mypy`, `poetry run black --check .`.
7) Smoke search: call `GET /search?q=change+address&limitPerMode=10` and confirm both semantic and lexical sections return results with scores and independent pagination via `offsetSemantic` / `offsetLexical`.
