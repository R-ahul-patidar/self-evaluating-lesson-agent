"""
memory.py — Memory Agent: reads and writes feedback patterns to SQLite.

This is the self-evolving mechanism of the system.
- Before generation: load recurring failures for the topic → pass to Generator
- After a FAIL: persist the failure patterns for future runs
"""

from __future__ import annotations

from src.models.schemas import EvaluationResult, MemoryRecord
from src.storage.database import get_memory_for_topic, upsert_memory


def load_memory_feedback(topic: str, content_type: str = "lesson") -> list[MemoryRecord]:
    """
    Load historical failure patterns for this topic.
    Called at the start of a workflow run so the Generator can avoid repeat mistakes.
    """
    return get_memory_for_topic(topic, content_type)


def save_evaluation_failures(
    topic: str,
    content_type: str,
    evaluation: EvaluationResult,
) -> None:
    """
    Persist each failed rubric check as a memory record.
    Called after each FAIL evaluation so future runs learn from these failures.
    """
    for check in evaluation.checks:
        if not check.passed:
            # Find the corresponding improvement suggestion
            suggestion = next(
                (s for s in evaluation.improvement_suggestions if check.name.lower() in s.lower()),
                f"Fix the '{check.name}' rubric check.",
            )
            record = MemoryRecord(
                topic=topic,
                content_type=content_type,
                failure_type=check.name,
                failure_reason=check.reason,
                suggested_correction=suggestion,
            )
            upsert_memory(record)


def format_memory_for_prompt(records: list[MemoryRecord]) -> str:
    """
    Format memory records as a human-readable string for injection into prompts.

    Example output:
        Past failures for this topic (learn from these):
        - [jargon_explained] (seen 3 times): "Embedding was used without explanation."
          → Fix: Define embedding with a simple analogy before using the term.
    """
    if not records:
        return ""

    lines = ["Past failures for this topic (learn from these and avoid repeating them):"]
    for r in records:
        times = "time" if r.frequency == 1 else "times"
        lines.append(
            f"- [{r.failure_type}] (seen {r.frequency} {times}): \"{r.failure_reason}\"\n"
            f"  → Fix: {r.suggested_correction}"
        )
    return "\n".join(lines)
