"""POST /webhooks/retell - call_started / call_ended / call_analyzed.

Returns 2xx fast; verifies the signature; upserts the call row so duplicate
or out-of-order deliveries are safe (see app/services/calls.py). Summary
email + SMS are stubbed (Phase 4/7) - see app/services/notify.py.

This route stays `async def` (it needs the raw body for signature
verification, before any JSON parsing happens) but pushes the blocking
DB work into FastAPI's threadpool via run_in_threadpool.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.db import get_pooled_connection
from app.deps import resolve_client
from app.logging import log_event
from app.models.webhooks import RetellWebhookPayload
from app.retell import verify_webhook_signature
from app.services.calls import upsert_call
from app.services.notify import send_summary_email
from app.services.summary import extract_summary
from app.settings import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _ms_to_utc(ms: int | None) -> datetime | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms is not None else None


def _handle_payload(client_id: str, payload: RetellWebhookPayload) -> None:
    """The blocking part: one connection, client lookup, call upsert, stub email."""
    call = payload.call
    duration_sec = call.duration_ms // 1000 if call.duration_ms is not None else None
    summary = extract_summary(call.call_analysis.model_dump() if call.call_analysis else None)

    with get_pooled_connection() as conn:
        client = resolve_client(conn, client_id)
        upsert_call(
            conn,
            client_id=client_id,
            retell_call_id=call.call_id,
            from_number=call.from_number,
            started_at=_ms_to_utc(call.start_timestamp),
            ended_at=_ms_to_utc(call.end_timestamp),
            duration_sec=duration_sec,
            transcript=call.transcript,
            recording_url=call.recording_url,
            summary=summary,
        )

    if payload.event == "call_analyzed" and summary:
        send_summary_email(
            client_id=client_id,
            notify_email=client["notify_email"],
            subject=f"[{client['company_name']} line] Call summary",
            body=summary,
        )


@router.post("/retell")
async def retell_webhook(request: Request, client_id: str = Query(...)):
    raw_body = await request.body()
    signature = request.headers.get("x-retell-signature")
    key_configured = bool(settings.retell_api_key or settings.retell_webhook_secret)
    if key_configured:
        if not verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="invalid signature")
    else:
        log_event(event="webhook_signature_skipped", reason="no Retell key configured yet")

    payload = RetellWebhookPayload.model_validate_json(raw_body)
    await run_in_threadpool(_handle_payload, client_id, payload)

    log_event(event="webhook_received", client_id=client_id, retell_call_id=payload.call.call_id, type=payload.event)
    return {"ok": True}
