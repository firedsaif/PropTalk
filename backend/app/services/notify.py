"""Outbound notifications: Resend email + Twilio SMS/call.

Phase 2: neither vendor is wired up yet (Resend lands in Phase 4, Twilio is
feature-flagged off until Phase 7 - see docs/phases.md money timeline). Both
functions log loudly so the gauntlet/QA process has a record, and return fast
so they never block the agent's spoken response (rules.md SS3 "fire-and-return").
"""
from __future__ import annotations

from app.logging import log_event
from app.settings import settings


def send_summary_email(*, client_id: str, notify_email: str | None, subject: str, body: str) -> bool:
    if not settings.resend_api_key or not notify_email:
        log_event(event="email_stub", client_id=client_id, to=notify_email, subject=subject)
        return False
    # Phase 4: real Resend call via httpx with an explicit timeout.
    return False


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
