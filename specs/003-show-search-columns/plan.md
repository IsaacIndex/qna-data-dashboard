# Implementation Plan: Search Result Column Selections

**Branch**: `003-show-search-columns` | **Date**: 2025-10-23 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/003-show-search-columns/spec.md`

## Summary

Extend the Streamlit search experience so analysts can configure dataset-specific supplemental columns that appear alongside search matches. Persist preferences in the existing SQLite metadata store, expose configuration through the app’s settings UI, and ensure multi-dataset searches render each row using that dataset’s saved column set while preserving sub-second response times.

## Technical Context

**Language/Runtime**: Python 3.11 (Streamlit frontend + FastAPI services) with Poetry-managed tooling; linting/typing via Ruff, Black, and Mypy already enforced in CI.  
**Quality Tooling**: Ruff, Black, Pytest (+pytest-cov), Mypy strict mode, and pytest-benchmark for performance regressions; no new tools required.  
**Testing Strategy**: Unit tests for preference repository/service logic, integration tests covering search endpoint + Streamlit rendering, data validation on column catalog joins, and benchmark to confirm <1s render for 10-column payloads.  
**User Experience Framework**: Streamlit pages backed by shared UI helpers in `app/pages` and `app/utils/ui`; adhere to WCAG 2.1 AA via Streamlit components and existing accessibility checklist.  
**Performance Budgets**: Maintain 1s P95 search render time (FR-006, SC-001), log render timings through existing search telemetry, and extend benchmarks under `tests/performance`.  
**Dependencies**: Streamlit for UI, Pandas for dataset metadata, SQLAlchemy + SQLite for persistence, existing search service abstractions in `app/services/search.py`; no external APIs touched.  
**Data & Storage**: Preferences stored locally in SQLite alongside other metadata; column catalog derived from ingestion metadata tables; retention aligned with local-only operation and no PII.  
**Scale/Scope**: Single analyst or small team concurrently using local dashboard; datasets up to 50k rows per spec with up to 10 supplemental columns per dataset.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Code Quality Rigor: Work stays within existing Streamlit/FastAPI modules and follows repository lint/type expectations; ADR not required because persistence leverages current SQLite metadata stack.
- Evidence-Driven Testing: Commit to new unit + integration coverage plus updated performance benchmark to protect the 1s render budget before implementation begins.
- Unified User Experience: Use current Streamlit layout patterns, update quickstart walkthrough, and document accessibility verifications per constitution.
- Performance Accountability: Reaffirm 1s P95 search render target, add instrumentation to search telemetry, and publish benchmark results in CI artifact.
- Governance: No waivers anticipated; if benchmark temporarily fails, remediation owner/due date will be recorded before code merge.

**Post-Design Review**: Research and Phase 1 outputs maintain alignment with all gates; no waivers or additional approvals required.

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
```
app/
├── main.py
├── api/
├── db/
├── pages/
├── services/
└── utils/

tests/
├── integration/
├── performance/
└── unit/
```

**Structure Decision**: Single Streamlit application under `app/` with supporting services/utils and shared SQLite metadata layer; tests organized by type under `tests/`.

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _None_ | — | — |
