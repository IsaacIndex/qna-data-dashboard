import json

from app.services.analytics import AnalyticsClient
from app.utils.logging import BufferedJsonlWriter


def test_analytics_client_records_latency_events(tmp_path) -> None:
    destination = tmp_path / "analytics.jsonl"
    client = AnalyticsClient(writer=BufferedJsonlWriter(destination, buffer_size=1))

    event = client.tab_switch_latency(
        42.3,
        tab="search",
        dataset_id="ds-1",
        success=False,
        detail="debounce",
    )

    assert event.event == "tab.switch.latency"
    assert event.duration_ms == 42.3
    assert event.tab == "search"
    assert event.detail == "debounce"

    payload = json.loads(destination.read_text().splitlines()[0])
    assert payload["event"] == "tab.switch.latency"
    assert payload["tab"] == "search"
    assert payload["dataset_id"] == "ds-1"
    assert payload["duration_ms"] == 42.3
    assert payload["success"] is False
