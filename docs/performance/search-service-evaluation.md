# Search Service Retrieval Options

**Scope**: Compare the current lexical SearchService (difflib-based) with an embeddings-based alternative for the LLM test data dashboard.

## Mental Model

- Lexical similarity: compares raw strings, scoring shared substrings and order; best when query wording closely matches an existing test case.
- Embeddings: encodes queries and test cases into vectors (for example 768-d) and scores cosine similarity; works when wording differs but meaning aligns.

## Retrieval Quality (Side by Side)

| Dimension | Lexical (difflib) | Embeddings |
| --- | --- | --- |
| Synonyms | Fails without literal overlap ("terminate policy" vs "cancel plan"). | Usually succeeds; synonyms land near each other. |
| Paraphrase | "How to change address" vs "I moved, update my contact details" scores low. | Scores high; both express the same intent. |
| Word order | Sensitive to ordering. | Less sensitive; semantics remain close. |
| Extra/missing words | Boilerplate can dilute overlap. | Model can focus on core meaning. |
| Multilingual | Breaks unless phrasing matches. | Works if using a multilingual model. |
| Typos | Minor robustness only. | Some robustness, model dependent. |
| Domain phrasing | Requires literal match. | Handles spelling/format variation better, especially if tuned. |
| Out-of-distribution phrasing | Very weak without overlap. | Better chance if the concept exists in training data. |
| Latency small N | Extremely fast. | Slight overhead for on-the-fly embedding. |
| Latency large N | O(N) string distance; slows as corpus grows. | Approximate NN keeps lookup sub-linear with an index. |
| Setup complexity | Pure Python, no model. | Needs embedding model and vector index (FAISS/pgvector, etc.). |
| Infrastructure | No external deps. | Model hosting + index storage. |
| Interpretability | Easy to explain via overlapping substrings. | Opaque; explain via examples. |

## Impact on the Dashboard

- What works today: great for exact regression checks, tiny curated datasets (50-100 prompts), and finding specific templates when you remember the phrasing.
- Where it breaks down: new production phrasing with low lexical overlap (for example "I moved house" vs "Change correspondence address") and discovering semantic clusters (address changes, payments) independent of wording.
- What embeddings add:
  - Semantic recall: "find me all test cases like this production query" even when phrasing drifts.
  - Gap analysis: identify dense production regions with few tests.
  - Failure pattern discovery: clusters of similar failures become easy to label and drill.
  - Better coverage for future prompts: resilient to style differences from business users.

## Migration / Hybrid Pattern

1. Precompute embeddings for all test cases and store them in a vector index.
2. At query time, embed the incoming query and pull top N (for example 50) from the index.
3. Optionally re-rank that short list with a lightweight string similarity to bias toward near-exact matches.

This yields semantic recall from embeddings plus precision from lexical ties when needed.

## When to Stay Lexical

- Small, stable datasets with standardized wording.
- Primary use case is "I roughly remember the text; find that row."
- Use embeddings as a phase-two upgrade once query diversity grows and lexical search feels limiting.

## Portfolio Note

I first shipped a difflib.SequenceMatcher-based search for near-exact matches. To improve coverage for paraphrased and real-world queries, I replaced the retrieval core with an embeddings pipeline: encode each test and incoming query, search by cosine similarity through a vector index, and surface semantic neighbors. The shift from lexical to semantic search improved relevance for new production queries, exposed test-set gaps, and made it easier to analyze clusters of similar failure modes.
