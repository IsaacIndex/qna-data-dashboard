from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

SessionStore = MutableMapping[str, Any]

SESSION_DEFAULTS: dict[str, Any] = {
    "active_tab": None,
    "selected_sheets": [],
    "selected_columns": [],
    "search_dataset_selection": [],
    "search_column_selection": [],
    "filters": {},
    "preference_status": "idle",
    "last_saved_at": None,
    "reset_requested": False,
    "reset_reason": None,
    "last_reset_at": None,
}


def _get_store(store: SessionStore | None) -> SessionStore:
    if store is not None:
        return store
    try:
        import streamlit as st  # type: ignore
    except (
        ModuleNotFoundError
    ) as error:  # pragma: no cover - Streamlit only available in app runtime
        raise RuntimeError("Streamlit session state is unavailable outside the app.") from error
    return st.session_state


def ensure_session_defaults(
    store: SessionStore | None = None,
    *,
    defaults: dict[str, Any] | None = None,
) -> SessionStore:
    """Populate default keys without overwriting existing selections."""
    state = _get_store(store)
    baseline = defaults or SESSION_DEFAULTS
    for key, value in baseline.items():
        if key not in state:
            state[key] = deepcopy(value)
    return state


def update_session_state(store: SessionStore | None = None, **updates: object) -> SessionStore:
    """Update session state with provided values after defaults are ensured."""
    state = ensure_session_defaults(store)
    for key, value in updates.items():
        state[key] = value
    return state


def request_reset(store: SessionStore | None = None, *, reason: str | None = None) -> bool:
    """Mark the session as pending reset with an optional reason."""
    state = ensure_session_defaults(store)
    state["reset_requested"] = True
    state["reset_reason"] = reason
    return True


def confirm_reset(
    store: SessionStore | None = None,
    *,
    keys: Sequence[str] | None = None,
) -> bool:
    """Apply a reset to selected keys only after a request flag is set."""
    state = ensure_session_defaults(store)
    if not state.get("reset_requested"):
        return False

    targets = keys or ("selected_sheets", "selected_columns", "filters", "active_tab")
    for key in targets:
        if key in SESSION_DEFAULTS:
            state[key] = deepcopy(SESSION_DEFAULTS[key])
        else:
            state.pop(key, None)

    state["reset_requested"] = False
    state["last_reset_at"] = datetime.now(UTC)
    state["reset_reason"] = None
    return True
