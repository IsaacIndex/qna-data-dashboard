# QA Checklist: Local Query Coverage Analytics

**Test Date**: 2025-10-21  
**Tester**: QA automation via pytest + manual Streamlit sanity

## End-to-End Workflow

- [x] Ingest CSV with two text columns → dataset transitions to `ready`, audit recorded.
- [x] Search page returns ranked matches with dataset + column filters applied.
- [x] `/search` API contract validated via pytest contract suite.
- [x] Coverage analytics refresh produces clusters and summary metrics without errors.
- [x] `/analytics/clusters` and `/analytics/summary` endpoints respond with expected schema.
- [x] Performance smoke: search latency benchmark remains under 1 second (local stub).
- [x] Quickstart instructions reproduced environment setup and Streamlit navigation.

## Manual Notes

- Analytics refresh reuses cached session state; reload the page when editing datasets outside the UI.
- Streamlit toast notifications confirm success/failure states for ingestion, search, and analytics actions.
