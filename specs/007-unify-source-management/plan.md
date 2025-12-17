# Implementation Plan: Unified Source Management

**Branch**: `[007-unify-source-management]` | **Date**: 2025-12-16 | **Spec**: /Users/isaacibm/GitHub/qna-data-dashboard/specs/007-unify-source-management/spec.md
**Input**: Feature specification from `/specs/007-unify-source-management/spec.md`

## Summary

Unify ingest views into a single, consistent source inventory with human-readable labels, canonical UUID mapping (including legacy remap), server-backed infinite scroll, and re-embed flows that avoid raw IDs. Automatically detect missing legacy sources and reinsert them with audit logging and conflict prompts. Maintain consistent statuses, grouping, and filtering across Source Management, Sheet Source Catalog, and Re-embed contexts.

## Technical Context

**Language/Runtime**: Python 3.11; Streamlit UI; FastAPI backend; pandas/pyarrow/openpyxl for sheet ingest; sentence-transformers + chromadb for embeddings.  
**Quality Tooling**: black, ruff, mypy, pytest/pytest-cov, pytest-benchmark; CI enforces lint/type/format/test with >=85% line coverage on core modules and 100% on critical ingest flows.  
**Testing Strategy**: Unit tests for UUID mapping, legacy reinsertion, list/filter/sort; integration tests for ingest tab unified list, re-embed action, bulk updates; data-validation tests for legacy header skipping; performance smoke via pytest-benchmark on list load and re-embed trigger path; accessibility/UX checklist for Streamlit components.  
**User Experience Framework**: Streamlit components with project-approved patterns; human-readable labels, server-backed infinite scroll; confirm dialogs on conflicts; accessibility targets WCAG 2.1 AA text/contrast/focus.  
**Performance Budgets**: Ingest tab initial render P95 ≤2s for 500 sources; infinite scroll batch append P95 ≤600ms per page; status refresh/consistency within one refresh cycle (≤5s); re-embed initiation UI response ≤1s.  
**Dependencies**: Local filesystem `data/ingest_sources`; chromadb vector store; sentence-transformers model; FastAPI ingestion/re-embed endpoints; audit logging mechanism (reuse existing logging). Ownership: ingest team. Risks: legacy files lacking metadata, large inventories, conflicting remaps.  
**Data & Storage**: Sources persisted under `data/ingest_sources` with canonical UUID mapping; embeddings stored in chromadb; metadata persisted alongside ingest records; no PII beyond filenames/paths expected. Retention: follow existing repo defaults; audit logs retained per current logging policy.  
**Scale/Scope**: Target up to ~5k sources per environment; concurrent analyst usage light (single-digit). Pagination via infinite scroll; server-side filter/sort. 

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Map modules and dependencies to approved coding standards, architectural boundaries, and documentation updates.
- Provide test coverage targets, required suites (unit, integration, performance), and evidence of failure-first execution.
- Document UX patterns, accessibility approach, and consistency checks planned for this work.
- Define performance budgets, instrumentation strategy, and how results will be reported in CI/release notes.
- Identify any principle waivers, governance approvals, or decision records required before implementation, including time-bound remediation plans for any temporary test or benchmark deferrals.

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
├── ingest/            # ingest flows, source management UI
├── embeddings/        # embedding/re-embed services
├── models/            # pydantic models/schemas
├── services/          # data access, chromadb, file IO
├── api/               # FastAPI endpoints
└── utils/

data/
└── ingest_sources/    # source files and metadata (canonical UUID mapping)

tests/
├── unit/
├── integration/
└── performance/
```

**Structure Decision**: Single Streamlit/FastAPI project under `app/` with supporting data under `data/` and tests under `tests/`.

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
