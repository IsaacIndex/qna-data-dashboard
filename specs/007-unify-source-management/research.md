# Research: Unified Source Management

## Decision: Canonical source UUID with legacy remap
- **Rationale**: Prevents collisions across tmp files, sheet catalog, and embeddings while keeping UI human-readable. Supports consistent re-embed targeting and status sync.
- **Alternatives considered**: Dataset+filename key (collides on duplicates); dataset+type+timestamp (unstable and opaque).

## Decision: Server-backed infinite scroll with server-side filter/sort
- **Rationale**: Keeps ingest tab responsive for large inventories; avoids client overfetch and mismatched counts; aligns with performance budgets.
- **Alternatives considered**: Full list load (risks timeouts); paged UI with page jumps (heavier UX friction).

## Decision: Auto-reinsert missing legacy sources into `data/ingest_sources` with audit log and conflict prompts
- **Rationale**: Keeps inventories consistent without silent gaps; prompts prevent accidental overwrites; audit trail supports traceability.
- **Alternatives considered**: Always prompt (slower workflows); flag-only/manual remediation (higher risk of drift).

## Decision: Observability for ingest actions
- **Rationale**: Log and metric events for legacy remap, reinsertion, re-embed start/complete, and status propagation enable troubleshooting and SLA checks.
- **Alternatives considered**: Minimal logging (insufficient for debugging); full tracing (overhead not justified for current scale).

## Decision: Performance budgets
- **Rationale**: P95 ingest tab render ≤2s for 500 sources; infinite scroll batch append ≤600ms; status refresh ≤5s; re-embed initiation ≤1s to maintain analyst usability.
- **Alternatives considered**: Unbounded latency targets (unverifiable); stricter sub-second render for all cases (not required for current scale).

## Decision: Security/auth reuse existing controls
- **Rationale**: Feature respects current authZ/authN; source visibility/actions already governed. No new PII introduced; filenames only.
- **Alternatives considered**: New role models (unnecessary for current scope).

## Decision: Integration scope
- **Rationale**: Use existing FastAPI endpoints for ingest/re-embed and chromadb for embeddings; file IO under `data/ingest_sources`; no new external services.
- **Alternatives considered**: Adding external storage/service (not needed for local dashboard scope).
