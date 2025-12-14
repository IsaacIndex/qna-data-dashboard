# Data Model: Embeddings-based Search Upgrade

## Entities

### Search Query
- Fields: `query_text` (string, required), `dataset_ids` (list[string], optional), `column_names` (list[string], optional), `min_similarity` (float 0-1, optional), `limit_per_mode` (int, default 10, max 50), `filters` (object for future filters).
- Constraints: `query_text` must be non-empty trimmed text; `limit_per_mode` applies independently to semantic and lexical modes.

### Test Case
- Fields: `id` (uuid/string, required), `dataset_id` (string, required), `text` (string, required), `metadata` (object: intent, category, notes, contextual labels), `updated_at` (datetime).
- Constraints: `id` unique per dataset; `text` normalized whitespace; contextual labels optional.
- Relationships: Many Test Cases belong to one dataset; surfaced in both lexical and semantic search.

### Embedding Index Entry
- Fields: `test_case_id` (string, required), `dataset_id` (string, required), `embedding` (vector float[], stored in Chroma), `model` (string, e.g., `nomic-embed-text`), `last_embedded_at` (datetime), `version` (string hash of model/config).
- Constraints: Unique on (`test_case_id`, `model`); `last_embedded_at` must be >= `test_case.updated_at` for freshness.
- State transitions: Needs re-embed when test case text changes or model version changes; on missing entry, falls back to lexical only.

### Search Result
- Fields: `test_case_id` (string), `dataset_id` (string), `text` (string), `similarity` (float 0-1), `mode` (`semantic` | `lexical`), `metadata` (object including contextual columns and labels), `rank` (int within mode list).
- Constraints: Rank is mode-scoped; similarity present for both modes (SequenceMatcher similarity normalized to 0-1).
- Relationships: Links back to Test Case; populated from Embedding Index Entry for semantic mode and raw text for lexical mode.

## Validation Rules
- All returned results must include `mode` and `similarity`; ranks reset per mode.
- Requests with empty or whitespace-only `query_text` must be rejected before search execution.
- If embeddings unavailable, semantic list may be empty; lexical list remains populated.

## Derived/Computed Data
- Similarity legend thresholds reused across both modes; lexical scores normalized to align with legend thresholds.
- Freshness check compares `last_embedded_at` vs `updated_at`; stale entries trigger re-embed queue or omission from semantic results.
