"""
database.py — SQLite persistence layer for the memory/feedback system.

Schema: memory_feedback table stores recurring failure patterns.
This is the self-evolving mechanism: repeated failures sharpen future prompts.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from src.config import DB_PATH
from src.models.schemas import MemoryRecord


def init_db() -> None:
    """Initialize the database schema. Safe to call multiple times (CREATE IF NOT EXISTS)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_feedback (
                memory_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT NOT NULL,
                content_type    TEXT NOT NULL DEFAULT 'lesson',
                failure_type    TEXT NOT NULL,
                failure_reason  TEXT NOT NULL,
                suggested_correction TEXT NOT NULL,
                frequency       INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL,
                last_seen       TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_topic_failure
            ON memory_feedback (topic, failure_type)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS run_history (
                run_id          TEXT PRIMARY KEY,
                topic           TEXT NOT NULL,
                content_type    TEXT NOT NULL,
                final_status    TEXT NOT NULL,
                attempt_count   INTEGER NOT NULL,
                timestamp       TEXT NOT NULL,
                result_json     TEXT
            )
        """)
        conn.commit()


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields an open sqlite3 connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_memory(record: MemoryRecord) -> None:
    """
    Insert or update a memory record.
    If the same (topic, failure_type) exists, increment frequency and update last_seen.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT memory_id, frequency FROM memory_feedback WHERE topic = ? AND failure_type = ?",
            (record.topic, record.failure_type),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE memory_feedback SET frequency = ?, last_seen = ?, failure_reason = ?, suggested_correction = ? "
                "WHERE memory_id = ?",
                (
                    existing["frequency"] + 1,
                    now,
                    record.failure_reason,
                    record.suggested_correction,
                    existing["memory_id"],
                ),
            )
        else:
            conn.execute(
                "INSERT INTO memory_feedback (topic, content_type, failure_type, failure_reason, suggested_correction, frequency, created_at, last_seen) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    record.topic,
                    record.content_type,
                    record.failure_type,
                    record.failure_reason,
                    record.suggested_correction,
                    now,
                    now,
                ),
            )


def get_memory_for_topic(topic: str, content_type: str = "lesson", limit: int = 5) -> list[MemoryRecord]:
    """
    Retrieve the most frequent failure patterns for a given topic.
    These are passed to the Generator as historical feedback.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memory_feedback WHERE topic = ? AND content_type = ? "
            "ORDER BY frequency DESC LIMIT ?",
            (topic, content_type, limit),
        ).fetchall()

    return [
        MemoryRecord(
            memory_id=row["memory_id"],
            topic=row["topic"],
            content_type=row["content_type"],
            failure_type=row["failure_type"],
            failure_reason=row["failure_reason"],
            suggested_correction=row["suggested_correction"],
            frequency=row["frequency"],
            created_at=row["created_at"],
            last_seen=row["last_seen"],
        )
        for row in rows
    ]


def save_run_result(run_id: str, topic: str, content_type: str,
                    final_status: str, attempt_count: int, result_json: str) -> None:
    """Persist a completed run to run_history."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO run_history (run_id, topic, content_type, final_status, attempt_count, timestamp, result_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, topic, content_type, final_status, attempt_count,
             datetime.now(timezone.utc).isoformat(), result_json),
        )
