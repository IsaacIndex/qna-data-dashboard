from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.utils.config import get_data_root
from app.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _audit_log_path() -> Path:
    root = get_data_root()
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "audit.log"


def record_audit(action: str, outcome: str, *, user: str | None, details: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "action": action,
        "outcome": outcome,
        "user": user,
        **details,
    }
    try:
        _audit_log_path().open("a", encoding="utf-8").write(json.dumps(entry) + "\n")
    except Exception:  # pragma: no cover - best-effort persistence
        LOGGER.warning("Failed to write audit log for %s", action)
    LOGGER.info("audit.%s %s %s", action, outcome, details)
    return entry
