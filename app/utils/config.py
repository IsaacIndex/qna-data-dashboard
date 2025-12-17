from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_ROOT = Path("./data")
DEFAULT_EMBEDDINGS_SUBDIR = "embeddings"
DEFAULT_INGEST_SUBDIR = "ingest_sources"
CHROMA_PERSIST_ENV = "CHROMA_PERSIST_DIR"
CHROMA_DB_ENV = "CHROMA_DB_DIR"
MODEL_ID_ENV = "EMBEDDING_MODEL_ID"
LEGACY_MODEL_ENV = "SENTENCE_TRANSFORMER_MODEL"
MODEL_VERSION_ENV = "EMBEDDING_MODEL_VERSION"
INGEST_STORAGE_ROOT_ENV = "INGEST_STORAGE_ROOT"
INGEST_MAX_BYTES_ENV = "INGEST_MAX_BYTES"
INGEST_ALLOWED_TYPES_ENV = "INGEST_ALLOWED_TYPES"
INGEST_CONCURRENCY_ENV = "INGEST_REEMBED_CONCURRENCY"


@dataclass(frozen=True)
class EmbeddingConfig:
    persist_directory: Path
    model_name: str
    model_version: str


@dataclass(frozen=True)
class IngestConfig:
    storage_root: Path
    max_bytes: int
    allowed_types: tuple[str, ...]
    reembed_concurrency: int


def get_data_root() -> Path:
    return Path(os.getenv("DATA_ROOT", DEFAULT_DATA_ROOT)).expanduser()


def get_chroma_persist_dir(data_root: Path | None = None) -> Path:
    base = os.getenv(CHROMA_PERSIST_ENV) or os.getenv(CHROMA_DB_ENV)
    if base:
        return Path(base).expanduser()
    root = data_root if data_root is not None else get_data_root()
    return (root / DEFAULT_EMBEDDINGS_SUBDIR).expanduser()


def get_embedding_model_id() -> str:
    return os.getenv(MODEL_ID_ENV) or os.getenv(LEGACY_MODEL_ENV) or "nomic-embed-text"


def get_embedding_model_version(model_name: str | None = None) -> str:
    version = os.getenv(MODEL_VERSION_ENV)
    if version:
        return version
    if model_name:
        return f"{model_name}-v1"
    return "v1"


def load_embedding_config(data_root: Path | None = None) -> EmbeddingConfig:
    model_name = get_embedding_model_id()
    return EmbeddingConfig(
        persist_directory=get_chroma_persist_dir(data_root),
        model_name=model_name,
        model_version=get_embedding_model_version(model_name),
    )


def get_ingest_storage_root(data_root: Path | None = None) -> Path:
    explicit = os.getenv(INGEST_STORAGE_ROOT_ENV)
    if explicit:
        return Path(explicit).expanduser()
    root = data_root if data_root is not None else get_data_root()
    return (root / DEFAULT_INGEST_SUBDIR).expanduser()


def load_ingest_config(data_root: Path | None = None) -> IngestConfig:
    max_bytes_default = 50 * 1024 * 1024
    max_bytes = int(os.getenv(INGEST_MAX_BYTES_ENV, max_bytes_default))
    allowed_env = os.getenv(INGEST_ALLOWED_TYPES_ENV)
    if allowed_env:
        allowed_types = tuple(
            part.strip().lower() for part in allowed_env.split(",") if part.strip()
        )
    else:
        allowed_types = ("csv", "xlsx", "xls", "parquet")
    reembed_concurrency = int(os.getenv(INGEST_CONCURRENCY_ENV, 3))
    return IngestConfig(
        storage_root=get_ingest_storage_root(data_root),
        max_bytes=max_bytes,
        allowed_types=allowed_types,
        reembed_concurrency=reembed_concurrency,
    )
