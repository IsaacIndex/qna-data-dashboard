# Tasks: Ingest Page Source Management

**Input**: Design documents from `/specs/006-ingest-source-management/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Define test tasks for every story. TDD is mandatory: write tests first and keep them in CI. Document any deferred test with risk, owner, and due date as a separate backlog task.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and baseline configuration for ingest work

- [X] T001 Create ingest storage base folder tracked for local runs in `data/ingest_sources/.gitkeep`
- [X] T002 Add ingest config defaults (max size 50 MB, allowed CSV/XLS/XLSX/Parquet, re-embed concurrency cap) in `app/utils/config.py`
- [X] T003 Add example environment variables for ingest settings and storage path in `.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models, storage helpers, and observability required before any user story

- [X] T004 Define ingest domain schemas (DocumentGroup, SourceFile with version_label, ColumnPreferenceSet, EmbeddingJob) in `app/services/ingest_models.py`
- [X] T005 [P] Implement ingest storage helper with versioned filenames, size/type validation, and header-tolerant column extraction in `app/services/ingest_storage.py`
- [X] T006 [P] Implement embedding job queue helper with per-group FIFO and 3 concurrent workers in `app/services/embedding_queue.py`
- [X] T007 Add audit logging utility for add/delete/re-embed actions with who/when/outcome metadata in `app/utils/audit.py`
- [X] T008 Add ingest test fixtures (sample CSV/XLSX/Parquet and corrupt file) in `tests/fixtures/ingest/`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Manage source files from ingest page (Priority: P1) - MVP

**Goal**: Analysts can add/delete sources in a selected group with statuses, metadata, auto-versioning, and validation feedback.

**Independent Test**: Upload and delete flows succeed with statuses/columns shown, validation errors surfaced, and audit logs recorded without affecting other groups.

### Tests for User Story 1 (write first)

