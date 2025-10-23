from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ExistingSheetSnapshot:
    id: str
    sheet_name: str
    checksum: str | None
    column_schema: Sequence[dict[str, object]]
    row_count: int


@dataclass(frozen=True, slots=True)
class DiscoveredSheetSnapshot:
    sheet_name: str
    checksum: str
    column_schema: Sequence[dict[str, object]]
    row_count: int


def match_sheets(
    existing: Sequence[ExistingSheetSnapshot],
    discovered: Sequence[DiscoveredSheetSnapshot],
    *,
    tolerance: str = "allow_same_schema",
) -> tuple[list[tuple[DiscoveredSheetSnapshot, ExistingSheetSnapshot | None]], list[ExistingSheetSnapshot]]:
    existing_by_name = {sheet.sheet_name: sheet for sheet in existing}
    unmatched_existing: dict[str, ExistingSheetSnapshot] = {sheet.id: sheet for sheet in existing}

    matches: list[tuple[DiscoveredSheetSnapshot, ExistingSheetSnapshot | None]] = []
    remaining: list[DiscoveredSheetSnapshot] = []

    for snapshot in discovered:
        existing_match = existing_by_name.pop(snapshot.sheet_name, None)
        if existing_match is not None:
            unmatched_existing.pop(existing_match.id, None)
            matches.append((snapshot, existing_match))
        else:
            remaining.append(snapshot)

    # Rebuild checksum index from unmatched entries only
    checksum_index: dict[str, list[ExistingSheetSnapshot]] = {}
    for sheet in unmatched_existing.values():
        if sheet.checksum:
            checksum_index.setdefault(sheet.checksum, []).append(sheet)

    next_remaining: list[DiscoveredSheetSnapshot] = []
    for snapshot in remaining:
        candidates = checksum_index.get(snapshot.checksum) or []
        if candidates:
            existing_match = candidates.pop(0)
            if not candidates:
                checksum_index.pop(snapshot.checksum, None)
            unmatched_existing.pop(existing_match.id, None)
            matches.append((snapshot, existing_match))
        else:
            next_remaining.append(snapshot)
    remaining = next_remaining

    if tolerance == "allow_same_schema" and remaining:
        unmatched_after_schema: list[DiscoveredSheetSnapshot] = []
        for snapshot in remaining:
            schema_key = _schema_signature(snapshot.column_schema)
            existing_match = None
            for candidate in unmatched_existing.values():
                if (
                    _schema_signature(candidate.column_schema) == schema_key
                    and candidate.row_count == snapshot.row_count
                    and _names_compatible(candidate.sheet_name, snapshot.sheet_name)
                ):
                    existing_match = candidate
                    break
            if existing_match is not None:
                unmatched_existing.pop(existing_match.id, None)
                matches.append((snapshot, existing_match))
            else:
                unmatched_after_schema.append(snapshot)
        remaining = unmatched_after_schema

    for snapshot in remaining:
        matches.append((snapshot, None))

    return matches, list(unmatched_existing.values())


def _schema_signature(schema: Sequence[dict[str, object]]) -> tuple[tuple[str, str], ...]:
    signature: list[tuple[str, str]] = []
    for entry in schema:
        name = str(entry.get("name") or "").strip().lower()
        inferred = str(entry.get("inferredType") or "").strip().lower()
        signature.append((name, inferred))
    return tuple(signature)


def _names_compatible(existing_name: str, discovered_name: str) -> bool:
    existing_lower = existing_name.lower()
    discovered_lower = discovered_name.lower()
    return existing_lower in discovered_lower or discovered_lower in existing_lower
