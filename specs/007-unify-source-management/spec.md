# Feature Specification: Unified Source Management

**Feature Branch**: `[007-unify-source-management]`  
**Created**: 2025-12-16  
**Status**: Draft  
**Input**: User description: "the expected behaviour is that the tab ingest providing an unified experience to manage the source, whether it is the embeddings or the tmp files, i see now the clear problem is 1. files in Source management section and Sheet Source Catalog section DO NOT match 2. some of the legacy files are not fitting correctly in this new UI 3. Re-embed sources section is allowing you to re-embed but the options are ids, which are hard to read the main point of the upcoming feature is to have a interactive way to manage the files, tmp files or embeddings. Able to group them and manage their status easily"

## Clarifications

### Session 2025-12-16

- Q: What should be the canonical unique identifier for sources across views? → A: Use an internal canonical source UUID for uniqueness; display label + dataset/type for users, remapping legacy files to the UUID.
- Q: How should large inventories be handled for performance? → A: Use server-backed infinite scroll with batched fetches and server-side filter/sort.
- Q: How should missing legacy sources be handled when absent from data/ingest_sources? → A: Auto-reinsert with audit logging; prompt only on conflicts or ambiguous mappings.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View unified source inventory (Priority: P1)

Analyst opens the ingest tab and sees a single, consistent list of all sources (tmp files, sheet catalog entries, embeddings) with aligned names and statuses instead of conflicting sections.

**Why this priority**: Resolves current confusion caused by mismatched lists, enabling analysts to trust the inventory before taking actions.

**Independent Test**: Load ingest tab with mixed source types and confirm the unified list matches the expected inventory count and statuses without discrepancies between sections.

**Acceptance Scenarios**:

1. **Given** sources exist across Source Management and Sheet Source Catalog, **When** the ingest tab loads, **Then** the unified list shows each source once with consistent status, type, and label across both contexts.
2. **Given** a source status changes (e.g., to ready or archived), **When** the list refreshes, **Then** the same status appears consistently for that source across Source Management, Sheet Source Catalog, and any detail view.

---

### User Story 2 - Re-embed sources with readable labels (Priority: P2)

Analyst initiates a re-embed action from the unified list and selects a source using a human-readable name (file/dataset/title) rather than raw IDs, with clear confirmation of the target.

**Why this priority**: Prevents mistakes during re-embedding by ensuring the user can identify the correct source quickly.

**Independent Test**: Trigger re-embed on a populated list and verify selection options and confirmations display human-friendly labels only, while the correct source is submitted for re-embedding.

**Acceptance Scenarios**:

1. **Given** multiple sources with similar IDs, **When** the analyst opens the re-embed selector, **Then** each option shows a human-readable label (e.g., file name, dataset, type) with no raw IDs displayed.
2. **Given** a source is selected for re-embedding, **When** the analyst confirms, **Then** the re-embed action starts for that exact source and the list reflects the updated job/status once available.

---

### User Story 3 - Manage legacy sources, grouping, and statuses (Priority: P3)

Analyst can see legacy sources alongside new ones, apply groupings, and update statuses (e.g., ready, archived, error) in bulk with clear feedback.

**Why this priority**: Ensures legacy and edge-case sources are not lost and can be curated consistently with new items.

**Independent Test**: Present a mixed set of legacy and new sources, perform bulk grouping/status updates, and verify all changes persist and display correctly across the ingest views.

**Acceptance Scenarios**:

1. **Given** legacy sources missing some attributes, **When** the analyst views them in the unified list, **Then** they appear with a clear legacy label and can be grouped or have status changed without errors.
2. **Given** multiple sources are selected, **When** the analyst applies a group tag or status change, **Then** each source reflects the update and any failures are reported per item.

---

### Edge Cases

