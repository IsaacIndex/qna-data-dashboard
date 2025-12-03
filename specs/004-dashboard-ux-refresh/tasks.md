---
description: "Executable task list for Q&A Dashboard UX Refresh"
---

# Tasks: Q&A Dashboard UX Refresh

**Input**: Design documents from `/Users/isaacibm/GitHub/qna-data-dashboard/specs/004-dashboard-ux-refresh/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/  
**Tests**: Tests are defined per user story (contract + integration) to keep increments independently verifiable.  
**Organization**: Tasks are grouped by user story so each increment can be built and tested independently.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline artifacts and fixtures required for downstream work

- [X] T001 Add analytics log placeholder to keep path available in git at `/Users/isaacibm/GitHub/qna-data-dashboard/data/logs/.gitkeep`
- [X] T002 Add multi-sheet test fixture covering missing/duplicate headers for ingestion and picker flows at `/Users/isaacibm/GitHub/qna-data-dashboard/tests/fixtures/multi_sheet_column_cases.xlsx`
- [X] T003 Document feature-specific run instructions and telemetry log location updates in `/Users/isaacibm/GitHub/qna-data-dashboard/specs/004-dashboard-ux-refresh/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared utilities and telemetry required before any user story can proceed

- [X] T004 [P] Add similarity palette and banding constants (0–100, five stops) for reuse across UI/backend in `/Users/isaacibm/GitHub/qna-data-dashboard/app/utils/constants.py`
- [X] T005 Extend analytics client to emit `search.latency`, `tab.switch.latency`, `preference.load/save`, and `column.selection.persist` events with buffered JSONL writer in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/analytics.py` and `/Users/isaacibm/GitHub/qna-data-dashboard/app/utils/logging.py`
- [X] T006 [P] Add shared column catalog aggregation helper (union + availability flags) based on `ColumnCatalog` entity in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/ingestion.py`
- [X] T007 Add session state helper to persist tab/page selections and reset confirmations in `/Users/isaacibm/GitHub/qna-data-dashboard/app/utils/session_state.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Readable search results with clear confidence (Priority: P1) - MVP

**Goal**: Render search results with contextual columns and a consistent 0–100% similarity color scale plus legend/text labels.  
**Independent Test**: Execute search on existing dataset and confirm contextual columns + similarity legend render with readable text even when no preferences are set.

### Tests for User Story 1

- [X] T008 [P] [US1] Add contract test for `/search` legend + contextual columns response in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/contract/test_search_endpoint.py`
- [X] T009 [P] [US1] Add Streamlit integration test for similarity legend/guidance when no contextual columns configured in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/integration/search/test_search_similarity_ui.py`

### Implementation for User Story 1

- [X] T010 [P] [US1] Update FastAPI `/search` route to return similarity legend palette and contextual column defaults in `/Users/isaacibm/GitHub/qna-data-dashboard/app/api/router.py`
- [X] T011 [P] [US1] Add similarity banding utility (0–20…86–100 with labels/colors) and unit coverage in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/search.py`
- [X] T012 [US1] Render contextual columns, legend, and inline guidance for empty preferences on the search page in `/Users/isaacibm/GitHub/qna-data-dashboard/app/pages/2_search.py`
- [X] T013 [US1] Emit `search.latency` analytics and include contextual column provenance per result in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/analytics.py`

**Checkpoint**: User Story 1 independently testable (search queries show contextual columns + similarity scale)

---

## Phase 4: User Story 2 - Guided column selection for trial embeddings (Priority: P2)

**Goal**: Provide deduplicated column picker across sheets with availability flags and minimal-click selection that persists across tab switches.  
**Independent Test**: Upload multi-sheet files (with/without missing headers), select columns, switch tabs, and confirm deduped list, unavailable badges, and persisted selections.

### Tests for User Story 2

- [X] T014 [P] [US2] Add contract test for `/datasets/{datasetId}/columns/catalog` dedup + availability responses in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/contract/test_column_catalog.py`
- [X] T015 [P] [US2] Add integration test for column picker dedupe, sheet chips, and persistence across tab switches in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/integration/ingest/test_column_picker_dedupe.py`

### Implementation for User Story 2

- [X] T016 [P] [US2] Implement column catalog union with sheet provenance and unavailable badges in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/ingestion.py`
- [X] T017 [P] [US2] Wire FastAPI endpoint `/datasets/{datasetId}/columns/catalog` to new aggregator with `includeUnavailable` support in `/Users/isaacibm/GitHub/qna-data-dashboard/app/api/router.py`
- [X] T018 [US2] Update ingest page column picker to show unique columns once with sheet chips and keyboard-friendly selection in `/Users/isaacibm/GitHub/qna-data-dashboard/app/pages/1_ingest.py`
- [X] T019 [US2] Persist column selections in session state across tabs and emit `column.selection.persist` analytics in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/preferences.py`

**Checkpoint**: User Story 2 independently testable (deduped picker + persisted selections)

---

## Phase 5: User Story 3 - Saved preferences and consistent defaults (Priority: P3)

**Goal**: Save device-local result layout/column preferences with optional backend mirror and reset confirmation without blocking search.  
**Independent Test**: Save preferences, restart the app, and verify auto-applied layouts with reset confirmation and non-blocking load behavior.

### Tests for User Story 3

- [X] T020 [P] [US3] Add contract test for preference mirror GET/POST non-blocking responses in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/contract/test_preferences_mirror.py`
- [X] T021 [P] [US3] Add integration test for device-local preference hydration and reset across app restart in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/integration/preferences/test_local_preferences.py`

### Implementation for User Story 3

- [X] T022 [P] [US3] Enhance preference adapter to hydrate `st.session_state` asynchronously from localStorage with safe defaults in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/preferences.py`
- [X] T023 [P] [US3] Implement optional backend mirror calls with error-tolerant handling for preferences in `/Users/isaacibm/GitHub/qna-data-dashboard/app/services/preferences.py` and `/Users/isaacibm/GitHub/qna-data-dashboard/app/api/router.py`
- [X] T024 [US3] Apply saved layouts/columns across search and ingest pages with reset confirmation copy in `/Users/isaacibm/GitHub/qna-data-dashboard/app/pages/2_search.py` and `/Users/isaacibm/GitHub/qna-data-dashboard/app/pages/1_ingest.py`

