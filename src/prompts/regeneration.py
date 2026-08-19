"""
regeneration.py — Prompt template for the Regeneration step.

When evaluation fails, this prompt injects the specific failure reasons
so the Generator produces a targeted fix — not just another blind attempt.
"""

from __future__ import annotations

from src.models.schemas import EvaluationResult, LearnerProfile, Rubric


def build_regeneration_prompt(
    topic: str,
    content_type: str,
    previous_content: str,
    evaluation: EvaluationResult,
    learner_profile: LearnerProfile,
    learning_goal: str,
    reference_context: str,
    rubric: Rubric,
    attempt_number: int,
    memory_feedback: str = "",
) -> str:
    """
    Build the regeneration prompt that explicitly addresses all failures.

    This is NOT a simple retry. It:
    1. Shows the failed checks and their reasons
    2. Shows the specific corrections required
    3. Shows the previous content (so the Generator can improve it, not start blind)
    4. Includes the full rubric so all checks are still satisfied
    """
    # Format failed checks
    failed_checks_text = "\n".join(
        f"  - [{check.name}] FAILED: {check.reason}"
        for check in evaluation.checks
        if not check.passed
    )

    # Format corrections required
    corrections_text = "\n".join(
        f"  {i+1}. {suggestion}"
        for i, suggestion in enumerate(evaluation.improvement_suggestions)
    )

    # Format all rubric requirements
    rubric_requirements = "\n".join(
        f"  - {check.name}: {check.description}"
        for check in rubric.checks
    )

    # Learner description
    learner_desc = (
        f"Education: {learner_profile.education_level.replace('_', ' ').title()}, "
        f"English: {learner_profile.english_level}, "
        f"Prior knowledge: {learner_profile.prior_knowledge}"
    )

    ref_section = ""
    if reference_context.strip():
        ref_section = f"""
## Reference Material (Use for accuracy and grounding)

{reference_context}

---
"""

    memory_section = ""
    if memory_feedback.strip():
        memory_section = f"""
## Historical Failures (Also avoid these recurring mistakes)

{memory_feedback}

---
"""

    prompt = f"""You are rewriting a {content_type} on "{topic}" (Attempt {attempt_number}).

The previous version was REJECTED because it failed quality checks.
You MUST fix ALL the failures listed below.

## Target Learner
{learner_desc}
Learning goal: {learning_goal}

## ❌ What Failed in the Previous Version

{failed_checks_text}

## ✅ Required Corrections

{corrections_text}
{ref_section}{memory_section}
## Full Quality Rubric (ALL checks must pass)

{rubric_requirements}

## Previous Version (for reference — rewrite and fix all failures)

{previous_content}

---

## Instructions

Write a COMPLETE, IMPROVED version of the {content_type} that:
1. Fixes EVERY failure listed above
2. Satisfies ALL rubric requirements
3. Is written for the target learner (simple language, no assumed knowledge)
4. Is standalone and complete — not a partial fix

Do not reference "the previous version" or "the evaluator". Just write the improved {content_type}.

Write the complete improved {content_type} now:"""

    return prompt
