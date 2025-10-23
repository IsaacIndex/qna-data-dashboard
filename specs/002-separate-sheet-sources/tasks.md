---
description: "Task list for Sheet-Level Data Sources feature"
---

# Tasks: Sheet-Level Data Sources

**Input**: Design documents under `/specs/002-separate-sheet-sources/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`  
**Tests**: Follow TDD — write contract, integration, and unit coverage before implementing feature code.  
**Organization**: Tasks are grouped by user story so each increment is independently testable and deliverable.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Task can run in parallel (isolated files, no blocking dependencies)
- **[Story]**: User story mapping (US1, US2, US3)
- Every description includes concrete file paths

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create shared fixtures, helpers, and constants used across all user stories

- [X] T001 Create multi-sheet workbook and CSV fixture builders in `tests/fixtures/sheet_sources/factory.py`
- [X] T002 Expose pytest fixtures for sheet bundles using factory helpers in `tests/conftest.py`
- [X] T003 Add sheet performance threshold constants (ingestion max, query p95) in `app/utils/constants.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish schema, repository, and service scaffolding for sheet sources

- [X] T004 Refactor SQLAlchemy models to add `SourceBundle`, `SheetSource`, `BundleAudit`, `SheetMetric`, and `QuerySheetLink` in `app/db/schema.py`
- [X] T005 Create DataFile decomposition migration and backfill logic in `app/db/migrations/002_sheet_sources.py`
- [X] T006 Extend `MetadataRepository` with bundle, sheet, audit, metric, and query link operations in `app/db/metadata.py`
- [X] T007 Refactor embedding jobs to operate on sheet-scoped datasets in `app/services/embeddings.py`
- [X] T008 Update search service to load sheet metadata and log sheet metrics in `app/services/search.py`
- [X] T009 Update analytics service to summarize sheet-scoped records and metrics in `app/services/analytics.py`

---

## Phase 3: User Story 1 - Discover sheet-based sources (Priority: P1) - MVP

**Goal**: Register each visible sheet as an independent data source with metadata and hidden sheet governance  
**Independent Test**: Automate workbook upload with three sheets and confirm the catalog exposes matching `SheetSource` entries while hidden tabs remain excluded unless opted in

### Tests for User Story 1

- [X] T010 [P] [US1] Add contract tests for `POST /api/source-bundles/import` covering hidden sheet policy handling in `tests/contract/test_source_bundles_api.py`
- [X] T011 [P] [US1] Add integration test for multi-sheet ingestion and catalog listing in `tests/integration/sheets/test_sheet_catalog.py`
- [X] T012 [P] [US1] Add unit tests for sheet enumeration and audit recording in `tests/unit/test_sheet_ingestion.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement SourceBundle ingestion with hidden sheet governance, sheet metrics, and previews in `app/services/ingestion.py`
- [X] T014 [US1] Expose `/api/source-bundles/import` and `/api/source-bundles/{bundleId}/sheets` responses in `app/api/router.py`
- [X] T015 [US1] Update Streamlit ingestion UI for sheet selection, hidden sheet acknowledgements, and catalog display in `app/pages/1_ingest.py`

---

## Phase 4: User Story 2 - Combine sheets across files (Priority: P2)

**Goal**: Enable analysts to join sheet sources from different bundles through the query builder  
**Independent Test**: Execute an automated scenario joining three sheet sources (two bundles plus CSV) and verify aggregate results match fixture expectations

### Tests for User Story 2

- [X] T016 [P] [US2] Add contract tests for `POST /api/queries/preview` covering cross-bundle joins in `tests/contract/test_queries_preview.py`
- [X] T017 [P] [US2] Add integration test for cross-sheet joins and aggregations in `tests/integration/sheets/test_sheet_queries.py`
- [X] T018 [P] [US2] Add unit tests for schema compatibility checks in `tests/unit/test_query_builder.py`

### Implementation for User Story 2

