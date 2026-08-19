---
name: lesson-agent-testing
description: >
  Testing guide and test patterns for the Self-Evaluating Lesson Agent.
  Use this skill when: writing new tests, debugging failing tests, adding
  test coverage for new features, or understanding how to mock the Gemini
  API for unit tests. Covers mock patterns, test categories, and how to
  add tests for new rubric checks or workflow nodes.
---

# Self-Evaluating Lesson Agent — Testing Skill

## Test Categories

| File | Category | Needs API? |
|---|---|---|
| `test_evaluator.py` | Unit — Evaluator Agent | ❌ (mocked) |
| `test_termination.py` | Unit — Workflow termination | ❌ (mocked) |
| `test_memory.py` | Unit — SQLite memory | ❌ (temp DB) |
| `test_dynamic_topic.py` | Unit — Generic architecture | ❌ |
| `test_api.py` | Integration — FastAPI routes | ❌ (mocked) |
| `test_workflow.py` | End-to-end — Full loop | ✅ Real API |

---

## How to Mock the LLM

All unit tests mock `ChatGoogleGenerativeAI` so no API key is needed:

```python
from unittest.mock import MagicMock, patch
import json

@patch("src.agents.evaluator.ChatGoogleGenerativeAI")
def test_something(self, mock_llm_cls):
    # Build your desired response JSON
    response_json = {
        "passed": False,
        "checks": [
            {"name": "accuracy", "passed": False, "reason": "Incorrect claim."}
        ],
        "critical_failures": ["accuracy"],
        "improvement_suggestions": ["Fix the claim."]
    }
    mock_response = MagicMock()
    mock_response.content = json.dumps(response_json)
    mock_llm_cls.return_value.invoke.return_value = mock_response

    from src.agents.evaluator import evaluate_content
    result = evaluate_content(...)
    assert not result.passed
```

**Important**: Always patch at the point of USE, not the point of definition.
- Evaluator uses: `src.agents.evaluator.ChatGoogleGenerativeAI`
- Generator uses: `src.agents.generator.ChatGoogleGenerativeAI`

---

## How to Mock FAISS

```python
@patch("src.knowledge.retriever.get_or_build_index")
def test_something(self, mock_index):
    mock_vs = MagicMock()
    mock_vs.similarity_search.return_value = []   # or return mock docs
    mock_index.return_value = mock_vs
    ...
```

---

## How to Use a Temp SQLite Database

```python
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.patcher = patch("src.storage.database.DB_PATH", Path(self.tmp))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        os.unlink(self.tmp)
```

---

## Test Coverage Requirements

### 9 Required Tests (from assessment)

| Test | File | Status |
|---|---|---|
| Valid content → PASS | `test_evaluator.py::test_valid_content_passes` | ✅ |
| Accuracy error → FAIL | `test_evaluator.py::test_accuracy_fail_on_retrain_claim` | ✅ |
| Jargon unexplained → FAIL | `test_evaluator.py::test_jargon_fail_on_unexplained_term` | ✅ |
| Missing example → FAIL | `test_evaluator.py::test_missing_example_fails_example_check` | ✅ |
| FAIL → regenerate → re-evaluate | `test_termination.py::test_workflow_terminates_after_retry_limit` | ✅ |
| Termination after retry limit | `test_termination.py::test_workflow_terminates_after_retry_limit` | ✅ |
| Memory stored + retrieved | `test_memory.py::test_memory_upsert_and_retrieve` | ✅ |
| POST /generate returns structured output | `test_api.py::test_post_generate_returns_run_id` | ✅ |
| Non-RAG topic uses same workflow | `test_dynamic_topic.py::test_no_rag_specific_branching_in_workflow` | ✅ |

---

## How to Add a Test for a New Rubric Check

1. Create a helper function that returns a mock evaluation JSON where only that check fails:

```python
def make_my_new_check_fail_response() -> str:
    rubric = Rubric.default_rag_rubric()
    checks = []
    for c in rubric.checks:
        if c.name == "my_new_check":
            checks.append({
                "name": c.name,
                "passed": False,
                "reason": "Specific reason why it failed."
            })
        else:
            checks.append({"name": c.name, "passed": True, "reason": "OK"})
    return json.dumps({
        "passed": False,
        "checks": checks,
        "critical_failures": ["my_new_check"],
        "improvement_suggestions": ["Specific correction."]
    })
```

2. Write a test method that uses this response:

```python
@patch("src.agents.evaluator.ChatGoogleGenerativeAI")
def test_my_new_check_fails(self, mock_llm_cls):
    mock_response = MagicMock()
    mock_response.content = make_my_new_check_fail_response()
    mock_llm_cls.return_value.invoke.return_value = mock_response

    from src.agents.evaluator import evaluate_content
    result = evaluate_content(
        generated_content="Content that doesn't satisfy my_new_check.",
        learner_profile=make_learner(),
        rubric=make_rubric(),
        reference_context="",
    )
    self.assertFalse(result.passed)
    check = next(c for c in result.checks if c.name == "my_new_check")
    self.assertFalse(check.passed)
```

---

## How to Write a Full End-to-End Test

End-to-end tests hit the real Gemini API. Use a `@unittest.skipUnless` guard:

```python
import os
import unittest

@unittest.skipUnless(os.getenv("GEMINI_API_KEY"), "Requires GEMINI_API_KEY")
class TestEndToEnd(unittest.TestCase):
    def test_full_rag_workflow(self):
        from src.graph.workflow import workflow
        from src.models.schemas import LearnerProfile, Rubric

        initial_state = {
            "run_id": "e2e-test",
            "topic": "Introduction to RAG",
            "content_type": "lesson",
            "demo_mode": False,
            "learner_profile": LearnerProfile.default_assessment(),
            "learning_goal": "Understand basics",
            "rubric": Rubric.default_rag_rubric(),
            "reference_context": "",
            "generated_content": "",
            "evaluation": None,
            "retry_count": 0,
            "max_retries": 2,
            "rejection_log": [],
            "memory_feedback": [],
            "steps_completed": [],
            "current_step": "starting",
            "final_status": "pending",
            "final_content": "",
            "error": None,
        }
        final_state = workflow.invoke(initial_state)
        assert final_state["final_status"] in ["PASS", "FAIL"]
        assert final_state["final_content"]
        assert len(final_state["steps_completed"]) > 0
```

---

## Running Tests

```bash
# All unit tests (no API key needed)
.\venv\Scripts\pytest tests/test_evaluator.py tests/test_memory.py tests/test_dynamic_topic.py tests/test_termination.py tests/test_api.py -v

# With API key (end-to-end)
$env:GEMINI_API_KEY="your_key"; .\venv\Scripts\pytest tests/ -v

# With coverage report
.\venv\Scripts\pytest tests/ --cov=src --cov-report=term-missing
```

---

## Pytest Configuration

Add to project root `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```
