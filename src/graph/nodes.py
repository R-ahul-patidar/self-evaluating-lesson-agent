"""
nodes.py — All LangGraph node functions.

Each node receives the full AgentState, performs its work,
and returns a partial state dict with ONLY the keys it updates.
LangGraph merges the partial update into the full state.

Node order: prepare_request → retrieve_context → generate_content
            → evaluate_content → decide_next_step
            → [regenerate_content → evaluate_content] (on FAIL)
            → finalize
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.agents.evaluator import evaluate_content
from src.agents.generator import generate_content, regenerate_content
from src.agents.memory import load_memory_feedback, save_evaluation_failures
from src.config import settings
from src.graph.state import AgentState
from src.knowledge.retriever import retrieve_context, retrieve_context_for_evaluation
from src.models.schemas import RejectionEntry


def node_prepare_request(state: AgentState) -> dict:
    """
    Initialise the workflow run.
    - Load historical memory feedback for this topic
    - Set retry counters and defaults
    """
    topic = state["topic"]
    content_type = state.get("content_type", "lesson")

    memory_feedback = load_memory_feedback(topic, content_type)

    return {
        "retry_count": 0,
        "max_retries": settings.max_retries,
        "rejection_log": [],
        "memory_feedback": memory_feedback,
        "steps_completed": ["request_received"],
        "current_step": "retrieving_context",
        "final_status": "pending",
        "error": None,
    }


def node_retrieve_reference_context(state: AgentState) -> dict:
    """
    Query FAISS to retrieve relevant reference chunks for the topic.
    This context is passed to both the Generator and Evaluator.
    """
    topic = state["topic"]
    try:
        # Use topic as the query — broad enough to retrieve comprehensive coverage
        context = retrieve_context(query=topic, topic=topic, top_k=4)
    except Exception as e:
        print(f"[Node] retrieve_reference_context warning: {e}")
        context = ""

    steps = list(state.get("steps_completed", []))
    steps.append("reference_context_retrieved")

    return {
        "reference_context": context,
        "steps_completed": steps,
        "current_step": "generating_content",
    }


def node_generate_content(state: AgentState) -> dict:
    """
    Generator Agent: produce the first version of the lesson.
    Passes memory feedback and reference context into the prompt.
    """
    content = generate_content(
        topic=state["topic"],
        content_type=state.get("content_type", "lesson"),
        learner_profile=state["learner_profile"],
        learning_goal=state.get("learning_goal", "Understand the basics"),
        reference_context=state.get("reference_context", ""),
        rubric=state["rubric"],
        memory_records=state.get("memory_feedback", []),
        demo_mode=state.get("demo_mode", False),
    )

    steps = list(state.get("steps_completed", []))
    steps.append("content_generated")

    return {
        "generated_content": content,
        "steps_completed": steps,
        "current_step": "evaluating_content",
    }


def node_evaluate_content(state: AgentState) -> dict:
    """
    Evaluator Agent: evaluate the current generated content.
    Uses a separate broader context retrieval for thorough grounding evaluation.
    """
    # Evaluator gets broader context (top_k=6)
    eval_context = state.get("reference_context", "")
    if not eval_context:
        try:
            eval_context = retrieve_context_for_evaluation(state["topic"], top_k=6)
        except Exception:
            eval_context = ""

    evaluation = evaluate_content(
        generated_content=state["generated_content"],
        learner_profile=state["learner_profile"],
        rubric=state["rubric"],
        reference_context=eval_context,
    )

    steps = list(state.get("steps_completed", []))
    attempt_num = state.get("retry_count", 0) + 1

    if evaluation.passed:
        steps.append(f"evaluation_passed_attempt_{attempt_num}")
        next_step = "finalizing"
    else:
        failed_names = [c.name for c in evaluation.checks if not c.passed]
        steps.append(f"evaluation_failed_attempt_{attempt_num}:{','.join(failed_names)}")
        next_step = "deciding_next_step"

    return {
        "evaluation": evaluation,
        "steps_completed": steps,
        "current_step": next_step,
    }


def node_regenerate_content(state: AgentState) -> dict:
    """
    Regeneration node: called only after a FAIL.
    Injects the specific failure reasons into the regeneration prompt.
    Records the failed attempt in the rejection log.
    Persists failures to SQLite memory.
    """
    evaluation = state["evaluation"]
    retry_count = state.get("retry_count", 0)
    attempt_number = retry_count + 1  # This was attempt N, now generating attempt N+1

    # Build rejection log entry for this failed attempt
    failed_checks = [c.name for c in evaluation.checks if not c.passed]
    failure_reasons = [c.reason for c in evaluation.checks if not c.passed]

    rejection_entry = RejectionEntry(
        attempt=attempt_number,
        status="REJECTED",
        failed_checks=failed_checks,
        failure_reasons=failure_reasons,
        changes_made=f"Regenerating with targeted corrections: {', '.join(evaluation.improvement_suggestions)}",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    rejection_log = list(state.get("rejection_log", []))
    rejection_log.append(rejection_entry)

    # Persist failures to SQLite memory (self-evolving mechanism)
    try:
        save_evaluation_failures(
            topic=state["topic"],
            content_type=state.get("content_type", "lesson"),
            evaluation=evaluation,
        )
    except Exception as e:
        print(f"[Node] Memory save warning: {e}")

    # Generate improved content with failure feedback injected
    new_content = regenerate_content(
        topic=state["topic"],
        content_type=state.get("content_type", "lesson"),
        previous_content=state["generated_content"],
        evaluation=evaluation,
        learner_profile=state["learner_profile"],
        learning_goal=state.get("learning_goal", "Understand the basics"),
        reference_context=state.get("reference_context", ""),
        rubric=state["rubric"],
        attempt_number=attempt_number + 1,
        memory_records=state.get("memory_feedback", []),
    )

    steps = list(state.get("steps_completed", []))
    steps.append(f"regenerated_attempt_{attempt_number + 1}")

    return {
        "generated_content": new_content,
        "rejection_log": rejection_log,
        "retry_count": retry_count + 1,
        "steps_completed": steps,
        "current_step": "evaluating_content",
    }


def node_finalize(state: AgentState) -> dict:
    """
    Finalize node: called when the workflow terminates (PASS or retry limit reached).
    Builds the final output and persists the run result.
    """
    evaluation = state.get("evaluation")
    retry_count = state.get("retry_count", 0)
    rejection_log = list(state.get("rejection_log", []))

    # Determine final status
    if evaluation and evaluation.passed:
        final_status = "PASS"
        final_content = state.get("generated_content", "")
    else:
        # Retry limit reached without passing
        final_status = "FAIL"
        final_content = state.get("generated_content", "")

        # If there's a final failed evaluation, add it to the rejection log
        if evaluation and not evaluation.passed:
            failed_checks = [c.name for c in evaluation.checks if not c.passed]
            failure_reasons = [c.reason for c in evaluation.checks if not c.passed]
            final_entry = RejectionEntry(
                attempt=retry_count + 1,
                status="REJECTED (RETRY LIMIT REACHED)",
                failed_checks=failed_checks,
                failure_reasons=failure_reasons,
                changes_made="No more retries available.",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            rejection_log.append(final_entry)

    steps = list(state.get("steps_completed", []))
    steps.append(f"finalized_{final_status.lower()}")

    return {
        "final_status": final_status,
        "final_content": final_content,
        "rejection_log": rejection_log,
        "steps_completed": steps,
        "current_step": "complete",
    }
