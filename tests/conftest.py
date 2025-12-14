from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.metadata import (
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.services.chroma_client import get_chroma_client
from tests.fixtures.sheet_sources.factory import (
    DEFAULT_CSV_HEADERS,
    DEFAULT_CSV_ROWS,
    DEFAULT_SHEETS,
    SheetDefinition,
    build_csv,
    build_workbook,
)


@pytest.fixture
def temp_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    return data_root


@pytest.fixture
def sqlite_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_path = tmp_path / "metadata.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("SQLITE_URL", url)
    return url


@pytest.fixture
def session_factory(sqlite_url: str) -> sessionmaker[Session]:
    engine = build_engine(sqlite_url)
    init_database(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_scope(session_factory) as session:
        yield session


@pytest.fixture
def metadata_repository(db_session) -> MetadataRepository:
    return MetadataRepository(db_session)


@pytest.fixture
def chroma_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    persist_dir = tmp_path / "chromadb"
    persist_dir.mkdir()
    monkeypatch.setenv("CHROMA_DB_DIR", str(persist_dir))
    get_chroma_client.cache_clear()
    client = get_chroma_client()
    try:
        yield client
    finally:
        try:
            client.reset()
        except Exception as error:
            print(f"Failed to reset Chroma client: {error}")
        get_chroma_client.cache_clear()


@pytest.fixture
def sheet_fixture_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "sheet_sources"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture
def sheet_definitions() -> list[SheetDefinition]:
    return list(DEFAULT_SHEETS)


@pytest.fixture
def workbook_builder(sheet_fixture_dir: Path):
    def _builder(
        *,
        sheets: Sequence[SheetDefinition] | None = None,
        filename: str = "multi_sheet.xlsx",
    ) -> Path:
        return build_workbook(sheet_fixture_dir / filename, sheets=sheets)

    return _builder


@pytest.fixture
def csv_builder(sheet_fixture_dir: Path):
    def _builder(
        *,
        headers: Sequence[str] | None = None,
        rows: Iterable[Sequence[object]] | None = None,
        filename: str = "sales_vs_budget.csv",
    ) -> Path:
        return build_csv(
            sheet_fixture_dir / filename,
            headers=headers or DEFAULT_CSV_HEADERS,
            rows=rows or DEFAULT_CSV_ROWS,
        )

    return _builder


@pytest.fixture
def default_workbook_path(workbook_builder):
    return workbook_builder()


@pytest.fixture
def sales_vs_budget_csv_path(csv_builder):
    return csv_builder()
