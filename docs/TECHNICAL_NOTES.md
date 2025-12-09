# Comparing string-based search vs embeddings-based search for LLM test data

## Background

We maintain an internal LLM test data dashboard that stores natural-language queries as test cases and lets us search across them to support regression testing, failure analysis, and gap discovery.

The first version of the dashboard used a purely **string-similarity based** search implementation built on `difflib.SequenceMatcher`. This worked well for near-exact matches: when a user typed a query that closely resembled an existing test case, the dashboard reliably surfaced the right row.

However, as real-world traffic and phrasing diversity increased, this lexical approach started to show limitations. It struggled with synonyms, paraphrased queries, and more conversational user inputs. To improve coverage for paraphrased and production-style queries, we are evaluating a shift from this string-based search to an **embeddings-based semantic search pipeline**.

In the target design, each test query and new input is encoded into a vector representation, and candidates are retrieved by cosine similarity through a vector index. This shift from lexical to semantic search should make it easier to:

- Find related test cases for new production queries
- Identify gaps in the existing test set
- Analyze clusters of similar failure patterns in LLM behaviour

This technical study documents the current versus target approaches and provides a concrete Python example of how embeddings-based search can be implemented and wired into the dashboard.

---

## 1. Mental model

- **Current approach (difflib / string similarity)**  
  - Compares raw text strings (character/word sequences).  
  - Scores based on how similar the characters/words are (shared substrings, order, etc.).  
  - Works best when the query is **very close in wording** to an existing test case.

- **Embeddings-based search**  
  - Converts each query + test case into a **vector** (e.g. 768-dimensional) that encodes meaning.  
  - Uses cosine similarity / dot-product between vectors.  
  - Works even when wording is different but meaning is close (synonyms, paraphrases).

---

## 2. Side-by-side comparison

### Retrieval quality

| Dimension | String similarity (difflib) | Embeddings-based search |
|----------|-----------------------------|--------------------------|
| Synonyms | Fails unless words literally overlap (`"terminate policy"` ≠ `"cancel plan"`). | Usually works, since embeddings place synonyms near each other. |
| Paraphrase | `"How to change address"` vs `"I moved, update my contact details"` → low score. | High similarity, both are “change address” intent. |
| Word order | Sensitive. `"policy cancellation fee"` vs `"fee for cancelling policy"` might drop score. | Less sensitive; both live in similar regions. |
| Extra / missing words | Extra boilerplate (“Hi, I want to ask about…”) can dilute shared substring. | Model can still focus on core semantics. |
| Multilingual / code-mixed | Basically broken unless the language / phrasing matches. | If you use multi-lingual embeddings, still works reasonably well. |

### Robustness & coverage

| Dimension | String similarity | Embeddings |
|----------|-------------------|-----------|
| Typos | Slight robustness for small typos, but not conceptual errors. | Somewhat robust if the embedding model is decent; still not perfect. |
| Domain phrases | Must literally match; small spelling/format differences hurt. | Fine, especially if you use domain-tuned embeddings. |
| Out-of-distribution phrasing | Very weak; no lexical overlap → no retrieval. | Better chance if meaning is expressible in the model’s training. |

### Operational aspects

| Dimension | String similarity | Embeddings |
|----------|-------------------|-----------|
| Setup complexity | Trivial (pure Python, no model). | Need embedding model, vector index (FAISS, pgvector, etc.). |
| Latency for small N | Very fast; just loops + difflib. | Slight overhead (model call) if you embed on the fly. |
| Latency for large N | O(N × string_distance); can get slow if test set grows. | ANN index makes it effectively sub-linear for large corpora. |
| Infrastructure | No external dependencies. | Need model hosting (OpenAI/Azure/self-hosted) + index storage. |
| Determinism | Deterministic: same strings → same score. | Deterministic given same model + params, but behavior tied to model version. |

### Interpretability

| Dimension | String similarity | Embeddings |
|----------|-------------------|-----------|
| “Why did I get this match?” | Easy: show overlapping substrings, highlighted diffs. | Harder: vector geometry is opaque; you explain via examples, not rules. |
| Debugging obvious bad hits | Look at strings, you immediately see mismatch. | Sometimes you see “semantically weird” hits that need model introspection. |

---

## 3. How this plays out in the LLM test data dashboard

Assume each row is something like:

- `user_query_text`
- Optional tags: `intent`, `category`, `notes`, `LLM_output`, etc.

### What string similarity gives you today

Good for:

- **Exact regression checks**:  
  Searching `"how to change my address"` and finding the test case that used almost the same wording.
