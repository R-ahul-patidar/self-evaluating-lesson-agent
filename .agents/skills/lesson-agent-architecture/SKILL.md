---
name: lesson-agent-architecture
description: >
  Complete architecture reference for the Self-Evaluating Lesson Agent.
  Use this skill when: adding new nodes, modifying the LangGraph workflow,
  changing agent behaviour, adding new rubric checks, or debugging the
  generate → evaluate → regenerate loop. Covers state schema, node
  responsibilities, conditional edge logic, and the polling API contract.
---

# Self-Evaluating Lesson Agent — Architecture Skill

## Project Purpose

An **agentic content generation system** that:
1. Generates a beginner educational lesson for any topic
2. Evaluates it against a strict PASS/FAIL rubric (10 checks for RAG)
3. Regenerates with targeted feedback when checks fail
4. Terminates after MAX_RETRIES=2
5. Persists failure patterns in SQLite for self-evolving behaviour

> **Central principle**: The system does NOT trust its first generation.
> It generates → evaluates → regenerates → ships only what passes.

---

## Stack

| Layer | Technology | Version |
|---|---|---|
| LLM | `gemini-3.5-flash-lite` via LangChain | latest |
| Embeddings | `models/gemini-embedding-001` | latest |
| Orchestration | LangGraph 1.x | 1.2+ |
| API | FastAPI + Uvicorn | 0.14+ |
| Vector store | FAISS (local, cached to disk) | 1.15 |
| Memory | SQLite (`sqlite3` stdlib) | built-in |
| UI | Jinja2 + Vanilla JS (polling) | — |
| Schemas | Pydantic v2 | 2.13+ |

---

## Repository Layout

```
src/
├── config.py           ← All env config (GEMINI_API_KEY, MAX_RETRIES, etc.)
├── main.py             ← FastAPI app entry point
├── api/
│   └── routes.py       ← GET /, POST /generate, GET /runs/{id}, GET /health
├── agents/
│   ├── generator.py    ← Generator Agent (gemini-3.5-flash-lite)
│   ├── evaluator.py    ← Evaluator Agent (temp=0, structured JSON output)
│   └── memory.py       ← Read/write SQLite memory records
├── graph/
│   ├── state.py        ← AgentState TypedDict
│   ├── nodes.py        ← All node functions
│   └── workflow.py     ← Graph assembly + conditional edges
├── knowledge/
│   ├── loader.py       ← Markdown loader + chunker
│   ├── embeddings.py   ← FAISS index build/load/cache
│   └── retriever.py    ← retrieve_context() interface
├── prompts/
│   ├── generator.py    ← Generation prompt templates
│   ├── evaluator.py    ← Evaluation prompt templates
│   └── regeneration.py ← Regeneration prompt (injects failures)
├── models/
│   └── schemas.py      ← All Pydantic models
└── storage/
    └── database.py     ← SQLite schema + upsert/query helpers
```

---

## LangGraph Workflow

```
START
  ↓
node_prepare_request       → load memory, init retry counters
  ↓
node_retrieve_reference_context  → FAISS query → top-4 chunks
  ↓
node_generate_content      → Generator Agent (first attempt)
  ↓
node_evaluate_content      → Evaluator Agent → EvaluationResult
  ↓
_decide_after_evaluation   ← CONDITIONAL EDGE
  ├── evaluation.passed=True     → node_finalize → END
  ├── retry_count < max_retries  → node_regenerate_content
  └── retry_count >= max_retries → node_finalize → END
  ↓ (on FAIL + retries available)
node_regenerate_content    → inject failures → Generator → new content
  ↓
node_evaluate_content      (loop back)
```

### Conditional Edge Logic (`workflow.py`)

```python
def _decide_after_evaluation(state: AgentState) -> str:
    if evaluation.passed:
        return "finalize"
    if retry_count < max_retries:
        return "regenerate"
    return "finalize"   # retry limit → terminate with FAIL
```

