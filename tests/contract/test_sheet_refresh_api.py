from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.db.metadata import (
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.services.embeddings import EmbeddingJob, EmbeddingSummary
from tests.fixtures.sheet_sources.factory import SheetDefinition


class SheetEmbeddingStub:
    def __init__(self) -> None:
        self.jobs: list[EmbeddingJob] = []

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        if job.sheet is None:
            raise AssertionError("Sheet embeddings should target sheet sources.")
        self.jobs.append(job)
        return EmbeddingSummary(vector_count=len(job.records), model_name="stub", model_dimension=1)


@pytest.fixture
def client(sqlite_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    app = create_app(embedding_service=SheetEmbeddingStub())
    return TestClient(app)


def _read_binary(path: Path) -> bytes:
    return path.read_bytes()


def _import_bundle(
    client: TestClient,
    *,
    upload_path: Path,
    display_name: str,
    selected_columns: list[str],
) -> tuple[int, dict[str, object]]:
    response = client.post(
        "/api/source-bundles/import",
        files={
            "file": (
                upload_path.name,
                _read_binary(upload_path),
                "application/octet-stream",
            )
        },
        data={
            "displayName": display_name,
            "selectedColumns": json.dumps(selected_columns),
            "hiddenSheetPolicy": json.dumps({"defaultAction": "exclude"}),
        },
    )
    return response.status_code, response.json()


def _bundle_sheet_path(bundle_id: str, filename: str) -> Path:
    data_root = Path(os.environ["DATA_ROOT"])
    return data_root / "bundles" / bundle_id / filename


def _find_sheet(catalog: dict[str, object], sheet_name: str) -> dict[str, object]:
    for sheet in catalog["sheets"]:
        if sheet["sheetName"] == sheet_name:
            return sheet
    raise AssertionError(f"Sheet {sheet_name} not found in catalog.")


def test_refresh_detects_renames_and_inactivates_removed_sheets(
    client: TestClient,
    workbook_builder,
    tmp_path: Path,
    sqlite_url: str,
) -> None:
    original_workbook = workbook_builder(filename="refresh_initial.xlsx")
    status, payload = _import_bundle(
        client,
        upload_path=original_workbook,
        display_name="Refresh Workbook",
        selected_columns=["region", "category", "revenue"],
    )
    assert status == 201

    bundle_id = payload["id"]
    catalog_before = client.get(f"/api/source-bundles/{bundle_id}/sheets").json()
    north_sheet = _find_sheet(catalog_before, "North")
    south_sheet = _find_sheet(catalog_before, "South")

    updated_workbook_path = workbook_builder(
        sheets=[
            SheetDefinition(
                name="SouthEast",
                headers=("region", "category", "revenue"),
                rows=(
                    ("south", "hardware", 89200),
                    ("south", "software", 102750),
                ),
            ),
            SheetDefinition(
                name="West",
                headers=("region", "category", "revenue"),
                rows=(
                    ("west", "hardware", 78000),
                    ("west", "software", 90500),
                ),
            ),
        ],
        filename="refresh_updated.xlsx",
    )

    engine = build_engine(sqlite_url)
    init_database(engine)
    SessionFactory = create_session_factory(engine)
    try:
        with session_scope(SessionFactory) as session:
            repo = MetadataRepository(session)
            bundle = repo.get_source_bundle(bundle_id)
            assert bundle is not None
            stored_path = Path(bundle.original_path)
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(updated_workbook_path, stored_path)
    finally:
        engine.dispose()

    refresh_response = client.post(
        f"/api/source-bundles/{bundle_id}/refresh",
        json={"allowHiddenSheets": []},
    )
    assert refresh_response.status_code == 202, refresh_response.text
    audit = refresh_response.json()
    assert audit["status"] == "succeeded"
    assert audit["sheetSummary"] == {"created": 1, "updated": 1, "deactivated": 1}

    catalog_after = client.get(f"/api/source-bundles/{bundle_id}/sheets").json()
    southeast_sheet = _find_sheet(catalog_after, "SouthEast")
    assert southeast_sheet["id"] == south_sheet["id"]
    assert southeast_sheet["status"] == "active"

    inactive_north = _find_sheet(catalog_after, "North")
    assert inactive_north["status"] == "inactive"

    west_sheet = _find_sheet(catalog_after, "West")
    assert west_sheet["status"] == "active"
    assert west_sheet["id"] not in {north_sheet["id"], south_sheet["id"]}


def test_patch_sheet_source_updates_metadata(
    client: TestClient,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="refresh_patch.xlsx")
    status, payload = _import_bundle(
        client,
        upload_path=workbook_path,
        display_name="Patch Workbook",
        selected_columns=["region", "category", "revenue"],
    )
    assert status == 201

    bundle_id = payload["id"]
    catalog = client.get(f"/api/source-bundles/{bundle_id}/sheets").json()
    target_sheet = _find_sheet(catalog, "North")

    patch_response = client.patch(
        f"/api/sheet-sources/{target_sheet['id']}",
        json={
            "description": "North region sales dashboard",
            "status": "inactive",
            "tags": ["sales", "north"],
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    payload = patch_response.json()
    assert payload["description"] == "North region sales dashboard"
    assert payload["status"] == "inactive"
    assert sorted(payload.get("tags", [])) == ["north", "sales"]
