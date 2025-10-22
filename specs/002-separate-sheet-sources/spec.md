# Feature Specification: Sheet-Level Data Sources

**Feature Branch**: `002-separate-sheet-sources`  
**Created**: 2025-10-21  
**Status**: Draft  
**Input**: User description: "the dashboard should treat every sheet in a source excel/ csv as a separate source, so i can perform cross-excel/csv and cross-sheets query and analysis"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover sheet-based sources (Priority: P1)

Data analysts uploading an Excel workbook want each visible sheet to appear as its own dataset in the data catalog so they can build dashboards from specific tabular views.

**Why this priority**: Without sheet-level exposure, analysts must manually split workbooks before analysis, blocking adoption of multi-sheet files. This is the foundational capability for the feature request.

**Independent Test**: Upload a workbook containing multiple sheets in an automated integration test; confirm the data catalog registers matching sheet-level entries with correct metadata and sample data previews.

**Acceptance Scenarios**:

1. **Given** an uploaded workbook with three visible sheets, **When** ingestion completes, **Then** the catalog lists three new sheet-level sources named using the workbook title and sheet name.  
2. **Given** a sheet marked as hidden in the workbook, **When** the file is ingested with default settings, **Then** the sheet is not exposed as a data source and a notification explains how to include hidden tabs.

---

### User Story 2 - Combine sheets across files (Priority: P2)

Dashboard builders need to query across sheet sources from different workbooks or CSV files, joining them within the query builder to create combined metrics and visualisations.

**Why this priority**: Cross-sheet analysis is the business outcome requested; once sheet sources exist, the ability to mix them unlocks new insights and eliminates spreadsheet preprocessing.

**Independent Test**: Execute an automated regression scenario that pulls columns from three sheet sources (across at least two files), defines joins/filters, and verifies aggregate results match a fixture.

**Acceptance Scenarios**:

1. **Given** sources registered for "Sales.xlsx:North" and "Budget.xlsx:North", **When** the user creates a query joining the two sheet sources on region, **Then** the dashboard returns combined metrics without manual data export.  
2. **Given** a CSV file and an Excel sheet with compatible schemas, **When** the user includes both in a query, **Then** the system allows joins, aggregations, and filters across the mixed file types.

---

### User Story 3 - Maintain sheet-source integrity (Priority: P3)

Data stewards want sheet-level sources to stay in sync when workbook structures change so dashboards and saved queries do not break after refreshes.

**Why this priority**: Organizations routinely revise workbooks; automated lifecycle management avoids data outages and manual rework.

**Independent Test**: Run an automated update scenario that replaces a workbook with renamed tabs, triggers a rescan, and asserts existing sheet-source IDs persist or are deactivated with clear status messaging.

**Acceptance Scenarios**:

1. **Given** an existing sheet source referenced in dashboards, **When** the workbook is refreshed with additional tabs, **Then** new sheet sources are added without impacting the existing dashboards.  
2. **Given** a sheet that was deleted from the workbook, **When** the next refresh runs, **Then** the corresponding sheet source is marked inactive and dependent queries receive a clear warning before execution.

---

### Edge Cases

- Workbooks containing more than 50 sheets must ingest without UI timeouts and present a manageable selection experience.  
- Duplicate sheet names across different files must remain uniquely identifiable through namespacing (e.g., file name + sheet name).  
- Sheets with inconsistent headers or mixed data types must prompt users to confirm or edit column definitions before the source becomes queryable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingestion workflow must automatically register each visible sheet in an uploaded Excel workbook as an independent data source, applying file-name + sheet-name naming and storing sheet-level metadata (row count, last refreshed).  
- **FR-002**: Users must be able to opt in hidden/protected sheets during ingestion via an explicit selection step, with audit logging of who enabled each non-visible tab.  
- **FR-003**: Each sheet source must inherit the parent file’s ownership, refresh cadence, and permissions, while allowing sheet-specific descriptions and tags for discovery.  
- **FR-004**: The query builder must support joins, unions, and aggregations across any combination of sheet sources from Excel and CSV files, enforcing type compatibility checks with actionable guidance when schemas differ.  
- **FR-005**: Dashboards and saved queries referencing sheet sources must continue to resolve after file refreshes; removed sheets must transition to an inactive state with user-facing warnings instead of hard failures.  
- **FR-006**: Refresh operations must detect renamed sheets and map them to existing sources when column schemas match, otherwise treat them as new sources and flag impacted dashboards for review.  
- **FR-007**: System metrics must capture ingestion duration per sheet and cross-sheet query execution time, surfacing alerts when performance exceeds defined thresholds (see Success Criteria).

### Key Entities *(include if feature involves data)*

- **Source File**: Represents an uploaded Excel workbook or CSV file, tracking file metadata, owner, refresh cadence, and processing status.  
- **Sheet Source**: Logical dataset derived from a single sheet within a source file, including sheet name, parent file reference, column schema, row counts, visibility state, and activation status.  
- **Query Definition**: Configuration object describing how sheet sources are combined (joins, filters, aggregations) for dashboards and saved analyses, referencing sheet-source identifiers and result metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of uploaded workbooks with up to 50 visible sheets produce the same number of active sheet sources within 2 minutes of ingestion completion.  
- **SC-002**: 95% of cross-sheet queries that join up to three sheet sources and return ≤100,000 rows produce results in under 5 seconds from execution request.  
- **SC-003**: Post-launch user survey of analysts shows at least 80% satisfaction with sheet-level sourcing for multi-tab workbooks within the first release cycle.  
- **SC-004**: Support tickets related to combining Excel or CSV sheets decrease by 60% within one quarter of feature launch, indicating adoption and reduced workaround effort.

## Assumptions

- Hidden sheets remain excluded from ingestion unless a user explicitly selects them, to prevent unintentional exposure of sensitive data.  
- CSV files continue to register as single sheet sources named after the file because they contain only one logical tab.  
- Performance targets assume workbooks up to 200 MB and 100,000 rows per sheet; larger files require existing bulk-load escalation paths.  
- Feature builds on the existing Excel/CSV connector for authentication, upload, and basic parsing; no new source integrations are introduced.
