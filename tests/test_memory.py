"""
test_memory.py — Tests for SQLite memory persistence.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestMemoryPersistence(unittest.TestCase):
    """Test that failure patterns are stored and retrieved across runs."""

    def setUp(self):
        """Use a temp database for each test."""
        self.tmp = tempfile.mktemp(suffix=".db")
        self.db_path = Path(self.tmp)

    def tearDown(self):
        try:
            if os.path.exists(self.tmp):
                os.unlink(self.tmp)
        except PermissionError:
            pass  # Windows may hold the file briefly; not critical for test cleanup

    def test_memory_upsert_and_retrieve(self):
        """A stored failure should be retrievable."""
        import src.storage.database as db_module
        from src.storage.database import init_db, upsert_memory, get_memory_for_topic
        from src.models.schemas import MemoryRecord

        with patch.object(db_module, 'DB_PATH', self.db_path):
            init_db()
            record = MemoryRecord(
                topic="Introduction to RAG",
                content_type="lesson",
                failure_type="jargon_explained",
                failure_reason="Embedding was not explained.",
                suggested_correction="Explain embedding with a simple analogy.",
            )
            upsert_memory(record)

            results = get_memory_for_topic("Introduction to RAG")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].failure_type, "jargon_explained")
            self.assertEqual(results[0].frequency, 1)

    def test_memory_frequency_increments_on_repeat(self):
        """Repeated failures for the same check should increment frequency."""
        import src.storage.database as db_module
        from src.storage.database import init_db, upsert_memory, get_memory_for_topic
        from src.models.schemas import MemoryRecord

        with patch.object(db_module, 'DB_PATH', self.db_path):
            init_db()
            record = MemoryRecord(
                topic="Introduction to RAG",
                content_type="lesson",
                failure_type="accuracy",
                failure_reason="Retraining claim.",
                suggested_correction="Remove retraining claim.",
            )
            upsert_memory(record)
            upsert_memory(record)  # Same failure again
            upsert_memory(record)  # Third time

            results = get_memory_for_topic("Introduction to RAG")
            accuracy_record = next(r for r in results if r.failure_type == "accuracy")
            self.assertEqual(accuracy_record.frequency, 3)

    def test_memory_returns_empty_for_new_topic(self):
        """A brand-new topic should have no memory records."""
        import src.storage.database as db_module
        from src.storage.database import init_db, get_memory_for_topic

        with patch.object(db_module, 'DB_PATH', self.db_path):
            init_db()
            results = get_memory_for_topic("A Brand New Topic Never Seen Before")
            self.assertEqual(results, [])

    def test_memory_format_for_prompt(self):
        """Memory records should format into a readable string for prompt injection."""
        from src.agents.memory import format_memory_for_prompt
        from src.models.schemas import MemoryRecord

        records = [
            MemoryRecord(
                topic="Introduction to RAG",
                content_type="lesson",
                failure_type="jargon_explained",
                failure_reason="Embedding not explained.",
                suggested_correction="Explain embedding with simple analogy.",
                frequency=3,
            )
        ]
        formatted = format_memory_for_prompt(records)
        self.assertIn("jargon_explained", formatted)
        self.assertIn("3 times", formatted)
        self.assertIn("Explain embedding", formatted)

    def test_empty_memory_returns_empty_string(self):
        """No memory records → empty string for prompt injection."""
        from src.agents.memory import format_memory_for_prompt
        result = format_memory_for_prompt([])
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
