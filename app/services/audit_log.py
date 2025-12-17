from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from app.utils.config import get_data_root
from app.utils.logging import get_logger


class AuditLogService:
    """Structured audit logging for ingest actions."""

    def __init__(self, data_root: Path | None = None) -> None:
        base = Path(data_root) if data_root is not None else get_data_root()
        self.log_path = (base / "logs" / "ingest_audit.jsonl").expanduser()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)

    def record_legacy_reinsertion(self, *, source_uuid: str, outcome: str, conflict: bool) -> dict[str, Any]:
        return self._record(
            "legacy.reinsert",
            {
                "source_uuid": source_uuid,
                "outcome": outcome,
                "conflict": conflict,
            },
        )

    def record_bulk_action(self, *, uuids: Sequence[str], outcome: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"uuids": list(uuids), "outcome": outcome}
        if details:
            payload.update(details)
        return self._record("sources.bulk_update", payload)

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        """Read the most recent audit entries for verification or debugging."""
        if not self.log_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for raw in self.log_path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return entries

    def _record(self, action: str, details: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            **details,
        }
        line = json.dumps(entry, default=str)
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            self.logger.warning("Failed to persist audit log for %s", action)
        self.logger.info("audit.%s %s", action, details)
        return entry
