# Feature Specification: Ingest Page Source Management

**Feature Branch**: `[006-ingest-source-management]`  
**Created**: 2025-12-14  
**Status**: Draft  
**Input**: User description: "revamp the ingest page, it should be able to manage, add / delete source files, re-embed the source, as well as switch between groups of document"

## Clarifications

### Session 2025-12-14

- Q: How should duplicate filenames within a document group be handled? → A: Auto-version the new upload, keep existing file, and show both entries.

### Session 2025-12-16

- Q: Should ingest show uploaded sources and temp files separately or together? → A: One unified list with a type badge and filters covering both uploaded and temporary items.

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

### User Story 1 - Manage source files from ingest page (Priority: P1)

Analysts manage the list of source files directly on the ingest page, adding new files and safely deleting obsolete ones while seeing ingestion status and metadata.

**Why this priority**: Core value—without reliable add/delete the ingest page cannot manage document inputs or stay current.

**Independent Test**: End-to-end add/delete of a source file shows clear status changes, surfaces column extraction results, and updates the visible list without affecting other features.

**Acceptance Scenarios**:

1. **Given** the ingest page with a selected document group, **When** the analyst uploads one or more source files, **Then** each file appears with filename, size, added-by, added-on, ingestion status, and extracted unique columns (missing headers are skipped without blocking upload).
2. **Given** an existing source in the list, **When** the analyst requests deletion and confirms, **Then** the source is removed from the list and no longer contributes to downstream search/embedding jobs.
3. **Given** a source with validation issues (e.g., unsupported type or corrupt file), **When** upload completes, **Then** the analyst sees a failure state with a reason and guidance to retry or remove the item.

---

### User Story 2 - Re-embed sources with updated context (Priority: P2)

Analysts trigger re-embedding for one or many sources to refresh embeddings when columns or content change, tracking job progress and results.

**Why this priority**: Keeps search quality high by reflecting the latest column choices and source updates without manual back-end work.

**Independent Test**: Triggering re-embed on a selected source (and a batch) runs to completion with status updates, refreshes contextual columns, and leaves prior embeddings intact until success.

**Acceptance Scenarios**:

1. **Given** an existing source, **When** the analyst triggers re-embed, **Then** the job enters a queued/processing/completed state and the source reflects updated contextual columns on success.
2. **Given** a re-embed job that fails, **When** it completes, **Then** the analyst sees a failure state with a clear error reason and the option to retry without removing the source.
3. **Given** multiple sources selected for re-embed, **When** the batch is submitted, **Then** progress is tracked per source and completion states are visible without blocking other ingest actions.

---

### User Story 3 - Switch between document groups (Priority: P3)

Analysts switch between document groups/datasets within the ingest page to view and manage their specific sources and saved column/context preferences.

**Why this priority**: Enables managing multiple datasets without leaving the ingest workflow, aligning sources, preferences, and embeddings per group.

**Independent Test**: Changing the selected group swaps the source list, preferences, and actions within a few seconds, preserving saved settings and not affecting other groups.

**Acceptance Scenarios**:

1. **Given** multiple document groups exist, **When** the analyst switches groups, **Then** the ingest page refreshes to show only that group’s sources, statuses, and saved contextual column selections.
2. **Given** group-specific preferences, **When** the analyst returns to a previously selected group, **Then** prior column/context choices and last viewed state are restored without extra setup.
3. **Given** a group with no sources, **When** it is selected, **Then** the analyst sees an empty state with guidance to add sources and re-embed once content is present.

### Edge Cases

