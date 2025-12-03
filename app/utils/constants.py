"""Centralised constants for sheet-source performance guardrails and shared UI scales."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

INGESTION_MAX_DURATION_MS = 120_000
"""Maximum allowed ingestion duration per bundle (2 minutes)."""

QUERY_PREVIEW_P95_MAX_MS = 5_000
"""Target 95th percentile latency threshold for cross-sheet query previews (5 seconds)."""


@dataclass(frozen=True)
class SimilarityBand:
    label: str
    min_score: int
    max_score: int
    color: str
    bucket: Literal["very_low", "low", "medium", "high", "very_high"]


SIMILARITY_SCALE_LABEL = "0-100%"
SIMILARITY_PALETTE: tuple[str, ...] = (
    "#2D3540",  # 0%
    "#3A617D",  # 25%
    "#228BBA",  # 50%
    "#14A57A",  # 75%
    "#0BC262",  # 100%
)

SIMILARITY_BANDS: tuple[SimilarityBand, ...] = (
    SimilarityBand("Very Low", 0, 20, SIMILARITY_PALETTE[0], "very_low"),
    SimilarityBand("Low", 21, 40, SIMILARITY_PALETTE[1], "low"),
    SimilarityBand("Medium", 41, 65, SIMILARITY_PALETTE[2], "medium"),
    SimilarityBand("High", 66, 85, SIMILARITY_PALETTE[3], "high"),
    SimilarityBand("Very High", 86, 100, SIMILARITY_PALETTE[4], "very_high"),
)
