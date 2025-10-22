# Quickstart — Sheet-Level Data Sources

## 1. Prepare the environment

1. Ensure Poetry dependencies are installed: `poetry install`.
2. Launch the local stack (Streamlit app + FastAPI backend):  
   ```bash
   poetry run qna-dashboard
   ```
3. Confirm access to the data storage directory defined in `.env` (default `data/`) so ingestion can persist bundle assets.

## 2. Upload a workbook and expose sheets

1. Navigate to the **Data Sources** page in the dashboard.
2. Click **Upload Workbook/CSV** and select your file.
3. Review detected sheets; by default, only visible tabs are pre-selected.
4. To include hidden/protected sheets, expand **Hidden Sheets**, check each sheet, and acknowledge the audit notice.
5. Choose column filters if you only need specific headers, then submit the upload.
6. Monitor the ingestion status toast (target <2 minutes for ≤50 sheets). Refresh the catalog list once ingestion completes.

## 3. Build a cross-sheet query

1. Open the **Query Builder** and click **New Query**.
2. Add sheet sources from the catalog search (look for names formatted as `Workbook:Sheet`).
3. Define joins by selecting matching columns; resolve any schema warnings shown in the compatibility panel.
4. Add filters and aggregations, then click **Preview** — expect results within 5 seconds for ≤100k rows.
5. Save the query and attach it to an existing dashboard or create a new visualisation.

## 4. Refresh and maintain sheet sources

1. On the bundle details page, click **Refresh Bundle** when the underlying workbook changes.
2. Review the pre-refresh summary showing new, renamed, or removed sheets; adjust hidden sheet approvals if necessary.
3. After the refresh, check the **Impacted Dashboards** list for any inactive sheets and follow prompts to resolve them.

## 5. Monitor performance and quality

1. Open **Admin → Metrics** to view ingestion duration and query latency charts for each sheet source.
2. Investigate alerts triggered when ingestion exceeds 120s or query previews exceed 5s at P95.
3. Use the **Audit Log** tab to trace who enabled hidden sheets and when structural changes occurred.

## 6. Troubleshooting tips

- **Hidden sheet missing**: Verify it was explicitly opted in during upload or refresh, and the user has permission to access protected tabs.
- **Schema mismatch warning**: Check that join columns share compatible data types; update the workbook or adjust column mapping in the builder.
- **Inactive sheet alert**: The source may have been deleted from the workbook; refresh the bundle or switch dashboards to an alternative sheet.
