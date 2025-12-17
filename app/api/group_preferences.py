from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.services.ingest_storage import IngestStorage, default_storage
from app.utils.audit import record_audit


def get_storage() -> IngestStorage:
    return default_storage


router = APIRouter(prefix="/api/groups")


def _pref_path(storage: IngestStorage, group_id: str) -> Path:
    root = storage.storage_root / group_id
    root.mkdir(parents=True, exist_ok=True)
    return root / "_preferences.json"


@router.get("/{group_id}/preferences", response_model=dict)
def get_preferences(
    group_id: str,
    storage: Annotated[IngestStorage, Depends(get_storage)],
) -> dict:
    try:
        return storage.load_preferences(group_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to load preferences") from exc


@router.put("/{group_id}/preferences", response_model=dict)
def save_preferences(
    group_id: str,
    payload: dict,
    storage: Annotated[IngestStorage, Depends(get_storage)],
) -> dict:
    selected = payload.get("selected_columns") or payload.get("selectedColumns") or []
    contextual = payload.get("contextual_fields") or payload.get("contextualFields") or []
    data = storage.save_preferences(group_id, selected, contextual)
    record_audit(
        "preferences.save",
        "success",
        user=None,
        details={"group": group_id, "count": len(selected)},
    )
    return data
