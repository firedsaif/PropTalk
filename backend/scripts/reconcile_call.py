"""Reconcile a call from Retell's API instead of waiting for the webhook.

WHY: the dev tunnel (cloudflared quick tunnel over a high-latency link) reliably drops
the big end-of-call webhooks (call_ended/call_analyzed carry the full transcript), so the
summary email never gets generated even though the call itself succeeded. Retell keeps the
full call on its side, so we *pull* it and run the exact same pipeline the webhook would
have - store the call row, set the outcome, send the summary email. Tunnel-independent.

This is also a real product robustness win, not just a dev crutch: webhook delivery can
always fail, and being able to reconcile from source-of-truth is good practice (Phase 6
keeps the webhook as the fast path, with this as the backstop / nightly sweep).

Usage (from backend/, venv active):
    python scripts/reconcile_call.py                 # newest call
    python scripts/reconcile_call.py call_0942...    # a specific call
    python scripts/reconcile_call.py --list 5        # show recent calls, do nothing
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.models.webhooks import RetellCall, RetellWebhookPayload  # noqa: E402
from app.routes.webhooks import _handle_payload  # noqa: E402
from app.settings import settings  # noqa: E402

WILLOWBROOK = "11111111-1111-1111-1111-111111111111"
API = "https://api.retellai.com"


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.retell_api_key}", "Content-Type": "application/json"}


def _get_call(call_id: str) -> dict:
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{API}/v2/get-call/{call_id}", headers=_headers())
    r.raise_for_status()
    return r.json()


def _recent_calls(limit: int) -> list[dict]:
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{API}/v2/list-calls", headers=_headers(), json={"limit": limit})
    r.raise_for_status()
    data = r.json()
    calls = data.get("calls") or data.get("data") or data if isinstance(data, list) else data
    return calls if isinstance(calls, list) else calls.get("calls", [])


def _newest_call_id() -> str | None:
    calls = _recent_calls(10)
    calls = [c for c in calls if c.get("call_id")]
    calls.sort(key=lambda c: c.get("start_timestamp") or 0, reverse=True)
    return calls[0]["call_id"] if calls else None


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--list":
        n = int(args[1]) if len(args) > 1 else 5
        import datetime

        for c in sorted(_recent_calls(n), key=lambda c: c.get("start_timestamp") or 0, reverse=True):
            ts = c.get("start_timestamp")
            when = datetime.datetime.fromtimestamp((ts or 0) / 1000).strftime("%m-%d %H:%M") if ts else "?"
            dur = (c.get("duration_ms") or 0) / 1000
            print(f"  {c.get('call_id')}  {when}  {dur:4.0f}s  {c.get('call_status')}")
        return

    call_id = args[0] if args else _newest_call_id()
    if not call_id:
        sys.exit("No call id given and no recent calls found.")

    call = _get_call(call_id)
    # Retell's get-call response uses the same field names as the webhook's `call` object,
    # and the model ignores extras - so it maps straight in with no translation layer.
    payload = RetellWebhookPayload(event="call_analyzed", call=RetellCall(**call))

    print(f"Reconciling {call_id} ...")
    print(f"  from={call.get('from_number')}  dur={ (call.get('duration_ms') or 0)/1000:.0f}s"
          f"  transcript={'yes' if call.get('transcript') else 'no'}")

    result = _handle_payload(WILLOWBROOK, payload)
    print(f"\nResult: {result}")
    if result and result.get("emailed"):
        print("Summary email sent.")
    elif result and result.get("emailed") is False:
        print("Email NOT sent (check the email_* log line: unconfigured, idempotency, or a Resend error).")


def _close_pool() -> None:
    """Close the shared pool before the interpreter tears down, or psycopg's __del__ tries
    to join its worker threads at finalization and prints a scary (harmless) traceback."""
    import app.db

    if app.db._pool is not None:
        app.db._pool.close()
        app.db._pool = None


if __name__ == "__main__":
    try:
        main()
    finally:
        _close_pool()
