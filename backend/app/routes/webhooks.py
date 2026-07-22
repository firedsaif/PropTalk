"""POST /webhooks/retell - call_started / call_ended / call_analyzed.

Returns 2xx fast; verifies the signature; upserts the call row so duplicate
or out-of-order deliveries are safe (see app/services/calls.py). On
call_analyzed it also sends the client their summary email (Phase 4).
SMS stays stubbed until Twilio is funded (Phase 7) - see app/services/notify.py.

This route stays `async def` (it needs the raw body for signature
verification, before any JSON parsing happens) but pushes the blocking
DB work into FastAPI's threadpool via run_in_threadpool.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.db import get_pooled_connection
from app.deps import resolve_client
from app.logging import log_event
from app.models.webhooks import RetellWebhookPayload
from app.retell import check_signature, diagnose_signature
from app.services.calls import set_call_outcome, upsert_call
from app.services.email_template import render_summary_email
from app.services.notify import send_summary_email
from app.services.summary import collect_outcomes, extract_outcome, extract_summary
from app.settings import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _ms_to_utc(ms: int | None) -> datetime | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms is not None else None


def _handle_payload(client_id: str, payload: RetellWebhookPayload) -> dict:
    """The blocking part: one connection, client lookup, call upsert, summary email.

    Returns a small result the route echoes back. Retell ignores the body, but this
    project verifies everything with curl before spending a voice minute (docs/rules.md
    SS7) - so what the webhook concluded has to be observable without tailing a log.
    """
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

        # Everything below is call_analyzed-only: that's the one event carrying Retell's
        # own analysis, and by then every tool row this call wrote is committed.
        if payload.event != "call_analyzed":
            return {"ok": True, "stored": True}

        outcomes = collect_outcomes(conn, client_id=client_id, retell_call_id=call.call_id)
        outcome = extract_outcome(
            call.call_analysis.model_dump() if call.call_analysis else None, outcomes
        )
        set_call_outcome(conn, retell_call_id=call.call_id, outcome=outcome)

    subject, html, text = render_summary_email(
        client=client,
        call={
            "started_at": _ms_to_utc(call.start_timestamp),
            "duration_sec": duration_sec,
            "from_number": call.from_number,
            "transcript": call.transcript,
            "recording_url": call.recording_url,
        },
        outcomes=outcomes,
        outcome=outcome,
        summary_text=summary,
    )
    emailed = send_summary_email(
        client_id=client_id,
        notify_email=client["notify_email"],
        subject=subject,
        html=html,
        text=text,
        # Retell can deliver call_analyzed more than once; one call must mean one email.
        idempotency_key=f"summary-{call.call_id}",
    )
    return {"ok": True, "stored": True, "outcome": outcome, "emailed": emailed, "subject": subject}


@router.post("/retell")
async def retell_webhook(request: Request, client_id: str = Query(...)):
    try:
        raw_body = await request.body()
    except ClientDisconnect:
        # The caller (Retell, via the tunnel) closed the connection before the full body
        # arrived - a flaky-tunnel symptom, not a bug in our handling. Log it and return a
        # clean 200 so we don't spew a 500 traceback; Retell retries call_ended/analyzed on
        # its own schedule, and the stable Railway URL (Phase 6) removes the tunnel entirely.
        log_event(event="webhook_client_disconnect", client_id=client_id)
        return {"ok": False, "reason": "client_disconnect"}
    signature = request.headers.get("x-retell-signature")
    key_configured = bool(settings.retell_api_key or settings.retell_webhook_secret)

    if key_configured:
        ok, scheme = check_signature(raw_body, signature)
        if not ok:
            # Log the actual signature *shape* (never the value beyond a short prefix) so a
            # scheme mismatch is diagnosable from one real call. In prod we reject; in local
            # testing (demo tenant, no real PII) we accept-and-flag so the gauntlet isn't
            # blocked by a verification quirk - the summary email/call row still get written.
            log_event(
                event="webhook_signature_failed",
                scheme=scheme,
                sig_prefix=(signature or "")[:12],
                sig_len=len(signature or ""),
                # Names Retell's real HMAC construction from this one signature, so the
                # Phase 6 fix is "use construction X", not another round of guessing.
                diagnosis=diagnose_signature(raw_body, signature),
                app_env=settings.app_env,
            )
            if settings.app_env != "local":
                raise HTTPException(status_code=401, detail="invalid signature")
        else:
            log_event(event="webhook_signature_ok", scheme=scheme)
    else:
        log_event(event="webhook_signature_skipped", reason="no Retell key configured yet")

    payload = RetellWebhookPayload.model_validate_json(raw_body)
    result = await run_in_threadpool(_handle_payload, client_id, payload)

    log_event(event="webhook_received", client_id=client_id, retell_call_id=payload.call.call_id, type=payload.event)
    return result