- Duplicate filenames across uploads within a group—new upload is auto-versioned (e.g., "name (2).xlsx") while keeping the prior file visible to avoid unintentional overwrite.
- Source files missing headers or with inconsistent sheets—column extraction should skip missing headers, surface only unique usable columns, and flag skipped sheets without blocking ingestion.
- Upload of unsupported or oversized files—reject gracefully with limits shown before upload and without crashing the ingest view.
- Deleting a source that is mid-embed—prevent deletion until job finishes or allow cancellation with confirmation that embeddings may be incomplete.
- Re-embed failures (network/interruption/content issues)—surface per-file errors and permit retry without losing prior embeddings.
- Switching groups during an ongoing upload or re-embed—operations continue in the background and states resume correctly when returning to that group.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Implementation MUST comply with repository coding standards, linting, and typing requirements with zero outstanding violations.
- **FR-002**: Each user story MUST define automated unit, integration, and regression tests with measurable coverage goals recorded in this spec; any temporary deferral requires documented risk, remediation owner, and target completion date.
- **FR-003**: User-facing flows MUST use approved UX patterns, component libraries, and meet accessibility criteria documented in project guidance.
- **FR-004**: Performance budgets (e.g., render latency, data refresh time) MUST be defined, instrumented, and reported prior to release.
- **FR-005**: Monitoring artifacts (dashboards, runbooks, alerts) MUST be updated when behaviour, tests, or performance budgets change.
- **FR-006**: Ingest page lists all sources (uploaded and temporary/ephemeral) for the selected document group with filename, size, added-by, added-on, ingestion/embedding status, type badge, and last updated time visible without requiring page reload; filters allow narrowing by type.
- **FR-007**: Adding sources supports single and multi-file uploads, validates file type/size before processing, and surfaces extraction results showing unique columns across all sheets while skipping missing headers per repository ingestion rules.
- **FR-008**: Deleting a source requires explicit confirmation, is blocked while an embed job is running (or allows cancel with warning), and removes the source from ingestion lists and downstream search/index usage once confirmed.
- **FR-009**: Re-embedding can be triggered per source and in batch; each job tracks queued/processing/completed/failed states, keeps prior embeddings active until success, and records failure reasons with retry options.
- **FR-010**: Document group switching control is available on the ingest page, persists the last selected group per user session, and refreshes lists, statuses, and preferences for that group within defined performance budgets.
- **FR-011**: Column and contextual preference selections are saved per dataset/group, pre-populate re-embed and ingestion actions, and are recoverable on return visits without manual re-selection.
- **FR-012**: All user actions (add/delete/re-embed) expose audit-friendly metadata (who, when, what action, outcome) visible in activity views/logs suitable for support and QA review.

### Key Entities *(include if feature involves data)*

- **Document Group**: A named collection of sources and their saved contextual column preferences; defines the scope for ingest actions and embeddings.
- **Source File**: An uploaded file associated with a document group containing raw content and extracted columns; holds metadata (owner, timestamps, status).
- **Column Preference Set**: The user-defined selection of unique columns and contextual fields per document group used for ingestion and embedding.
- **Embedding Job**: A processing task that generates or refreshes embeddings for one or more sources; tracks status, timing, and outcome for audit and retries.

## Assumptions & Dependencies

- Existing authentication/authorization already limits ingest actions to permitted analysts; no new roles are introduced here.
- Ingestion and embedding infrastructure (storage, processing workers, search index) remains available and scales to typical dataset sizes defined in current SLAs.
- Column extraction uses the established tolerant behavior: missing headers are skipped, and only unique columns across sheets are surfaced for selection.
- Search/index update pathways already support swapping embeddings and removing sources without downtime; this feature orchestrates those capabilities through the ingest page.
- Document groups are pre-created or managed elsewhere; this feature consumes existing groups and does not create new group definitions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of source uploads reach a visible ingestion-ready state with extracted columns within 2 minutes for standard file sizes.
- **SC-002**: 95% of deletion requests remove the source from the ingest list and downstream search/index views within 1 minute of confirmation.
- **SC-003**: 95% of re-embed jobs complete with refreshed contextual columns within 5 minutes for typical datasets; failed jobs expose actionable error reasons 100% of the time.
- **SC-004**: Switching document groups updates visible sources and preferences in under 3 seconds for 95% of interactions.
- **SC-005**: Post-release survey/support signals show at least 90% of analysts can manage sources (add/delete/re-embed) without requesting admin assistance, and related support tickets decrease by 30% within one release cycle.
