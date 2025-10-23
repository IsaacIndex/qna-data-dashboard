# Feature Specification: Search Result Column Selections

**Feature Branch**: `003-show-search-columns`  
**Created**: 2025-10-23  
**Status**: Draft  
**Input**: User description: "when using the search function, the results should also show additional columns (based on selection) to tell more information about the matching rows"

## Clarifications

### Session 2025-10-23

- Q: How should column selections behave when search results span multiple datasets? → A: Apply each dataset's saved column preference to its results.

## User Scenarios & Testing *(mandatory)*

> Constitution Alignment: For each story, describe the automated checks that prove code quality, testing coverage, UX consistency, and performance expectations before implementation begins.

### User Story 1 - Surface Contextual Columns in Search (Priority: P1)

A data analyst runs a search across imported datasets and immediately sees each matching row with the relevant contextual columns they selected, so they can understand why the row matched without opening the source file.

**Why this priority**: Without contextual columns, analysts must leave the search view to interpret matches, slowing decision-making and reducing trust in search relevance.

**Independent Test**: Can be fully tested by executing representative searches after configuring column visibility and verifying the results list displays the selected fields for every returned row.

**Acceptance Scenarios**:

1. **Given** at least one dataset has been processed and columns flagged as available for display, **When** the analyst runs a search, **Then** the results list shows each match with baseline metadata (dataset name, column, row identifier) plus all currently selected contextual columns.
2. **Given** selected contextual columns contain null or empty values for some matches, **When** those rows appear in search results, **Then** the interface presents a standardized placeholder so analysts can distinguish missing data from rendering errors.

---

### User Story 2 - Configure Search Result Columns (Priority: P2)

An analyst customizes which supplemental columns appear alongside search matches, previewing available fields from multiple datasets and saving the configuration without needing developer support.

**Why this priority**: Allowing analysts to tailor the context shown eliminates repeated export requests and improves alignment with ongoing investigations.

**Independent Test**: Can be fully tested by selecting and deselecting columns in the configuration panel, persisting the choice, and confirming subsequent searches reflect the updated selection.

**Acceptance Scenarios**:

1. **Given** the analyst opens the column configuration panel, **When** they select new fields and save, **Then** subsequent searches display only the chosen set in the order defined.

---

### User Story 3 - Persist Column Preferences (Priority: P3)

A returning analyst signs back in and finds their search column configuration intact for the datasets they work with most often, so follow-up investigations resume without reconfiguration.

**Why this priority**: Persisted preferences reduce repetitive setup work and encourage consistent analysis across team members sharing devices or schedules.

**Independent Test**: Can be fully tested by setting a column configuration, signing out (or clearing session), returning within the retention period, and verifying the previous selections remain active or can be restored with a single action.

**Acceptance Scenarios**:

1. **Given** the analyst saved a column configuration on a prior session, **When** they return before the preference retention period expires, **Then** the previously selected columns load automatically for the same datasets.
2. **Given** the analyst wants to reset to the default column view, **When** they invoke the reset control, **Then** the system restores baseline metadata columns and clears any stored custom selections.

---

### Edge Cases

- Search executes with no additional columns selected: fallback to baseline metadata without errors or empty visual gaps.
- Analyst selects columns that are unavailable for some datasets: UI indicates per-result when a column is unsupported rather than failing the entire result rendering.
- Analyst chooses a large number of columns: result list maintains horizontal readability through responsive layout or horizontal scrolling while keeping performance within agreed budgets.
- Datasets updated after preference saved: system reconciles renamed or removed columns gracefully, prompting the analyst to review selections.
- Column configuration stored for one user is accessed by another role: access control prevents cross-user leakage of personalized settings unless explicitly shared.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Search results MUST display baseline metadata (dataset name, column, row identifier) plus all user-selected contextual columns for every returned record.
- **FR-009**: When a search returns rows from multiple datasets, each row MUST render the supplemental columns defined by that dataset’s saved preference without constraining other datasets to the same column set.
- **FR-002**: Analysts MUST be able to select up to 10 additional display columns per dataset from the metadata catalog and define their order without developer intervention.
- **FR-003**: Column selections MUST persist per user and per dataset for at least 30 days of inactivity, with controls to restore defaults instantly.
- **FR-004**: When a selected column lacks data for a specific result, the interface MUST render a consistent placeholder label and log the occurrence for observability.
- **FR-005**: The system MUST reconcile outdated selections by notifying the analyst when columns are renamed or removed and prompting for an updated choice before rendering results.
- **FR-006**: Rendering search results with up to 10 supplemental columns MUST complete within 1 second for datasets containing up to 50k rows on supported hardware, matching existing search performance expectations.
- **FR-007**: Audit logging MUST capture column selection changes (user, dataset, timestamp, selected fields) to support governance reviews.
- **FR-008**: The configuration UI MUST honor accessibility requirements (keyboard navigation, screen reader labels) so analysts using assistive technologies can manage column visibility.

### Key Entities *(include if feature involves data)*

- **Search Result Row**: Represents an individual match returned by the search engine, including baseline metadata, selected contextual column values, and flags for missing or unsupported fields.
- **Column Preference**: Captures the ordered list of additional columns an analyst has chosen for a given dataset scope, along with timestamps and provenance for observability.
- **Displayable Column Catalog**: Describes the set of columns available for selection per dataset, including human-friendly labels, data type, and availability status (active, deprecated, missing).

### Assumptions

- Analysts authenticate through existing mechanisms that allow per-user preferences to be stored securely.
- Each dataset has at least three baseline metadata fields (dataset name, column, row identifier) available for display regardless of analyst selections.
- The ingestion pipeline continues to flag columns that are missing headers, ensuring the displayable catalog only lists valid fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of search result views render all selected columns within 1 second for datasets up to 50k rows on supported hardware.
- **SC-002**: 85% of surveyed analysts report they can confirm row relevance directly from the search results without opening the source data.
- **SC-003**: At least 90% of saved column preference sets remain valid (no missing columns) over a 30-day observation period.
- **SC-004**: Support requests for ad-hoc column additions to search exports decrease by 30% within one release after launch.
