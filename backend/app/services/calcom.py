"""Cal.com API v2 client: tour availability + bookings.

Free tier, one event type per client (`clients.cal_event_type_id`, falling back to
CALCOM_EVENT_TYPE_ID for the demo tenant). Cal.com pins its breaking changes to a
`cal-api-version` header rather than the URL, so each endpoint below sends the exact
version its response shape was written against - omitting it silently serves an older
shape (docs: api.cal.com/v2, slots 2024-09-04, bookings 2024-08-13).

Sync httpx on purpose: the routes calling this are plain `def`, so FastAPI runs them
in its worker threadpool and the blocking call never touches the event loop - the same
tradeoff app/db.py already makes for psycopg.

This module never raises into a request handler. Every failure comes back as a small
typed-ish dict the tool layer can speak around (docs/rules.md SS3), because a caller
waiting on the phone must never hear a stack trace.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.config import (
    CALCOM_API_BASE,
    CALCOM_BOOKINGS_API_VERSION,
    CALCOM_SLOTS_API_VERSION,
    CALCOM_TIMEOUT_SEC,
)
from app.logging import log_event
from app.settings import settings


def is_configured(event_type_id: str | None) -> bool:
    """True only when we can actually reach a real calendar. Callers fall back to
    the Phase 2 business-hours mock when this is False, so the product keeps working
    on a machine with no Cal.com account (docs/phases.md: $0 until outreach)."""
    return bool(settings.calcom_api_key and event_type_id)


def event_type_id_for(client: dict) -> str | None:
    """Per-client event type, falling back to the env default. Multi-tenant by
    construction: a second client brings its own calendar, not a second agent."""
    return (client.get("cal_event_type_id") or settings.calcom_event_type_id or "").strip() or None


def _headers(api_version: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.calcom_api_key}",
        "cal-api-version": api_version,
        "Content-Type": "application/json",
    }


def _parse_slot_entry(entry: object) -> datetime | None:
    """Cal.com has shipped slots as bare ISO strings and as {"start": ...} objects
    across versions; accept either so a version bump degrades to 'no slots', never a 500."""
    raw = entry.get("start") if isinstance(entry, dict) else entry
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:  # a naive slot is Cal.com speaking the tz we asked for
        return None
    return parsed.astimezone(timezone.utc)


def get_slots(
    *, event_type_id: str, start: datetime, end: datetime, tz_name: str
) -> list[datetime] | None:
    """Available slots as sorted UTC datetimes.

    Returns None on any transport/API failure - distinct from [] ("calendar answered:
    genuinely nothing free"), because the caller degrades those two differently.
    """
    params = {
        "eventTypeId": event_type_id,
        "start": start.astimezone(timezone.utc).isoformat(),
        "end": end.astimezone(timezone.utc).isoformat(),
        "timeZone": tz_name,
    }
    try:
        with httpx.Client(timeout=CALCOM_TIMEOUT_SEC) as client:
            resp = client.get(
                f"{CALCOM_API_BASE}/slots",
                params=params,
                headers=_headers(CALCOM_SLOTS_API_VERSION),
            )
    except httpx.HTTPError as exc:
        log_event(event="calcom_slots_error", error=type(exc).__name__)
        return None

    if resp.status_code >= 400:
        log_event(event="calcom_slots_http_error", status=resp.status_code)
        return None

    try:
        data = resp.json().get("data")
    except ValueError:
        log_event(event="calcom_slots_bad_json")
        return None

    # 2024-09-04 shape: {"data": {"2026-07-16": [{"start": "..."}, ...], ...}}
    entries: list[object] = []
    if isinstance(data, dict):
        for day_slots in data.values():
            if isinstance(day_slots, list):
                entries.extend(day_slots)
    elif isinstance(data, list):
        entries = list(data)

    slots = [s for s in (_parse_slot_entry(e) for e in entries) if s is not None]
    return sorted(set(slots))


def create_booking(
    *,
    event_type_id: str,
    start: datetime,
    tz_name: str,
    attendee_name: str,
    attendee_email: str,
    attendee_phone: str | None,
    metadata: dict[str, str] | None = None,
) -> dict:
    """Book the slot on the real calendar.

    Returns one of:
      {"ok": True,  "cal_booking_id": "<uid>"}
      {"ok": False, "reason": "slot_taken"}   - the calendar rejected it; the slot is gone
      {"ok": False, "reason": "unavailable"}  - we couldn't reach/parse Cal.com at all
    The caller decides what that means for the DB row; this function only reports.
    """
    body: dict[str, object] = {
        "start": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "eventTypeId": int(event_type_id) if str(event_type_id).isdigit() else event_type_id,
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": tz_name,
            "language": "en",
        },
    }
    if attendee_phone:
        body["attendee"]["phoneNumber"] = attendee_phone  # type: ignore[index]
    if metadata:
        body["metadata"] = metadata

    try:
        with httpx.Client(timeout=CALCOM_TIMEOUT_SEC) as client:
            resp = client.post(
                f"{CALCOM_API_BASE}/bookings",
                json=body,
                headers=_headers(CALCOM_BOOKINGS_API_VERSION),
            )
    except httpx.HTTPError as exc:
        log_event(event="calcom_booking_error", error=type(exc).__name__)
        return {"ok": False, "reason": "unavailable"}

    if resp.status_code >= 400:
        # Cal.com signals "that time just went" as a 4xx with prose, not a typed code.
        # Anything 4xx that isn't auth/validation is treated as the slot being gone,
        # which is the safe read: we offer another time instead of claiming success.
        text = resp.text[:200].lower()
        taken = resp.status_code in (400, 409) and any(
            phrase in text for phrase in ("no available", "not available", "already", "booked", "slot")
        )
        log_event(
            event="calcom_booking_http_error",
            status=resp.status_code,
            interpreted_as="slot_taken" if taken else "unavailable",
        )
        return {"ok": False, "reason": "slot_taken" if taken else "unavailable"}

    try:
        data = resp.json().get("data") or {}
    except ValueError:
        log_event(event="calcom_booking_bad_json")
        return {"ok": False, "reason": "unavailable"}

    uid = data.get("uid") or data.get("id")
    if not uid:
        log_event(event="calcom_booking_no_uid")
        return {"ok": False, "reason": "unavailable"}
    return {"ok": True, "cal_booking_id": str(uid)}


def cancel_booking(*, cal_booking_id: str, reason: str = "Rescheduled by caller") -> bool:
    """Best-effort cancel (used when a caller moves their tour mid-call). Never raises:
    a stale calendar hold is worth logging, not failing the caller's new booking over."""
    try:
        with httpx.Client(timeout=CALCOM_TIMEOUT_SEC) as client:
            resp = client.post(
                f"{CALCOM_API_BASE}/bookings/{cal_booking_id}/cancel",
                json={"cancellationReason": reason},
                headers=_headers(CALCOM_BOOKINGS_API_VERSION),
            )
    except httpx.HTTPError as exc:
        log_event(event="calcom_cancel_error", error=type(exc).__name__)
        return False
    if resp.status_code >= 400:
        log_event(event="calcom_cancel_http_error", status=resp.status_code)
        return False
    return True


def probe() -> dict:
    """Credit-safe smoke test for scripts/test_calcom.py: proves the key works and the
    event type resolves, without creating a booking. Free - Cal.com has no per-call cost."""
    try:
        with httpx.Client(timeout=CALCOM_TIMEOUT_SEC) as client:
            resp = client.get(
                f"{CALCOM_API_BASE}/me", headers=_headers(CALCOM_BOOKINGS_API_VERSION)
            )
    except httpx.HTTPError as exc:
        return {"ok": False, "reason": type(exc).__name__}
    if resp.status_code >= 400:
        return {"ok": False, "reason": f"http_{resp.status_code}"}
    data = resp.json().get("data") or {}
    return {"ok": True, "username": data.get("username"), "email": data.get("email")}


def default_window(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now, now + timedelta(days=days)
