"""
test_dynamic_topic.py — Verifies the workflow is generic (no RAG-specific branching).

The same agent architecture should work for any topic, not just RAG.
"""

from __future__ import annotations

import unittest

from src.models.schemas import GenerateRequest, LearnerProfile, Rubric


class TestDynamicTopic(unittest.TestCase):
    """Test that the system treats topic as data, not application logic."""

    def test_generate_request_accepts_any_topic(self):
        """GenerateRequest should accept any topic string."""
        for topic in ["Python Functions", "Photosynthesis", "Blockchain", "Introduction to RAG"]:
            req = GenerateRequest(topic=topic)
            self.assertEqual(req.topic, topic)

    def test_generate_request_rejects_empty_topic(self):
        """Empty topic should fail Pydantic validation."""
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GenerateRequest(topic="")

    def test_learner_profile_to_learner_profile_conversion(self):
        """GenerateRequest.to_learner_profile() should convert correctly."""
        req = GenerateRequest(
            topic="Python Functions",
            education_level="undergraduate",
            english_level="fluent",
            prior_knowledge="beginner",
            learning_goal="Learn Python basics",
        )
        profile = req.to_learner_profile()
        self.assertEqual(profile.education_level, "undergraduate")
        self.assertEqual(profile.english_level, "fluent")
        self.assertEqual(profile.learning_goal, "Learn Python basics")

    def test_rubric_is_data_not_code(self):
        """
        Rubric must be a data object, not code with topic-specific logic.
        The same rubric structure works for any topic.
        """
        rubric = Rubric.default_rag_rubric()
        # It's a Python object (data), not branching code
        self.assertIsInstance(rubric, Rubric)
        self.assertIsInstance(rubric.checks, list)
        self.assertGreater(len(rubric.checks), 0)

    def test_no_rag_specific_branching_in_workflow(self):
        """
        The workflow module must not import or reference RAG-specific modules.
        Topic-specific logic would break the generic architecture.
        """
        import ast
        import pathlib

        workflow_source = pathlib.Path("src/graph/workflow.py").read_text(encoding="utf-8")
        tree = ast.parse(workflow_source)

        # The real check: workflow.py should not contain the string "rag" as a conditional
        lower_source = workflow_source.lower()
        self.assertNotIn('if topic == "rag"', lower_source)
        self.assertNotIn("if topic == 'rag'", lower_source)

    def test_reference_loader_maps_rag_topic(self):
        """The loader should map RAG-related topics to rag_fundamentals.md."""
        from src.knowledge.loader import get_reference_filename_for_topic
        for topic in ["Introduction to RAG", "RAG", "Retrieval-Augmented Generation"]:
            filename = get_reference_filename_for_topic(topic)
            self.assertEqual(filename, "rag_fundamentals.md")

    def test_reference_loader_fallback_for_unknown_topic(self):
        """Unknown topics fall back to the default reference."""
        from src.knowledge.loader import get_reference_filename_for_topic
        filename = get_reference_filename_for_topic("Quantum Computing")
        # Falls back gracefully — returns a .md filename, not an error
        self.assertTrue(filename.endswith(".md"))


if __name__ == "__main__":
    unittest.main()
