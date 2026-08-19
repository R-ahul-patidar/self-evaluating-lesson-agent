# Self-Evaluating Lesson Agent

An agentic AI content platform built with **LangGraph**, **Google Gemini**, **FAISS**, and **FastAPI** that autonomously generates educational lessons, evaluates its own quality against a strict 10-check PASS/FAIL rubric, and iteratively self-corrects until the content is ready to ship — without human intervention.

> **Target Audience:** 12th-grade graduate from India, limited English vocabulary, non-English-medium background, starting AI from zero.  
> **Primary Demonstration Topic:** Introduction to RAG (Retrieval-Augmented Generation)

---

## 📑 Table of Contents

- [What It Does](#-what-it-does)
- [Target Learner Profile](#-target-learner-profile)
- [System Architecture & LangGraph Workflow](#-system-architecture--langgraph-workflow)
- [Code Traceability Matrix](#-code-traceability-matrix)
- [The 10-Check Evaluation Rubric](#-the-10-check-evaluation-rubric)
- [Self-Evolving Memory System](#-self-evolving-memory-system)
- [Quick Start & Setup](#-quick-start--setup)
- [API Contract & Polling Flow](#-api-contract--polling-flow)
- [Testing Suite](#-testing-suite)
- [Demo Mode & Loom Walkthrough Guide](#-demo-mode--loom-walkthrough-guide)
- [Project Directory Structure](#-project-directory-structure)
- [Design Decisions & Architecture Rules](#-design-decisions--architecture-rules)

---

## 🎯 What It Does

The system **does not trust its first generation**. Instead, it executes an autonomous quality control loop:

```
User enters a topic (e.g., "Introduction to RAG")
       │
       ▼
1. RETRIEVE ──── Query FAISS vector store (models/gemini-embedding-001)
       │
       ▼
2. GENERATE ──── Generator Agent creates beginner lesson (gemini-3.5-flash-lite)
       │
       ▼
3. EVALUATE ──── Evaluator Agent checks 10 hard PASS/FAIL rubric criteria (temp=0.0)
       │
       ├──► ALL PASS ──► Finalize & Ship ──► Persist run to SQLite
       │
       └──► ANY FAIL ──► Extract root causes & actionable suggestions
                             │
                             ▼
4. EVOLVE   ──── Persist failure patterns to SQLite memory
                             │
                             ▼
5. RETRY    ──── Regenerate with targeted feedback (Max 2 retries)
                             │
                             └──► Loops back to Step 2 (GENERATE with feedback)
```

---

## 🎓 Target Learner Profile

The system explicitly models the target learner in state and prompts:

| Attribute | Specification | Design Impact |
|---|---|---|
| **Education Level** | 12th-Grade Graduate | Concepts explained from foundational first principles. |
| **Regional Context** | India | Culturally relevant, relatable real-world analogies. |
| **Language Ability** | Limited English vocabulary | Plain English, short sentences, zero unexplained jargon. |
| **AI Knowledge** | None (Absolute Beginner) | Assumes zero prior knowledge of ML, vectors, or embeddings. |
| **Learning Goal** | Kickstart AI career | Focus on *what it is*, *why it matters*, and *how it works step-by-step*. |

---

## 🏗️ System Architecture & LangGraph Workflow

```
                    ┌─────────────────────────┐
                    │      Incoming POST      │
                    │       /generate         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   node_prepare_request  │
                    │ (Load memory & state)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ node_retrieve_reference │
                    │ (FAISS Vector Search)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  node_generate_content  │
                    │   (Generator Agent)     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
         ┌─────────►│  node_evaluate_content  │
         │          │   (Evaluator Agent)     │
         │          └────────────┬────────────┘
         │                       │
         │          ┌────────────▼────────────┐
         │          │ _decide_after_evaluation│
         │          └──────┬────────────┬─────┘
         │                 │            │
  (FAIL + Retries < 2)     │            │ (ALL PASS or Retries >= 2)
         │                 │            │
┌────────┴──────────────┐  │   ┌────────▼──────────────┐
│node_regenerate_content│◄─┘   │     node_finalize     │
│ (Inject failure diffs │      │(Ship lesson/rejection)│
│  & update SQLite DB)  │      └────────┬──────────────┘
└───────────────────────┘               │
                               ┌────────▼──────────────┐
                               │          END          │
                               └───────────────────────┘
```

### Key Architectural Principles

1. **Independent Evaluator:** The Evaluator Agent operates in an isolated context with `temperature=0.0`. It receives only the generated lesson, rubric, and reference text — never the Generator's internal system prompts.
2. **Topic is Data, Not Code:** There is no `if topic == "RAG"` branching. The workflow is completely generic and functions for any educational topic.
3. **Guaranteed Bounded Termination:** Enforced via LangGraph conditional edges with `max_retries = 2`. The loop is mathematically guaranteed to terminate.
4. **Targeted Failure Injection:** Regeneration is NOT a blind re-run. Specific failed check names, evaluator reasons, and required corrections are injected into the prompt.

---

## 🗺️ Code Traceability Matrix

This matrix maps every requirement from the Take-Home Assessment directly to the source code implementation:

| Assessment Requirement | Primary File(s) | Primary Function / Class / Object |
|---|---|---|
| **Learner Profile Modeling** | `src/models/schemas.py`<br>`src/prompts/generator.py` | `LearnerProfile`<br>`build_generation_prompt()` |
| **Grounded Reference Retrieval** | `references/rag_fundamentals.md`<br>`src/knowledge/loader.py`<br>`src/knowledge/embeddings.py`<br>`src/knowledge/retriever.py` | `load_and_chunk_reference()`<br>`build_faiss_index()`<br>`retrieve_context()` |
| **Generator Agent** | `src/agents/generator.py`<br>`src/prompts/generator.py` | `generate_content()`<br>`GENERATOR_SYSTEM_PROMPT` |
| **Evaluator Agent (temp=0.0)** | `src/agents/evaluator.py`<br>`src/prompts/evaluator.py` | `evaluate_content()`<br>`_get_evaluator_llm()` |
| **10-Check PASS/FAIL Rubric** | `src/models/schemas.py` | `Rubric.default_rag_rubric()`<br>`EvaluationResult`<br>`RubricCheck` |
| **Regeneration with Feedback** | `src/agents/generator.py`<br>`src/prompts/regeneration.py` | `regenerate_content()`<br>`build_regeneration_prompt()` |
| **LangGraph Orchestration** | `src/graph/state.py`<br>`src/graph/nodes.py`<br>`src/graph/workflow.py` | `AgentState`<br>`_decide_after_evaluation()`<br>`build_workflow()` |
| **Rejection Log Output** | `src/models/schemas.py`<br>`src/graph/nodes.py` | `RejectionEntry`<br>`node_finalize()` |
| **Self-Evolving SQLite Memory** | `src/storage/database.py`<br>`src/agents/memory.py` | `upsert_memory()`<br>`get_memory_for_topic()`<br>`format_memory_for_prompt()` |
| **FastAPI Backend & Polling** | `src/main.py`<br>`src/api/routes.py` | `app`<br>`start_generate()`<br>`get_run_status()` |
| **Interactive UI** | `templates/index.html`<br>`static/js/app.js`<br>`static/css/style.css` | `startGeneration()`<br>`pollRunStatus()`<br>`updateWorkflowSteps()` |
| **Deliberate Error Demo Mode** | `src/prompts/generator.py`<br>`templates/index.html` | `DEMO_MODE_INJECTION`<br>`#demo_mode` checkbox |

---

## 📊 The 10-Check Evaluation Rubric

Every lesson is evaluated against 10 strict boolean checkpoints with zero partial credit:

| # | Check Name | What It Verifies |
|---|---|---|
| 1 | `accuracy` | No materially incorrect technical claims (e.g. catches false retraining claims). |
| 2 | `grounding` | Important factual claims match the verified reference knowledge base. |
| 3 | `beginner_friendly` | Language and sentence structure suitable for limited-English learners. |
| 4 | `jargon_explained` | Every technical term is clearly defined with a simple analogy before/when used. |
| 5 | `why_rag` | Clearly explains the problem RAG solves (hallucinations & static training data). |
| 6 | `rag_workflow` | Step-by-step workflow: Query → Retrieve → Augment → Generate. |
| 7 | `example` | Contains at least one concrete, real-world scenario (e.g. customer support manual). |
| 8 | `key_concept_coverage` | Covers: Knowledge Base, Embeddings, Vector Database, Retrieval, Context, Generation. |
| 9 | `coherent_teaching_flow` | Logical progression from simple concepts to technical mechanics without jumping. |
| 10 | `standalone` | Self-contained; learner grasps the core concepts without needing external search. |

---

## 🧠 Self-Evolving Memory System

The platform learns from past failures through an embedded SQLite database (`output/memory.db`):

1. **Failure Logging:** When any rubric check fails, `save_evaluation_failures()` records the topic, failed check name, evaluator reason, and suggested correction.
2. **Frequency Weighting:** If the same check fails multiple times across runs, the `frequency` counter increments and updates `last_seen`.
3. **Prompt Sharpening:** At the start of every new run, `load_memory_feedback()` retrieves the top historical pitfalls and injects them directly into the Generator's prompt:

```markdown
## ⚠️ Historical Failures (Avoid these mistakes from past attempts)
- [jargon_explained] (seen 3 times): "Embedding was used without explanation."
  → Fix: Define embedding with a simple analogy before using the term.
```

---

## 🚀 Quick Start & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Google Gemini API Key ([Get a free API key here](https://aistudio.google.com/))

### Installation Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/self-evaluating-lesson-agent.git
cd self-evaluating-lesson-agent

# 2. Create and activate a virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env

# Edit .env and paste your Gemini API key:
# GEMINI_API_KEY=AIzaSy...
```

### Running the Application

```bash
# Start the FastAPI server with live reloading
uvicorn src.main:app --reload

# Alternatively:
# python src/main.py
```

Open your browser and navigate to: **`http://localhost:8000`**

---

## 🔌 API Contract & Polling Flow

The application uses an asynchronous background execution pattern with client-side polling:

```
Browser                          FastAPI (Port 8000)               Background Worker
   │                                      │                                │
   ├── POST /generate (JSON body) ───────►│                                │
   │                                      ├── Spawns thread ──────────────►│ (Runs LangGraph)
   │◄── 200 OK { run_id: "uuid" } ────────┤                                │
   │                                      │                                │
   │─── GET /runs/{run_id} (every 2s) ───►│                                │
   │◄── 200 OK { status: "running", ... }─┤                                │
   │                                      │                                │
   │─── GET /runs/{run_id} ──────────────►│                                │
   │◄── 200 OK { status: "PASS", ... } ───┤◄── Updates run_store ──────────┤ (Graph ends)
   │                                      │
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the Jinja2 HTML dashboard. |
| `POST` | `/generate` | Validates `GenerateRequest`, spawns background graph, returns `{ run_id }`. |
| `GET` | `/runs/{run_id}` | Returns current execution snapshot (`RunStatus`) polled every 2s. |
| `GET` | `/health` | Health check endpoint returning model and timestamp. |

---

## 🧪 Testing Suite

All unit tests use mocked LLM responses so they can run without a live API key or internet access:

```bash
# Run the complete test suite
pytest -v

# Run individual test modules
pytest tests/test_evaluator.py -v     # Evaluator agent, schema validation & JSON parsing
pytest tests/test_memory.py -v        # SQLite memory persistence & frequency counter
pytest tests/test_dynamic_topic.py -v # Topic-as-data & generic workflow verification
pytest tests/test_termination.py -v   # Max retries & guaranteed loop termination
pytest tests/test_api.py -v           # FastAPI endpoints, validation & status polling
```

---

## 🎬 Demo Mode & Loom Walkthrough Guide

The UI features a built-in **Demo Mode** switch specifically designed for the assessment video demonstration.

### Recommended 15–20 Minute Video Structure

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Introduction & Architecture Overview (3–4 mins)                    │
│    • Show docs/architecture.md and explain LangGraph state flow.       │
│    • Explain Generator vs. Evaluator independence (temp=0.0).          │
│                                                                        │
│ 2. Standard Passing Run (4–5 mins)                                     │
│    • Generate "Introduction to RAG" with standard settings.            │
│    • Observe live step-by-step progress cards updating via polling.   │
│    • Review the 10/10 PASS evaluation table and final lesson.          │
│                                                                        │
│ 3. Deliberate Error Catching & Auto-Healing (5–6 mins)                 │
│    • Turn ON the "Demo Mode" toggle in the UI.                         │
│    • System injects deliberate fallacy: "RAG retrains model on upload".│
│    • Watch Evaluator catch it: accuracy → FAIL on Attempt 1.           │
│    • Inspect the Rejection Log (failure reasons + planned corrections).│
│    • Watch Attempt 2 regenerate, correct the error, and PASS.          │
│                                                                        │
│ 4. Self-Evolving Memory & Code Walkthrough (3–4 mins)                  │
│    • Inspect output/memory.db to show how failure patterns persist.    │
│    • Show Code Traceability Matrix and explain trade-off decisions.    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Directory Structure

```
self-evaluating-lesson-agent/
├── .agents/                    # Agent skills, rules, and architecture specs
├── docs/
│   ├── architecture.md         # In-depth architectural breakdown & data flow
│   └── design_decisions.md     # Rationale for framework, model, & storage choices
├── output/
│   ├── faiss_index/            # Cached FAISS vector database
│   └── memory.db               # Persisted SQLite memory & run history
├── references/
│   └── rag_fundamentals.md     # Ground truth knowledge base document
├── src/
│   ├── agents/
│   │   ├── generator.py        # Generator Agent (content creation & rewrite)
│   │   ├── evaluator.py        # Evaluator Agent (temp=0.0 strict quality gate)
│   │   └── memory.py           # Self-evolving SQLite memory manager
│   ├── api/
│   │   └── routes.py           # FastAPI endpoints & background execution
│   ├── graph/
│   │   ├── state.py            # TypedDict AgentState definition
│   │   ├── nodes.py            # LangGraph step functions
│   │   └── workflow.py         # Graph assembly & conditional retry edges
│   ├── knowledge/
│   │   ├── embeddings.py       # Google Generative AI embeddings & FAISS index
│   │   ├── loader.py           # Markdown chunker & reference loader
│   │   └── retriever.py        # Similarity search retrieval interface
│   ├── models/
│   │   └── schemas.py          # Pydantic data contracts (API, Rubric, Evaluation)
│   ├── prompts/
│   │   ├── generator.py        # Generation prompt templates
│   │   ├── evaluator.py        # Strict JSON evaluation prompt templates
│   │   └── regeneration.py     # Targeted feedback regeneration templates
│   ├── storage/
│   │   └── database.py         # SQLite schema, tables & queries
│   ├── config.py               # Pydantic Settings environment configuration
│   └── main.py                 # FastAPI application entrypoint
├── static/
│   ├── css/style.css           # Modern dark-theme responsive UI styles
│   └── js/app.js               # Vanilla JS polling & UI state controller
├── templates/
│   ├── base.html               # Jinja2 base layout template
│   └── index.html              # Main dashboard template
├── tests/                      # Comprehensive unit & integration tests
├── .env.example                # Example environment configuration template
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## ⚖️ Design Decisions & Architecture Rules

- **Why LangGraph instead of a while loop?** Explicit typed state, declarative retry edges, and inspectable node execution.
- **Why temperature=0.0 for Evaluator?** Quality evaluation must be deterministic and objective; randomness is a defect in a quality gate.
- **Why FAISS with local caching?** Zero external cloud database dependencies; fast local similarity search with disk cache validated by document timestamps (`ref_mtime`).
- **Why SQLite for memory?** Built into Python stdlib, zero setup overhead, easily inspectable, and persistent across application restarts.
- **Why Vanilla JS with 2s polling?** Lightweight, resilient, and eliminates complex WebSocket connection state management while delivering real-time UX.