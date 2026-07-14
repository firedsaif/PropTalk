"""Structured JSON logging: one line per tool call, latency included.

Never put PII (phone numbers, full transcripts) in the message field -
callers pass only IDs and category fields, never raw caller-supplied text.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

logger = logging.getLogger("proptalk")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def log_event(**fields) -> None:
    fields.setdefault("ts", datetime.now(timezone.utc).isoformat())
    logger.info(json.dumps(fields, default=str))


@contextmanager
def timed_tool(tool: str, *, client_id: str | None, retell_call_id: str | None) -> Iterator[dict]:
    """Times a tool call and logs {ts, client_id, retell_call_id, tool, latency_ms, ok, reason}.

    Usage: `with timed_tool(...) as ctx: ... ctx["ok"] = True`
    """
    start = time.perf_counter()
    ctx: dict = {"ok": False, "reason": None}
    try:
        yield ctx
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            client_id=client_id,
            retell_call_id=retell_call_id,
            tool=tool,
            latency_ms=round(latency_ms, 1),
            ok=ctx.get("ok"),
            reason=ctx.get("reason"),
        )
