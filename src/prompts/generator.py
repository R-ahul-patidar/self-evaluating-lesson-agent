"""
generator.py — Prompt templates for the Generator Agent.

Design principle: ALL prompt strings live here. No prompt text in agent logic or routes.
The Generator receives data and these functions produce the final prompt strings.
"""

from __future__ import annotations

from src.models.schemas import LearnerProfile, Rubric


GENERATOR_SYSTEM_PROMPT = """You are an expert educator and curriculum designer specializing in technology education.
Your task is to create clear, accurate, beginner-friendly educational lesson content.

Your writing principles:
- Use simple, everyday language appropriate for the learner's level
- Explain every technical term the first time you use it
- Use analogies and real-world examples generously
- Build from simple to complex — never introduce a concept without foundation
- Be specific, not vague — use concrete examples, not abstract descriptions
- Write in short paragraphs with clear headings
- The learner should finish the lesson and feel confident, not confused
"""


def build_generation_prompt(
    topic: str,
    content_type: str,
    learner_profile: LearnerProfile,
    learning_goal: str,
    reference_context: str,
    rubric: Rubric,
    memory_feedback: str = "",
    demo_mode_injection: str = "",
) -> str:
    """
    Build the user-facing generation prompt.

    Args:
        topic: e.g. "Introduction to RAG"
        content_type: e.g. "lesson"
        learner_profile: the target learner
        learning_goal: e.g. "Understand the basics from zero"
        reference_context: retrieved chunks from FAISS knowledge base
        rubric: the evaluation rubric checks to satisfy
        memory_feedback: formatted historical failures from SQLite memory
        demo_mode_injection: if demo_mode, inject deliberate error instruction
    """
    # Format rubric requirements
    rubric_requirements = "\n".join(
        f"  - {check.name}: {check.description}"
        for check in rubric.checks
    )

    # Learner description
    learner_desc = (
        f"Education: {learner_profile.education_level.replace('_', ' ').title()}\n"
        f"English level: {learner_profile.english_level}\n"
        f"Prior knowledge: {learner_profile.prior_knowledge}\n"
        f"Country/context: {learner_profile.country_context}\n"
        f"Learning goal: {learner_profile.learning_goal}"
    )

    # Reference context section
    ref_section = ""
    if reference_context.strip():
        ref_section = f"""
## Reference Material (Use this to ground your lesson in accurate facts)

{reference_context}

---
"""

    # Memory feedback section
    memory_section = ""
    if memory_feedback.strip():
        memory_section = f"""
## ⚠️ Historical Failures (Avoid these mistakes from past attempts)

{memory_feedback}

---
"""

    # Demo mode section
    demo_section = ""
    if demo_mode_injection:
        demo_section = f"""
## ⚠️ DEMO MODE INSTRUCTION

{demo_mode_injection}

---
"""

    prompt = f"""Create a complete {content_type} on the topic: **{topic}**

## Target Learner Profile

{learner_desc}
Learning goal: {learning_goal}
{ref_section}{memory_section}{demo_section}
## Quality Requirements (Your lesson MUST satisfy all of these)

{rubric_requirements}

## Instructions

Write a complete, standalone {content_type} that teaches "{topic}" to the target learner.

The learner starts from zero. After reading your {content_type}, they should understand:
- What {topic} is
- Why it matters
- How it works (step by step)
- At least one real-world example
- Key takeaways

Format the {content_type} with clear headings, short paragraphs, and plain language.
Explain every technical term when you first use it.
Do NOT assume prior knowledge.

Write the complete {content_type} now:"""

    return prompt


DEMO_MODE_INJECTION = """You must include this EXACT incorrect statement somewhere in your lesson:
"RAG retrains the language model whenever a new document is uploaded."

This is intentionally wrong and will be caught by the quality evaluator.
Include it naturally within the lesson text."""
