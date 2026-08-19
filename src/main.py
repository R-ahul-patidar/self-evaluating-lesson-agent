"""
main.py — FastAPI application entry point.

Mounts static files, includes routers, and starts the server.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and resources on startup."""
    init_db()
    print("[App] Self-Evaluating Lesson Agent started.")
    print("[App] Visit: http://localhost:8000")
    yield


app = FastAPI(
    title="Self-Evaluating Lesson Agent",
    description="An agentic system that generates educational content and evaluates its own quality.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    from src.config import settings
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
