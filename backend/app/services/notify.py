"""Outbound notifications: Resend email (Phase 4) + Twilio SMS/call (deferred to Phase 7).

Both are fire-and-return: they log loudly and never raise, so a vendor having a bad day
can't take down a webhook or block the agent's spoken response (docs/rules.md SS3).

Twilio stays feature-flagged off until it's funded - the summary email carries the value
on its own (docs/phases.md money timeline).
"""
from __future__ import annotations

import httpx

from app.config import RESEND_API_URL, RESEND_TIMEOUT_SEC
from app.logging import log_event
from app.settings import settings


def send_summary_email(
    *,
    client_id: str,
    notify_email: str | None,
    subject: str,
    html: str,
    text: str,
    idempotency_key: str | None = None,
) -> bool:
    """Send the post-call summary. Returns True only on a confirmed accept.

    Unconfigured (no key / no recipient) is a logged no-op, not an error: the backend
    has to stay runnable on a machine with no Resend account.
    """
    if not settings.resend_api_key or not settings.from_email or not notify_email:
        log_event(
            event="email_stub",
            client_id=client_id,
            reason="resend_not_configured",
            subject=subject,
        )
        return False

    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}
    if idempotency_key:
        # Retell re-delivers webhooks; without this a retry means the PM's phone buzzes
        # twice for one call. Resend honours the key for 24h.
        headers["Idempotency-Key"] = idempotency_key[:256]

    try:
        with httpx.Client(timeout=RESEND_TIMEOUT_SEC) as client:
            resp = client.post(
                RESEND_API_URL,
                headers=headers,
                json={
                    "from": settings.from_email,
                    "to": [notify_email],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            )
    except httpx.HTTPError as exc:
        log_event(event="email_send_error", client_id=client_id, error=type(exc).__name__)
        return False

    if resp.status_code >= 400:
        # Body, not just status: Resend's 403 for "unverified domain, can only send to
        # your own address" is the single most likely failure on the free tier, and the
        # status alone doesn't say that.
        log_event(
            event="email_send_failed",
            client_id=client_id,
            status=resp.status_code,
            detail=resp.text[:200],
        )
        return False

    log_event(event="email_sent", client_id=client_id, subject=subject)
    return True


def alert_escalation(*, client_id: str, escalation_phone: str | None, unit: str, issue: str) -> bool:
    log_event(
        event="escalation_alert",
        client_id=client_id,
        escalation_phone=escalation_phone,
        unit=unit,
        issue=issue,
    )
    if not settings.feature_sms_enabled or not settings.twilio_account_sid:
        return False
    # Phase 7: real Twilio SMS + fallback call via httpx with an explicit timeout.
    return False
