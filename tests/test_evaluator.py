"""
test_evaluator.py — Unit tests for the Evaluator Agent.

Tests cover: valid content → PASS, deliberate errors → specific FAIL checks.
These tests use mock content so they don't require a live Gemini API call.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from src.models.schemas import EvaluationResult, LearnerProfile, Rubric, RubricCheck


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_learner() -> LearnerProfile:
    return LearnerProfile.default_assessment()


def make_rubric() -> Rubric:
    return Rubric.default_rag_rubric()


def make_all_pass_response() -> str:
    """A mock evaluator JSON response where all checks pass."""
    rubric = make_rubric()
    checks = [{"name": c.name, "passed": True, "reason": "Criterion fully met."} for c in rubric.checks]
    return json.dumps({
        "passed": True,
        "checks": checks,
        "critical_failures": [],
        "improvement_suggestions": [],
    })


def make_accuracy_fail_response() -> str:
    """Evaluator response where accuracy fails due to retraining claim."""
    rubric = make_rubric()
    checks = []
    for c in rubric.checks:
        if c.name == "accuracy":
            checks.append({
                "name": c.name,
                "passed": False,
                "reason": "The lesson states 'RAG retrains the language model whenever a document is uploaded' which is incorrect. RAG does not retrain the model.",
            })
        else:
            checks.append({"name": c.name, "passed": True, "reason": "Criterion met."})
    return json.dumps({
        "passed": False,
        "checks": checks,
        "critical_failures": ["accuracy"],
        "improvement_suggestions": ["Remove the incorrect claim about retraining. RAG retrieves context at query time; it does not modify model weights."],
    })


def make_jargon_fail_response() -> str:
    """Evaluator response where jargon check fails."""
    rubric = make_rubric()
    checks = []
    for c in rubric.checks:
        if c.name == "jargon_explained":
            checks.append({
                "name": c.name,
                "passed": False,
                "reason": "'Embedding' is used without explanation. The learner does not know what an embedding is.",
            })
        else:
            checks.append({"name": c.name, "passed": True, "reason": "Criterion met."})
    return json.dumps({
        "passed": False,
        "checks": checks,
        "critical_failures": ["jargon_explained"],
        "improvement_suggestions": ["Explain 'embedding' as a list of numbers representing the meaning of text, using a simple analogy."],
    })


def make_missing_example_response() -> str:
    """Evaluator response where example check fails."""
    rubric = make_rubric()
    checks = []
    for c in rubric.checks:
        if c.name == "example":
            checks.append({
                "name": c.name,
                "passed": False,
                "reason": "No concrete real-world example is provided in the lesson.",
            })
        else:
            checks.append({"name": c.name, "passed": True, "reason": "Criterion met."})
    return json.dumps({
        "passed": False,
        "checks": checks,
        "critical_failures": ["example"],
        "improvement_suggestions": ["Add a concrete example such as a customer support chatbot that uses RAG to answer questions from a company manual."],
    })


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEvaluatorSchemas(unittest.TestCase):
    """Test that Pydantic evaluation schemas work correctly."""

    def test_evaluation_result_all_pass(self):
        """Valid lesson should produce passed=True when all checks pass."""
        rubric = make_rubric()
        checks = [RubricCheck(name=c.name, passed=True, reason="OK") for c in rubric.checks]
        result = EvaluationResult(
            passed=True,
            checks=checks,
            critical_failures=[],
            improvement_suggestions=[],
        )
        self.assertTrue(result.passed)
        self.assertEqual(len(result.checks), len(rubric.checks))
        self.assertEqual(result.critical_failures, [])

    def test_evaluation_result_with_failure(self):
        """Accuracy failure should produce passed=False."""
        checks = [
            RubricCheck(name="accuracy", passed=False, reason="Incorrect retraining claim."),
            RubricCheck(name="grounding", passed=True, reason="OK"),
        ]
        result = EvaluationResult(
            passed=False,
            checks=checks,
            critical_failures=["accuracy"],
            improvement_suggestions=["Remove incorrect claim."],
        )
        self.assertFalse(result.passed)
        self.assertIn("accuracy", result.critical_failures)

    def test_rubric_has_all_expected_checks(self):
        """Default RAG rubric must have exactly 10 checks."""
        rubric = make_rubric()
        expected_names = {
            "accuracy", "grounding", "beginner_friendly", "jargon_explained",
            "why_rag", "rag_workflow", "example", "key_concept_coverage",
            "coherent_teaching_flow", "standalone"
        }
        actual_names = {c.name for c in rubric.checks}
        self.assertEqual(actual_names, expected_names)


class TestEvaluatorAgent(unittest.TestCase):
    """Test the Evaluator Agent with mocked LLM responses."""

    @patch("src.agents.evaluator.ChatGoogleGenerativeAI")
    def test_valid_content_passes(self, mock_llm_cls):
        """A well-written lesson should produce all PASS checks."""
        mock_response = MagicMock()
        mock_response.content = make_all_pass_response()
        mock_llm_cls.return_value.invoke.return_value = mock_response

        from src.agents.evaluator import evaluate_content
        result = evaluate_content(
            generated_content="A comprehensive lesson on RAG with examples.",
            learner_profile=make_learner(),
            rubric=make_rubric(),
            reference_context="RAG retrieves context at query time.",
        )
        self.assertTrue(result.passed)
        self.assertTrue(all(c.passed for c in result.checks))

    @patch("src.agents.evaluator.ChatGoogleGenerativeAI")
    def test_accuracy_fail_on_retrain_claim(self, mock_llm_cls):
        """Lesson with retraining claim should trigger accuracy FAIL."""
        mock_response = MagicMock()
        mock_response.content = make_accuracy_fail_response()
        mock_llm_cls.return_value.invoke.return_value = mock_response

        from src.agents.evaluator import evaluate_content
        result = evaluate_content(
            generated_content="RAG retrains the language model whenever a document is uploaded.",
            learner_profile=make_learner(),
            rubric=make_rubric(),
            reference_context="",
        )
        self.assertFalse(result.passed)
        accuracy_check = next(c for c in result.checks if c.name == "accuracy")
        self.assertFalse(accuracy_check.passed)
        self.assertIn("accuracy", result.critical_failures)

    @patch("src.agents.evaluator.ChatGoogleGenerativeAI")
    def test_jargon_fail_on_unexplained_term(self, mock_llm_cls):
        """Lesson using 'embedding' without explanation should fail jargon check."""
        mock_response = MagicMock()
        mock_response.content = make_jargon_fail_response()
        mock_llm_cls.return_value.invoke.return_value = mock_response

        from src.agents.evaluator import evaluate_content
        result = evaluate_content(
            generated_content="RAG uses embedding to find similar documents.",
            learner_profile=make_learner(),
            rubric=make_rubric(),
            reference_context="",
        )
        self.assertFalse(result.passed)
        jargon_check = next(c for c in result.checks if c.name == "jargon_explained")
        self.assertFalse(jargon_check.passed)

    @patch("src.agents.evaluator.ChatGoogleGenerativeAI")
    def test_missing_example_fails_example_check(self, mock_llm_cls):
        """Lesson without examples should fail the example check."""
        mock_response = MagicMock()
        mock_response.content = make_missing_example_response()
        mock_llm_cls.return_value.invoke.return_value = mock_response

        from src.agents.evaluator import evaluate_content
        result = evaluate_content(
            generated_content="RAG is a retrieval technique. It retrieves documents.",
            learner_profile=make_learner(),
            rubric=make_rubric(),
            reference_context="",
        )
        self.assertFalse(result.passed)
        example_check = next(c for c in result.checks if c.name == "example")
        self.assertFalse(example_check.passed)

    @patch("src.agents.evaluator.ChatGoogleGenerativeAI")
    def test_malformed_json_returns_fallback(self, mock_llm_cls):
        """Evaluator should gracefully handle unparseable LLM responses."""
        mock_response = MagicMock()
        mock_response.content = "I cannot evaluate this lesson at this time."
        mock_llm_cls.return_value.invoke.return_value = mock_response

        from src.agents.evaluator import evaluate_content
        result = evaluate_content(
            generated_content="Some content.",
            learner_profile=make_learner(),
            rubric=make_rubric(),
            reference_context="",
        )
        # Should return a safe fallback, not raise
        self.assertIsInstance(result, EvaluationResult)
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
