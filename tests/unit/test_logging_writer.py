import json

from app.utils.logging import BufferedJsonlWriter


def test_buffered_jsonl_writer_flushes(tmp_path) -> None:
    destination = tmp_path / "analytics.jsonl"
    writer = BufferedJsonlWriter(destination, buffer_size=2)

    writer.write({"event": "one"})
    assert writer.pending() == 1
    assert not destination.exists()

    writer.write({"event": "two"})
    assert destination.exists()

    contents = destination.read_text().splitlines()
    assert [json.loads(line)["event"] for line in contents] == ["one", "two"]

    writer.write({"event": "three"})
    writer.flush()
    lines = destination.read_text().splitlines()
    assert json.loads(lines[-1])["event"] == "three"
