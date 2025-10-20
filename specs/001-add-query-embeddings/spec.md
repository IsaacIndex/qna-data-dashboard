# Feature Specification: LLM Test Query Embedding Analysis

**Feature Branch**: `001-add-query-embeddings`  
**Created**: 2025-10-20  
**Status**: Draft  
**Input**: User description: "this is a project to store, process (convert to embeddings per column) and search csv files for natural queries test cases for LLM. it aims to help 1) search for similiar queries based on keywords 2) analyze how diverse the coverage of the test cases are based on how different and similar the test queries are"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest Test Query Dataset (Priority: P1)

QA lead uploads a CSV of natural language test queries, maps relevant columns, and kicks off embedding generation so the dataset becomes searchable.

**Why this priority**: Without successful ingestion and embeddings, downstream search and analysis cannot function, making this the foundation of the feature.

**Independent Test**: Upload a representative CSV, configure column mappings, and confirm the system completes ingestion and embedding generation with clear feedback to the user.

**Acceptance Scenarios**:

1. **Given** a CSV file with designated query columns, **When** the user uploads the file and selects columns to index, **Then** the system stores the dataset, confirms ingestion, and begins embedding generation.
2. **Given** an ingested dataset awaiting processing, **When** embedding generation completes, **Then** the user receives confirmation that the dataset is ready for search and analysis.

---

### User Story 2 - Discover Similar Test Queries (Priority: P2)

QA analyst searches the repository using natural language or keywords to surface similar existing test queries along with key metadata.

**Why this priority**: Fast discovery of overlapping or relevant test cases prevents duplication and accelerates test design efforts.

**Independent Test**: Execute representative search queries and verify that relevant test cases appear with similarity indicators and contextual filters.

**Acceptance Scenarios**:

1. **Given** an embedded dataset, **When** the user submits a natural-language search, **Then** the system returns a ranked list of matching queries with similarity scores, their originating dataset, and preview context.

---

### User Story 3 - Analyze Coverage Diversity (Priority: P3)

Product quality manager reviews similarity insights to understand redundancy and gaps across test suites.

**Why this priority**: Diversity analysis builds on search to provide business insight, supporting strategic decisions about test coverage.

**Independent Test**: Generate a coverage report for a dataset and verify the presence of diversity metrics, duplicate clusters, and actionable summaries.

**Acceptance Scenarios**:

1. **Given** processed datasets with embeddings, **When** the user opens the coverage report, **Then** the system displays similarity distribution, duplicate clusters, and recommendations for balancing coverage.

---

### Edge Cases

- Large CSV uploads exceeding the supported row limit must surface a clear error and suggest remediation steps (e.g., splitting the file).
- Rows containing empty or non-text values in indexed columns must be skipped with a warning while preserving the rest of the dataset.
- Re-ingesting an updated CSV with the same identifier must allow users to confirm whether to replace or version the dataset without losing prior analytics.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow authorized users to upload CSV datasets, map columns containing natural-language queries, and confirm ingestion settings prior to processing.
- **FR-002**: System MUST generate and store embeddings for every selected column in each row upon ingestion and flag any rows that cannot be embedded.
- **FR-003**: System MUST provide visibility into ingestion and embedding progress, including completion status and error details.
- **FR-004**: System MUST allow users to trigger reprocessing of an existing dataset to regenerate embeddings after data changes.
- **FR-005**: System MUST offer a search interface that accepts natural-language phrases or keywords and queries embedded datasets.
- **FR-006**: System MUST return search results ordered by similarity relevance, including similarity scores, dataset identifiers, and key column previews.
- **FR-007**: System MUST allow users to filter search results by dataset, column, tag, and time of ingestion to narrow context.
- **FR-008**: System MUST generate coverage insights that summarize similarity distributions, highlight duplicate clusters, and call out underrepresented query areas.
- **FR-009**: System MUST allow users to export or download coverage reports for offline review and collaboration.

### Key Entities *(include if feature involves data)*

- **Dataset**: Represents an uploaded CSV file; includes metadata such as owner, upload timestamp, column mappings, row count, and processing status.
- **QueryRecord**: Represents a single row from a dataset; includes the original query text, additional column values, tags, and linkage to embeddings.
- **EmbeddingVector**: Represents the vectorized representation of a query for a specific column; includes embedding values, model version, and quality flags.
- **CoverageInsight**: Represents aggregated analytics derived from embeddings; includes similarity distribution metrics, duplicate clusters, and recommended follow-ups.

## Assumptions

- Primary users are QA leads, test engineers, and product quality managers responsible for maintaining LLM test suites.
- Initial release targets datasets up to 50,000 rows and 10 indexed columns per dataset; larger volumes require planned scaling.
- The organization has access to an embedding generation service that can process the anticipated data volume within agreed SLAs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of CSV uploads up to 50,000 rows complete ingestion and embedding generation within 10 minutes of submission.
- **SC-002**: 95% of search queries return a ranked result set with similarity scores in under 2 seconds.
- **SC-003**: In pilot feedback, 90% of users rate the relevance of the top five search results as "useful" or better.
- **SC-004**: Coverage reports identify duplicate clusters accounting for at least 95% of redundant queries detected during manual review within one week of deployment.