**Checkpoint**: User Story 3 independently testable (device-local preferences load, mirror, reset)

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance, documentation, and final validation

- [X] T025 [P] Add performance smoke tests for search execution and tab switch latency budgets in `/Users/isaacibm/GitHub/qna-data-dashboard/tests/performance/test_latency_budgets.py`
- [X] T026 [P] Update documentation for similarity palette, guidance copy, and reset behaviors in `/Users/isaacibm/GitHub/qna-data-dashboard/specs/004-dashboard-ux-refresh/quickstart.md` and `/Users/isaacibm/GitHub/qna-data-dashboard/specs/004-dashboard-ux-refresh/research.md`
- [X] T027 Run end-to-end quickstart validation (ingest, column picker, search, preferences, analytics log) and record outcomes in `/Users/isaacibm/GitHub/qna-data-dashboard/specs/004-dashboard-ux-refresh/checklists/validation.md`

---

## Dependencies & Execution Order

- Foundational (Phase 2) depends on Setup (Phase 1) and blocks all user stories.  
- User stories can proceed after Phase 2; recommended order by priority: US1 (P1) → US2 (P2) → US3 (P3).  
- Polish (Phase 6) after targeted user stories are complete.

Dependency graph: Setup → Foundational → US1 → US2 → US3 → Polish (US2/US3 may run in parallel after Foundational if staffed, but MVP is US1).

## Parallel Execution Examples

- **US1**: T008 and T009 (tests) can run in parallel while T011 builds banding utility; T010 depends on T011.  
- **US2**: T014 and T015 can run in parallel; T016/T017 can proceed together; T018 waits on T016/T017 outputs.  
- **US3**: T020 and T021 in parallel; T022/T023 in parallel; T024 after preference adapter/mirror updates.

## Implementation Strategy

- MVP first: complete Setup → Foundational → User Story 1, then validate via T008–T013.  
- Incremental delivery: add User Story 2, validate picker flows; then User Story 3 for saved preferences.  
- Keep tasks independently testable; prefer small merges per task to maintain clarity and rollback safety.
