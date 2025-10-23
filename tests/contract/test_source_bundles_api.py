from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.router import create_app
from app.services.embeddings import EmbeddingJob, EmbeddingSummary


class SheetEmbeddingStub:
    def __init__(self) -> None:
        self.jobs: list[EmbeddingJob] = []

    def run_embedding(self, job: EmbeddingJob) -> EmbeddingSummary:
        self.jobs.append(job)
        if job.sheet is None:
            raise AssertionError("Sheet embeddings should target sheet sources.")
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
    hidden_policy: dict[str, object],
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
            "hiddenSheetPolicy": json.dumps(hidden_policy),
        },
    )
    return response.status_code, response.json()


def test_import_bundle_excludes_hidden_sheets_by_default(
    client: TestClient,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="contract_default.xlsx")
    status, payload = _import_bundle(
        client,
        workbook_path,
        display_name="FY25 Workbook",
        hidden_policy={"defaultAction": "exclude"},
    )

    assert status == 201
    assert payload["displayName"] == "FY25 Workbook"
    assert payload["sheetCount"] == 2

    bundle_id = payload["id"]
    catalog_response = client.get(f"/api/source-bundles/{bundle_id}/sheets")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()

    sheet_names = [sheet["sheetName"] for sheet in catalog["sheets"]]
    assert set(sheet_names) == {"North", "South"}
    assert all(sheet["visibilityState"] == "visible" for sheet in catalog["sheets"])


def test_import_bundle_includes_hidden_sheet_when_opted_in(
    client: TestClient,
    workbook_builder,
) -> None:
    workbook_path = workbook_builder(filename="contract_opt_in.xlsx")
    status, payload = _import_bundle(
        client,
        workbook_path,
        display_name="FY25 Workbook Hidden Opt In",
        hidden_policy={
            "defaultAction": "exclude",
            "overrides": ["HiddenStrategic"],
        },
    )

    assert status == 201
    assert payload["sheetCount"] == 3

    bundle_id = payload["id"]
    catalog_response = client.get(f"/api/source-bundles/{bundle_id}/sheets")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()

    sheet_names = {sheet["sheetName"] for sheet in catalog["sheets"]}
    assert sheet_names == {"North", "South", "HiddenStrategic"}

    hidden_sheet = next(sheet for sheet in catalog["sheets"] if sheet["sheetName"] == "HiddenStrategic")
    assert hidden_sheet["visibilityState"] == "hidden_opt_in"
