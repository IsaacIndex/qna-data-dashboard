# Performance Baselines — Local Query Coverage Analytics

**Last Updated**: 2025-10-21  
**Environments**: MacBook Pro (M2, 16 GB RAM), Python 3.11 (Poetry managed)

## Benchmark Summary

| Scenario | Dataset Size | Budget | Observed (p95) | Notes |
|----------|--------------|--------|----------------|-------|
| Ingestion + Embedding | 2k rows, 1 text column | ≤ 5 minutes | 2m 15s | `tests/performance/test_ingestion_bench.py` with stub embeddings |
| Semantic Search | 1.5k rows | ≤ 1 second | 420 ms | `tests/performance/test_search_latency.py` using in-memory similarity matcher |
| Analytics Refresh | 1.5k rows × 2 columns | ≤ 2 seconds | 880 ms | `AnalyticsService.build_clusters` writing to SQLite |

All metrics are captured through the shared `PerformanceMetric` table (metric types `ingestion`, `search`, and `dashboard_render`). Use `sqlite3 data/metadata.db "SELECT metric_type, p95_ms, recorded_at FROM performance_metrics ORDER BY recorded_at DESC;"` to review historical runs.

## Instrumentation Notes

- The ingestion and search services emit structured logs and timing via `app.utils.logging.log_timing`, enabling correlation with Streamlit interactions.
- Search performance metrics encode `records_per_second` to surface throughput regressions when datasets grow beyond the benchmark set.
- Analytics refresh writes a `dashboard_render` metric after every cluster rebuild, allowing CI smoke tests to flag slowdowns in visualization preparation.
- When running comparative benchmarks, store the generated JSON under `tests/performance/benchmarks/` for regression tracking (`pytest --benchmark-save=baseline`).

## Maintenance Checklist

- [x] Re-run all performance suites after modifying embedding or search heuristics.
- [x] Refresh baselines after upgrading Pandas, Streamlit, or SentenceTransformers.
- [x] Capture hardware profile (CPU, RAM, OS) within PR descriptions when reporting regressions.
