"""
schemas.py — All Pydantic models used across the entire application.

These models serve as the single source of truth for:
  - API request / response shapes
  - LangGraph state sub-types
  - Evaluator structured output
  - SQLite memory records
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


# ── Learner Profile ───────────────────────────────────────────────────────────

class LearnerProfile(BaseModel):
    """Represents the target learner for whom the lesson is generated."""
    education_level: str = Field(default="12th_grade", description="e.g. 12th_grade, undergraduate")
    english_level: str = Field(default="limited", description="native | fluent | intermediate | limited | none")
    prior_knowledge: str = Field(default="none", description="none | beginner | intermediate | advanced")
    country_context: str = Field(default="India")
    learning_goal: str = Field(default="Understand the basics from zero")

    @classmethod
    def default_assessment(cls) -> "LearnerProfile":
        """The default 12th-grade Indian beginner profile from the assessment."""
        return cls(
            education_level="12th_grade",
            english_level="limited",
            prior_knowledge="none",
            country_context="India",
            learning_goal="Understand the topic from zero and kickstart an AI career",
        )


# ── Rubric ────────────────────────────────────────────────────────────────────

class RubricCheckDefinition(BaseModel):
    """A single rubric check definition (what to evaluate and why)."""
    name: str
    description: str
    required: bool = True


class Rubric(BaseModel):
    """A complete evaluation rubric — represented as config/data, not code."""
    name: str
    checks: list[RubricCheckDefinition]

    @classmethod
    def default_rag_rubric(cls) -> "Rubric":
        return cls(
            name="RAG Lesson Rubric",
            checks=[
                RubricCheckDefinition(name="accuracy", description="No materially incorrect technical claims about RAG."),
                RubricCheckDefinition(name="grounding", description="Important factual claims are consistent with the provided reference material."),
                RubricCheckDefinition(name="beginner_friendly", description="Language is appropriate for the target learner (limited English, no AI background)."),
                RubricCheckDefinition(name="jargon_explained", description="All important technical terms (embeddings, vector DB, retrieval, etc.) are explained before or when used."),
                RubricCheckDefinition(name="why_rag", description="The lesson clearly explains the problem RAG solves and why it is useful."),
                RubricCheckDefinition(name="rag_workflow", description="The lesson correctly explains the full RAG workflow: Question → Retrieve → Augment context → Generate answer."),
                RubricCheckDefinition(name="example", description="At least one concrete, beginner-friendly real-world example is present."),
                RubricCheckDefinition(name="key_concept_coverage", description="Core concepts are all present: embeddings, vector database, retrieval, context, generation."),
                RubricCheckDefinition(name="coherent_teaching_flow", description="The lesson progresses logically from simple to complex, not jumping around."),
                RubricCheckDefinition(name="standalone", description="A learner can understand the core concept without needing any external resources."),
            ],
        )


# ── Evaluation ────────────────────────────────────────────────────────────────

class RubricCheck(BaseModel):
    """Result of a single rubric check — strictly PASS or FAIL."""
    name: str
    passed: bool
    reason: str


class EvaluationResult(BaseModel):
    """Full structured evaluation output from the Evaluator Agent."""
    passed: bool = Field(description="True only if ALL checks passed.")
    checks: list[RubricCheck]
    critical_failures: list[str] = Field(default_factory=list, description="Short summary of each failed check.")
    improvement_suggestions: list[str] = Field(default_factory=list, description="Specific, actionable corrections the Generator must make.")


# ── Rejection Log ─────────────────────────────────────────────────────────────

class RejectionEntry(BaseModel):
    """Records a single failed generation attempt."""
    attempt: int
    status: str = "REJECTED"
    failed_checks: list[str]
    failure_reasons: list[str]
    changes_made: str = ""  # Populated after regeneration
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Memory ────────────────────────────────────────────────────────────────────

class MemoryRecord(BaseModel):
    """A persisted failure pattern used for self-evolving behaviour."""
    memory_id: Optional[int] = None
    topic: str
    content_type: str
    failure_type: str   # maps to rubric check name
    failure_reason: str
    suggested_correction: str
    frequency: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── API Request / Response ────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Incoming API request to generate a lesson."""
    topic: str = Field(..., min_length=1, max_length=200, description="The topic to teach.")
    content_type: str = Field(default="lesson")
    education_level: str = Field(default="12th_grade")
    english_level: str = Field(default="limited")
    prior_knowledge: str = Field(default="none")
    country_context: str = Field(default="India")
    learning_goal: str = Field(default="Understand the basics from zero")
    reference_source: str = Field(default="default", description="Which reference document set to use.")
    demo_mode: bool = Field(default=False, description="If True, inject deliberate error for demonstration.")

    def to_learner_profile(self) -> LearnerProfile:
        return LearnerProfile(
            education_level=self.education_level,
            english_level=self.english_level,
            prior_knowledge=self.prior_knowledge,
            country_context=self.country_context,
            learning_goal=self.learning_goal,
        )


class RunStatus(BaseModel):
    """Snapshot of a workflow run — polled by the UI every 2 seconds."""
    run_id: str
    topic: str
    status: str = "running"   # running | PASS | FAIL
    current_step: str = "initializing"
    steps_completed: list[str] = Field(default_factory=list)
    attempt: int = 0
    max_attempts: int = 3
    evaluation: Optional[EvaluationResult] = None
    rejection_log: list[RejectionEntry] = Field(default_factory=list)
    final_content: Optional[str] = None
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    """Final complete response returned when the workflow finishes."""
    run_id: str
    topic: str
    content_type: str
    final_status: str   # PASS | FAIL
    attempt_count: int
    final_content: str
    evaluation: EvaluationResult
    rejection_log: list[RejectionEntry]
    memory_feedback_used: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class StartRunResponse(BaseModel):
    """Immediate response to POST /generate — gives the client a run_id to poll."""
    run_id: str
    message: str = "Workflow started. Poll /runs/{run_id} for status."
