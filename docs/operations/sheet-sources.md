# Sheet Sources Governance

## Purpose

Define operational guidelines for managing hidden sheets, refresh approvals, and catalog hygiene introduced with sheet-level data sources.

## Hidden Sheet Approvals

- Hidden and protected tabs remain excluded by default during ingestion.
- Analysts must opt in hidden sheets from the ingestion UI, acknowledge the audit notice, and state a business justification.
- Every opt-in is persisted via `bundle_audits.hidden_sheets_enabled`; review this field before granting additional access.
- Revoke access by setting the sheet status to `inactive` using `PATCH /api/sheet-sources/{sheetId}` or through the Streamlit catalog view.

## Refresh Workflow

1. Upload the updated workbook to the bundle directory (`data/bundles/{bundleId}`) or provide the new path during refresh.
2. Trigger `POST /api/source-bundles/{bundleId}/refresh` with the list of hidden sheets that should remain visible.
3. Monitor the response `sheetSummary` for created, updated, and deactivated sheets.
4. Resolve inactive sheets before dashboards execute by reactivating the sheet via the PATCH endpoint once the data is validated.

## Catalog Hygiene

- Streamlit surfaces status badges for each sheet; on-call teams should scan for inactive or deprecated entries weekly.
- Query Builder previews include warnings when referencing inactive sheets, enabling analysts to remediate stale references.
- Use `docs/performance/002-sheet-sources.md` to coordinate performance triage with ingestion owners when refreshes fall outside the agreed thresholds.
