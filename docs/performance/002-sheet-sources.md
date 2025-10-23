# Sheet Sources Performance Runbook

This runbook tracks the performance commitments introduced by feature `002-separate-sheet-sources`.

## Key Metrics

- **Sheet ingestion duration (ms)** — recorded per sheet in `sheet_metrics` with `metric_type = ingestion_duration_ms`.
- **Query preview latency (ms)** — recorded per sheet in `sheet_metrics` with `metric_type = query_p95_ms`.
- **Processed rows** — captured in ingestion audits to validate throughput while diagnosing slow sheets.

## Thresholds & Alerts

| Metric | Threshold | Alert Owner |
|--------|-----------|-------------|
| Sheet ingestion duration | > 120,000 ms | Data pipeline on-call |
| Query preview latency (P95) | > 5,000 ms | Dashboard experience on-call |

Alerts surface in the existing on-call channel via the metrics processor. Both thresholds originate from the feature specification and guard against regressions in the ingestion pipeline and the query preview path.

## Response Playbook

1. **Acknowledge alert** and review recent `sheet_metrics` entries for the impacted sheet IDs.
2. **Verify ingestion audits** via `/api/source-bundles/{bundleId}/sheets` to confirm row counts and hidden sheet approvals.
3. **Check raw bundle file** under `data/bundles/{bundleId}` for size spikes or format changes.
4. **Rerun preview locally** using the Streamlit Query Builder to reproduce latency and collect warnings.
5. **Escalate** to the ingestion engineer if the slowdown persists after trimming columns or resolving workbook anomalies.

## Dashboards & Tooling

- Streamlit ingestion page highlights inactive sheets and exposes last refresh timestamps.
- Query Builder displays warnings when previewing inactive or hidden sheets, helping analysts validate stale content.
- Use the CLI task `pytest tests/integration/sheets/test_sheet_refresh_service.py` to exercise the refresh reconciliation flow after remediation.
