"""
evaluator.py — Prompt templates for the Evaluator Agent.

The evaluator must return STRICT structured JSON output — no vague prose.
The prompt is designed to force per-check PASS/FAIL decisions with clear reasons.
"""

from __future__ import annotations

from src.models.schemas import LearnerProfile, Rubric


EVALUATOR_SYSTEM_PROMPT = """You are a strict educational content quality reviewer.
Your job is to evaluate a lesson against a rubric and determine if each criterion PASSES or FAILS.

Rules:
- Be strict. Do not give the benefit of the doubt.
- PASS means the criterion is clearly and fully met.
- FAIL means the criterion is missing, incomplete, or incorrect.
- No partial credit. Each check is either PASS or FAIL.
- For each FAIL, provide a specific, actionable reason.
- Your output MUST be valid JSON matching the exact schema provided.
- Do not add any text outside the JSON.
"""


def build_evaluation_prompt(
    generated_content: str,
    learner_profile: LearnerProfile,
    rubric: Rubric,
    reference_context: str,
) -> str:
    """
    Build the evaluation prompt for the Evaluator Agent.

    The evaluator receives:
    - The generated lesson
    - The learner profile (to assess beginner-friendliness)
    - The rubric (list of checks)
    - Reference material (to verify factual accuracy and grounding)
    """
    # Format rubric checks for the prompt
    checks_formatted = "\n".join(
        f'{i+1}. name: "{check.name}"\n   criterion: {check.description}'
        for i, check in enumerate(rubric.checks)
    )

    learner_desc = (
        f"Education: {learner_profile.education_level.replace('_', ' ').title()}, "
        f"English: {learner_profile.english_level}, "
        f"Prior knowledge: {learner_profile.prior_knowledge}"
    )

    ref_section = ""
    if reference_context.strip():
        ref_section = f"""
## Reference Material (Ground Truth for Accuracy and Grounding checks)

{reference_context}

---
"""

    prompt = f"""Evaluate the following lesson against the rubric below.

## Target Learner
{learner_desc}

## Rubric Checks
{checks_formatted}
{ref_section}
## Lesson to Evaluate

{generated_content}

---

## Instructions

Evaluate the lesson against EACH rubric check above.

For each check, decide strictly: PASS or FAIL.

PASS = the criterion is clearly and completely met.
FAIL = the criterion is missing, incomplete, or incorrect. Be specific about what failed.

After evaluating all checks:
- Set "passed" to true ONLY if ALL individual checks passed.
- List all failed check names in "critical_failures".
- For each failure, write ONE specific correction in "improvement_suggestions".

Return your evaluation as valid JSON in EXACTLY this format:

{{
  "passed": true or false,
  "checks": [
    {{
      "name": "<check name from rubric>",
      "passed": true or false,
      "reason": "<specific reason — what passed or what exactly failed>"
    }}
  ],
  "critical_failures": ["<failed check name 1>", "<failed check name 2>"],
  "improvement_suggestions": ["<specific correction 1>", "<specific correction 2>"]
}}

Return ONLY the JSON. No other text."""

    return prompt
