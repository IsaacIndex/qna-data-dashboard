# Tasks: Unified Source Management

**Input**: Design documents from `/specs/007-unify-source-management/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included for every story per TDD guidance: write tests first and ensure they fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and baseline tooling

- [X] T001 Align repository structure with plan (app/, data/ingest_sources/, tests/) at /Users/isaacibm/GitHub/qna-data-dashboard
- [X] T002 Configure lint/format/type/test automation for new modules (pyproject.toml, CI) in /Users/isaacibm/GitHub/qna-data-dashboard
- [X] T003 [P] Ensure test fixtures location and sample source data under data/ingest_sources/ for local runs
- [X] T004 [P] Scaffold performance smoke test harness in tests/performance/test_ingest_perf.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story

- [X] T005 Implement Source and LegacySource models per data-model.md in app/models/source.py
- [X] T006 [P] Implement source repository for file/metadata/UUID access in app/services/source_repository.py
- [X] T007 [P] Add UUID mapping & legacy detection utilities in app/utils/source_uuid.py
- [X] T008 Implement audit logging helper for legacy reinsertion and bulk actions in app/services/audit_log.py
- [X] T009 [P] Scaffold shared Streamlit components/layout for ingest filters in app/ingest/components/base_filters.py
- [X] T010 Establish ingest API router base (list/reconcile/re-embed routes container) in app/api/routes/ingest.py
- [X] T011 [P] Add observability hooks (logging/metrics stubs) for ingest actions in app/utils/metrics.py

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - View unified source inventory (Priority: P1) - MVP

**Goal**: Unified list across Source Management/Sheet Catalog/Re-embed with consistent labels/statuses and infinite scroll

**Independent Test**: Load ingest tab with mixed source types and confirm unified list counts/statuses align across contexts with server-backed pagination

### Tests for User Story 1 (write first)

- [X] T012 [P] [US1] Contract test for GET /sources list with filter/sort/cursor in tests/contract/test_sources_list.py
- [X] T013 [P] [US1] Integration test for unified list rendering and status consistency in tests/integration/test_unified_source_list.py

### Implementation for User Story 1

- [X] T014 [P] [US1] Implement GET /sources with server-side filter/sort/cursor in app/api/routes/ingest.py
- [X] T015 [P] [US1] Implement source aggregation/service for unified inventory in app/services/source_service.py
- [X] T016 [US1] Build Streamlit unified list UI with infinite scroll and disambiguated labels in app/ingest/unified_list.py
- [X] T017 [US1] Implement status refresh/sync logic across contexts in app/ingest/status_sync.py
- [X] T018 [US1] Add mixed-source fixtures (tmp, sheet, embedding, legacy) for list tests in tests/fixtures/sources_mixed.py

**Checkpoint**: User Story 1 independently functional and testable

---

## Phase 4: User Story 2 - Re-embed sources with readable labels (Priority: P2)

**Goal**: Re-embed flow uses human-readable labels, maps to canonical UUID, and reflects job status

**Independent Test**: Trigger re-embed from unified list, select by label/dataset/type, and verify correct source is enqueued and status reflects

### Tests for User Story 2 (write first)

- [X] T019 [P] [US2] Contract test for POST /sources/reembed using UUID input in tests/contract/test_reembed.py
- [X] T020 [P] [US2] Integration test for re-embed selector showing human-readable options in tests/integration/test_reembed_selector.py

### Implementation for User Story 2

- [X] T021 [P] [US2] Implement POST /sources/reembed to enqueue jobs by UUID in app/api/routes/reembed.py
- [X] T022 [US2] Update Streamlit re-embed selector to show labels/dataset/type (no raw IDs) in app/ingest/reembed_panel.py
- [X] T023 [US2] Handle re-embed confirmation, job feedback, and status refresh in app/ingest/reembed_panel.py
- [X] T024 [US2] Update embedding service to accept UUID target and emit job status in app/embeddings/service.py

**Checkpoint**: User Story 2 independently functional and testable

---

## Phase 5: User Story 3 - Manage legacy sources, grouping, and statuses (Priority: P3)

**Goal**: Legacy sources visible and actionable; bulk grouping/status updates; auto-reinsert missing legacy files with audit/conflict prompts

**Independent Test**: Present mixed legacy/new sources, perform bulk grouping/status changes, run legacy reconcile to auto-reinsert missing items with conflict prompts, and verify consistency across views

### Tests for User Story 3 (write first)

- [X] T025 [P] [US3] Contract test for POST /sources/reconcile-legacy with conflict handling in tests/contract/test_legacy_reconcile.py
- [X] T026 [P] [US3] Integration test for bulk grouping/status updates and per-item feedback in tests/integration/test_bulk_grouping.py
- [X] T027 [P] [US3] Unit test for legacy UUID remap and auto-reinsert logic with audit in tests/unit/test_legacy_reinsert.py

### Implementation for User Story 3

- [X] T028 [US3] Implement POST /sources/reconcile-legacy auto-reinsert with audit/conflict prompts in app/api/routes/legacy.py
- [X] T029 [US3] Implement legacy reconcile service for missing files into data/ingest_sources/ in app/services/legacy_reconcile.py
- [X] T030 [US3] Implement bulk status/group update endpoint with per-item results in app/api/routes/ingest.py
- [X] T031 [US3] Implement Streamlit bulk actions UI (group/status, conflict prompts) in app/ingest/bulk_actions.py
- [X] T032 [US3] Extend filters/sorts for group/type/status/dataset in app/ingest/unified_list.py

**Checkpoint**: User Story 3 independently functional and testable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final refinements across stories

- [X] T033 Update quickstart and README with new flows and endpoints in /Users/isaacibm/GitHub/qna-data-dashboard/docs and specs/007-unify-source-management/quickstart.md
- [X] T034 [P] Finalize performance benchmarks and thresholds in tests/performance/test_ingest_perf.py
- [X] T035 [P] Accessibility review and fixes for Streamlit components (focus, labels, contrast) in app/ingest/
- [X] T036 Cross-story logging/metrics verification and audit log review in app/utils/metrics.py and app/services/audit_log.py

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (Phase 1) → Foundational (Phase 2) → User Stories (Phases 3–5) → Polish (Phase 6)

### User Story Dependencies
- US1 (P1) depends on Phase 2 completion; delivers MVP.
- US2 (P2) depends on Phase 2; can proceed in parallel with US1 after foundation but should verify UI reuse.
- US3 (P3) depends on Phase 2; may proceed in parallel after foundation; uses UUID mapping/logging from foundational tasks.

### Parallel Opportunities
- Marked [P] tasks across phases can be parallelized when file scopes do not collide.
- After Phase 2, US1/US2/US3 implementation tasks can run in parallel by different contributors.
- Test tasks marked [P] can be authored concurrently before implementation.

---

## Implementation Strategy

- MVP first: Complete Phases 1–3 (US1), validate independent tests, and demo unified list.
- Incremental delivery: Layer US2 then US3, each validated independently with their tests.
- Maintain TDD: Write contract/integration/unit tests before implementing endpoints/UI/services.
