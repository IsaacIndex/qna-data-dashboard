from __future__ import annotations

from pathlib import Path

from app.services.audit_log import AuditLogService


def test_audit_log_writes_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    service = AuditLogService()

    entry = service.record_legacy_reinsertion(source_uuid="123", outcome="succeeded", conflict=False)
    another = service.record_bulk_action(uuids=["1", "2"], outcome="partial", details={"status": "ready"})

    log_path = service.log_path
    contents = log_path.read_text().strip().splitlines()

    assert len(contents) == 2
    assert entry["action"] == "legacy.reinsert"
    assert another["action"] == "sources.bulk_update"

    tail = service.tail()
    assert len(tail) == 2
    assert tail[-1]["action"] == "sources.bulk_update"
