"""
generator.py — Generator Agent.

Responsibilities:
- Call Gemini (gemini-3.5-flash-lite) via LangChain
- Produce educational lesson content for any topic
- Accept historical memory feedback and reference context
- Fully generic — works for RAG, Python, ML, or any other topic
"""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from typing import Any

from src.config import settings
from src.models.schemas import LearnerProfile, Rubric, MemoryRecord
from src.agents.memory import format_memory_for_prompt
from src.prompts.generator import (
    GENERATOR_SYSTEM_PROMPT,
    DEMO_MODE_INJECTION,
    build_generation_prompt,
)


def _extract_text_content(content: Any) -> str:
    """Extract clean string text regardless of whether LLM returns str or list of content blocks."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
        return "".join(texts).strip()
    return str(content).strip()


def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=settings.temperature,
    )


def generate_content(
    topic: str,
    content_type: str,
    learner_profile: LearnerProfile,
    learning_goal: str,
    reference_context: str,
    rubric: Rubric,
    memory_records: list[MemoryRecord] | None = None,
    demo_mode: bool = False,
) -> str:
    """
    Generate educational content for the given topic.

    Args:
        topic: The topic to generate content for
        content_type: e.g. "lesson"
        learner_profile: Target learner characteristics
        learning_goal: What the learner should achieve
        reference_context: Retrieved FAISS context chunks
        rubric: The evaluation rubric (so Generator knows what to satisfy)
        memory_records: Historical failures from SQLite memory
        demo_mode: If True, inject deliberate error for demo purposes

    Returns:
        Generated lesson text as a string
    """
    llm = _get_llm()

    memory_feedback = format_memory_for_prompt(memory_records or [])
    demo_injection = DEMO_MODE_INJECTION if demo_mode else ""

    user_prompt = build_generation_prompt(
        topic=topic,
        content_type=content_type,
        learner_profile=learner_profile,
        learning_goal=learning_goal,
        reference_context=reference_context,
        rubric=rubric,
        memory_feedback=memory_feedback,
        demo_mode_injection=demo_injection,
    )

    messages = [
        SystemMessage(content=GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    response = llm.invoke(messages)
    return _extract_text_content(response.content)


def regenerate_content(
    topic: str,
    content_type: str,
    previous_content: str,
    evaluation,  # EvaluationResult — avoiding circular import with type hint
    learner_profile: LearnerProfile,
    learning_goal: str,
    reference_context: str,
    rubric: Rubric,
    attempt_number: int,
    memory_records: list[MemoryRecord] | None = None,
) -> str:
    """
    Regenerate content by explicitly addressing all evaluation failures.

    This is NOT a simple retry — the failure reasons are injected directly
    into the prompt so the Generator knows exactly what to fix.
    """
    from src.prompts.regeneration import build_regeneration_prompt

    llm = _get_llm()
    memory_feedback = format_memory_for_prompt(memory_records or [])

    user_prompt = build_regeneration_prompt(
        topic=topic,
        content_type=content_type,
        previous_content=previous_content,
        evaluation=evaluation,
        learner_profile=learner_profile,
        learning_goal=learning_goal,
        reference_context=reference_context,
        rubric=rubric,
        attempt_number=attempt_number,
        memory_feedback=memory_feedback,
    )

    messages = [
        SystemMessage(content=GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    response = llm.invoke(messages)
    return _extract_text_content(response.content)
