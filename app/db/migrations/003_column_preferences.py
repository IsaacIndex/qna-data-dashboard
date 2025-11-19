from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db.schema import ColumnPreference, ColumnPreferenceChange


def run(engine: Engine) -> None:
    """
    003_column_preferences: Ensure preference and audit tables exist.

    The migration is idempotent and only creates tables if they are missing.
    """

    inspector = inspect(engine)

    if not inspector.has_table(ColumnPreference.__tablename__):
        ColumnPreference.__table__.create(engine, checkfirst=True)

    if not inspector.has_table(ColumnPreferenceChange.__tablename__):
        ColumnPreferenceChange.__table__.create(engine, checkfirst=True)
