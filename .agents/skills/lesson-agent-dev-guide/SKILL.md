---
name: lesson-agent-dev-guide
description: >
  Developer workflow guide for the Self-Evaluating Lesson Agent.
  Use this skill when: setting up the project from scratch, running the dev
  server, configuring environment variables, understanding the live update
  polling flow, or preparing the Loom demo. Covers setup, run, env config,
  the demo_mode flag, and Loom walkthrough steps.
---

# Self-Evaluating Lesson Agent — Developer Guide Skill

## Quick Setup

```bash
# 1. Clone and enter project
cd self-evaluating-lesson-agent

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env file and add your Gemini API key
cp .env.example .env
# Edit .env and set: GEMINI_API_KEY=your_actual_key

# 5. Run the app
uvicorn src.main:app --reload

# 6. Open browser
# http://localhost:8000
```

---

## Required Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | — | Your Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-3.5-flash-lite` | LLM model name |
| `EMBEDDING_MODEL` | No | `models/gemini-embedding-001` | Embedding model |
| `TEMPERATURE` | No | `0.2` | Generator temperature (0.0 = deterministic) |
| `MAX_RETRIES` | No | `2` | Maximum regeneration attempts |
| `DB_PATH` | No | `output/memory.db` | SQLite database path |
| `FAISS_INDEX_PATH` | No | `output/faiss_index` | FAISS index cache directory |

---

## Running Tests

```bash
# Run all tests
.\venv\Scripts\pytest tests/ -v

# Run specific test file
.\venv\Scripts\pytest tests/test_evaluator.py -v
.\venv\Scripts\pytest tests/test_memory.py -v
.\venv\Scripts\pytest tests/test_dynamic_topic.py -v
.\venv\Scripts\pytest tests/test_termination.py -v
.\venv\Scripts\pytest tests/test_api.py -v

# Tests that require live Gemini API (skip in CI if no key):
# tests/test_workflow.py  ← end-to-end, needs API key
```

---

## UI Live Update (Polling) Flow

The UI does NOT block on the LLM call. Instead:

```
Browser                FastAPI              Background Thread
   |                      |                       |
   |-- POST /generate --→ |                       |
   |← { run_id } ---------|  spawns thread ------→|
   |                      |                       | running workflow...
   |-- GET /runs/{id} --→ |                       |
   |← { status: "running", steps: [...] } ------→|
   |  (every 2 seconds)                           | workflow completes
   |-- GET /runs/{id} --→ |                       |
   |← { status: "PASS", final_content: "..." }   |
   |  clearInterval, show results                 |
```

The `steps_completed` list in the run store is what drives the UI step indicators.
Each node in nodes.py appends a step identifier before returning.

---

## Demo Mode

When the user checks **Demo Mode** in the UI form:

1. `GenerateRequest.demo_mode = True` is sent to the API
2. In `node_generate_content`, `demo_mode=True` is passed to `generate_content()`
3. `DEMO_MODE_INJECTION` string is added to the generation prompt:
   > "You MUST include this EXACT incorrect statement: 'RAG retrains the language model whenever a new document is uploaded.'"
4. The generator embeds this incorrect claim in the lesson
5. The evaluator catches it → `accuracy → FAIL`
6. The regeneration prompt explicitly corrects it
7. The final lesson passes all checks

**What this demonstrates live:**
- The evaluator is independent and actually catches errors
- The regeneration uses targeted feedback (not a blind retry)
- The full loop: FAIL → feedback → regenerate → PASS

---

## FAISS Index Rebuild

The FAISS index is cached to `output/faiss_index/`.

- **First run**: index is built from `references/rag_fundamentals.md` (takes ~5s)
- **Subsequent runs**: index is loaded from disk (instant)
- **Force rebuild**: delete `output/faiss_index/` directory
- **Stale detection**: index is rebuilt if reference `.md` file is newer than the index metadata

---

## Loom Demo Walkthrough (15-20 min)

### Section 1 — Architecture Overview (3 min)
- Open `docs/architecture.md` in browser
- Walk through the LangGraph workflow diagram
- Explain the 5 components: Knowledge Layer, Generator, Evaluator, Regenerator, Memory

### Section 2 — Normal Run (5 min)
1. Open `http://localhost:8000`
2. Enter "Introduction to RAG", keep defaults, click Generate
3. Watch workflow steps appear progressively (polling)
4. Show all 10 rubric checks — all PASS
5. Show the final lesson content

### Section 3 — Demo Mode (Error Catching) (5 min)
1. Check "Demo Mode" checkbox
2. Click Generate
3. Watch: `content_generated` → `evaluation_failed_attempt_1: accuracy`
4. Show Evaluation panel: `accuracy → FAIL` with reason
5. Watch: `regenerated_attempt_2` → `evaluation_passed_attempt_2`
6. Show Rejection Log: Attempt 1, what failed, what changed
7. Show Final Lesson: PASSED, Attempts: 2

### Section 4 — Memory / Self-Evolving (3 min)
- Run a second generation for the same topic
- Show SQLite memory in `output/memory.db`
- Explain how past failures feed into future generator prompts

### Section 5 — Code Walkthrough (4 min)
- `src/graph/workflow.py` — show the conditional edge logic
- `src/prompts/regeneration.py` — show how failures are injected
- `src/agents/evaluator.py` — show temperature=0, JSON parsing
- `src/models/schemas.py` — show Pydantic models

---

## Adding a New Content Type

1. Add content type to `GenerateRequest` validation in `schemas.py`
2. Create a new rubric in `schemas.py` (e.g., `Rubric.default_quiz_rubric()`)
3. Update rubric selection logic in `routes.py` `_run_workflow()`:
   ```python
   rubric = Rubric.default_rag_rubric() if content_type == "lesson" else Rubric.default_quiz_rubric()
   ```
4. Add quiz-specific reference document to `references/`
5. No changes to Generator, Evaluator, LangGraph workflow, or UI needed

---

## Common Issues

| Issue | Cause | Fix |
|---|---|---|
| `GEMINI_API_KEY not set` | Missing .env | Copy `.env.example` to `.env` and add key |
| FAISS build error | Missing numpy | `pip install numpy` |
| `langchain_community not found` | Old requirements | `pip install langchain-community` |
| Evaluator always returns FAIL | JSON parse error | Check evaluator prompt; add logging |
| Polling never stops | Status never reaches PASS/FAIL | Check background thread for exceptions |
| Port 8000 in use | Another app running | `uvicorn src.main:app --port 8001` |
