"""
state.py — LangGraph typed state definition.

Every piece of data that flows through the workflow lives here.
Using TypedDict for LangGraph compatibility.
Keeping the state serializable for polling (the API reads from it).
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from src.models.schemas import (
    EvaluationResult,
    LearnerProfile,
    MemoryRecord,
    RejectionEntry,
    Rubric,
)


class AgentState(TypedDict, total=False):
    # ── Run metadata ──────────────────────────────────────────────────────────
    run_id: str
    topic: str
    content_type: str
    demo_mode: bool

    # ── Learner configuration ─────────────────────────────────────────────────
    learner_profile: LearnerProfile
    learning_goal: str

    # ── Rubric ────────────────────────────────────────────────────────────────
    rubric: Rubric

    # ── Knowledge layer ───────────────────────────────────────────────────────
    reference_context: str

    # ── Generation ────────────────────────────────────────────────────────────
    generated_content: str

    # ── Evaluation ────────────────────────────────────────────────────────────
    evaluation: Optional[EvaluationResult]

    # ── Retry control ─────────────────────────────────────────────────────────
    retry_count: int          # How many retries have happened (0 = first attempt)
    max_retries: int          # Maximum allowed retries

    # ── History ───────────────────────────────────────────────────────────────
    rejection_log: list[RejectionEntry]
    memory_feedback: list[MemoryRecord]

    # ── Workflow progress (for polling UI) ────────────────────────────────────
    steps_completed: list[str]
    current_step: str

    # ── Final output ──────────────────────────────────────────────────────────
    final_status: str          # "PASS" | "FAIL" | "pending"
    final_content: str
    error: Optional[str]
