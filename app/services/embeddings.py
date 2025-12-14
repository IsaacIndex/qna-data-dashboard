from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.db.metadata import MetadataRepository
from app.db.schema import DataFile, QueryRecord, SheetSource
from app.services.chroma_client import get_chroma_client
from app.utils.config import EmbeddingConfig, load_embedding_config
from app.utils.logging import get_logger

try:  # pragma: no cover - optional heavy dependency for production use
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

LOGGER = get_logger(__name__)
EMBEDDINGS_OFFLINE = os.getenv("QNA_EMBEDDINGS_OFFLINE", "1") == "1"


@dataclass
class EmbeddingSummary:
    vector_count: int
    model_name: str
    model_dimension: int


@dataclass
class EmbeddingJob:
    data_file: DataFile | None
    records: Sequence[QueryRecord]
    metadata_repository: MetadataRepository
    sheet: SheetSource | None = None


class EmbeddingService:
    """Generate embeddings and persist them to ChromaDB with SQLite metadata."""

    def __init__(
        self,
        *,
        metadata_repository: MetadataRepository,
        chroma_client: object | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        persist_directory: str | Path | None = None,
        batch_size: int = 32,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.config = self._build_config(
            model_name=model_name,
            model_version=model_version,
            persist_directory=persist_directory,
        )
        self.chroma_client = chroma_client or get_chroma_client(
            persist_directory=str(self.config.persist_directory)
        )
        self.batch_size = batch_size
        self.requested_model_name = self.config.model_name
        self.model_tag = f"{self.config.model_name}:{self.config.model_version}"
        self._model: SentenceTransformer | None = None

    def _build_config(
        self,
        *,
        model_name: str | None,
        model_version: str | None,
        persist_directory: str | Path | None,
    ) -> EmbeddingConfig:
        defaults = load_embedding_config()
        resolved_model = model_name or defaults.model_name
        resolved_version = model_version or defaults.model_version
        resolved_dir = (
            Path(persist_directory).expanduser()
            if persist_directory
            else defaults.persist_directory
        )
        return EmbeddingConfig(
            persist_directory=resolved_dir,
            model_name=resolved_model,
            model_version=resolved_version,
        )

    def _load_model(self) -> SentenceTransformer | None:  # pragma: no cover - heavy path
        if EMBEDDINGS_OFFLINE:
            return None
        if SentenceTransformer is None:
            return None
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.config.model_name)
            except Exception as error:  # pragma: no cover - fallback path for offline envs
                LOGGER.warning(
                    "Failed to load SentenceTransformer model '%s': %s. "
                    "Falling back to hash-based embeddings.",
                    self.config.model_name,
                    error,
                )
                self._model = None
        return self._model

    def _hash_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for index in range(0, 32, 4):
            chunk = digest[index : index + 4]
            values.append(float(int.from_bytes(chunk, "big") % 1000) / 1000.0)
        return values

    def embed_texts(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        return self._generate_embeddings(texts)

    def _generate_embeddings(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        model = self._load_model()
        if model is None:  # fallback when transformers unavailable
            fallback_vectors = [self._hash_embedding(text) for text in texts]
            return (
                fallback_vectors,
                len(fallback_vectors[0]) if fallback_vectors else 0,
                "hash-fallback",
            )
        vectors = model.encode(
            list(texts), batch_size=self.batch_size, convert_to_numpy=True, show_progress_bar=False
        )
        dimension = 0
        if len(vectors):
            dimension = vectors.shape[1]  # type: ignore[attr-defined]
        return vectors.tolist(), dimension, self.config.model_name

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        texts = [record.text for record in job.records]
        if not texts:
            return EmbeddingSummary(
                vector_count=0, model_name=self.requested_model_name, model_dimension=0
            )

        vectors, dimension, model_name = self._generate_embeddings(texts)
        target_prefix, collection_display = self._resolve_target(job)
        collection_name = self._build_collection_name(target_prefix)
        collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={
                "display_name": collection_display,
                "model_name": self.config.model_name,
                "model_version": self.config.model_version,
            },
        )

        ids = [f"{collection_name}-{index}" for index in range(len(texts))]
        collection.upsert(ids=ids, embeddings=vectors, documents=texts)

        for record, vector_id in zip(job.records, ids, strict=False):
            job.metadata_repository.upsert_embedding(
                record_id=record.id,
                model_name=model_name,
                model_version=self.config.model_version,
                vector_path=vector_id,
                embedding_dim=dimension,
            )

        job.metadata_repository.session.flush()  # type: ignore[attr-defined]
        return EmbeddingSummary(
            vector_count=len(texts), model_name=model_name, model_dimension=dimension
        )

    def _resolve_target(self, job: EmbeddingJob) -> tuple[str, str]:
        if job.sheet is not None:
            return f"sheet_{job.sheet.id}", job.sheet.display_label
        if job.data_file is not None:
            return f"dataset_{job.data_file.id}", job.data_file.display_name
        raise ValueError("EmbeddingJob requires either a sheet or data_file target.")

    def _build_collection_name(self, target_prefix: str) -> str:
        raw = f"{target_prefix}-{self.model_tag}"
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
        trimmed = cleaned[:63].rstrip("-")
        return trimmed or target_prefix
