# Feature Specification: Embeddings-based Search Upgrade

**Feature Branch**: `[005-embedding-search]`  
**Created**: 2025-12-09  
**Status**: Draft  
**Input**: User description: "enhance the current search function with embeddings and vector search, details in docs/TECHNICAL_NOTES.md"

## Clarifications

### Session 2025-12-09

- Q: Should users be able to search with SequenceMatcher and embeddings together or choose one? → A: Run both per query and present separate labeled sections/tabs with scores.
- Q: How many results should be shown per mode and how is pagination handled? → A: Show top 10 results per mode with independent pagination/load more.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

> Constitution Alignment: For each story, describe the automated checks that prove code quality, testing coverage, UX consistency, and performance expectations before implementation begins.

### User Story 1 - [Brief Title] (Priority: P1)
Find relevant test cases via semantic search

**Why this priority**: Analysts need reliable retrieval for paraphrased or production-style queries to keep regression coverage effective.

**Independent Test**: Run a paraphrased query against the dashboard search and verify semantic and lexical sections both return results with clear labels, scores, and top-10 pagination per mode.

**Acceptance Scenarios**:

1. **Given** a production-style query with different wording than stored tests, **When** the analyst searches, **Then** the top results include semantically similar test cases with visible relevance scores within the top 10 of the embeddings section.
2. **Given** a query that matches an existing test closely, **When** the analyst searches, **Then** the near-exact match appears in the lexical section and semantically close alternatives appear in the embeddings section, each within their top-10 lists.

---

### User Story 2 - [Brief Title] (Priority: P2)
Preserve context with dataset-specific columns

**Why this priority**: Analysts rely on contextual fields (e.g., intent, category, trial metadata) to interpret matches; preferences must persist across searches.

**Independent Test**: Execute searches with saved contextual column preferences and confirm results render those fields consistently for each dataset.

**Acceptance Scenarios**:

1. **Given** saved display preferences for contextual columns, **When** the analyst runs a semantic search, **Then** results include those columns per dataset without requiring re-selection.
2. **Given** a dataset lacking a preferred column, **When** the analyst searches, **Then** the UI omits the missing column gracefully while preserving other preferences.

---

### User Story 3 - [Brief Title] (Priority: P3)
Resilient fallback when embeddings are unavailable

**Why this priority**: Search must remain available during embedding outages or index rebuilds so analysts can keep working.

**Independent Test**: Simulate an unavailable embedding service/index and verify search still returns lexical results with clear messaging.

**Acceptance Scenarios**:

1. **Given** the embedding index cannot be reached, **When** the analyst searches, **Then** the system automatically falls back to string-based matching and informs the analyst of reduced relevance.
2. **Given** embeddings recover after an outage, **When** the next search occurs, **Then** semantic results resume without user intervention.

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases
- Empty or very short queries that should return a clear validation message instead of running the semantic search.
- Queries containing only stopwords or non-text characters that should not degrade the index.
- Datasets with new or updated test cases before embeddings are refreshed.
- Missing contextual columns for a dataset (already tolerated per ingestion updates) while still rendering other selected columns.
- Mixed-language or code-mixed queries where embeddings may be less effective and should still return best-effort results.
- Large result sets where only top-N are shown; ensure pagination or caps are consistent.
- Duplicate or near-duplicate test cases that should not crowd the top results.
- Fallback transition between semantic and lexical search without losing user filters or preferences.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements
- **FR-001**: Dashboard search MUST run both semantic (embeddings) and lexical (SequenceMatcher) retrieval per query and present separately labeled sections/tabs with scores for each mode.
- **FR-002**: When embedding services or indexes are unavailable, the system MUST fall back to existing string-based search and clearly message that results may be less relevant.
- **FR-003**: Search responses MUST include similarity indicators (e.g., score or badge) so analysts can gauge relevance at a glance.
- **FR-004**: Search results MUST honor dataset-specific contextual column preferences already saved by analysts and omit missing columns without errors.
- **FR-005**: Newly added or updated test cases MUST be represented in semantic search within a defined refresh window (same day) without requiring manual steps from analysts.
- **FR-006**: Search interactions MUST preserve existing filters (dataset, sheet source, trial selection) and deliver consistent pagination with a default top 10 results per mode and “load more” that paginates independently per mode.
- **FR-007**: The feature MUST maintain accessibility and usability parity with the current search UI, including keyboard navigation and readable status messaging for fallbacks.

### Key Entities *(include if feature involves data)*

- **Search Query**: Analyst-entered text and active filters/preferences used to retrieve matches.
- **Test Case**: Stored query with associated metadata (intent, category, notes, contextual columns) used for comparison and display.
- **Embedding Index Entry**: Vector representation of a test case linked to its metadata and freshness timestamp.
- **Search Result**: Ranked item combining a test case, similarity indicator, and contextual fields shown to the analyst.

## Assumptions

- Embedding generation is available within the organization without adding new user-facing authentication steps.
- Daily or more frequent embedding refresh is acceptable to keep new/updated test cases searchable.
- Existing search UI patterns, filters, and column preference storage remain in place and are extended, not replaced.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes
- **SC-001**: At least 90% of evaluated paraphrased production queries return a relevant test case within the top 5 results during acceptance testing.
- **SC-002**: 95% of search requests complete in under 2 seconds for current dataset sizes under normal load.
- **SC-003**: 100% of searches during simulated embedding outages still return lexical results with clear fallback messaging.
- **SC-004**: At least 80% of analysts in pilot sessions report improved ability to find related tests compared to the prior string-based search.
