"""PropTalk US — FastAPI backend.

Phase 0: a minimal, provably-running app with a health check.
Tool endpoints (/tools/*) and the Retell webhook arrive in Phase 2.
See docs/architecture.md for the target structure.
"""
from fastapi import FastAPI

app = FastAPI(title="PropTalk US API", version="0.0.1")


@app.get("/health")
def health() -> dict:
    """Liveness probe. Used by Railway (prod) and local smoke tests."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"service": "proptalk-us", "status": "alive", "docs": "/docs"}
