# Feature Specification: Local Query Coverage Analytics

**Feature Branch**: `001-add-query-analytics`  
**Created**: 2025-10-21  
**Status**: Draft  
**Input**: User description: "this is a project to store, process (convert to embeddings per column) and search csv files for natural queries test cases for LLM. it aims to help 1) search for similiar queries based on keywords 2) analyze how diverse the coverage of the test cases are based on how different and similar the test queries are. It should run purely in local. based on this, it should have 1) data input (excels,csv) 2) search function that is near instant (to search for similar queries across excels or csvs, may specify to only search for specific columns per excel) 3) charts dashboard to show the coverage of the queries"

## User Scenarios & Testing *(mandatory)*

> Constitution Alignment: For each story, describe the automated checks that prove code quality, testing coverage, UX consistency, and performance expectations before implementation begins.

### User Story 1 - Curate Local Test Corpus (Priority: P1)

A QA lead loads multiple CSV/Excel files containing natural language test queries, selects the relevant text columns, and kicks off embedding so the dataset becomes searchable offline.

**Why this priority**: Without curated and embedded data, the rest of the experience cannot deliver value; this establishes the foundation for search and analytics.

**Independent Test**: Can be fully tested by importing representative files, confirming column selection metadata is saved, and verifying embeddings and indexes are generated without external services.

**Acceptance Scenarios**:

1. **Given** the user provides a valid CSV or Excel file under the supported size limit, **When** they select one or more text columns and start processing, **Then** the system confirms ingestion, computes embeddings for each selected column, and shows the dataset as ready for search.
2. **Given** a file that uses a different delimiter or sheet name, **When** the user maps it during import, **Then** the system respects the mapping and embeds only the chosen content while skipping non-text columns.

---

### User Story 2 - Discover Similar Queries (Priority: P1)

A tester enters a natural-language prompt and instantly finds semantically similar queries across all imported datasets, with options to narrow by dataset or column.

**Why this priority**: Rapid semantic search is the primary value proposition, enabling teams to reuse and refine test coverage efficiently.

**Independent Test**: Can be fully tested by issuing queries that should match known records, validating ranked results, and confirming filter controls adjust the result set without re-importing data.

**Acceptance Scenarios**:

1. **Given** at least one processed dataset, **When** the user searches for a keyword-free natural language query, **Then** the system returns the top relevant matches with similarity scores in under one second.
2. **Given** multiple datasets are indexed, **When** the user applies a dataset or column filter, **Then** the results update immediately to reflect only the selected scope.

---

### User Story 3 - Analyze Coverage Diversity (Priority: P2)

A product quality manager views charts that highlight clusters of similar queries, gaps in topic coverage, and overlap between datasets to decide where new test cases are required.

**Why this priority**: Visual insights create actionable decisions about redundancy and gaps, extending the tool’s value beyond search into planning and reporting.

**Independent Test**: Can be fully tested by loading processed datasets, rendering coverage dashboards, and confirming users can interpret diversity metrics without needing to run searches.

**Acceptance Scenarios**:

1. **Given** processed datasets with embeddings, **When** the user opens the analytics dashboard, **Then** they see charts summarizing cluster diversity, frequency distributions, and overlap metrics for selected datasets.
2. **Given** the user filters to a subset of datasets or time ranges, **When** they refresh the dashboard, **Then** the visualizations recalculate and clearly indicate redundant versus unique query groups.

---

### Edge Cases

- How does the system handle files that exceed the documented maximum row or file-size limit?
- What happens when selected columns contain non-text data or null values?
- How are duplicate queries across different files surfaced during search and analytics?
- How does the search respond when no results meet the similarity threshold?
- What feedback is shown if embedding computation is interrupted (e.g., machine sleep, process kill)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to import CSV or Excel files from local storage, preview columns, and select which text fields to embed before processing.
- **FR-002**: The system MUST compute and store embeddings locally for each selected column, track processing status, and prevent search until processing completes successfully.
- **FR-003**: Searches MUST accept natural-language input, return at least the top 20 matches ranked by semantic similarity, and display associated metadata (file name, column, row identifier).
- **FR-004**: Users MUST be able to filter search results by dataset, column, and minimum similarity score without re-running embedding.
- **FR-005**: Search response time MUST remain under one second for indexes containing up to 100k rows across all datasets on a typical modern laptop (quad-core CPU, 16 GB RAM).
- **FR-006**: The analytics dashboard MUST visualize query clusters, similarity distributions, and redundancy indicators, with controls to adjust dataset scope and similarity thresholds.
- **FR-007**: All processing, storage, and analytics MUST execute without requiring network connectivity or transmitting data outside the user’s machine.
- **FR-008**: The system MUST provide audit logs or reports summarizing ingestion actions, failed records, and last refresh time to support troubleshooting.

### Key Entities *(include if feature involves data)*

- **Data File**: Represents an imported CSV or Excel source, including metadata such as file path, original column names, row counts, and processing status.
- **Query Record**: Represents a single row from a selected column, storing the original text, source identifiers (file, column, row), and any analyst-provided tags.
- **Embedding Vector**: Represents the numerical embedding generated for a query record, linked to the specific column configuration and version to support reprocessing.
- **Similarity Cluster**: Represents a grouped collection of query records deemed semantically related, including cluster metrics (size, centroid similarity, diversity score).

### Assumptions

- Users operate on machines with sufficient local resources to process up to 100k text records within minutes.
- Source files are UTF-8 encoded and free of personally identifiable information, so no additional compliance workflows are required.
- Users have permission to read and analyze all provided datasets; role-based access control is out of scope for this release.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of ingestion jobs for datasets up to 100k rows complete within 5 minutes without manual intervention.
- **SC-002**: 95% of semantic searches return ranked results within 1 second for the first 20 matches on supported hardware.
- **SC-003**: At least 80% of pilot users report that the coverage dashboards help them identify redundant or missing query areas in under 10 minutes.
- **SC-004**: Teams reduce duplicated natural-language test cases by 30% within one release cycle after adopting the tool, measured via comparison of pre/post import reports.
