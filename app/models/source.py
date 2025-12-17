from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceType(str, Enum):
    tmp_file = "tmp_file"
    sheet = "sheet"
    embedding = "embedding"


class SourceStatus(str, Enum):
    new = "new"
    ingesting = "ingesting"
    ready = "ready"
    archived = "archived"
    error = "error"


class LegacyReason(str, Enum):
    missing_headers = "missing_headers"
    prior_format = "prior_format"
    missing_uuid = "missing_uuid"


class RemapStatus(str, Enum):
    pending = "pending"
    mapped = "mapped"
    failed = "failed"


class Source(BaseModel):
    uuid: str
    label: str
    dataset: str
    type: SourceType
    status: SourceStatus = SourceStatus.new
    groups: list[str] = Field(default_factory=list)
    last_updated: datetime | None = None
    legacy: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("label", "dataset")
    @classmethod
    def _require_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("label and dataset must be non-empty")
        return text

    @field_validator("groups")
    @classmethod
    def _dedupe_groups(cls, groups: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for raw in groups:
            name = raw.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(name)
        return result


class LegacySource(Source):
    legacy_reason: LegacyReason
    remap_status: RemapStatus = RemapStatus.pending
    original_id: str | None = None

    @model_validator(mode="after")
    def _force_legacy_flag(self) -> "LegacySource":
        self.legacy = True
        return self
