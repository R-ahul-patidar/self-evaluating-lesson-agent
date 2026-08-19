"""
routes.py — FastAPI route handlers.

Endpoints:
  GET  /          → Render home page (Jinja2)
  POST /generate  → Start workflow in background thread, return run_id
  GET  /runs/{id} → Return current run status (polled by UI every 2s)
  GET  /health    → Health check

Design: Business logic is NOT in route handlers.
Routes only validate input, dispatch work, and format responses.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.graph.workflow import workflow
from src.models.schemas import (
    GenerateRequest,
    GenerateResponse,
    LearnerProfile,
    RejectionEntry,
    RunStatus,
    StartRunResponse,
    Rubric,
)
from src.storage.database import init_db, save_run_result

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# In-memory run store: run_id → RunStatus
# Thread-safe for our use case (single-writer per run, multiple readers)
_run_store: dict[str, dict[str, Any]] = {}
_run_lock = threading.Lock()


# ── Home & About ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")


# ── Generate ──────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=StartRunResponse)
async def start_generate(request_data: GenerateRequest):
    """
    Start the agentic workflow in a background thread.
    Returns immediately with a run_id the client can poll.
    """
    # Ensure DB is initialized
    init_db()

    run_id = str(uuid.uuid4())

    # Initialize run status in the store
    with _run_lock:
        _run_store[run_id] = {
            "run_id": run_id,
            "topic": request_data.topic,
            "status": "running",
            "current_step": "initializing",
            "steps_completed": [],
            "attempt": 1,
            "max_attempts": settings.max_retries + 1,
            "evaluation": None,
            "rejection_log": [],
            "final_content": None,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    # Launch workflow in background thread
    thread = threading.Thread(
        target=_run_workflow,
        args=(run_id, request_data),
        daemon=True,
    )
    thread.start()

    return StartRunResponse(run_id=run_id)


def _run_workflow(run_id: str, request_data: GenerateRequest) -> None:
    """
    Execute the LangGraph workflow and write status updates to _run_store.
    This runs in a background thread.
    """
    try:
        learner_profile = request_data.to_learner_profile()
        rubric = Rubric.default_rag_rubric()  # In future: lookup by content_type

        initial_state = {
            "run_id": run_id,
            "topic": request_data.topic,
            "content_type": request_data.content_type,
            "demo_mode": request_data.demo_mode,
            "learner_profile": learner_profile,
            "learning_goal": request_data.learning_goal,
            "rubric": rubric,
            "reference_context": "",
            "generated_content": "",
            "evaluation": None,
            "retry_count": 0,
            "max_retries": settings.max_retries,
            "rejection_log": [],
            "memory_feedback": [],
            "steps_completed": [],
            "current_step": "starting",
            "final_status": "pending",
            "final_content": "",
            "error": None,
        }

        # Run the workflow — LangGraph executes all nodes
        final_state = workflow.invoke(initial_state)

        # Build structured response
        evaluation = final_state.get("evaluation")
        rejection_log = final_state.get("rejection_log", [])
        final_status = final_state.get("final_status", "FAIL")
        final_content = final_state.get("final_content", "")
        steps = final_state.get("steps_completed", [])

        # Serialize for response
        eval_dict = evaluation.model_dump() if evaluation else None
        rejection_log_dicts = [e.model_dump() for e in rejection_log]

        with _run_lock:
            _run_store[run_id].update({
                "status": final_status,
                "current_step": "complete",
                "steps_completed": steps,
                "attempt": final_state.get("retry_count", 0) + 1,
                "evaluation": eval_dict,
                "rejection_log": rejection_log_dicts,
                "final_content": final_content,
                "error": None,
            })

        # Persist to SQLite
        try:
            result_json = json.dumps({
                "final_status": final_status,
                "final_content": final_content,
                "evaluation": eval_dict,
                "rejection_log": rejection_log_dicts,
            })
            save_run_result(
                run_id=run_id,
                topic=request_data.topic,
                content_type=request_data.content_type,
                final_status=final_status,
                attempt_count=final_state.get("retry_count", 0) + 1,
                result_json=result_json,
            )
        except Exception as db_err:
            print(f"[Routes] DB save warning: {db_err}")

    except Exception as e:
        error_msg = str(e)
        print(f"[Routes] Workflow error for {run_id}: {error_msg}")
        with _run_lock:
            _run_store[run_id].update({
                "status": "error",
                "current_step": "error",
                "error": error_msg,
            })


# ── Poll run status ───────────────────────────────────────────────────────────

@router.get("/runs/{run_id}")
async def get_run_status(run_id: str):
    """
    Return the current status of a workflow run.
    Called by the UI every 2 seconds via JavaScript polling.
    """
    with _run_lock:
        run = _run_store.get(run_id)

    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    return run


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "model": settings.gemini_model, "timestamp": datetime.now(timezone.utc).isoformat()}
