"""
workflow.py — LangGraph graph assembly.

Wires all nodes together with conditional edges to implement:
  START → prepare → retrieve → generate → evaluate → decide
              ↓                                          ↓
           (PASS)                                     (FAIL)
              ↓                                          ↓
           finalize ← ─ ─ ─ ─ ─ ─ regenerate ← decide (if retries < max)
              ↓                    (retry limit → finalize)
             END

Design decision: LangGraph is used instead of a bare loop because:
- The state is explicitly typed and tracked
- Conditional edges make the retry logic declarative, not imperative
- The graph is inspectable and debuggable
- Future nodes (e.g., human-in-the-loop review) can be added without rewriting the loop
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from src.graph.state import AgentState
from src.graph.nodes import (
    node_prepare_request,
    node_retrieve_reference_context,
    node_generate_content,
    node_evaluate_content,
    node_regenerate_content,
    node_finalize,
)


def _decide_after_evaluation(state: AgentState) -> str:
    """
    Conditional edge function: decide what to do after evaluation.

    Returns:
        "finalize" — if evaluation passed
        "regenerate" — if failed and retries remaining
        "finalize" — if failed and retry limit reached
    """
    evaluation = state.get("evaluation")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if evaluation and evaluation.passed:
        return "finalize"

    if retry_count < max_retries:
        return "regenerate"

    # Retry limit reached — terminate with final FAIL
    return "finalize"


def build_workflow() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("prepare_request", node_prepare_request)
    graph.add_node("retrieve_reference_context", node_retrieve_reference_context)
    graph.add_node("generate_content", node_generate_content)
    graph.add_node("evaluate_content", node_evaluate_content)
    graph.add_node("regenerate_content", node_regenerate_content)
    graph.add_node("finalize", node_finalize)

    # Entry point
    graph.set_entry_point("prepare_request")

    # Linear edges
    graph.add_edge("prepare_request", "retrieve_reference_context")
    graph.add_edge("retrieve_reference_context", "generate_content")
    graph.add_edge("generate_content", "evaluate_content")

    # Conditional edge after evaluation
    graph.add_conditional_edges(
        "evaluate_content",
        _decide_after_evaluation,
        {
            "finalize": "finalize",
            "regenerate": "regenerate_content",
        },
    )

    # After regeneration, go back to evaluation (the retry loop)
    graph.add_edge("regenerate_content", "evaluate_content")

    # Finalize → END
    graph.add_edge("finalize", END)

    return graph.compile()


# Module-level compiled graph (built once on import)
workflow = build_workflow()
