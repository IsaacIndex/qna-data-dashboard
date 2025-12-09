# Research: Embeddings-based Search Upgrade

## Decisions

1) Decision: Use ChromaDB as the vector store (local persistence under `./data/embeddings`).
- Rationale: Already a repo dependency, supports local-first persistence, aligns with Streamlit/FastAPI offline use, and keeps footprint small without external services.
- Alternatives considered: FAISS (good performance but adds build steps and separate persistence), pgvector (requires DB setup contrary to local-first goal), in-memory-only stores (lose persistence and refresh guarantees).

2) Decision: Use HuggingFace Nomic Embed model for embedding generation.
- Rationale: User requirement; open-source, locally runnable, and compatible with existing sentence-transformers integration; avoids external API reliance.
- Alternatives considered: all-MiniLM-L6-v2 (smaller but not requested), OpenAI text-embedding-3 (external dependency and cost), Instructor XL (heavier latency for this dashboard scale).

3) Decision: Dual-mode search executes both semantic (Chroma embeddings) and lexical (SequenceMatcher) per query with separate top-10 lists and independent pagination.
- Rationale: Meets clarified requirement to co-exist modes, keeps UI scannable, and preserves lexical precision while adding semantic recall.
- Alternatives considered: Single-mode toggle (reduces recall/visibility), interleaved combined list (harder to interpret mode provenance), higher per-mode caps (risks latency/scroll bloat).

4) Decision: Refresh embeddings on a same-day cadence (or on-demand trigger) when test cases change.
- Rationale: Matches spec requirement for freshness without blocking ingestion; balances compute with expected dataset size.
- Alternatives considered: Real-time embedding on every write (higher latency during ingestion), weekly batches (stale results for new tests), manual-only refresh (risks drift).
