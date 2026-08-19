"""
test_api.py — Integration tests for FastAPI routes.
Tests POST /generate, GET /runs/{id}, GET /health.
"""

from __future__ import annotations

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestAPIRoutes(unittest.TestCase):

    def setUp(self):
        with patch("src.storage.database.DB_PATH"):
            from src.main import app
            self.client = TestClient(app)

    def test_health_endpoint(self):
        """GET /health should return status ok."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("model", data)

    def test_home_returns_html(self):
        """GET / should return HTML."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_about_returns_html(self):
        """GET /about should return HTML."""
        response = self.client.get("/about")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    @patch("src.api.routes.workflow")
    @patch("src.api.routes.init_db")
    def test_post_generate_returns_run_id(self, mock_init_db, mock_workflow):
        """POST /generate should return a run_id immediately."""
        # Mock the workflow so it doesn't call Gemini
        mock_workflow.invoke.return_value = {
            "final_status": "PASS",
            "final_content": "A complete RAG lesson.",
            "evaluation": {
                "passed": True,
                "checks": [{"name": "accuracy", "passed": True, "reason": "OK"}],
                "critical_failures": [],
                "improvement_suggestions": [],
            },
            "rejection_log": [],
            "retry_count": 0,
            "steps_completed": ["request_received", "content_generated", "evaluation_passed_attempt_1", "finalized_pass"],
        }

        response = self.client.post("/generate", json={
            "topic": "Introduction to RAG",
            "content_type": "lesson",
            "education_level": "12th_grade",
            "english_level": "limited",
            "prior_knowledge": "none",
            "learning_goal": "Understand basics",
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertIsInstance(data["run_id"], str)
        self.assertGreater(len(data["run_id"]), 0)

    def test_post_generate_empty_topic_returns_422(self):
        """POST /generate with empty topic should return 422 validation error."""
        response = self.client.post("/generate", json={"topic": ""})
        self.assertEqual(response.status_code, 422)

    def test_post_generate_missing_topic_returns_422(self):
        """POST /generate with no topic field should return 422."""
        response = self.client.post("/generate", json={"content_type": "lesson"})
        self.assertEqual(response.status_code, 422)

    def test_get_run_not_found_returns_404(self):
        """GET /runs/{run_id} with unknown id should return 404."""
        response = self.client.get("/runs/nonexistent-run-id-12345")
        self.assertEqual(response.status_code, 404)

    @patch("src.api.routes.workflow")
    @patch("src.api.routes.init_db")
    def test_poll_endpoint_returns_structured_status(self, mock_init_db, mock_workflow):
        """GET /runs/{run_id} should return structured run status."""
        # Start a run to get a run_id
        mock_workflow.invoke.return_value = {
            "final_status": "PASS",
            "final_content": "Lesson content.",
            "evaluation": {
                "passed": True,
                "checks": [],
                "critical_failures": [],
                "improvement_suggestions": [],
            },
            "rejection_log": [],
            "retry_count": 0,
            "steps_completed": [],
        }

        post_response = self.client.post("/generate", json={"topic": "Python Functions"})
        run_id = post_response.json()["run_id"]

        # Poll the status — may need a brief wait for the background thread
        time.sleep(0.1)
        get_response = self.client.get(f"/runs/{run_id}")
        self.assertEqual(get_response.status_code, 200)

        data = get_response.json()
        self.assertIn("run_id", data)
        self.assertIn("status", data)
        self.assertIn("topic", data)
        self.assertEqual(data["topic"], "Python Functions")


if __name__ == "__main__":
    unittest.main()
