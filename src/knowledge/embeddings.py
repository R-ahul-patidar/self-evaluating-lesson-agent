"""
embeddings.py — FAISS index management using Google models/gemini-embedding-001.

Design decisions:
- Index is cached to disk (output/faiss_index/) and reused across requests.
- Rebuilt only when reference documents change (detected by mtime).
- Uses GoogleGenerativeAIEmbeddings from LangChain — same API key as the LLM.
- No sentence-transformers dependency — keeps the stack minimal.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.config import FAISS_INDEX_PATH, REFERENCES_DIR, settings
from src.knowledge.loader import load_and_chunk_reference, get_reference_filename_for_topic


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Return a configured GoogleGenerativeAIEmbeddings instance."""
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.gemini_api_key,
    )


def _index_meta_path(index_name: str) -> Path:
    return FAISS_INDEX_PATH / f"{index_name}.meta.json"


def _is_index_stale(index_name: str, reference_filename: str) -> bool:
    """Check if the FAISS index is older than the reference document."""
    meta_path = _index_meta_path(index_name)
    index_dir = FAISS_INDEX_PATH / index_name

    if not meta_path.exists() or not index_dir.exists():
        return True  # Index doesn't exist yet

    meta = json.loads(meta_path.read_text())
    ref_path = REFERENCES_DIR / reference_filename
    if not ref_path.exists():
        return True

    ref_mtime = ref_path.stat().st_mtime
    indexed_mtime = meta.get("ref_mtime", 0)
    return ref_mtime > indexed_mtime


def build_faiss_index(
    reference_filename: str,
    index_name: str,
    chunk_size: int = 600,
    overlap: int = 100,
    force_rebuild: bool = False,
) -> FAISS:
    """
    Build (or load from disk) a FAISS index for a given reference document.

    Args:
        reference_filename: e.g. "rag_fundamentals.md"
        index_name: identifier for the saved index directory
        chunk_size: characters per chunk
        overlap: overlap between chunks
        force_rebuild: ignore cache and always rebuild

    Returns:
        A ready-to-query FAISS vectorstore instance.
    """
    embeddings = _get_embeddings()
    index_dir = FAISS_INDEX_PATH / index_name

    # Load from disk if fresh
    if not force_rebuild and not _is_index_stale(index_name, reference_filename):
        print(f"[Knowledge] Loading FAISS index from disk: {index_dir}")
        return FAISS.load_local(
            str(index_dir),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    # Rebuild index
    print(f"[Knowledge] Building FAISS index for: {reference_filename}")
    chunks = load_and_chunk_reference(reference_filename, chunk_size=chunk_size, overlap=overlap)

    if not chunks:
        raise ValueError(f"No content found in reference document: {reference_filename}")

    vectorstore = FAISS.from_texts(chunks, embedding=embeddings)

    # Persist to disk
    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))

    # Save metadata
    ref_path = REFERENCES_DIR / reference_filename
    meta = {
        "reference_filename": reference_filename,
        "index_name": index_name,
        "chunk_count": len(chunks),
        "ref_mtime": ref_path.stat().st_mtime if ref_path.exists() else 0,
        "built_at": time.time(),
    }
    _index_meta_path(index_name).write_text(json.dumps(meta, indent=2))
    print(f"[Knowledge] FAISS index built: {len(chunks)} chunks, saved to {index_dir}")

    return vectorstore


# Module-level cache: { index_name -> FAISS instance }
_index_cache: dict[str, FAISS] = {}


def get_or_build_index(reference_filename: str) -> FAISS:
    """
    Get a cached FAISS index or build it if needed.
    Safe to call on every request — only rebuilds when stale.
    """
    index_name = reference_filename.replace(".md", "").replace(" ", "_")

    # Check in-memory cache first
    if index_name in _index_cache:
        if not _is_index_stale(index_name, reference_filename):
            return _index_cache[index_name]

    # Build / load from disk
    vectorstore = build_faiss_index(reference_filename, index_name)
    _index_cache[index_name] = vectorstore
    return vectorstore
