# Research: Q&A Dashboard UX Refresh

## Findings

- Decision: Use a 5-stop similarity color scale from cool-gray (#E5E7EB at 0%) → soft blue (#93C5FD at 25%) → teal (#22D3EE at 50%) → emerald (#10B981 at 75%) → deep teal (#0F766E at 100%) with text labels for each range (“Very Low”, “Low”, “Medium”, “High”, “Very High”) plus a numeric 0–100% value and legend displayed above the results grid.  
  Rationale: Neutral-to-teal gradient keeps contrast readable on light backgrounds, aligns with existing dashboard blues/greens, and avoids red/green reliance while still giving a quick scan cue; text labels + numbers satisfy clarity even without color-blind-safe palette.  
  Alternatives considered: Classic red→yellow→green heatmap (risk of alarming semantics and contrast issues), monochrome single-hue ramp (harder to quickly parse confidence tiers), or icon-only badges (insufficient for quick scanning without legend).

- Decision: Emit analytics events as structured JSONL records via the existing logging stack to `data/logs/analytics.jsonl`, with each event containing `event`, `duration_ms`, `dataset_id`, `tab`, `success`, and timestamp; UI code forwards events through a thin client that falls back to in-memory buffering if the log path is unavailable.  
  Rationale: Keeps telemetry local/offline as required, integrates with the current logging directory, and makes it easy to assert on events in tests without adding remote dependencies; buffering avoids blocking the UI when disk is transiently unavailable.  
  Alternatives considered: Sending metrics to remote services (disallowed/offline), storing only in SQLite (adds locking contention on hot paths), or silently discarding telemetry when file access fails (loses observability).

- Decision: Scope result layout/column preferences to browser `localStorage` as the primary source of truth, keyed by dataset ID + page context + version; on load, hydrate `st.session_state` from localStorage asynchronously while rendering search defaults immediately. Optionally mirror a best-effort copy to the existing metadata preference tables for analytics/audit but never block the UI on that call.  
  Rationale: Meets requirement for device/browser-local storage and non-blocking loads, while respecting the existing preference schema for optional auditing; asynchronous hydration prevents search-tab blocking and preserves selections across tabs in-session.  
  Alternatives considered: Relying solely on backend-stored preferences (violates device-local requirement and can block on I/O), cookies (size limits and awkward JSON handling), or session-only state (loses persistence across browser restarts).

- Decision: Present deduplicated column choices by precomputing a union catalog with sheet provenance and availability flags; render a flat list grouped by column name with chips for sheet origin, hide missing headers by default but show an inline “unavailable” badge when selection would reference them, and support keyboard toggle/confirm.  
  Rationale: Matches requirement to list unique columns once while keeping sheet context, minimizes clicks, and keeps missing headers from blocking flow; aligns with existing ingestion improvements that skip missing headers.  
  Alternatives considered: Per-sheet pickers (reintroduce duplicates and extra clicks), hiding provenance entirely (analysts lose context), or forcing missing headers to be selectable (risk of errors later).

- Decision: Performance guardrails: cache dataset metadata/column catalogs with `st.cache_data`, debounce search inputs, and precompute similarity color bands server-side to avoid per-row recalculation; ensure tab switches reuse cached selections from `st.session_state` and avoid heavy recomputation in `on_tab_change` handlers.  
  Rationale: Keeps interactions under 2s P95, reduces rerender overhead, and aligns with the local-first setup; caching plus debounce prevent redundant backend calls when analysts type or switch tabs quickly.  
  Alternatives considered: Uncached per-render recomputation (risks >2s latency), client-only color computation (duplicated logic and harder testability), or aggressive background polling (wasted cycles with minimal UX gain).