- **Tiny datasets** (e.g. 50–100 prompts) where wording is already standardized.  
- **Debugging templates**: quickly locating prompts that contain a very specific phrase.

Weak for:

- New production query phrased differently from your test set.  
- Looking for **semantic clusters** of failures (e.g. all address-change queries) regardless of exact wording.

### What embeddings would add

With embeddings, the workflow becomes more powerful:

1. **“Find me all test cases like this production query”**  
   - Embed the production query.  
   - Search against embedded test dataset.  
   - You get a **semantic neighborhood**: different wordings, same intent.

2. **Gap analysis**  
   - Detect **regions of the embedding space** where production queries are dense but you have few or no tests.  
   - Directly tells you where to add new test prompts.

3. **Pattern discovery for failure modes**  
   - Cluster test cases where the LLM fails similarly (their embeddings are usually close).  
   - Auto-label “problematic clusters” and drill down.

4. **Better coverage for future prompts**  
   - Even if business users write in a different style than your original seed tests, embedding search still works.

---

## 4. Typical migration / hybrid pattern

You don’t have to fully abandon string similarity. A common pattern:

1. **Precompute embeddings** for all test cases and store them in a vector index.
2. At query time:
   - **Embed the query**.
   - Use the vector index to pull top-N candidates (e.g. N = 50).
   - Optionally **re-rank those N** with:
     - Another embedding similarity, or
     - A lightweight **string similarity** for fine-grained ordering.

This gives you:

- Semantic recall from embeddings.
- Extra precision from string matching, if you want “almost exact match” at the top.

---

## 5. When embeddings might *not* be necessary

Stick with difflib (or something similar) if:

- Your test data size is small and stable.
- Wording patterns are already highly standardized.
- Primary use case is:  
  “I know roughly the text, just find that test row”.

Or treat embeddings as “Phase 2”: only after the test set and query diversity grow enough that lexical search feels limiting.

---



## 7. Technical example: Embeddings-based search with LangChain

Below is a minimal Python example showing how to:

1. Store a small corpus of test queries
2. Build a LangChain vector store over them
3. Perform semantic search for a new query

This example uses **LangChain** with `OpenAIEmbeddings` and an in-memory `FAISS` vector store. In a real system you’d typically replace the in-memory FAISS instance with a persisted FAISS index, pgvector, or another vector DB.

```python
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# 1. Your test cases (what you already store in the dashboard)
TEST_CASES = [
    {"id": 1, "text": "How do I change my correspondence address?"},
    {"id": 2, "text": "Cancel my insurance policy"},
    {"id": 3, "text": "What is the premium payment due date?"},
    {"id": 4, "text": "Update my phone number"},
]

# 2. Configure the embedding model used by LangChain
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"  # or another HF model you use
)

# 3. Build a FAISS vector store from the test cases
texts = [t["text"] for t in TEST_CASES]
metadatas = [{"id": t["id"]} for t in TEST_CASES]

vector_store = FAISS.from_texts(
    texts=texts,
    embedding=embeddings,
    metadatas=metadatas,
)


def semantic_search(query: str, k: int = 3):
    """Return top-k most similar test cases for a given query text."""
    # LangChain handles: embed query → search vector index → return docs + scores
    docs_and_scores = vector_store.similarity_search_with_score(query, k=k)

    results = []
    for doc, score in docs_and_scores:
        results.append(
            {
                "id": doc.metadata["id"],
                "text": doc.page_content,
                # Depending on the backend, 'score' may be a distance (lower is better)
                "score": float(score),
            }
        )
    return results


if __name__ == "__main__":
    user_query = "I moved house, how can I update my mailing address?"
    hits = semantic_search(user_query, k=3)

    print(f"Query: {user_query}
")
    for rank, hit in enumerate(hits, start=1):
        print(f"#{rank} (score={hit['score']:.3f}) - id={hit['id']}")
        print(f"  {hit['text']}
")
```

### How this wires into your dashboard

- **Backend SearchService**:
  - Load `TEST_CASES` from your DB.
  - Build the LangChain `FAISS` vector store (or another vector store) at startup or via a batch job.
  - Expose an endpoint `/search?query=...` that calls `semantic_search(query)`.

- **Frontend**:
  - Uses your existing search UI, but instead of calling string-based search, calls the new semantic search endpoint.
  - Displays the top-k test cases with their scores and metadata (intent, tags, LLM output, pass/fail, etc.).

For larger datasets you can point LangChain at a persistent vector backend (e.g. a persisted FAISS index, pgvector, Qdrant, etc.) and still keep the same high-level `semantic_search` API in your code.

