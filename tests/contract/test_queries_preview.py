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


def _find_sheet_id(catalog: dict[str, object], sheet_name: str) -> str:
    for sheet in catalog["sheets"]:
        if sheet["sheetName"] == sheet_name:
            return sheet["id"]
    raise AssertionError(f"Sheet {sheet_name} not found in catalog.")


def test_preview_cross_bundle_join(
    client: TestClient,
    workbook_builder,
    csv_builder,
) -> None:
    workbook_path = workbook_builder(filename="contract_queries.xlsx")
    csv_path = csv_builder(
        filename="contract_budget.csv",
        headers=("region", "category", "budget"),
        rows=(
            ("north", "hardware", 130000),
            ("north", "software", 95000),
            ("south", "hardware", 88000),
            ("south", "software", 101000),
        ),
    )

    wb_status, wb_payload = _import_bundle(
        client,
        upload_path=workbook_path,
        display_name="Sales Workbook",
        selected_columns=["region", "category", "revenue"],
    )
    assert wb_status == 201

    csv_status, csv_payload = _import_bundle(
        client,
        upload_path=csv_path,
        display_name="Budget CSV",
        selected_columns=["region", "category", "budget"],
    )
    assert csv_status == 201

    wb_catalog = client.get(f"/api/source-bundles/{wb_payload['id']}/sheets")
    assert wb_catalog.status_code == 200
    csv_catalog = client.get(f"/api/source-bundles/{csv_payload['id']}/sheets")
    assert csv_catalog.status_code == 200

    north_sheet_id = _find_sheet_id(wb_catalog.json(), "North")
    csv_sheet_id = _find_sheet_id(csv_catalog.json(), "__csv__")

    preview_payload = {
        "sheets": [
            {"sheetId": north_sheet_id, "alias": "sales", "role": "primary"},
            {
                "sheetId": csv_sheet_id,
                "alias": "budget",
                "role": "join",
                "joinKeys": ["region", "category"],
            },
        ],
        "filters": [
            {"sheetAlias": "sales", "column": "region", "operator": "eq", "value": "north"},
        ],
        "projections": [
            {"expression": "sales.category", "label": "category"},
            {"expression": "sales.revenue", "label": "revenue"},
            {"expression": "budget.budget", "label": "budget"},
        ],
    }

    response = client.post("/api/queries/preview", json=preview_payload)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["headers"] == ["category", "revenue", "budget"]
    assert payload["warnings"] == []
    assert payload["executionMetrics"]["rowCount"] == 2
    assert payload["rows"] == [
        ["hardware", "125000", "130000"],
        ["software", "98500", "95000"],
    ]
