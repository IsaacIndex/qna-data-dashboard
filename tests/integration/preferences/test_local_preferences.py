from __future__ import annotations

from datetime import datetime, timezone

from app.services.preferences import hydrate_local_preferences
from app.utils.session_state import confirm_reset, request_reset


def test_local_preferences_hydrate_and_reset_cycle() -> None:
    defaults = ["question", "response"]

    store: dict[str, object] = {}
    snapshot = hydrate_local_preferences(store, dataset_id="ds-1", payload=None, defaults=defaults)
    assert store["selected_columns"] == defaults
    assert store["preference_status"] == "ready"
    assert snapshot.source == "defaults"
    assert snapshot.max_columns == len(defaults)

    payload = {
        "datasetId": "ds-1",
        "deviceId": "device-123",
        "version": 2,
        "selectedColumns": [
            {"name": "notes", "displayLabel": "Notes", "position": 1},
            {"name": "response", "displayLabel": "Answer", "position": 0},
        ],
        "maxColumns": 5,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    updated = hydrate_local_preferences(store, dataset_id="ds-1", payload=payload, defaults=defaults)
    assert store["selected_columns"] == ["response", "notes"]
    assert store["preference_source"] == "localStorage"
    assert store["preference_version"] == 2
    assert updated.user_id == "device-123"
    assert updated.version == 2
    assert updated.max_columns == 5

    new_session: dict[str, object] = {}
    hydrate_local_preferences(new_session, dataset_id="ds-1", payload=payload, defaults=defaults)
    request_reset(new_session, reason="clear preferences")
    assert new_session["reset_requested"] is True
    assert confirm_reset(new_session, keys=("selected_columns", "filters", "preference_status"))
    assert new_session["selected_columns"] == []
    rehydrated = hydrate_local_preferences(new_session, dataset_id="ds-1", payload=None, defaults=["question"])
    assert new_session["selected_columns"] == ["question"]
    assert rehydrated.source == "defaults"
    assert rehydrated.selected_columns[0].display_label == "question"