- Legacy sources missing headers or metadata must still display and allow safe actions, with warnings instead of blocking the list.
- Duplicate file names across sheets or tmp files should be disambiguated by dataset/source context to avoid wrong selection.
- Sources with unsupported or partially ingested files should show an error/blocked state without appearing as ready.
- Bulk status/group updates with mixed permissions or partial failures must report per-item results and leave unaffected items unchanged.
- Large inventories should use server-backed infinite scroll with batched fetches and server-side filter/sort to avoid timeouts or mismatched counts between sections.
- Re-embed attempts on archived or errored sources should prompt for confirmation and show why the action may be limited.
- Legacy items without prior UUIDs must be remapped to a canonical UUID before actions; remap failures should surface as item-level errors without blocking other sources.
- Missing legacy sources discovered outside `data/ingest_sources` should be auto-reinserted with audit logging, prompting only when mappings are ambiguous or overwrite risk exists.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingest tab MUST present a single unified source list whose entries (name, type, status, dataset) match across Source Management, Sheet Source Catalog, and Re-embed contexts with no duplicates or omissions.
- **FR-002**: Each source entry MUST display a human-readable label (file name/dataset/title plus type) and a canonical status drawn from a consistent set (e.g., new, ingesting, ready, archived, error).
- **FR-003**: Legacy or partially described sources MUST be rendered with a clear legacy indicator and allowed actions; missing attributes should default to safe placeholders without blocking grouping or status changes.
- **FR-004**: The Re-embed sources selector MUST list options using human-readable labels only (no raw IDs) and confirm the chosen source before starting the re-embed action.
- **FR-005**: Users MUST be able to select multiple sources and apply group tags and status changes in a single bulk action, receiving per-item success or error feedback.
- **FR-006**: Status and grouping updates MUST persist and appear consistently across all ingest views within one refresh cycle of the action completing.
- **FR-007**: Users MUST be able to filter or sort the unified list by type, status, group, dataset, and last updated to quickly locate specific sources.
- **FR-008**: All sources, including legacy items, MUST be mapped to a canonical internal source UUID; UI displays human-readable label plus dataset/type while the UUID remains the authoritative key across Source Management, Sheet Source Catalog, and Re-embed contexts.
- **FR-009**: Large inventories MUST use server-backed infinite scroll with batched fetches; filter and sort operations execute server-side to maintain responsive load and refresh times.
- **FR-010**: When legacy sources are missing from `data/ingest_sources`, the system MUST auto-reinsert them with audit logging; prompt the user only when mappings are ambiguous or would overwrite existing records, and keep inventories in sync after resolution.

### Key Entities *(include if feature involves data)*

- **Source**: Any ingestible item (tmp file, sheet catalog entry, embedding) with attributes such as human-readable label, dataset, type, status, group tags, last updated time, and a canonical internal source UUID used as the unique key.
- **Legacy Source**: Source lacking full metadata or using prior formats; carries a legacy indicator, remaps to the canonical source UUID, and may have inferred defaults for missing attributes.
- **Embedding Job**: Operation that (re)embeds a source, tracking target source label, job status, and last run time.
- **Group**: User-applied tag used to cluster sources for filtering and bulk actions.
- **Status**: Canonical state for a source (e.g., new, ingesting, ready, archived, error) displayed consistently across views.

## Assumptions

- Existing authentication/authorization rules continue to govern which sources a user can view or act on.
- The canonical status vocabulary is shared across ingest views; any additional states reuse these labels or map to them visibly.
- Ingestion tolerates missing column headers by skipping absent columns while keeping sources visible for management actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Unified source list shows a 100% match in counts and statuses between Source Management, Sheet Source Catalog, and Re-embed views on refresh for the same environment.
- **SC-002**: At least 95% of sources present human-readable labels (no raw IDs) across listing and re-embed selection in validation samples.
- **SC-003**: Analysts can locate and initiate a re-embed for a target source within 3 steps and under 1 minute from landing on the ingest tab.
- **SC-004**: Bulk grouping/status updates apply successfully to at least 95% of selected sources with per-item feedback and zero silent failures.
