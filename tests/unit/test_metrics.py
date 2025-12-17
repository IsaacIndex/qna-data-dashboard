from __future__ import annotations

from app.utils import metrics
from app.utils.metrics import emit_ingest_metric, emit_ingest_timing, measure_ingest, timing_payload


def test_emit_ingest_metric_returns_payload() -> None:
    payload = emit_ingest_metric("legacy_reinsert", status="success", dataset="analytics")
    assert payload["event"] == "ingest.legacy_reinsert"
    assert payload["status"] == "success"
    assert payload["dataset"] == "analytics"
    assert "timestamp" in payload


def test_timing_payload_includes_elapsed() -> None:
    payload = timing_payload("ingest.list", elapsed_ms=12.5, status="ok")
    assert payload["event"] == "ingest.list.timing"
    assert payload["elapsed_ms"] == 12.5


def test_emit_ingest_timing_prefixes_event() -> None:
    payload = emit_ingest_timing("sources.list", elapsed_ms=5.0, status="ok")
    assert payload["event"] == "ingest.sources.list.timing"
    assert payload["elapsed_ms"] == 5.0


def test_measure_ingest_wraps_block(monkeypatch) -> None:
    calls: list[dict] = []

    def _mock_emit(event: str, *, elapsed_ms: float, **fields) -> dict:
        payload = {"event": event, "elapsed_ms": elapsed_ms, **fields}
        calls.append(payload)
        return payload

    monkeypatch.setattr(metrics, "emit_ingest_timing", _mock_emit)

    with measure_ingest("sources.bulk_update", requested=2):
        pass

    assert calls, "Expected timing emission from measure_ingest"
    assert calls[0]["event"] == "sources.bulk_update"
    assert calls[0]["requested"] == 2
    assert calls[0]["elapsed_ms"] >= 0