- [X] T009 [P] [US1] Add contract tests for list/upload/delete endpoints in `tests/contract/test_ingest_sources.py`
- [X] T010 [P] [US1] Add integration test for ingest page add/delete flow with status updates in `tests/integration/test_ingest_page_sources.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement list/upload endpoints with versioned filenames, size/type checks, and column extraction in `app/api/ingest_sources.py`
- [X] T012 [P] [US1] Implement delete endpoint with embed-in-progress guard and audit hook in `app/api/ingest_sources.py`
- [X] T013 [P] [US1] Extend ingest storage helper for extracted unique columns and missing-header skips in `app/services/ingest_storage.py`
- [X] T014 [US1] Build ingest page UI for source list, upload (multi-file), validation errors, and delete confirmations in `app/pages/1_ingest.py`
- [X] T015 [US1] Add audit logging calls for add/delete events in `app/pages/1_ingest.py`
- [X] T016 [US1] Add unit tests for storage helper versioning, size/type limits, and header skipping in `tests/unit/test_ingest_storage.py`

**Checkpoint**: User Story 1 independently testable (upload/delete with statuses and audit)

---

## Phase 4: User Story 2 - Re-embed sources with updated context (Priority: P2)

**Goal**: Analysts trigger single or batch re-embeds with per-source status tracking, retries, and preserved prior embeddings until success.

**Independent Test**: Re-embed requests queue with 3-concurrent cap, expose per-source states, and allow retry on failure without breaking other ingest actions.

### Tests for User Story 2 (write first)

- [X] T017 [P] [US2] Add contract tests for re-embed queue and job status endpoints in `tests/contract/test_reembed.py`
- [X] T018 [P] [US2] Add integration test for batch re-embed flow with mixed success/failure states in `tests/integration/test_reembed_flow.py`

### Implementation for User Story 2

- [X] T019 [US2] Implement re-embed enqueue endpoint with batch source_ids and job ids response in `app/api/ingest_sources.py`
- [X] T020 [P] [US2] Implement embedding job status endpoint exposing queued/processing/completed/failed/cancelled in `app/api/ingest_sources.py`
- [X] T021 [US2] Enhance embedding queue helper for retries, queue position, and preserved prior embeddings until success in `app/services/embedding_queue.py`
- [X] T022 [US2] Update ingest page UI to trigger single/batch re-embed, show per-source job status, and retry failed jobs in `app/pages/1_ingest.py`
- [X] T023 [US2] Add unit tests for queue concurrency cap, FIFO ordering, and retry logic in `tests/unit/test_embedding_queue.py`

**Checkpoint**: User Story 2 independently testable (re-embed with tracked statuses and retries)

---

## Phase 5: User Story 3 - Switch between document groups (Priority: P3)

**Goal**: Analysts switch groups and see group-specific sources and saved column/context preferences restored quickly with empty-state guidance.

**Independent Test**: Switching groups refreshes lists/preferences within budget, persists selections per group, and handles empty groups gracefully.

### Tests for User Story 3 (write first)

- [X] T024 [P] [US3] Add integration test for group switching persistence and performance budget (<3s) in `tests/integration/test_group_switch.py`
- [X] T025 [P] [US3] Add integration test for empty-group guidance state in `tests/integration/test_group_empty_state.py`

### Implementation for User Story 3

- [X] T026 [US3] Persist last-selected group and restore column/context preferences via session state in `app/pages/1_ingest.py`
- [X] T027 [P] [US3] Implement save/load preferences endpoint for a group in `app/api/group_preferences.py`
- [X] T028 [P] [US3] Persist preference sets per group (selected columns + contextual fields) in `app/services/ingest_storage.py`
- [X] T029 [US3] Add unit tests for preference persistence and restore behavior in `tests/unit/test_preferences.py`

**Checkpoint**: User Story 3 independently testable (group switching with persisted preferences)

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, documentation, and performance

- [X] T030 Update quickstart with any new commands/flags and validation steps in `specs/006-ingest-source-management/quickstart.md`
- [X] T031 Add performance smoke covering upload readiness, delete propagation, re-embed duration, and group switch latency in `tests/performance/test_ingest_perf.py`
- [X] T032 [P] Refresh user-facing docs or walkthroughs reflecting ingest UI changes in `docs/`
- [X] T033 [P] Final accessibility and UX copy review notes for ingest page in `specs/006-ingest-source-management/plan.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (Phase 1): No dependencies.
- Foundational (Phase 2): Depends on Phase 1 completion; BLOCKS all user stories.
- User Stories (Phases 3-5): Start after Phase 2; proceed in priority order (P1 → P2 → P3) or in parallel once foundation is ready.
- Polish: After all desired user stories are complete.

### User Story Dependencies
- User Story 1 (P1): Starts after Phase 2; independent of other stories.
- User Story 2 (P2): Starts after Phase 2; can run parallel with US1 implementation once shared helpers exist but should not block US1.
- User Story 3 (P3): Starts after Phase 2; reads preference storage from foundation and can proceed parallel to US2 once endpoints stable.

### Parallel Opportunities
- Tasks marked [P] within the same phase can run concurrently (different files, no ordering).
- Different user stories can proceed in parallel after Phase 2 if staffed separately.
- Contract and integration tests marked [P] can be authored in parallel before implementations.
- UI and API tasks can progress in parallel when they touch distinct files (e.g., `app/pages/ingest.py` vs `app/api/*.py`).

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Setup (Phase 1) and Foundational (Phase 2).
2. Finish User Story 1 tasks and validate via contract + integration + unit tests.
3. Demo upload/delete with statuses and audit; ensure performance budgets hold.

### Incremental Delivery
1. Deliver US1 (MVP), then US2 (re-embed), then US3 (group switching).
2. Validate each story independently with its test set before moving on.
3. Apply Polish tasks after all stories meet acceptance.

### Parallel Team Strategy
- After Phase 2, one track can own US1 UI/API, another owns US2 embedding queue/endpoints, and another owns US3 preferences and switching UI. Coordination via shared helpers and contracts.
