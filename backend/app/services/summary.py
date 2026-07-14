"""Call summary. Phase 2: use whatever Retell's own post-call analysis gives us
(call_analysis.call_summary on the call_analyzed event) - no extra LLM bill.
A custom LLM pass over the transcript (docs/RETELL_AGENT_CONFIG.md SS D) is a later
phase if Retell's built-in summary isn't good enough for the client email.
"""
from __future__ import annotations


def extract_summary(call_analysis: dict | None) -> str | None:
    if not call_analysis:
        return None
    return call_analysis.get("call_summary")
