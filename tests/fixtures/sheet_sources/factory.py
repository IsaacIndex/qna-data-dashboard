from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - dependency is optional in production but required for tests
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class SheetDefinition:
    """Declarative sheet structure used to build workbook fixtures."""

    name: str
    headers: Sequence[str]
    rows: Sequence[Sequence[object]]
    hidden: bool = False


DEFAULT_HEADERS: tuple[str, ...] = ("region", "category", "revenue")
DEFAULT_SHEETS: tuple[SheetDefinition, ...] = (
    SheetDefinition(
        name="North",
        headers=DEFAULT_HEADERS,
        rows=(
            ("north", "hardware", 125_000),
            ("north", "software", 98_500),
        ),
    ),
    SheetDefinition(
        name="South",
        headers=DEFAULT_HEADERS,
        rows=(
            ("south", "hardware", 89_200),
            ("south", "software", 102_750),
        ),
    ),
    SheetDefinition(
        name="HiddenStrategic",
        headers=DEFAULT_HEADERS,
        rows=(
            ("south", "services", 45_000),
            ("north", "services", 58_250),
        ),
        hidden=True,
    ),
)

DEFAULT_CSV_HEADERS: tuple[str, ...] = ("region", "budget", "owner")
DEFAULT_CSV_ROWS: tuple[tuple[object, ...], ...] = (
    ("north", 150_000, "Finance"),
    ("south", 110_000, "Finance"),
    ("west", 90_500, "Finance"),
)


class FixtureBuildError(RuntimeError):
    """Raised when fixture generation cannot proceed (e.g., missing dependency)."""


def _ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_workbook(
    destination: Path,
    sheets: Sequence[SheetDefinition] | None = None,
) -> Path:
    """
    Create an Excel workbook with the provided sheet definitions.

    Args:
        destination: Target file path for the workbook.
        sheets: Optional sequence of sheet definitions. Defaults to DEFAULT_SHEETS.

    Returns:
        The destination path for convenience.
    """

    if Workbook is None:  # pragma: no cover - guard for missing dependency
        raise FixtureBuildError(
            "openpyxl is required to build workbook fixtures. Install via `poetry install`."
        )

    _ensure_directory(destination)
    workbook = Workbook()
    active = workbook.active
    workbook.remove(active)

    for sheet in sheets or DEFAULT_SHEETS:
        worksheet = workbook.create_sheet(title=sheet.name)
        worksheet.append(list(sheet.headers))
        for row in sheet.rows:
            worksheet.append(list(row))
        if sheet.hidden:
            worksheet.sheet_state = "hidden"

    workbook.save(destination)
    return destination


def build_csv(
    destination: Path,
    headers: Sequence[str] | None = None,
    rows: Iterable[Sequence[object]] | None = None,
) -> Path:
    """
    Create a CSV fixture populated with the provided headers and rows.

    Args:
        destination: Target file path for the CSV.
        headers: Optional sequence of column headers (defaults to DEFAULT_CSV_HEADERS).
        rows: Iterable of row sequences (defaults to DEFAULT_CSV_ROWS).

    Returns:
        The destination path.
    """

    _ensure_directory(destination)
    resolved_headers = list(headers or DEFAULT_CSV_HEADERS)
    resolved_rows = list(rows or DEFAULT_CSV_ROWS)

    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(resolved_headers)
        for row in resolved_rows:
            writer.writerow(list(row))

    return destination
