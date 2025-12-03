from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.db.metadata import MetadataRepository, create_session_factory, session_scope, build_engine
from app.services.embeddings import EmbeddingJob, EmbeddingSummary


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
    workbook_path: Path,
    *,
    display_name: str,
) -> tuple[int, dict[str, object]]:
    response = client.post(
        "/api/source-bundles/import",
        files={
            "file": (
                workbook_path.name,
                _read_binary(workbook_path),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={
            "displayName": display_name,
            "selectedColumns": json.dumps(["region", "category", "revenue"]),
            "hiddenSheetPolicy": json.dumps(
                {
                    "defaultAction": "exclude",
                    "overrides": ["HiddenStrategic"],
                }
            ),
        },
    )
    return response.status_code, response.json()


def _inject_unavailable_column(dataset_id: str, column_name: str) -> None:
    engine = build_engine()
    SessionFactory = create_session_factory(engine)
    with session_scope(SessionFactory) as session:
        repo = MetadataRepository(session)
        sheets = repo.list_sheet_sources(bundle_id=dataset_id)
        assert sheets, "Expected sheets to exist for dataset"
        target = sheets[0]
        schema = list(target.column_schema or [])
        schema.append(
            {
                "name": column_name,
                "display_label": column_name.title(),
                "availability": "missing",
            }
        )
        repo.update_sheet_source(
            target,
            column_schema=schema,
            last_refreshed_at=datetime.now(timezone.utc),
        )


def test_column_catalog_dedupes_and_returns_sheet_provenance(
    client: TestClient,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="contract_column_catalog.xlsx")
    status, payload = _import_bundle(
        client,
        workbook_path,
        display_name="FY25 Workbook",
    )
    assert status == 201, payload
    dataset_id = payload["id"]

    catalog_response = client.get(f"/api/source-bundles/{dataset_id}/sheets")
    assert catalog_response.status_code == 200
    sheet_catalog = catalog_response.json()["sheets"]
    assert sheet_catalog, "Expected sheet catalog to be populated"

    response = client.get(f"/datasets/{dataset_id}/columns/catalog")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["datasetId"] == dataset_id

    columns = payload["columns"]
    names = {entry["columnName"] for entry in columns}
    assert {"region", "category", "revenue"}.issubset(names)

    region = next(entry for entry in columns if entry["columnName"] == "region")
    assert region["availability"] == "available"
    assert len(region["sheetProvenance"]) == len(sheet_catalog)
    assert region["displayLabel"] == "region"


def test_column_catalog_includes_unavailable_when_requested(
    client: TestClient,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="contract_column_catalog_unavailable.xlsx")
    status, payload = _import_bundle(
        client,
        workbook_path,
        display_name="FY25 Workbook Unavailable",
    )
    assert status == 201, payload
    dataset_id = payload["id"]
    _inject_unavailable_column(dataset_id, "ghost header")

    default_response = client.get(f"/datasets/{dataset_id}/columns/catalog")
    assert default_response.status_code == 200
    default_names = {entry["columnName"] for entry in default_response.json()["columns"]}
    assert "ghost header" not in default_names

    with_unavailable = client.get(
        f"/datasets/{dataset_id}/columns/catalog",
        params={"includeUnavailable": "true"},
    )
    assert with_unavailable.status_code == 200, with_unavailable.text
    payload = with_unavailable.json()

    ghost = next(entry for entry in payload["columns"] if entry["columnName"] == "ghost header")
    assert ghost["availability"] == "missing"
    assert ghost["sheetProvenance"], "Expected provenance for unavailable column"
