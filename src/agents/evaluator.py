"""
evaluator.py — Evaluator Agent.

Responsibilities:
- Call Gemini with structured JSON output mode
- Evaluate generated content against the rubric
- Return a strict Pydantic EvaluationResult (PASS/FAIL per check)
- Never return vague qualitative feedback — always actionable structured output

Design decision: The evaluator is a SEPARATE agent from the generator.
It receives the lesson + rubric + reference context independently,
without access to the generator's internal state or prompts.
This separation is what makes the quality gate meaningful.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.models.schemas import EvaluationResult, LearnerProfile, Rubric, RubricCheck
from src.prompts.evaluator import EVALUATOR_SYSTEM_PROMPT, build_evaluation_prompt


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


def _get_evaluator_llm() -> ChatGoogleGenerativeAI:
    """
    The evaluator uses a lower temperature than the generator
    for more deterministic, consistent judgements.
    """
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.0,  # Deterministic evaluation
    )


def _extract_json(text: str) -> dict:
    """
    Extract JSON from LLM response text.
    Handles cases where the model wraps JSON in markdown code blocks.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding a JSON object in the text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from evaluator response:\n{text[:500]}")


def _build_fallback_evaluation(rubric: Rubric, error: str) -> EvaluationResult:
    """
    Build a safe fallback evaluation if parsing fails.
    Marks everything as FAIL with the error as reason.
    """
    return EvaluationResult(
        passed=False,
        checks=[
            RubricCheck(name=check.name, passed=False, reason=f"Evaluation error: {error}")
            for check in rubric.checks
        ],
        critical_failures=[check.name for check in rubric.checks],
        improvement_suggestions=["Fix the evaluator error and retry."],
    )


def evaluate_content(
    generated_content: str,
    learner_profile: LearnerProfile,
    rubric: Rubric,
    reference_context: str,
) -> EvaluationResult:
    """
    Evaluate generated content against the rubric.

    Args:
        generated_content: The lesson text to evaluate
        learner_profile: Used to assess beginner-friendliness
        rubric: The full rubric with all check definitions
        reference_context: Reference material for accuracy/grounding checks

    Returns:
        EvaluationResult with per-check PASS/FAIL and improvement suggestions
    """
    llm = _get_evaluator_llm()

    user_prompt = build_evaluation_prompt(
        generated_content=generated_content,
        learner_profile=learner_profile,
        rubric=rubric,
        reference_context=reference_context,
    )

    messages = [
        SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw = _extract_text_content(response.content)
        data = _extract_json(raw)
        result = EvaluationResult(**data)

        # Ensure consistency: if any check failed, overall passed must be False
        any_failed = any(not check.passed for check in result.checks)
        if any_failed and result.passed:
            result.passed = False

        return result

    except Exception as e:
        error_msg = str(e)
        print(f"[Evaluator] Error parsing evaluation response: {error_msg}")
        return _build_fallback_evaluation(rubric, error_msg)