- [X] T019 [US2] Implement cross-sheet query preview orchestration with compatibility warnings in `app/services/query_builder.py`
- [X] T020 [US2] Wire `/api/queries/preview` endpoint to the query builder service in `app/api/router.py`
- [X] T021 [US2] Persist `QueryDefinition` and `QuerySheetLink` relationships for saved queries in `app/db/metadata.py`
- [X] T022 [US2] Build Streamlit query builder page and navigation entry in `app/pages/4_query_builder.py` and `app/main.py`

---

## Phase 5: User Story 3 - Maintain sheet-source integrity (Priority: P3)

**Goal**: Keep sheet sources stable across refreshes with rename detection, deactivation, and proactive warnings  
**Independent Test**: Replace a workbook with renamed and deleted sheets, trigger refresh, and verify existing sheet IDs persist or deactivate with warnings before query execution

### Tests for User Story 3

- [X] T023 [P] [US3] Add contract tests for `/api/source-bundles/{bundleId}/refresh` and `/api/sheet-sources/{sheetId}` in `tests/contract/test_sheet_refresh_api.py`
- [X] T024 [P] [US3] Add integration test for rename detection and inactive sheet warnings in `tests/integration/sheets/test_sheet_refresh_service.py`
- [X] T025 [P] [US3] Add unit tests for refresh reconciliation heuristics in `tests/unit/test_sheet_refresh_utils.py`

### Implementation for User Story 3

- [X] T026 [US3] Implement bundle refresh reconciliation with checksum and schema comparison in `app/services/ingestion.py`
- [X] T027 [US3] Implement `/api/source-bundles/{bundleId}/refresh` summary response in `app/api/router.py`
- [X] T028 [US3] Implement `/api/sheet-sources/{sheetId}` PATCH handler for metadata updates in `app/api/router.py`
- [X] T029 [US3] Surface inactive and renamed sheet warnings during previews in `app/services/query_builder.py`
- [X] T030 [US3] Display refresh status and inactive sheet messaging in `app/pages/1_ingest.py` and `app/pages/4_query_builder.py`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize documentation, governance, and operational guidance

- [X] T031 Document sheet metrics alert thresholds and runbook in `docs/performance/002-sheet-sources.md`
- [X] T032 Publish hidden sheet governance procedures in `docs/operations/sheet-sources.md`
- [X] T033 Update quickstart steps for sheet uploads, query builder, and refresh workflow in `specs/002-separate-sheet-sources/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (Phase 1) → Foundational (Phase 2) → US1 (Phase 3) → US2 (Phase 4) → US3 (Phase 5) → Polish (Phase 6)
- Foundational tasks (T004–T009) must complete before any user story implementation to prevent schema drift.

### User Story Dependency Graph
- US1 (P1) ➜ US2 (P2) ➜ US3 (P3)

### Task Dependency Highlights
- T019 depends on T006 and T013 to ensure query builder has sheet metadata.
- T026 requires T013 and T021 so refresh logic can reconcile persisted sheet IDs and query links.
- T030 depends on T015 and T022 to render refresh and warning states in the UI.

## Parallel Execution Examples
- **US1**: T010–T012 can run in parallel; after T013 lands, T014 and T015 proceed concurrently (API vs. UI).
- **US2**: T016–T018 execute concurrently; T019 and T021 can run in parallel once repository extensions (T006) are verified.
- **US3**: T023–T025 run in parallel; following T026, T027 and T028 can proceed simultaneously while UI updates (T030) wait for API stability.

## Implementation Strategy
1. Deliver Phases 1–2 to introduce schema, repository, and migration scaffolding.
2. Complete US1 (T010–T015) to achieve the MVP sheet catalog.
3. Layer US2 (T016–T022) to unlock cross-sheet query previews.
4. Add US3 (T023–T030) to harden refresh integrity and warnings.
5. Finish with Polish tasks (T031–T033) covering documentation and operational readiness.

## Validation Checklist
- All tasks follow the required checklist format with IDs, optional `[P]`, and story labels where needed.
- Each user story has pre-implementation tests and implementation tasks that are independently testable.
- Shared prerequisites are isolated to Phases 1–2 to keep later phases parallel-friendly.
