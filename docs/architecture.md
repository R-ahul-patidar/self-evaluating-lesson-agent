# Architecture — Self-Evaluating Lesson Agent

## System Overview

```
                    USER
                      │
                      ▼
              Configure Request
        (topic, content_type, learner_profile,
         learning_goal, reference_source, demo_mode)
                      │
                      ▼
              FastAPI POST /generate
                      │
              Background Thread
                      │
              ┌───────▼────────┐
              │  LangGraph     │
              │  Workflow      │
              └───────┬────────┘
                      │
            ┌─ prepare_request ─────────────────────┐
            │   Load memory · Init state             │
            └───────────────────────────────────────┘
                      │
            ┌─ retrieve_reference_context ───────────┐
            │   FAISS (gemini-embedding-001) · top-4 │
            └───────────────────────────────────────┘
                      │
            ┌─ generate_content ─────────────────────┐
            │ Generator Agent · gemini-3.5-flash-lite│
            │   Inputs: topic + learner + ref +       │
            │           rubric + memory feedback      │
            └───────────────────────────────────────┘
                      │
            ┌─ evaluate_content ─────────────────────┐
            │   Evaluator Agent · temp=0             │
            │   10 PASS/FAIL rubric checks           │
            │   Structured JSON output (Pydantic)    │
            └───────────────────────────────────────┘
                      │
            ┌─ decide_next_step ─────────────────────┐
            │   PASS       → finalize → END          │
            │   FAIL + <2  → regenerate_content      │
            │   FAIL + ≥2  → finalize (FAIL) → END   │
            └───────────────────────────────────────┘
                      │
            ┌─ regenerate_content ───────────────────┐
            │   Inject failure feedback into prompt  │
            │   Save failures to SQLite memory       │
            │   Generator Agent rewrites draft       │
            └─────────────────┬──────────────────────┘
                              │
                  (Loops back to evaluate_content)
                              │
            ┌─ finalize ──────────────────────────────┐
            │   Build rejection log · Set final_status│
            │   Persist run to SQLite                 │
            └───────────────────────────────────────┘
                      │
              JS Polling GET /runs/{id}
                      │
              UI renders result
```

---

## Component Responsibilities

### Generator Agent (`src/agents/generator.py`)
- Calls `gemini-3.5-flash-lite` via LangChain `ChatGoogleGenerativeAI`
- Two entry points: `generate_content()` (first attempt) and `regenerate_content()` (targeted retry)
- Accepts: topic, content_type, learner_profile, reference_context, rubric, memory_feedback, demo_mode
- Returns: lesson text as a string
- **Does NOT know** about the evaluator's internals

### Evaluator Agent (`src/agents/evaluator.py`)
- Calls `gemini-3.5-flash-lite` with `temperature=0` for deterministic judgements
- Returns structured `EvaluationResult` (parsed from JSON response)
- Handles malformed JSON gracefully (fallback evaluation)
- **Does NOT know** about the generator's prompts — fully independent

### Memory Agent (`src/agents/memory.py`)
- Reads historical failures from SQLite before generation
- Writes failure patterns after each FAIL evaluation
- Self-evolving: frequency counter increments on repeated failures
- Formatted failures are injected into the generator prompt

### Knowledge Layer (`src/knowledge/`)
- `loader.py`: loads markdown, chunks by paragraph boundaries with 100-char overlap
- `embeddings.py`: builds/loads FAISS index using `models/gemini-embedding-001`
- `retriever.py`: `retrieve_context(query, topic, top_k=4)` — public interface
- Index cached to disk; staleness detected by reference file mtime

### LangGraph Workflow (`src/graph/`)
- `state.py`: `AgentState` TypedDict — all data flows through here
- `nodes.py`: each node receives state, returns partial state dict
- `workflow.py`: graph assembly, conditional edges, compiled once on import

---

## Data Flow

```
GenerateRequest (Pydantic)
    → AgentState (TypedDict)
        → EvaluationResult (Pydantic)
            → RejectionEntry (Pydantic)
                → GenerateResponse (Pydantic)
                    → JSON to client
```

---

## Polling Architecture

```
POST /generate
  Validates GenerateRequest
  Creates run_store[run_id] = { status: "running", ... }
  Spawns background thread
  Returns { run_id } immediately

Background Thread
  Runs LangGraph workflow.invoke(initial_state)
  Updates run_store[run_id] on completion

GET /runs/{run_id}  (called every 2s by JS)
  Reads run_store[run_id]
  Returns current status snapshot

JS terminates polling when status ∈ { "PASS", "FAIL", "error" }
```

---

## SQLite Schema

### `memory_feedback` table

```sql
CREATE TABLE memory_feedback (
    memory_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    topic           TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'lesson',
    failure_type    TEXT NOT NULL,         -- rubric check name
    failure_reason  TEXT NOT NULL,
    suggested_correction TEXT NOT NULL,
    frequency       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    last_seen       TEXT NOT NULL
);
```

### `run_history` table

```sql
CREATE TABLE run_history (
    run_id          TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    final_status    TEXT NOT NULL,
    attempt_count   INTEGER NOT NULL,
    timestamp       TEXT NOT NULL,
    result_json     TEXT
);
```

---

## FAISS Index

- Stored at: `output/faiss_index/{index_name}/`
- Built from: `references/*.md`
- Embedding model: `models/gemini-embedding-001`
- Chunk size: 600 chars, 100-char overlap
- Staleness: detected by comparing `ref_mtime` in metadata JSON
- In-memory cache: prevents disk reads on repeated requests
