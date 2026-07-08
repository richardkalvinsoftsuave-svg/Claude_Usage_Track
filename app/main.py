"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import dashboard, uploads

# Create tables on startup (simple zero-migration setup for SQLite default).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Claude Usage Tracker",
    description="On-premise backend for tracking Claude Code usage from screenshots.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded screenshots.
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# ── API routers ──
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])

# ── Health (both /health and /api/health for flexibility) ──
@app.get("/health", tags=["health"])
@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
