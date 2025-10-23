from __future__ import annotations

import importlib

from sqlalchemy.engine import Engine


def run_migrations(engine: Engine) -> None:
    """Apply idempotent metadata migrations in sequence."""
    sheet_sources = importlib.import_module(".002_sheet_sources", package=__name__)
    sheet_sources.run(engine)
