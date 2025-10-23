from __future__ import annotations

import pytest

from app.services.query_builder import QueryBuilderService, QueryValidationError


def _schema(name: str, inferred_type: str) -> dict[str, object]:
    return {"name": name, "inferredType": inferred_type, "nullable": False}


def test_validate_join_keys_missing_column_raises() -> None:
    primary_schema = [_schema("region", "string")]
    join_schema = [_schema("region_code", "string")]

    with pytest.raises(QueryValidationError, match="Join column 'region' missing on sheet alias 'budget'"):
        QueryBuilderService.validate_join_keys(
            primary_schema,
            join_schema,
            join_keys=["region"],
            primary_alias="sales",
            join_alias="budget",
        )


def test_validate_join_keys_type_mismatch_warns() -> None:
    primary_schema = [_schema("region", "string")]
    join_schema = [_schema("region", "number")]

    warnings = QueryBuilderService.validate_join_keys(
        primary_schema,
        join_schema,
        join_keys=["region"],
        primary_alias="sales",
        join_alias="budget",
    )

    assert warnings == [
        "Join column 'region' uses incompatible types between 'sales' (string) and 'budget' (number)."
    ]


def test_validate_join_keys_accepts_matching_types() -> None:
    primary_schema = [_schema("region", "string"), _schema("category", "string")]
    join_schema = [_schema("region", "string"), _schema("category", "string")]

    warnings = QueryBuilderService.validate_join_keys(
        primary_schema,
        join_schema,
        join_keys=["region", "category"],
        primary_alias="sales",
        join_alias="budget",
    )

    assert warnings == []
