from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.utils.logging import get_logger

LOGGER = get_logger(__name__)


def emit_ingest_metric(event: str, **fields: Any) -> dict[str, Any]:
    """Lightweight metrics stub that returns the payload and logs it for observability."""
    payload = {"event": _normalize_event(event), "timestamp": datetime.now(UTC).isoformat(), **fields}
    _log_payload(payload)
    return payload


def timing_payload(event: str, *, elapsed_ms: float, **fields: Any) -> dict[str, Any]:
    payload = {
        "event": f"{_normalize_event(event)}.timing",
        "elapsed_ms": elapsed_ms,
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }
    return payload


def emit_ingest_timing(event: str, *, elapsed_ms: float, **fields: Any) -> dict[str, Any]:
    payload = timing_payload(event, elapsed_ms=elapsed_ms, **fields)
    _log_payload(payload)
    return payload


@contextmanager
def measure_ingest(event: str, **fields: Any) -> None:
    """Context manager to emit timing metrics around ingest operations."""
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        emit_ingest_timing(event, elapsed_ms=elapsed_ms, **fields)


def _normalize_event(event: str) -> str:
    return event if event.startswith("ingest.") else f"ingest.{event}"


def _log_payload(payload: dict[str, Any]) -> None:
    try:
        LOGGER.info(json.dumps(payload))
    except Exception:
        LOGGER.info("%s %s", payload.get("event", "ingest.metric"), payload)
