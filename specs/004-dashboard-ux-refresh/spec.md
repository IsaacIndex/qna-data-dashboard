# Feature Specification: Q&A Dashboard UX Refresh

**Feature Branch**: `004-dashboard-ux-refresh`  
**Created**: 2025-12-01  
**Status**: Draft  
**Input**: User description: "Revamp the Q&A data dashboard to feel intuitive and welcoming for analysts of all skill levels. Prioritize a clean layout with clear hierarchy, plain-language labels, and helpful defaults. Surface unique columns and dataset-specific context clearly. Streamline the flow for selecting sheets, choosing columns for trial embeddings, and saving preferences— minimize clicks and avoid dead ends. Provide inline guidance where choices aren’t obvious, and ensure empty/error states are informative. Keep interactions fast, predictable, and consistent across pages. For example, - show the similarity score with colour scale - keep the selected items when switching tabs"

## Clarifications

### Session 2025-12-01

- Q: What accessibility and color guidance should the similarity scale follow? → A: Use a consistent color scale mapped to 0–100% similarity with clear legend/text so users can quickly scan rows; color-blind safety is not required.

### Session 2025-12-02

- Q: What observability signals are required to validate speed and state persistence? → A: Emit analytics events for search latency, tab switch latency, preference load/save success/failure, and column selection persistence outcomes.

### Session 2025-12-09

- Q: How should saved result columns/layout preferences be scoped? → A: Keep preferences device/browser-local only and ensure preference loading never blocks the search tab.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Readable search results with clear confidence (Priority: P1)

Analysts run semantic searches and immediately understand result relevance through plain-language labels, contextual columns, and a color-scaled similarity score that is also accessible via text/legend.

**Why this priority**: Fast interpretation of search results is core to the dashboard’s value; confidence cues and context reduce misreads and rework.

**Independent Test**: Can be fully tested by executing search queries against an existing dataset and verifying color-scale similarity scores, contextual columns, and guidance render consistently without configuring other features.

**Acceptance Scenarios**:

1. **Given** a dataset with saved contextual column preferences, **When** an analyst runs a search, **Then** each result shows the chosen contextual columns plus a similarity score rendered with a consistent color scale and readable text label.
2. **Given** no contextual columns are yet configured, **When** an analyst runs a search, **Then** inline guidance prompts them to pick contextual fields before results and no empty UI placeholders appear.

---

### User Story 2 - Guided column selection for trial embeddings (Priority: P2)

Analysts select sheets and columns for trial embeddings with deduplicated column options across sheets, concise guidance, and minimal clicks.

**Why this priority**: Accurate column selection is necessary for quality embeddings and downstream search; guidance prevents confusion from duplicated or missing headers.

**Independent Test**: Can be fully tested by uploading multi-sheet files (with and without missing headers), selecting columns, switching tabs, and confirming selections persist and previews update without rework.

**Acceptance Scenarios**:

1. **Given** a multi-sheet upload with overlapping column names, **When** the analyst opens the column picker, **Then** unique columns are listed once with sheet context, unavailable headers are clearly flagged, and the analyst can select columns without duplicate effort.
2. **Given** an analyst has selected sheets and columns, **When** they switch tabs or steps and return, **Then** their selections remain intact unless they explicitly reset.

---

### User Story 3 - Saved preferences and consistent defaults (Priority: P3)

Analysts save and reuse preferred result layouts, column sets, and display defaults across sessions with clear reset options.

**Why this priority**: Persisted preferences reduce setup time and keep experiences consistent across pages for repeat users.

**Independent Test**: Can be fully tested by setting preferences in one session, restarting the app, and verifying the saved layout, column sets, and guidance appear without reconfiguration.

**Acceptance Scenarios**:

1. **Given** an analyst saves a column set and display defaults, **When** they return in a new session, **Then** the preferences auto-apply across relevant pages with an option to restore defaults.
2. **Given** an analyst wants to discard a saved configuration, **When** they select reset, **Then** defaults are restored and a confirmation message explains what changed.

---

### Edge Cases

- No datasets uploaded: pages show actionable guidance to ingest data and disable dependent controls until data exists.
- Missing or duplicate headers in uploads: column lists skip missing headers gracefully and clearly mark unavailable items without blocking the flow.
- Low or no similarity results: results list remains navigable with an informative empty state and suggestions to adjust queries or sources.
- Tab or page switches mid-selection: selections persist within the session unless explicitly reset; warn before destructive resets.
- Invalid file types or corrupt sheets: user sees clear error messaging and next steps without partial state left behind.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Session selections (uploads, sheet choices, column picks, filters, and tab-level choices) MUST persist across tab or page switches during a session, with an explicit reset control before clearing state.
- **FR-002**: Search results MUST display similarity scores with a consistent color scale mapped to 0–100% similarity, paired with a legend and text labels for quick scanning; the scale must be applied uniformly across pages.
- **FR-003**: Dataset-specific contextual columns MUST render alongside each result based on saved preferences, with inline guidance and safe defaults when no preference is set; unavailable columns are clearly indicated without breaking the view.
- **FR-004**: Column selection for trial embeddings MUST present deduplicated unique column names across sheets, flag missing or unusable headers, and allow selection with minimal clicks and keyboard support.
- **FR-005**: Empty and error states (no data, invalid files, low-signal searches, failed ingestion) MUST provide plain-language explanations and actionable next steps without leaving the UI in a blocked or ambiguous state.
- **FR-006**: User preferences for layouts, column sets, and display defaults MUST persist per device/browser (local storage) without blocking the search tab if unavailable, and be restorable to defaults with confirmation messaging.
- **FR-007**: Core interactions (search execution, tab switching, column selection updates) MUST complete with visible feedback in under 2 seconds for typical datasets (e.g., up to hundreds of thousands of rows), and status messaging must appear if longer.
- **FR-008**: Emit analytics events for search latency, tab switch latency, preference load/save success or failure, and column selection persistence outcomes to validate speed and state retention.

### Key Entities *(include if feature involves data)*

- **Dataset**: An uploaded file containing one or more sheets; attributes include display name, row count, and ingestion status.
- **Sheet**: A tab within a dataset containing rows and column headers; may include missing or duplicated headers.
- **Column**: A field available for selection; attributes include name, display label, availability state, and originating sheet.
- **Column Preference**: A saved set of contextual columns (order, labels, max count) per dataset used to render search results.
- **Search Result**: A matched row with similarity score, contextual column values, and dataset/sheet provenance.
- **Session State**: In-session selections (tabs, filters, column picks) that persist until reset or session end.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: First-time analysts can configure contextual columns and run a search with readable, color-coded similarity scores in under 3 minutes without assistance (usability test).
- **SC-002**: 95% of tab/page switches during a session retain current selections and preferences with no unintended resets across tested scenarios.
- **SC-003**: 90% of search executions on typical datasets return results with visible similarity score and contextual columns within 2 seconds, with clear status messaging on slower cases.
- **SC-004**: 90% of first-time analysts complete sheet and column selection for trial embeddings on the first attempt using inline guidance (usability test completion rate).
- **SC-005**: Support or feedback items related to confusing column/context display or lost selections decrease by at least 40% in the release period compared to the prior baseline.
