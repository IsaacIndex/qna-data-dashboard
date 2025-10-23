"""Centralised constants for sheet-source performance guardrails."""

INGESTION_MAX_DURATION_MS = 120_000
"""Maximum allowed ingestion duration per bundle (2 minutes)."""

QUERY_PREVIEW_P95_MAX_MS = 5_000
"""Target 95th percentile latency threshold for cross-sheet query previews (5 seconds)."""