---

## AgentState Schema

```python
class AgentState(TypedDict, total=False):
    run_id: str
    topic: str
    content_type: str
    demo_mode: bool
    learner_profile: LearnerProfile
    learning_goal: str
    rubric: Rubric
    reference_context: str
    generated_content: str
    evaluation: Optional[EvaluationResult]
    retry_count: int
    max_retries: int
    rejection_log: list[RejectionEntry]
    memory_feedback: list[MemoryRecord]
    steps_completed: list[str]    # ← polled by UI
    current_step: str
    final_status: str             # "PASS" | "FAIL" | "pending"
    final_content: str
    error: Optional[str]
```

---

## Pydantic Evaluation Schema

```python
class EvaluationResult(BaseModel):
    passed: bool          # True ONLY if ALL checks passed
    checks: list[RubricCheck]
    critical_failures: list[str]          # failed check names
    improvement_suggestions: list[str]    # specific corrections

class RubricCheck(BaseModel):
    name: str
    passed: bool
    reason: str           # specific reason for PASS or FAIL
```

---

## Polling API Contract

```
POST /generate
  Body: GenerateRequest JSON
  Returns: { "run_id": "uuid" }   ← immediately, workflow starts in bg thread

GET /runs/{run_id}
  Returns: RunStatus JSON (polled every 2s by JS)
  Fields: run_id, topic, status, current_step, steps_completed,
          attempt, max_attempts, evaluation, rejection_log, final_content, error

status values: "running" | "PASS" | "FAIL" | "error"
```

---

## The 10 RAG Rubric Checks

| Check | What it verifies |
|---|---|
| `accuracy` | No materially incorrect technical claims |
| `grounding` | Claims consistent with FAISS reference material |
| `beginner_friendly` | Language appropriate for target learner |
| `jargon_explained` | All technical terms explained before/when used |
| `why_rag` | Explains the problem RAG solves |
| `rag_workflow` | Correct: Query → Retrieve → Augment → Generate |
| `example` | At least one concrete real-world example |
| `key_concept_coverage` | Embeddings, vector DB, retrieval all present |
| `coherent_teaching_flow` | Logical progression, simple → complex |
| `standalone` | Learner can understand without external resources |

---

## Key Design Decisions

### Why LangGraph instead of a while loop?
Explicit typed state + conditional edges = declarative retry logic.
New nodes (e.g. human-in-the-loop review) can be added without rewriting the loop.

### Why is the evaluator a separate agent?
It receives lesson + rubric + reference independently, without access to
the generator's prompts. This is what makes the quality gate meaningful.

### Why FAISS cached to disk?
Rebuilt once on first request, then reused. Saves embedding API cost.
Staleness is detected by comparing reference file mtime.

### Why temperature=0 for the evaluator?
Deterministic judgements. We don't want creative variation in PASS/FAIL decisions.

### Why is rubric a Pydantic object?
It's swappable per topic. A "Python Functions" topic can have a different rubric
than "Introduction to RAG" without any code changes.

---

## How to Add a New Node

1. Write the node function in `src/graph/nodes.py`
   - Receives `state: AgentState`
   - Returns `dict` with ONLY the keys it updates
2. Register in `workflow.py`: `graph.add_node("my_node", my_node_fn)`
3. Add edges: `graph.add_edge("previous_node", "my_node")`
4. Rebuild: `workflow = build_workflow()`

## How to Add a New Topic Reference

1. Create `references/{topic_slug}.md` with verified content
2. Add mapping in `src/knowledge/loader.py → get_reference_filename_for_topic()`
3. FAISS index is built automatically on first request

## How to Add a New Rubric Check

1. Add `RubricCheckDefinition(name="...", description="...")` to `Rubric.default_rag_rubric()`
2. The evaluator prompt automatically includes all checks
3. Add a corresponding test in `tests/test_evaluator.py`
