# Implementation Plan: Sheet-Level Data Sources

**Branch**: `002-separate-sheet-sources` | **Date**: 2025-10-21 | **Spec**: [Feature Specification](./spec.md)  
**Input**: Feature specification from `/specs/002-separate-sheet-sources/spec.md`

## Summary

Expose each Excel workbook sheet and CSV file as independently queryable data sources, update ingestion and catalog layers to manage sheet metadata, and enhance the query builder so analysts can combine sheet sources across files while preserving dashboard stability through refresh cycles.

## Technical Context

**Language/Runtime**: Python 3.11 runtime managed via Poetry; enforcement through Ruff (lint), Black (format), and MyPy (strict typing) already wired into CI.  
**Quality Tooling**: Existing `poetry run lint`, `format`, `typecheck`, and `pytest` commands stay authoritative; no new tooling introduced, but ingestion modules will extend coverage with targeted fixtures.  
**Testing Strategy**: Commit to unit coverage for sheet parsing utilities, integration tests for ingestion-to-catalog registration, contract tests for query builder joins, and performance benchmarks validating ingestion (<2 min for 50 sheets) plus cross-sheet query latency (95% <5 s).  
**User Experience Framework**: Streamlit-centric UI leveraging existing design tokens and component helpers in `app/pages`; accessibility checks align with WCAG 2.1 AA via Streamlit semantics and manual QA checklist updates.  
**Performance Budgets**: Ingestion budget: register up to 50 sheets within 2 minutes; Query budget: joins across up to three sheet sources should render results <5 seconds at 95th percentile; monitor via metrics logged to existing ingestion audit tables and dashboard telemetry.  
**Dependencies**: Continue using `pandas`, `openpyxl`, and `pyarrow` for file parsing, `sqlalchemy` metadata models for catalog storage, and Streamlit/FastAPI interfaces; require coordination with ChromaDB embeddings to ensure sheet IDs map to vector stores.  
**Data & Storage**: Sheet sources persist in SQLite-backed SQLAlchemy models (`app/db/schema.py`) with embeddings stored via ChromaDB vectors; retains existing retention policies (local fixture storage) and must append sheet-level metadata (row counts, visibility, refresh state).  
**Scale/Scope**: Target analyst team concurrency of 25 simultaneous dashboard sessions, typical workbook <=200 MB with ≤100k rows per sheet; cross-sheet queries expected to aggregate ≤100k rows per execution.

## Constitution Check

- Aligns with Code Quality Rigor by documenting ingestion/catalog changes here and extending shared utilities instead of ad-hoc scripts; no architectural boundary violations anticipated.  
- Evidence-Driven Testing satisfied through planned unit/integration/performance suites plus coverage thresholds (≥85% module coverage, 100% for ingestion critical path) and failure-first tests for new join scenarios.  
- Unified User Experience maintained by reusing Streamlit components for catalog selection, adding accessibility review notes, and updating the feature quickstart for new sheet-selection flow.  
- Performance Accountability supported by explicit ingestion/query budgets, instrumentation via existing audit tables, and CI benchmarks under `tests/performance/` for ingestion timing.  
- No waivers or governance approvals required; all dependencies remain within approved stack.

**Post-Phase 1 validation**: Design artifacts (research, data model, contracts, quickstart) uphold the above commitments; no new constitutional risks identified.

## Project Structure

### Documentation (this feature)

```
specs/002-separate-sheet-sources/
├── plan.md           # Implementation plan (this document)
├── research.md       # Phase 0 output
├── data-model.md     # Phase 1 output
├── quickstart.md     # Phase 1 output
├── contracts/        # Phase 1 API/contract artifacts
└── tasks.md          # Created by /speckit.tasks (not part of this command)
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

data/
docs/
specs/
tests/
├── integration/
├── performance/
└── unit/
```

**Structure Decision**: Treat `app/` as the single project housing ingestion, catalog, and UI layers; extend existing `app/services` for ingestion updates, `app/db` for schema changes, and `tests/*` directories for new coverage while keeping data artifacts under `data/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|

*No constitutional violations identified.*
