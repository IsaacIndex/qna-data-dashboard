from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from app.models.source import LegacyReason, SourceType

SOURCE_NAMESPACE = UUID("6f3ed160-3ed9-4cb0-9ad8-30b89ab1a7bc")


def canonical_source_key(*, label: str, dataset: str, source_type: SourceType) -> str:
    """Normalized identity string for deterministic UUIDs."""
    return f"{dataset.strip().lower()}|{source_type.value}|{label.strip().lower()}"


def stable_source_uuid(*, label: str, dataset: str, source_type: SourceType) -> str:
    key = canonical_source_key(label=label, dataset=dataset, source_type=source_type)
    return str(uuid5(SOURCE_NAMESPACE, key))


def detect_legacy_reason(entry: dict, *, path_exists: bool) -> LegacyReason | None:
    if not entry.get("uuid") and not entry.get("id"):
        return LegacyReason.missing_uuid
    if not entry.get("extracted_columns"):
        return LegacyReason.missing_headers
    if entry.get("legacy"):
        return LegacyReason.prior_format
    if not path_exists:
        return LegacyReason.missing_uuid
    return None


def _load_uuid_map(map_path: Path) -> dict[str, str]:
    if not map_path.exists():
        return {}
    try:
        return json.loads(map_path.read_text())
    except json.JSONDecodeError:
        return {}


def _persist_uuid_map(map_path: Path, mapping: dict[str, str]) -> None:
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(mapping, indent=2))


def ensure_canonical_uuid(
    *,
    label: str,
    dataset: str,
    source_type: SourceType,
    original_id: str | None = None,
    map_path: Path | None = None,
) -> str:
    """
    Produce a stable UUID for a source, persisting a legacy mapping when a map_path is provided.
    """
    mapping: dict[str, str] = {}
    if map_path is not None:
        mapping = _load_uuid_map(map_path)
        key = f"legacy:{original_id}" if original_id else f"source:{canonical_source_key(label=label, dataset=dataset, source_type=source_type)}"
        if key in mapping:
            return mapping[key]
    if original_id:
        identity = f"{canonical_source_key(label=label, dataset=dataset, source_type=source_type)}|{original_id}"
    else:
        identity = canonical_source_key(label=label, dataset=dataset, source_type=source_type)
    uuid_value = str(uuid5(SOURCE_NAMESPACE, identity)) if map_path else stable_source_uuid(label=label, dataset=dataset, source_type=source_type)
    if map_path is not None:
        mapping[key] = uuid_value
        _persist_uuid_map(map_path, mapping)
    return uuid_value
