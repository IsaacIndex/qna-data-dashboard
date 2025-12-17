# Ingest Page: Unified Source Management

- Unified source inventory spans tmp files, sheet catalog entries, and embeddings with server-side filters for dataset/type/status/group and infinite scroll pagination; labels stay human-readable while UUIDs remain authoritative.
- Bulk actions apply status/group updates across selected sources and return per-item results so partial failures don’t block the rest; audit entries capture requested changes.
- Re-embed panel queues jobs by label (dataset/type shown) and hides raw IDs; status overrides flow back into the unified list so analysts can confirm progress without digging into UUIDs.
- Legacy reconcile can run in dry-run mode to surface conflicts, then reinsert missing files under `data/ingest_sources/` with audit logging and canonical UUID remap.
- Accessibility: focus outlines are enabled for dropdowns/buttons, default filters start at “All” values, and help text guides keyboard navigation across selectors.
