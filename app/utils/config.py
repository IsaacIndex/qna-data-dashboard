from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_ROOT = Path("./data")
DEFAULT_EMBEDDINGS_SUBDIR = "embeddings"
CHROMA_PERSIST_ENV = "CHROMA_PERSIST_DIR"
CHROMA_DB_ENV = "CHROMA_DB_DIR"
MODEL_ID_ENV = "EMBEDDING_MODEL_ID"
LEGACY_MODEL_ENV = "SENTENCE_TRANSFORMER_MODEL"
MODEL_VERSION_ENV = "EMBEDDING_MODEL_VERSION"


@dataclass(frozen=True)
class EmbeddingConfig:
    persist_directory: Path
    model_name: str
    model_version: str


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
