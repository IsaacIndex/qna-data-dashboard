from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from app.db.metadata import MetadataRepository
from app.db.schema import DataFile, QueryRecord
from app.services.chroma_client import get_chroma_client
from app.utils.logging import get_logger

try:  # pragma: no cover - optional heavy dependency for production use
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

LOGGER = get_logger(__name__)


@dataclass
class EmbeddingSummary:
    vector_count: int
    model_name: str
    model_dimension: int


@dataclass
class EmbeddingJob:
    data_file: DataFile
    records: Sequence[QueryRecord]
    metadata_repository: MetadataRepository


class EmbeddingService:
    """Generate embeddings and persist them to ChromaDB with SQLite metadata."""

    def __init__(
        self,
        *,
        metadata_repository: MetadataRepository,
        chroma_client: Any | None = None,
        model_name: str | None = None,
        batch_size: int = 32,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.chroma_client = chroma_client or get_chroma_client()
        self.requested_model_name = model_name or os.getenv(
            "SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"
        )
        self.batch_size = batch_size
        self._model: Optional[SentenceTransformer] = None

    def _load_model(self) -> Optional[SentenceTransformer]:  # pragma: no cover - heavy path
        if SentenceTransformer is None:
            return None
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.requested_model_name)
            except Exception as error:  # pragma: no cover - fallback path for offline envs
                LOGGER.warning(
                    "Failed to load SentenceTransformer model '%s': %s. "
                    "Falling back to hash-based embeddings.",
                    self.requested_model_name,
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

    def _generate_embeddings(self, texts: Sequence[str]) -> tuple[list[list[float]], int, str]:
        model = self._load_model()
        if model is None:  # fallback when transformers unavailable
            fallback_vectors = [self._hash_embedding(text) for text in texts]
            return fallback_vectors, len(fallback_vectors[0]) if fallback_vectors else 0, "hash-fallback"
        vectors = model.encode(
            list(texts), batch_size=self.batch_size, convert_to_numpy=True, show_progress_bar=False
        )
        dimension = 0
        if len(vectors):
            dimension = vectors.shape[1]  # type: ignore[attr-defined]
        return vectors.tolist(), dimension, self.requested_model_name

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        texts = [record.text for record in job.records]
        if not texts:
            return EmbeddingSummary(vector_count=0, model_name=self.requested_model_name, model_dimension=0)

        vectors, dimension, model_name = self._generate_embeddings(texts)
        collection = self.chroma_client.get_or_create_collection(
            name=f"dataset_{job.data_file.id}",
            metadata={"display_name": job.data_file.display_name},
        )

        ids = [f"{job.data_file.id}-{index}" for index in range(len(texts))]
        collection.upsert(ids=ids, embeddings=vectors, documents=texts)

        for record, vector_id in zip(job.records, ids):
            job.metadata_repository.upsert_embedding(
                record_id=record.id,
                model_name=model_name,
                model_version="1",
                vector_path=vector_id,
                embedding_dim=dimension,
            )

        job.metadata_repository.session.flush()  # type: ignore[attr-defined]
        return EmbeddingSummary(vector_count=len(texts), model_name=model_name, model_dimension=dimension)
