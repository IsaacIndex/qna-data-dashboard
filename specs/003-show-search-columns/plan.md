# Implementation Plan: Search Result Column Selections

**Branch**: `003-show-search-columns` | **Date**: 2025-10-23 | **Spec**: `specs/003-show-search-columns/spec.md`
**Input**: Feature specification from `specs/003-show-search-columns/spec.md`

## Summary

Deliver dataset-specific contextual columns in search results so analysts see baseline metadata plus their saved supplemental fields without leaving the search view. Technical approach leverages new persisted column-preference records, enriches the existing search service to attach contextual values at query time, and surfaces configuration controls in Streamlit with API parity for automation.

## Technical Context

**Language/Runtime**: Python 3.11 runtime with Streamlit UI, FastAPI backend, and SQLAlchemy ORM over SQLite. Code adheres to Ruff linting, Black formatting, and MyPy typing enforced in CI via Poetry scripts.  
**Quality Tooling**: Maintain `ruff`, `black`, `mypy`, `pytest`, and coverage thresholds (`pytest --cov=app`). Introduce contract tests aligned with OpenAPI for column-preference endpoints; update CI configuration if new test modules are added.  
**Testing Strategy**: Add unit tests for repository/helpers managing column preferences, integration tests covering search results with dataset-specific contextual columns, contract tests for new API endpoints, and performance regression check ensuring search latency benchmark (`tests/performance/test_search_latency.py`) remains ≤1s with 10 supplemental columns.  
**User Experience Framework**: Streamlit components (multiselect, reorder controls via `st.data_editor` or equivalent) following existing dashboard styling. Accessibility verified with keyboard navigation through selection controls and placeholder copy consistent with UX guidelines. Toast/banners reuse `app.pages` helpers.  
**Performance Budgets**: Honor FR-006 1s P95 render budget by batching preference lookups and column hydration inside `SearchService`. Instrument search timing using existing `record_performance_metric` calls plus additional logging for contextual column hydration time.  
**Dependencies**: Extend `app.db.schema` and `MetadataRepository` with new SQLAlchemy models; rely on existing ingestion metadata to build column catalogs. No external services beyond current embeddings infrastructure. Risk: migrations must not regress ingestion/search.  
**Data & Storage**: Persist `ColumnPreference` and `ColumnPreferenceChange` tables in SQLite, keyed by dataset and optional user. Store ordered column metadata (name, label, position). Ensure GDPR alignment by limiting stored user identifiers to existing auth IDs and retaining audit logs >=30 days.  
**Scale/Scope**: Target concurrent analysts <20 with datasets up to 50k rows and 10 contextual columns. Search candidate limit remains 5k (configurable) with expectation of <5 MB payload per response. Preferences expected to remain O(number of datasets × users) and cached per session.

## Constitution Check

- **Code Quality Rigor**: Document schema/api additions in this plan and in-code docstrings; reuse repository patterns to avoid duplication. Update developer docs (quickstart) before implementation. No waivers required.  
- **Evidence-Driven Testing**: Commit failing tests first for preference persistence and search rendering. Maintain existing coverage thresholds and add benchmarks ensuring performance budget validation. No deferrals planned; any temporary gaps require waiver filed in tasks.md.  
- **Unified User Experience**: Reuse Streamlit components with accessible labels, placeholder `"—"` for nulls, and dataset-specific banners when columns missing. Coordinate with design tokens already used in recent ingestion updates.  
- **Performance Accountability**: Define 1s P95 limit for searches with supplemental columns; log hydration timings and extend performance test fixture to assert budget. Results published through existing `record_performance_metric` pipeline.  
- **Governance & Approvals**: No constitution waivers anticipated. Schema change documented via alembic migration plan; audit logging satisfied through `ColumnPreferenceChange`. If new CLI command added for resets, ensure ADR not required (matches existing CLI patterns).

## Project Structure

### Documentation (this feature)

```
specs/003-show-search-columns/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── column-preferences.openapi.yaml
└── tasks.md            # Phase 2 output (pending)
```

### Source Code (repository root)

```
app/
├── api/
│   └── router.py                # REST endpoints for search + new preferences API
├── db/
│   ├── schema.py                # SQLAlchemy models (add ColumnPreference tables)
│   └── metadata.py              # Repository methods for preferences & catalogs
├── pages/
│   └── 2_search.py              # Streamlit UI for search + configuration controls
├── services/
│   ├── search.py                # Enrich SearchResult with contextual columns
│   └── preferences.py           # NEW helper to manage preference logic
└── utils/
    └── logging.py

tests/
├── contract/
│   └── test_column_preferences_api.py   # NEW OpenAPI contract coverage
├── integration/
│   └── test_search_columns.py          # Validate UI/service integration
├── performance/
│   └── test_search_latency.py          # Extend benchmark for contextual columns
└── unit/
    └── test_column_preferences.py      # Repository + service units
```

**Structure Decision**: Extend existing single-project layout under `app/` while introducing `services/preferences.py` for reusable preference orchestration. Tests mirror repository structure, ensuring contract, integration, performance, and unit coverage without creating new top-level packages.

## Complexity Tracking

*(No constitution violations identified; table intentionally left blank.)*
