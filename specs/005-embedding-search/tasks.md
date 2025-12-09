# Tasks: Embeddings-based Search Upgrade

**Input**: Design documents from `/specs/005-embedding-search/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include targeted tests for each story to validate dual-mode search, pagination, contextual columns, and fallback behaviour. Avoid creating new test case datasets per user request; reuse existing fixtures.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Ensure environment, tooling, and dependencies are ready for dual-mode search work.

- [ ] T001 Verify poetry environment and install dependencies (chromadb, sentence-transformers, nomic model availability) in `/Users/isaacibm/GitHub/qna-data-dashboard`
- [ ] T002 Document local env variables for data and Chroma persistence (`DATA_ROOT`, `CHROMA_PERSIST_DIR`) in `specs/005-embedding-search/quickstart.md` and `.env.example` if present
- [ ] T003 [P] Confirm lint/format/typecheck commands run clean on baseline (`poetry run ruff check`, `black --check`, `mypy`, `pytest`) from repo root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core plumbing required before story work begins.

- [ ] T004 Add configuration constants for Chroma persistence path and Nomic model ID in `app/utils/config.py` (or closest config module)
- [ ] T005 [P] Extend embedding service initialization to build Chroma client with persistence and model version tagging in `app/services/embeddings.py`
- [ ] T006 [P] Normalize SequenceMatcher and embedding similarity scales with shared legend helpers in `app/services/search.py`
- [ ] T007 Add request parameter parsing for per-mode limits (`limitPerMode`) and legacy params compatibility in `app/api/router.py`
- [ ] T008 Update contract documentation with new per-mode pagination fields in `specs/005-embedding-search/contracts/search.yaml`

**Checkpoint**: Foundation ready - dual-mode search can be implemented per story.

---

## Phase 3: User Story 1 - Find relevant test cases via semantic search (Priority: P1) - MVP

**Goal**: Dual-mode search returns semantic and lexical results with clear labels, scores, and top-10 pagination per mode.

**Independent Test**: Run `/search?q=<paraphrased>` and verify semantic and lexical sections each return up to 10 results with scores and labels; pagination/load-more works per mode.

### Tests for User Story 1

- [ ] T009 [P] [US1] Add contract test for `/search` dual-mode response shape and per-mode pagination in `tests/contract/test_search_api.py`
- [ ] T010 [P] [US1] Add integration test for semantic vs lexical ranking and top-10 caps in `tests/integration/test_search_dual_mode.py`

### Implementation for User Story 1

- [ ] T011 [P] [US1] Implement embedding-backed search path with Chroma + Nomic model query embedding in `app/services/search.py`
- [ ] T012 [P] [US1] Implement combined response assembling semantic_results and lexical_results with per-mode ranks/scores in `app/services/search.py`
- [ ] T013 [US1] Wire `/search` endpoint to return dual lists and per-mode pagination fields in `app/api/router.py`
- [ ] T014 [US1] Update similarity legend and response schema serialization to include mode tags in `app/services/search.py` and `app/api/router.py`
- [ ] T015 [US1] Update Streamlit search page to render labeled semantic and lexical sections with per-mode load-more in `app/pages/2_search.py`

**Checkpoint**: User Story 1 independently delivers dual-mode search with pagination and scores.

---

## Phase 4: User Story 2 - Preserve context with dataset-specific columns (Priority: P2)

**Goal**: Search results honor saved contextual column preferences per dataset across both modes.

**Independent Test**: Execute searches with saved column preferences and confirm both semantic and lexical sections show those contextual fields; missing columns are skipped gracefully.

### Tests for User Story 2

- [ ] T016 [P] [US2] Add integration test verifying contextual columns appear per dataset across modes in `tests/integration/test_search_context_columns.py`

### Implementation for User Story 2

- [ ] T017 [P] [US2] Ensure contextual metadata from preferences is attached to both semantic and lexical results in `app/services/search.py`
- [ ] T018 [US2] Render contextual columns for both modes and handle unavailable columns without errors in `app/pages/2_search.py`
- [ ] T019 [US2] Align API response metadata fields for contextual columns with existing defaults in `app/api/router.py`

**Checkpoint**: User Story 2 independently preserves and displays contextual columns across search modes.

---

## Phase 5: User Story 3 - Resilient fallback when embeddings are unavailable (Priority: P3)

**Goal**: Search remains available with lexical results and clear messaging when embeddings/index are unavailable; resumes semantic automatically when restored.

**Independent Test**: Simulate embedding/index outage; verify `/search` returns lexical results only with fallback message; on recovery, semantic results return without user action.

### Tests for User Story 3

- [ ] T020 [P] [US3] Add integration test covering semantic unavailability fallback and recovery in `tests/integration/test_search_fallback.py`

### Implementation for User Story 3

- [ ] T021 [P] [US3] Implement detection of embedding/index errors and surface fallback flag/message in `app/services/search.py`
- [ ] T022 [US3] Propagate fallback state in `/search` response payload in `app/api/router.py`
- [ ] T023 [US3] Display fallback banner/state on Streamlit search page while preserving filters and pagination in `app/pages/2_search.py`

**Checkpoint**: User Story 3 independently provides graceful fallback and recovery.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize documentation, performance, and quality gates.

- [ ] T024 [P] Update `specs/005-embedding-search/quickstart.md` with any new env flags or commands validated during implementation
- [ ] T025 Run full quality suite (ruff, black --check, mypy, pytest) and fix findings in repo root
- [ ] T026 [P] Add performance smoke benchmark for `/search` P95 <2s using representative dataset in `tests/performance/test_search_latency.py`
- [ ] T027 Update user-facing legend/help text for dual-mode search in `app/pages/2_search.py`
- [ ] T028 [P] Document Chroma persistence and refresh cadence in `docs/TECHNICAL_NOTES.md` and `README.md` references

---

## Dependencies & Execution Order

- Phase order: Setup → Foundational → US1 (P1) → US2 (P2) → US3 (P3) → Polish.
- User Story order by priority: US1 → US2 → US3. Stories can proceed in parallel after Foundational if capacity allows, but US2/US3 depend on dual-mode groundwork from US1 code paths.

## Parallel Execution Examples

- Setup: T002 and T003 can run in parallel after T001.
- Foundational: T005 and T006 can proceed in parallel after T004; T007 and T008 parallel after config is in place.
- US1: T009 and T010 in parallel; T011 and T012 in parallel before wiring tasks T013–T015.
- US2: T016 parallel with T017 once US1 plumbing is present.
- US3: T020 parallel with T021; UI/API wiring T022–T023 sequential.

## Implementation Strategy

- MVP: Complete Setup + Foundational + US1 to deliver dual-mode search with pagination and scores.
- Incremental: Layer US2 contextual columns, then US3 fallback handling; finish with polish/performance.
