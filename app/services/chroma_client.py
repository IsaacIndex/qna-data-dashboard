from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from app.utils.config import (
    CHROMA_DB_ENV,
    CHROMA_PERSIST_ENV,
    DEFAULT_DATA_ROOT,
    DEFAULT_EMBEDDINGS_SUBDIR,
)
from app.utils.logging import get_logger

try:  # pragma: no cover - optional dependency for production persistence
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None

LOGGER = get_logger(__name__)

DEFAULT_CHROMA_DIR = str(DEFAULT_DATA_ROOT / DEFAULT_EMBEDDINGS_SUBDIR)
CHROMA_MODE = os.getenv("QNA_USE_CHROMADB", "1").lower()
PREFER_REAL_CHROMA = CHROMA_MODE in {"1", "true", "yes", "on", "persist"}
_RUNTIME_STATE: dict[str, object] = {
    "persist_directory": Path(DEFAULT_CHROMA_DIR),
    "is_persistent": False,
    "last_error": None,
}


@dataclass(frozen=True)
class ChromaRuntimeState:
    persist_directory: Path
    prefers_persistent: bool
    is_persistent: bool
    last_error: str | None


class InMemoryCollection:
    def __init__(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        self.name = name
        self.metadata = metadata or {}
        self._documents: dict[str, str] = {}
        self._embeddings: dict[str, list[float]] = {}

    def add(self, ids: list[str], documents: list[str], embeddings: list[list[float]]) -> None:
        self.upsert(ids=ids, documents=documents, embeddings=embeddings)

    def upsert(self, ids: list[str], documents: list[str], embeddings: list[list[float]]) -> None:
        for idx, doc, vector in zip(ids, documents, embeddings, strict=False):
            self._documents[idx] = doc
            self._embeddings[idx] = list(vector)

    def count(self) -> int:
        return len(self._documents)

    def reset(self) -> None:
        self._documents.clear()
        self._embeddings.clear()


class InMemoryChromaClient:
    def __init__(self) -> None:
        self._collections: dict[str, InMemoryCollection] = {}

    def get_or_create_collection(
        self, name: str, metadata: dict[str, Any] | None = None
    ) -> InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryCollection(name, metadata)
        return self._collections[name]

    def reset(self) -> None:
        for collection in self._collections.values():
            collection.reset()
        self._collections.clear()


def _resolve_persist_directory(persist_directory: str | None = None) -> Path:
    base_env = os.getenv(CHROMA_PERSIST_ENV) or os.getenv(CHROMA_DB_ENV)
    base_value = persist_directory or base_env or DEFAULT_CHROMA_DIR
    base = Path(base_value)
    base.mkdir(parents=True, exist_ok=True)
    _RUNTIME_STATE["persist_directory"] = base
    return base


def _build_real_chroma_client(persist_directory: Path) -> object:  # pragma: no cover - slow path
    if chromadb is None:
        raise RuntimeError("chromadb package is not installed")
    # PersistentClient handles local on-disk storage; fallback to in-memory on failure.
    return chromadb.PersistentClient(path=str(persist_directory))


@lru_cache(maxsize=1)
def get_chroma_client(persist_directory: str | None = None) -> object:  # type: ignore[override]
    base = _resolve_persist_directory(persist_directory)
    if PREFER_REAL_CHROMA:
        try:
            client = _build_real_chroma_client(base)
            _RUNTIME_STATE["is_persistent"] = True
            _RUNTIME_STATE["last_error"] = None
            return client
        except Exception as error:  # pragma: no cover - log and fall back
            LOGGER.warning(
                "Failed to initialize persistent ChromaDB client: %s. Falling back to in-memory.",
                error,
            )
            _RUNTIME_STATE["is_persistent"] = False
            _RUNTIME_STATE["last_error"] = str(error)
    else:
        _RUNTIME_STATE["is_persistent"] = False
        _RUNTIME_STATE["last_error"] = None
    return InMemoryChromaClient()


def get_or_create_collection(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
    persist_directory: str | None = None,
) -> object:
    client = get_chroma_client(persist_directory=persist_directory)
    return client.get_or_create_collection(name=name, metadata=metadata or {})


def get_chroma_runtime_state() -> ChromaRuntimeState:
    return ChromaRuntimeState(
        persist_directory=cast(Path, _RUNTIME_STATE["persist_directory"]),
        prefers_persistent=PREFER_REAL_CHROMA,
        is_persistent=bool(_RUNTIME_STATE["is_persistent"]),
        last_error=cast(str | None, _RUNTIME_STATE["last_error"]),
    )
