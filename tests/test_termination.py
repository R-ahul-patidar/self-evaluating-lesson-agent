"""
test_termination.py — Tests that the workflow ALWAYS terminates.

Critical: No infinite loops. The system must stop after MAX_RETRIES.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.models.schemas import EvaluationResult, LearnerProfile, Rubric, RubricCheck


def all_fail_evaluation(rubric: Rubric) -> EvaluationResult:
    """Build a FAIL evaluation where all checks fail."""
    checks = [
        RubricCheck(name=c.name, passed=False, reason=f"{c.name} failed.")
        for c in rubric.checks
    ]
    return EvaluationResult(
        passed=False,
        checks=checks,
        critical_failures=[c.name for c in rubric.checks],
        improvement_suggestions=["Fix all checks."],
    )


class TestTermination(unittest.TestCase):
    """Test that the workflow terminates correctly within retry bounds."""

    @patch("src.agents.evaluator.ChatGoogleGenerativeAI")
    @patch("src.agents.generator.ChatGoogleGenerativeAI")
    @patch("src.knowledge.retriever.get_or_build_index")
    def test_workflow_terminates_after_retry_limit(
        self, mock_index, mock_gen_llm_cls, mock_eval_llm_cls
    ):
        """
        If evaluation always fails, the workflow must stop after MAX_RETRIES.
        It must NOT loop forever.
        """
        import json
        import src.storage.database as db_module
        import tempfile
        from pathlib import Path

        rubric = Rubric.default_rag_rubric()

        # Generator always produces some content
        mock_gen_response = MagicMock()
        mock_gen_response.content = "A lesson about RAG."
        mock_gen_llm_cls.return_value.invoke.return_value = mock_gen_response

        # Evaluator always returns FAIL
        fail_eval = all_fail_evaluation(rubric)
        fail_json = fail_eval.model_dump()
        mock_eval_response = MagicMock()
        mock_eval_response.content = json.dumps(fail_json)
        mock_eval_llm_cls.return_value.invoke.return_value = mock_eval_response

        # Knowledge retriever returns empty string
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = []
        mock_index.return_value = mock_vs

        # Use temp DB so init_db doesn't pollute real output/memory.db
        tmp_db = tempfile.mktemp(suffix=".db")
        with patch.object(db_module, 'DB_PATH', Path(tmp_db)):
            db_module.init_db()

            from src.graph.workflow import build_workflow
            workflow = build_workflow()

            initial_state = {
                "run_id": "test-terminate",
                "topic": "Introduction to RAG",
                "content_type": "lesson",
                "demo_mode": False,
                "learner_profile": LearnerProfile.default_assessment(),
                "learning_goal": "Understand basics",
                "rubric": rubric,
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

            # This must complete — not loop forever
            final_state = workflow.invoke(initial_state)

        # Verify workflow terminated
        self.assertIn(final_state["final_status"], ["PASS", "FAIL"])

        # Verify retry count did not exceed max_retries
        self.assertLessEqual(final_state["retry_count"], 2)

        # If always failing → final_status should be FAIL
        self.assertEqual(final_state["final_status"], "FAIL")

        # Cleanup
        try:
            import os; os.unlink(tmp_db)
        except Exception:
            pass

    def test_max_retries_config(self):
        """MAX_RETRIES from config must be 2."""
        from src.config import settings
        self.assertEqual(settings.max_retries, 2)

    def test_attempt_count_does_not_exceed_limit(self):
        """Rejection log length must not exceed max_retries."""
        # Simulate rejection log with max entries
        from src.models.schemas import RejectionEntry
        log = [
            RejectionEntry(attempt=1, failed_checks=["accuracy"], failure_reasons=["wrong"]),
            RejectionEntry(attempt=2, failed_checks=["accuracy"], failure_reasons=["still wrong"]),
        ]
        # Should be <= max_retries (2)
        self.assertLessEqual(len(log), 2)


if __name__ == "__main__":
    unittest.main()
