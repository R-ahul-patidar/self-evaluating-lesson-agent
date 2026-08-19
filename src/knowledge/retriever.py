"""
retriever.py — Query the FAISS index to get relevant context chunks.

This is the interface the Generator and Evaluator use. They call retrieve_context()
and get back a plain string — the internal FAISS/embedding details are hidden.
"""

from __future__ import annotations

from src.knowledge.embeddings import get_or_build_index
from src.knowledge.loader import get_reference_filename_for_topic


def retrieve_context(
    query: str,
    topic: str,
    top_k: int = 4,
) -> str:
    """
    Retrieve the most relevant context for a query from the knowledge base.

    Args:
        query: The question or topic to search for (can be the topic itself)
        topic: Used to select the correct reference document
        top_k: Number of chunks to retrieve and concatenate

    Returns:
        A single string of the most relevant reference text.
    """
    reference_filename = get_reference_filename_for_topic(topic)
    vectorstore = get_or_build_index(reference_filename)

    results = vectorstore.similarity_search(query, k=top_k)
    if not results:
        return ""

    context_parts = [doc.page_content for doc in results]
    return "\n\n---\n\n".join(context_parts)


def retrieve_context_for_evaluation(
    topic: str,
    top_k: int = 6,
) -> str:
    """
    Retrieve broad context for the evaluator.
    Uses the topic itself as the query to get comprehensive coverage.
    Retrieves slightly more chunks (top_k=6) for thorough grounding evaluation.
    """
    return retrieve_context(query=topic, topic=topic, top_k=top_k)
