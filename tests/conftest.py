from __future__ import annotations

import os
from collections.abc import Iterator
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
        except Exception:
            pass
        get_chroma_client.cache_clear()
