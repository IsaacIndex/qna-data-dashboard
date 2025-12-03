# Implementation Plan: Q&A Dashboard UX Refresh

**Branch**: `004-dashboard-ux-refresh` | **Date**: `2025-12-02` | **Spec**: `/Users/isaacibm/GitHub/qna-data-dashboard/specs/004-dashboard-ux-refresh/spec.md`
**Input**: Feature specification from `/specs/004-dashboard-ux-refresh/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Revamp the Streamlit-based Q&A dashboard UX so analysts of all skill levels can quickly ingest multi-sheet datasets, pick trial embedding columns, and read search results with contextual columns plus a consistent 0–100% similarity color scale. Emphasis is on low-friction flows (minimal clicks, preserved selections across tabs), plain-language guidance, and fast, predictable interactions with device-local preference storage.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Runtime**: Python 3.11; Streamlit UI with FastAPI backend; type-hinted codebase enforced via mypy; CI runs ruff + black for lint/format.  
**Quality Tooling**: `ruff`, `black`, `mypy`, `pytest` with coverage; Streamlit accessibility linting via component guidelines; contract tests under `tests/contract`; performance smoke tests under `tests/performance`.  
**Testing Strategy**: Unit tests for ingestion/search state managers and preference adapters; integration tests for Streamlit flows (tab switches, column picker dedupe, empty/error states); contract tests for API search/ingestion endpoints; performance checks targeting <2s P95 for search execution/tab switches on typical datasets; add analytics event assertions.  
**User Experience Framework**: Streamlit multipage app (`app/pages`), shared UI utilities/components under `app/services`/`app/utils`; copy and layout follow existing dashboard patterns plus manual additions (unique column listing, dataset-specific contextual columns). Accessibility: WCAG 2.1 AA alignment for text/labels; color-blind safety not required for similarity scale but legend/text required.  
**Performance Budgets**: Search execute + render P95 ≤2s; tab switch state restoration ≤2s; column picker refresh and dedup render ≤1.5s; preference load must be non-blocking for search tab; instrumentation to emit latency events.  
**Dependencies**: Streamlit UI stack; FastAPI/SQLAlchemy backend; SQLite metadata store; optional ChromaDB + SentenceTransformers (local mode by default); local storage (browser) for device-scoped preferences.  
**Data & Storage**: Local-first data root (`./data`), SQLite at `sqlite:///data/metadata.db`, optional Chroma persistence under `<DATA_ROOT>/chromadb`; preference payloads stored in browser local storage with fallbacks; ingestion handles CSV/Excel with missing headers gracefully.  
**Scale/Scope**: Single-user, local-first experience; datasets up to hundreds of thousands of rows; low concurrent load but must keep UI responsive during ingest/search; session state must persist across tabs until explicit reset.

**Color Scale**: 5-stop neutral→teal gradient (0% #E5E7EB, 25% #93C5FD, 50% #22D3EE, 75% #10B981, 100% #0F766E) with text labels and 0–100% numeric legend shown above results.  
**Telemetry**: Structured JSONL events written to `data/logs/analytics.jsonl` with in-memory buffering fallback; fields include `event`, `duration_ms`, `dataset_id`, `tab`, `success`, and timestamp; stays local/offline.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Coding standards: Python 3.11 with ruff/black/mypy enforced; Streamlit/FastAPI boundaries maintained (UI logic in `app/pages`, services in `app/services`, persistence in `app/db`). Documentation updates committed in `specs/004-dashboard-ux-refresh/*` plus quickstart/UX notes.
- Testing: Unit + integration + contract suites extended for session persistence, column dedupe, and similarity scale rendering; performance smoke for <2s P95 interactions; commit failing tests first where feasible. Coverage targets ≥85% for touched modules; no waivers planned.
- UX patterns/accessibility: Use existing Streamlit component patterns, plain-language labels, WCAG 2.1 AA for text/contrast; similarity legend/text included; empty/error states use actionable guidance. Copy aligns with manual additions (unique column listing, dataset-specific contextual columns with saved preferences).
- Performance/instrumentation: Budgets defined above; emit analytics events for search latency, tab switch latency, preference load/save, column selection persistence; ensure logs/metrics surfaced in CI artifacts or local run logs; add benchmarks to `tests/performance/` if new paths introduced.
- Governance/waivers: No waivers requested; any temporary test/performance deferrals require documented owner/date before implementation and must be added to plan + research artifacts.

*Post-design re-check*: Clarifications resolved in `research.md`; data model, contracts, and quickstart documented. No principle violations identified; instrumentation and performance budgets captured for implementation.

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
specs/004-dashboard-ux-refresh/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── spec.md

app/
├── main.py
├── pages/                # Streamlit pages (ingest, search, analytics, query builder)
├── services/             # Domain services for ingestion, embeddings, search, analytics
├── db/                   # SQLAlchemy models/repositories
├── api/                  # FastAPI factory and routes
└── utils/                # Shared helpers

tests/
├── unit/
├── integration/
├── contract/
├── performance/
└── fixtures/
```

**Structure Decision**: Single Streamlit/FastAPI project under `app/` with shared tests in `/tests` and feature documentation in `/specs/004-dashboard-ux-refresh/`.

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
