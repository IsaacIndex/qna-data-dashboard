# Research Summary — Sheet-Level Data Sources

## Decision 1: Sheet discovery and registration

- **Decision**: Enumerate all visible worksheets during ingestion using `openpyxl` (Excel) or treat CSV files as a single pseudo-sheet, creating one `DataFile` entry per sheet with shared file hash metadata.
- **Rationale**: Leveraging the existing ingestion service keeps hashing, audit logging, and embedding triggers intact while allowing sheet-level ownership and refresh tracking.
- **Alternatives considered**:
  - Register a parent file record with child sheet references only in memory — rejected because lifecycle hooks (embeddings, audits, metrics) operate on `DataFile` entities and would require extensive refactoring.
  - Introduce a new sheet catalog table separate from `DataFile` — rejected to avoid duplicating metadata and complicating joins with embeddings.

## Decision 2: Hidden/protected sheet handling

- **Decision**: Default to excluding hidden/protected sheets but expose an explicit selection step in the ingestion UI to opt in, recording the actor and timestamp in audit logs.
- **Rationale**: Matches assumption in spec about safeguarding sensitive tabs while providing a governed path to include them with traceability.
- **Alternatives considered**:
  - Always ingest hidden sheets — rejected due to privacy risk and unexpected data exposure.
  - Require workbook preprocessing outside the app — rejected because it contradicts the primary value proposition (avoiding manual splitting).

## Decision 3: Naming and identity stability

- **Decision**: Namespace sheet sources as `{workbook_display_name}:{sheet_name}` while persisting stable IDs and storing sheet position + hash to aid rename detection.
- **Rationale**: Human-readable identifiers aid discovery, and auxiliary metadata allows detecting renames and reattachments during refresh without breaking downstream references.
- **Alternatives considered**:
  - Use numeric suffixes (`Sheet 1`) only — rejected because it obscures meaning and complicates cross-file differentiation.
  - Generate UUID-based names — rejected as it hinders analyst recognition and usability in the query builder.

## Decision 4: Cross-sheet query execution

- **Decision**: Extend the query builder service to treat each sheet-backed `DataFile` as a source table in the in-memory query engine, enforcing schema compatibility checks before execution.
- **Rationale**: Reusing the current analytical pipeline avoids standing up new storage engines while fulfilling the requirement for cross-file joins.
- **Alternatives considered**:
  - Materialize sheets into a centralized warehouse — rejected due to increased complexity, infrastructure overhead, and conflict with local/offline usage.
  - Restrict joins to shared schema templates only — rejected because it would limit analyst flexibility compared to the stated goal.

## Decision 5: Refresh and lifecycle management

- **Decision**: During file refresh, compare sheet hashes and column schemas to decide whether to reuse existing sheet source IDs, mark them inactive, or create new ones; notify dashboards of inactive sources before execution.
- **Rationale**: Maintains stability for unchanged sheets while gracefully handling deletions or major schema shifts, aligning with spec requirements for dashboard continuity.
- **Alternatives considered**:
  - Forcefully recreate all sheet sources on each refresh — rejected because it would break saved queries and dashboards.
  - Block refresh when mismatches occur — rejected since analysts need the ability to evolve workbooks without halting ingestion.
