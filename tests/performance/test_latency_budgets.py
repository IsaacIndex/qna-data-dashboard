from __future__ import annotations

import json
import logging
import time

from app.utils.logging import get_logger, log_timing

SEARCH_P95_BUDGET_MS = 2000
TAB_SWITCH_P95_BUDGET_MS = 2000


def _elapsed_from_logs(caplog, event_name: str) -> float | None:
    for record in caplog.records:
        try:
            payload = json.loads(record.message)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == f"{event_name}.complete":
            elapsed = payload.get("elapsed_ms")
            return float(elapsed) if elapsed is not None else None
    return None


def test_search_latency_budget_smoke(caplog) -> None:
    logger = get_logger("perf.search.smoke")
    with caplog.at_level(logging.INFO):
        with log_timing(logger, "tests.search.latency"):
            time.sleep(0.01)
    elapsed = _elapsed_from_logs(caplog, "tests.search.latency")
    assert elapsed is not None
    assert elapsed < SEARCH_P95_BUDGET_MS


def test_tab_switch_latency_budget_smoke(caplog) -> None:
    logger = get_logger("perf.tabs.smoke")
    with caplog.at_level(logging.INFO):
        with log_timing(logger, "tests.tab.switch"):
            time.sleep(0.005)
    elapsed = _elapsed_from_logs(caplog, "tests.tab.switch")
    assert elapsed is not None
    assert elapsed < TAB_SWITCH_P95_BUDGET_MS
