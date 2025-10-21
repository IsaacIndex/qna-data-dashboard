# Tasks: Local Query Coverage Analytics

**Input**: Design documents from `/specs/001-add-query-analytics/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Each user story includes contract, integration, and performance checks aligned with Evidence-Driven Testing requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish tooling, dependencies, and repository layout required by the implementation plan.

- [X] T001 Configure Python 3.11 runtime and base dependencies (Streamlit, pandas, pyarrow, openpyxl, sentence-transformers, chromadb, plotly, pytest, mypy) in `pyproject.toml`
- [X] T002 Add linting/formatting/type-check configuration via `pyproject.toml` scripts and `.ruff.toml`
- [X] T003 [P] Create environment template documenting `DATA_ROOT`, `CHROMA_DB_DIR`, `SQLITE_URL`, and `SENTENCE_TRANSFORMER_MODEL` in `.env.example`
- [X] T004 [P] Document local storage policy (raw files + persisted metadata, no processed copies) in `data/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST exist before user story implementation.

**WARNING: CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Define SQLite schema for DataFile, QueryRecord, EmbeddingVector, SimilarityCluster, ClusterMembership, IngestionAudit, and PerformanceMetric in `app/db/schema.py`
- [X] T006 Implement database session and repository helpers for persisted metadata in `app/db/metadata.py`
- [X] T007 Create persistent ChromaDB client factory with on-disk configuration in `app/services/chroma_client.py`
- [X] T008 [P] Provide Streamlit caching helpers wrapping long-lived resources in `app/utils/caching.py`
- [X] T009 [P] Implement structured logging and performance instrumentation utilities in `app/utils/logging.py`
- [X] T010 Establish shared test fixtures for temporary data roots, SQLite DB, and Chroma collections in `tests/conftest.py`
- [X] T011 Scaffold Streamlit entry point to register multipage layout and ensure data directories exist in `app/main.py`

**Checkpoint**: Foundation ready—user story implementation can now begin.

---

## Phase 3: User Story 1 - Curate Local Test Corpus (Priority: P1) – MVP

**Goal**: Enable CSV/Excel ingestion, column selection, embedding, and audit persistence for offline datasets.

**Independent Test**: Import representative files, confirm column mapping metadata persists, embeddings populate ChromaDB, and ingestion audit reflects status without network access.

### Tests for User Story 1 (write before implementation)

