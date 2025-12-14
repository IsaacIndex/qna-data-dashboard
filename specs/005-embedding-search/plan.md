# Implementation Plan: Embeddings-based Search Upgrade

**Branch**: `[005-embedding-search]` | **Date**: 2025-12-09 | **Spec**: /Users/isaacibm/GitHub/qna-data-dashboard/specs/005-embedding-search/spec.md
**Input**: Feature specification from `/specs/005-embedding-search/spec.md`

## Summary

Deliver dual-mode search that runs embeddings (semantic) and SequenceMatcher (lexical) per query, showing separate labeled sections with top-10 pagination per mode. Embeddings use ChromaDB for storage and HuggingFace Nomic Embed for vector generation (LangChain allowed if helpful). Preserve contextual columns, filters, and fallback to lexical-only when embeddings are unavailable while keeping searches under 2s P95.

## Technical Context

- **Language/Runtime**: Python 3.11. Streamlit UI + FastAPI backend. Type checking via mypy (strict options); formatting via Black (line length 100); lint via Ruff; coverage via pytest + pytest-cov.
- **Quality Tooling**: `poetry run ruff check`, `poetry run black --check .`, `poetry run mypy`, `poetry run pytest --cov=app --cov-report=term-missing`. Maintain >=85% coverage overall, 100% on critical search paths; add contract tests for API shape changes.
- **Testing Strategy**: Unit tests for search service (dual-mode ranking, normalization, pagination), embedding service (Chroma persistence, model invocation), and preference handling. Integration tests via FastAPI TestClient for `/search` (semantic+lexical responses, fallback messaging). Data validation on embedding freshness. Performance smoke to assert P95 search latency <2s for representative dataset size.
- **User Experience Framework**: Streamlit pages using existing patterns; accessibility per WCAG 2.1 AA with keyboard navigation and readable status/fallback messages; reuse contextual column rendering conventions.
- **Performance Budgets**: Search P95 <2s end-to-end; embedding refresh same-day (target <=15m batch for new/updated tests); top-10 per mode default to cap payload; “load more” paginates per mode without regressing latency.
- **Dependencies**: ChromaDB (persisted under `./data/embeddings`), HuggingFace Nomic Embed model via sentence-transformers; LangChain permitted as wrapper if it keeps configuration minimal; existing AnalyticsClient for latency metrics; SequenceMatcher for lexical scores.
- **Data & Storage**: Local datasets under `./data`; SQLite metadata via SQLAlchemy/Alembic; Chroma persistence directory configurable via `CHROMA_PERSIST_DIR`; embeddings tagged with model version for refresh decisions; no external data residency concerns.
- **Scale/Scope**: Local-first analyst usage; expected tens of thousands of test cases per dataset, single-digit concurrent users. Pagination defaults (10 per mode) keep payloads light; cap limitPerMode to 50.

## Constitution Check

- Coding standards and architecture: Python 3.11, shared services under `app/services`, adherence to lint/type/format gates. No new stacks beyond mandated Chroma + Nomic model (already compatible).
- Testing commitments: Unit + integration + contract coverage defined; maintain >=85% coverage overall and 100% on critical search paths; failure-first tests for dual-mode behaviour and fallback.
- UX/accessibility: Reuse Streamlit patterns, include labeled sections/tabs per mode, clear fallback messaging, and keyboard-friendly navigation; align with WCAG 2.1 AA.
- Performance: Budgets defined (search P95 <2s, embedding refresh same-day/<=15m batch); instrument latency via existing AnalyticsClient; add benchmarks under `tests/performance/` if needed.
- Governance/waivers: None requested; current plan aligns with constitution with no principle waivers.

## Project Structure

### Documentation (this feature)

```
specs/005-embedding-search/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md             # Created by /speckit.tasks
```

### Source Code (repository root)

```
app/
├── api/
├── db/
├── pages/
├── services/
└── utils/

tests/
├── integration/
├── unit/
└── performance/         # add if new perf checks
```

**Structure Decision**: Single Python project with Streamlit UI and FastAPI API in `app/`; tests grouped under `tests/` with unit/integration (and performance as needed).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
