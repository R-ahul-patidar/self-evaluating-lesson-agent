"""
config.py — All environment-based configuration for the Self-Evaluating Lesson Agent.
No API keys or model names are hard-coded here; all values come from .env / environment.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    # ── Gemini LLM ────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    embedding_model: str = "models/gemini-embedding-001"
    temperature: float = 0.2

    # ── Agent behaviour ───────────────────────────────────────────────────────
    max_retries: int = 2

    # ── Application ───────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # ── Storage ───────────────────────────────────────────────────────────────
    db_path: str = "output/memory.db"
    faiss_index_path: str = "output/faiss_index"

    # ── References ────────────────────────────────────────────────────────────
    references_dir: str = "references"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

# Derived paths (absolute) ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / settings.db_path
FAISS_INDEX_PATH = BASE_DIR / settings.faiss_index_path
REFERENCES_DIR = BASE_DIR / settings.references_dir

# Ensure output directory exists
(BASE_DIR / "output").mkdir(parents=True, exist_ok=True)
FAISS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
