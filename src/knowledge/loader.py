"""
loader.py — Loads and chunks markdown reference documents for embedding into FAISS.

Design decision: The loader is topic-agnostic. It reads any markdown files from
the references directory and splits them into overlapping chunks. This means
adding a new reference document (Python, ML, etc.) requires zero code changes.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config import REFERENCES_DIR


def load_reference_document(filename: str) -> str:
    """Load a single markdown reference file by filename."""
    path = REFERENCES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Reference document not found: {path}")
    return path.read_text(encoding="utf-8")


def load_all_references() -> dict[str, str]:
    """Load all markdown files from the references directory."""
    docs = {}
    for md_file in REFERENCES_DIR.glob("*.md"):
        docs[md_file.stem] = md_file.read_text(encoding="utf-8")
    return docs


def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Strategy: Split by double-newline (paragraph boundaries) first,
    then merge short paragraphs until chunk_size is reached.
    Overlap is achieved by including the tail of the previous chunk.
    """
    # Clean up extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    # Split by paragraph
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from tail of previous chunk
            if chunks and overlap > 0:
                tail = chunks[-1][-overlap:]
                current = (tail + "\n\n" + para).strip()
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


def load_and_chunk_reference(filename: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Load a reference document and return its text chunks."""
    text = load_reference_document(filename)
    return chunk_text(text, chunk_size=chunk_size, overlap=overlap)


def get_reference_filename_for_topic(topic: str) -> str:
    """
    Map a topic to its reference filename.

    For unknown topics, falls back to default RAG reference.
    This keeps the system generic — new topics just need a new .md file.
    """
    topic_lower = topic.lower()
    mapping = {
        "rag": "rag_fundamentals.md",
        "retrieval-augmented generation": "rag_fundamentals.md",
        "retrieval augmented generation": "rag_fundamentals.md",
        "introduction to rag": "rag_fundamentals.md",
    }
    for key, filename in mapping.items():
        if key in topic_lower:
            return filename

    # Check if a matching file exists in references/
    slug = topic_lower.replace(" ", "_").replace("-", "_")
    candidate = REFERENCES_DIR / f"{slug}.md"
    if candidate.exists():
        return candidate.name

    # Default fallback
    return "rag_fundamentals.md"
