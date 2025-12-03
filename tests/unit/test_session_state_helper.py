from datetime import datetime, timezone

from app.utils.session_state import (
    confirm_reset,
    ensure_session_defaults,
    request_reset,
    update_session_state,
)


def test_defaults_preserve_existing_values() -> None:
    store: dict[str, object] = {"active_tab": "search"}
    ensure_session_defaults(store)

    assert store["active_tab"] == "search"
    assert "selected_sheets" in store and store["selected_sheets"] == []
    assert "filters" in store


def test_reset_requires_request_and_resets_when_confirmed() -> None:
    store: dict[str, object] = {}
    ensure_session_defaults(store)

    assert not confirm_reset(store)

    request_reset(store, reason="clear selections")
    assert store["reset_requested"] is True
    assert store["reset_reason"] == "clear selections"

    updated = confirm_reset(store)
    assert updated is True
    assert store["reset_requested"] is False
    assert store["selected_columns"] == []
    assert store["filters"] == {}
    assert isinstance(store["last_reset_at"], datetime)
    assert store["last_reset_at"].tzinfo == timezone.utc


def test_update_session_state_sets_values() -> None:
    store: dict[str, object] = {}
    update_session_state(store, active_tab="ingest", selected_columns=["a"])

    assert store["active_tab"] == "ingest"
    assert store["selected_columns"] == ["a"]
