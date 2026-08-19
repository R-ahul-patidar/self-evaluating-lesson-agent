# Design Decisions — Self-Evaluating Lesson Agent

## 1. Why LangGraph (not a while loop)?

**Decision**: Use LangGraph for workflow orchestration.

**Rationale**:
- Explicit typed state flows through every node — no hidden global state
- Conditional edges make the retry logic declarative, not imperative
- The workflow is inspectable: you can visualize the graph
- Future nodes (e.g., human-in-the-loop review, A/B evaluation) can be added without rewriting the loop
- LangGraph's `retry_count < max_retries` conditional edge terminates cleanly

**Alternative considered**: A simple `while retry_count < MAX_RETRIES` Python loop.
Rejected because: no explicit state, harder to debug, harder to extend, no graph visualization.

---

## 2. Why is the Evaluator a Separate Agent?

**Decision**: The Evaluator is fully independent of the Generator.

**Rationale**:
- The Evaluator receives only: lesson text + rubric + reference + learner profile
- It has NO access to the Generator's system prompt or internal instructions
- This independence is what makes the quality gate meaningful
- If the Evaluator could see the Generator's prompt, it would be biased toward approving it

**Alternative considered**: A single "generate and evaluate" prompt.
Rejected because: there's no independence — the model can't objectively critique its own instructions.

---

## 3. Why Pydantic for Evaluator Output?

**Decision**: Force structured JSON output from the Evaluator, validated by Pydantic.

**Rationale**:
- Vague evaluator output ("the lesson seems good") is useless for regeneration
- Pydantic guarantees each check has: `name`, `passed` (bool), `reason` (string)
- Malformed JSON is caught and a safe fallback is returned
- The structured output is what enables targeted regeneration — we know exactly which check failed and why

**Implementation**: The evaluator prompt ends with an explicit JSON schema. The response is parsed with `json.loads()`, then `EvaluationResult(**data)`.

---

## 4. Why gemini-3.5-flash-lite?

**Decision**: Use `gemini-3.5-flash-lite` for both Generator and Evaluator.

**Rationale**:
- Ultra-fast, lightweight model with high structured reasoning capability
- Highly cost-effective and token-efficient — ideal for iterative agentic loops that make multiple LLM invocations per run
- Reliable JSON schema compliance for the evaluator's structured Pydantic output
- Unified API key management across LLM and embeddings

---

## 5. Why models/gemini-embedding-001?

**Decision**: Use Google's `models/gemini-embedding-001` via LangChain instead of heavy local embedding models.

**Rationale**:
- Shared Google Gemini API key — zero extra credentials or local model downloads
- High-quality semantic embeddings integrated directly with LangChain's `GoogleGenerativeAIEmbeddings`
- Zero additional local dependencies (no PyTorch, no local HuggingFace weights)
- Disk-cached FAISS vector index prevents redundant embedding API calls

**Trade-off**: Embedding model calls use API tokens, fully mitigated by caching the FAISS index to disk.

---

## 6. Why FAISS (not Pinecone/Chroma/Weaviate)?

**Decision**: Use FAISS for local vector retrieval.

**Rationale**:
- No external service required — runs entirely locally
- No API key, no cloud cost, no internet dependency for retrieval
- Fast enough for the scale of this assessment (< 100 chunks)
- The index is cached to disk — built once, reused every request

**Trade-off**: FAISS doesn't support real-time document updates as elegantly as cloud vector stores.
Acceptable for this use case since reference documents are static.

---

## 7. Why SQLite (not Redis/PostgreSQL)?

**Decision**: Use SQLite for persistent memory.

**Rationale**:
- Zero infrastructure — no server to start, no configuration
- The `sqlite3` module is in Python's standard library — no extra dependency
- File-based — the database is just `output/memory.db`, easy to inspect and backup
- Sufficient for the scale: storing hundreds of failure records

**Trade-off**: Not suitable for multi-process deployments. For production, swap to PostgreSQL.

---

## 8. Why Simple Polling (not SSE/WebSockets)?

**Decision**: UI polls `GET /runs/{run_id}` every 2 seconds.

**Rationale**:
- Easiest to implement with Vanilla JS — a simple `setInterval`
- No special server-side streaming setup required
- Sufficient for a demo: 2-second polling lag is imperceptible for 10-30s workflows
- Works with any HTTP client — no CORS or protocol issues

**Trade-off**: 2-second polling lag. For production, SSE would give sub-second updates.

---

## 9. Why is the Rubric a Pydantic Object?

**Decision**: Represent rubrics as `Rubric` Pydantic model instances, not hard-coded strings.

**Rationale**:
- A "Python Functions" topic can use a completely different rubric
- The same Generator, Evaluator, and workflow handle all topics
- Adding a new content type (Quiz, Tutorial) only requires a new `Rubric` instance
- The rubric checks are passed to both the Generator (so it knows what to satisfy) and the Evaluator (so it knows what to check)

**The core insight**: Topic-specific logic is configuration, not code.

---

## 10. Why Separate Prompt Templates?

**Decision**: All prompts live in `src/prompts/` — no prompt strings in agent or route files.

**Rationale**:
- Prompts can be iterated without touching agent logic
- Prompts are testable in isolation (just call the builder function)
- The regeneration prompt is particularly important: it explicitly injects failure reasons, not just the original prompt
- Separating prompts from logic is a key engineering discipline for LLM applications

---

## 11. Why temperature=0 for the Evaluator?

**Decision**: Evaluator LLM uses `temperature=0`.

**Rationale**:
- Evaluation should be deterministic and consistent
- The same lesson evaluated twice should produce the same PASS/FAIL result
- Creative variation is desirable for generation; it's a defect for evaluation
- Temperature=0 reduces the risk of the evaluator being inconsistent across retries

---

## 12. The Regeneration Strategy

**Decision**: Regeneration explicitly injects failure reasons — it's not a blind retry.

**Rationale**:
- Simply re-running the same generation prompt would produce very similar output
- The regeneration prompt includes: failed check names, failure reasons, required corrections, previous content
- The Generator can see exactly what went wrong and what to fix
- This is the difference between a self-correcting system and a random retry loop

**Example** of what the regeneration prompt includes:
```
❌ What Failed:
  - [jargon_explained] FAILED: 'Embedding' is used without explanation.

✅ Required Corrections:
  1. Explain 'embedding' as a list of numbers representing text meaning,
     using a simple analogy before using the term.
```
