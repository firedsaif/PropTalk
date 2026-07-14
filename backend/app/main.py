"""PropTalk US - FastAPI backend.

Phase 2: the 6 /tools/* endpoints + /webhooks/retell. See docs/architecture.md
for the target structure and docs/rules.md for the per-tool definition of done.
"""
from fastapi import FastAPI

from app.routes import tools, webhooks

app = FastAPI(title="PropTalk US API", version="0.2.0")

app.include_router(tools.router)
app.include_router(webhooks.router)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Used by Railway (prod) and local smoke tests."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"service": "proptalk-us", "status": "alive", "docs": "/docs"}
