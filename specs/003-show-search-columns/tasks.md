# Tasks: Search Result Column Selections

**Input**: Design documents from `/specs/003-show-search-columns/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare development environment and baseline metrics

- [X] T001 Install dev dependencies defined in poetry.lock (`poetry.lock`)
- [X] T002 Run baseline search performance benchmark before changes (`tests/performance/test_search_latency.py`)
- [X] T003 Ingest sample dataset per quickstart instructions for validation (`specs/003-show-search-columns/quickstart.md`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core persistence and service scaffolding that unlocks all user stories

- [X] T004 Create alembic migration for column preference tables (`app/db/migrations/003_column_preferences.py`)
- [X] T005 Extend SQLAlchemy models with ColumnPreference and ColumnPreferenceChange (`app/db/schema.py`)
- [X] T006 Add displayable column catalog loader and preference query stubs (`app/db/metadata.py`)
- [X] T007 Scaffold preference orchestration module with typed interfaces (`app/services/preferences.py`)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Surface Contextual Columns in Search (Priority: P1) - MVP

**Goal**: Display baseline metadata plus dataset-specific contextual columns for every search result row.

**Independent Test**: Execute representative searches after configuring column visibility and verify results include the selected contextual fields for each row.

### Tests for User Story 1 (write before implementation)

- [X] T008 [P] [US1] Add integration coverage for contextual column rendering across datasets (`tests/integration/test_search_columns.py`)
- [X] T009 [P] [US1] Extend search performance benchmark to assert hydration stays ≤1s (`tests/performance/test_search_latency.py`)

### Implementation for User Story 1

- [X] T010 [US1] Implement preference retrieval and contextual column hydration helpers (`app/db/metadata.py`)
- [X] T011 [P] [US1] Enrich search service to attach contextual columns and missing flags (`app/services/search.py`)
- [X] T012 [US1] Render contextual columns, placeholders, and dataset notices in search UI (`app/pages/2_search.py`)
- [X] T013 [P] [US1] Instrument missing-column logging for observability (`app/utils/logging.py`)

**Checkpoint**: User Story 1 independently delivers contextual search results

---

## Phase 4: User Story 2 - Configure Search Result Columns (Priority: P2)

**Goal**: Provide an analyst-facing configuration panel to select, reorder, and save supplemental search columns per dataset.

**Independent Test**: Select and deselect columns in the configuration panel, persist the choice, and confirm subsequent searches show the updated selection.

### Tests for User Story 2 (write before implementation)

- [X] T014 [P] [US2] Add contract tests for save and catalog endpoints (`tests/contract/test_column_preferences_api.py`)
- [X] T015 [P] [US2] Add unit tests covering selection validation and ordering rules (`tests/unit/test_column_preferences.py`)

### Implementation for User Story 2

- [X] T016 [US2] Implement catalog fetch and save operations in preference service (`app/services/preferences.py`)
- [X] T017 [US2] Wire FastAPI routes for catalog and save endpoints (`app/api/router.py`)
- [X] T018 [US2] Build Streamlit configuration panel with multiselect and reorder controls (`app/pages/2_search.py`)
- [X] T019 [P] [US2] Enforce selection validation and order persistence in repository layer (`app/db/metadata.py`)

**Checkpoint**: User Story 2 independently enables analysts to configure displayed columns

---

## Phase 5: User Story 3 - Persist Column Preferences (Priority: P3)

**Goal**: Ensure column preferences persist across sessions, support resets, and capture audit logs for governance.

**Independent Test**: Save a column configuration, restart the session, verify selections reload automatically, and reset to defaults to confirm cleanup.

### Tests for User Story 3 (write before implementation)

- [ ] T020 [P] [US3] Add integration test covering preference persistence and reset workflow (`tests/integration/test_column_preferences_persistence.py`)
- [ ] T021 [P] [US3] Extend unit tests to verify audit logging entries on preference changes (`tests/unit/test_column_preferences.py`)

### Implementation for User Story 3

- [X] T022 [US3] Load persisted preferences and manage cache invalidation on session start (`app/services/preferences.py`)
- [X] T023 [US3] Persist audit trail entries for preference mutations (`app/db/metadata.py`)
- [X] T024 [US3] Implement delete/reset endpoint with retention safeguards (`app/api/router.py`)
- [X] T025 [US3] Add reset control and default restoration flow in search UI (`app/pages/2_search.py`)

**Checkpoint**: User Story 3 independently guarantees persisted preferences with governance logging

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize documentation, quality gates, and release readiness

- [X] T026 [P] Update quickstart documentation with configuration and reset steps (`specs/003-show-search-columns/quickstart.md`)
- [X] T027 Run full targeted test suite and capture evidence for CI updates (`tests/`)
- [X] T028 [P] Review logging and performance instrumentation alignment with plan (`app/utils/logging.py`)

---

## Dependencies & Execution Order

- Setup (Phase 1) → Foundational (Phase 2) → User Story 1 (Phase 3) → User Story 2 (Phase 4) → User Story 3 (Phase 5) → Polish (Phase 6)
- User Story 1 is prerequisite for User Stories 2 and 3 to ensure contextual rendering baseline behavior is stable.
- User Story 2 depends on Foundational components and can begin once Phase 2 completes; User Story 3 depends on completion of User Story 2’s save workflows.

## Parallel Execution Opportunities

- After Phase 2, T008 and T009 can execute in parallel to validate search behavior and performance.
- Within User Story 2, T014 and T015 can proceed concurrently, as can T016 and T019 once contract tests exist.
- During User Story 3, T020 and T021 can run in parallel before implementation starts.
- Polish tasks T026 and T028 can be handled simultaneously while T027 runs.

## Implementation Strategy

1. Deliver MVP by completing Phases 1–3, enabling contextual columns in search results.
2. Iterate with Phase 4 to add analyst-controlled configuration while maintaining independent testability.
3. Extend to Phase 5 for persistence, reset handling, and audit trails, ensuring each increment ships safely.
4. Close with Phase 6 polish tasks to document changes, verify observability, and finalize performance evidence.
