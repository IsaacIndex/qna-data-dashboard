# Quickstart: Embeddings-based Search Upgrade

1) Install deps: `poetry install` (Python 3.11). Ensure `chromadb` and `sentence-transformers` are present (already in deps).
2) Set data roots (optional): `export DATA_ROOT=./data` and `export CHROMA_PERSIST_DIR=./data/embeddings`.
3) Model: Ensure HuggingFace access (if needed) and allow download of `nomic-embed-text` (cached locally by sentence-transformers).
4) Launch API/Streamlit:
   - API: `poetry run uvicorn app.api.router:create_app --factory --reload`
   - UI: `poetry run streamlit run app/main.py`
5) Run tests: `poetry run pytest` (includes coverage via `--cov=app --cov-report=term-missing`).
6) Lint/typecheck/format: `poetry run ruff check`, `poetry run mypy`, `poetry run black --check .`.
7) Smoke search: call `GET /search?q=change+address&limitPerMode=10` and confirm both semantic and lexical sections return results with scores.
