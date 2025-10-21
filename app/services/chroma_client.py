from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CHROMA_DIR = "data/chromadb"
USE_REAL_CHROMA = os.getenv("QNA_USE_CHROMADB", "0") == "1"


class InMemoryCollection:
    def __init__(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        self.name = name
        self.metadata = metadata or {}
        self._documents: Dict[str, str] = {}
        self._embeddings: Dict[str, List[float]] = {}

    def add(self, ids: List[str], documents: List[str], embeddings: List[List[float]]) -> None:
        self.upsert(ids=ids, documents=documents, embeddings=embeddings)

    def upsert(self, ids: List[str], documents: List[str], embeddings: List[List[float]]) -> None:
        for idx, doc, vector in zip(ids, documents, embeddings):
            self._documents[idx] = doc
            self._embeddings[idx] = list(vector)

    def count(self) -> int:
        return len(self._documents)

    def reset(self) -> None:
        self._documents.clear()
        self._embeddings.clear()


class InMemoryChromaClient:
    def __init__(self) -> None:
        self._collections: Dict[str, InMemoryCollection] = {}

    def get_or_create_collection(self, name: str, metadata: dict[str, Any] | None = None) -> InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryCollection(name, metadata)
        return self._collections[name]

    def reset(self) -> None:
        for collection in self._collections.values():
            collection.reset()
        self._collections.clear()


def _resolve_persist_directory(persist_directory: str | None = None) -> Path:
    base = Path(persist_directory or os.getenv("CHROMA_DB_DIR", DEFAULT_CHROMA_DIR))
    base.mkdir(parents=True, exist_ok=True)
    return base


@lru_cache(maxsize=1)
def get_chroma_client(persist_directory: str | None = None):  # type: ignore[override]
    if USE_REAL_CHROMA:
        raise RuntimeError(
            "Real ChromaDB client not available in this environment. Set QNA_USE_CHROMADB=0 to use in-memory store."
        )
    _resolve_persist_directory(persist_directory)
    return InMemoryChromaClient()


def get_or_create_collection(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
    persist_directory: str | None = None,
):
    client = get_chroma_client(persist_directory=persist_directory)
    return client.get_or_create_collection(name=name, metadata=metadata or {})
