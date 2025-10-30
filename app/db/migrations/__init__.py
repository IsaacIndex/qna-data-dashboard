from __future__ import annotations

import importlib

from sqlalchemy.engine import Engine


def run_migrations(engine: Engine) -> None:
    """Apply idempotent metadata migrations in sequence."""
    sheet_sources = importlib.import_module(".002_sheet_sources", package=__name__)
    sheet_sources.run(engine)
    column_preferences = importlib.import_module(".003_column_preferences", package=__name__)
    column_preferences.run(engine)