- [X] T012 [P] [US1] Author ingestion unit tests covering CSV/Excel variations and validation in `tests/unit/test_ingestion.py`
- [X] T013 [P] [US1] Add ingestion workflow integration test ensuring embeddings materialize before search in `tests/integration/test_ingest_workflow.py`
- [X] T014 [P] [US1] Create dataset import contract test for `/datasets` and `/datasets/import` in `tests/contract/test_datasets_api.py`
- [X] T015 [P] [US1] Establish ingestion performance benchmark validating <5 minute budget in `tests/performance/test_ingestion_bench.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement ingestion pipeline for DataFile and QueryRecord persistence in `app/services/ingestion.py`
- [X] T017 [US1] Implement embedding orchestration with SentenceTransformers batching in `app/services/embeddings.py`
- [X] T018 [US1] Extend metadata helpers with ingestion audit persistence and duplicate detection in `app/db/metadata.py`
- [X] T019 [US1] Expose dataset CRUD and import endpoints per OpenAPI contract in `app/api/router.py`
- [X] T020 [US1] Build Streamlit ingestion page with file upload, column selection, and job status UI in `app/pages/1_ingest.py`

**Checkpoint**: Ingestion pipeline functional and independently testable.

---

## Phase 4: User Story 2 - Discover Similar Queries (Priority: P1)

**Goal**: Deliver instant semantic search with dataset/column filters using persisted embeddings.

**Independent Test**: Run natural-language searches against known records, verify ranked results under 1 second, and confirm filter scope adjustments without re-ingestion.

### Tests for User Story 2 (write before implementation)

- [ ] T021 [P] [US2] Add `/search` contract coverage validating query params and responses in `tests/contract/test_search_api.py`
- [ ] T022 [P] [US2] Add semantic search integration test covering filters and similarity thresholds in `tests/integration/test_search_api.py`
- [ ] T023 [P] [US2] Record search performance benchmark enforcing <1 second latency in `tests/performance/test_search_latency.py`

### Implementation for User Story 2

- [ ] T024 [US2] Implement search service querying ChromaDB with metadata filters in `app/services/search.py`
- [ ] T025 [US2] Register `/search` endpoint and response serialization per OpenAPI contract in `app/api/router.py`
- [ ] T026 [US2] Build Streamlit search page with query input, filters, and results table in `app/pages/2_search.py`

**Checkpoint**: Semantic search available and independently testable.

---

## Phase 5: User Story 3 - Analyze Coverage Diversity (Priority: P2)

**Goal**: Provide analytics dashboard with clustering, redundancy metrics, and dataset overlap insights.

**Independent Test**: Render dashboards for clustered datasets, adjust filters/time ranges, and verify charts update with persisted labeling metadata.

### Tests for User Story 3 (write before implementation)

- [ ] T027 [P] [US3] Add analytics contract tests for `/analytics/clusters` and `/analytics/summary` in `tests/contract/test_analytics_api.py`
- [ ] T028 [P] [US3] Add analytics integration test validating clustering and diversity metrics in `tests/integration/test_analytics_dashboard.py`

### Implementation for User Story 3

- [ ] T029 [US3] Implement analytics service generating clusters, redundancy ratios, and summaries in `app/services/analytics.py`
- [ ] T030 [US3] Persist clustering metadata and performance metrics in `app/db/metadata.py`
- [ ] T031 [US3] Implement analytics endpoints per OpenAPI contract in `app/api/router.py`
- [ ] T032 [US3] Build Streamlit analytics dashboard with Plotly visualizations in `app/pages/3_analytics.py`

**Checkpoint**: Analytics dashboard functional and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, accessibility, and release readiness spanning all stories.

- [ ] T033 [P] Update quickstart with final commands, test workflows, and maintenance notes in `specs/001-add-query-analytics/quickstart.md`
- [ ] T034 Capture accessibility QA results and remediation checklist in `specs/001-add-query-analytics/checklists/accessibility.md`
- [ ] T035 Document performance benchmark baselines and instrumentation usage in `docs/performance/001-add-query-analytics.md`
- [ ] T036 Validate end-to-end workflow using documented steps and log outcomes in `specs/001-add-query-analytics/checklists/qa.md`

---

## Dependencies & Execution Order

- **Setup (Phase 1)** must precede all other work.
- **Foundational (Phase 2)** tasks depend on Setup and block all user stories; complete before starting Phase 3+.
- **User Story 1 (Phase 3)** depends on Foundational completion and delivers the MVP ingestion pipeline.
- **User Story 2 (Phase 4)** depends on Foundational completion and leverages ingestion outputs; can start after or alongside late-stage US1 tasks once shared modules are stable.
- **User Story 3 (Phase 5)** depends on US1 data availability; may run in parallel with US2 after ingestion flow is stable.
- **Polish (Phase 6)** depends on completion of desired user stories.

### User Story Dependency Graph
- US1 → enables US2 and US3
- US2 → independent of US3 (can progress in parallel once US1 data exists)
- US3 → requires US1 data; independent of US2 results

---

## Parallel Execution Examples

### User Story 1
- Tests: T012, T013, T014, T015 can run concurrently after shared fixtures (T010) exist.
- Implementation: T016 and T017 can progress in parallel, followed by T018 → T019 → T020.

### User Story 2
- Tests: T021, T022, T023 run in parallel once US1 artifacts exist.
- Implementation: T024 can proceed while T026 designs UI; merge into T025 once service contracts are stable.

### User Story 3
- Tests: T027 and T028 run together leveraging persisted metadata from US1.
- Implementation: T029 and T030 can develop side-by-side, with T031 and T032 layering API and UI afterwards.

---

## Implementation Strategy

### MVP First (User Story 1)
1. Complete Phases 1–2 to establish tooling and infrastructure.
2. Deliver Phase 3 (US1) including tests T012–T015 and implementation T016–T020.
3. Validate ingestion independently before expanding scope.

### Incremental Delivery
1. After MVP, complete Phase 4 (US2) to unlock semantic search and demonstrate end-to-end value.
2. Proceed to Phase 5 (US3) for analytics enhancements as a subsequent release.
3. Use Phase 6 for documentation, accessibility, and performance hardening prior to release.

### Parallel Team Strategy
1. Team collaborates on Phases 1–2.
2. Assign US1 core ingestion to one track; once stable, parallelize US2 and US3 using shared fixtures and services.
3. Reserve polish tasks for final integration and release-readiness sprint.

---
