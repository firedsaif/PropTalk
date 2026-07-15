"""Tour scheduling: availability + booking.

Phase 4 wires this to a real Cal.com calendar. Two rules shape everything below:

1. **The calendar is authoritative for what's free; our DB is authoritative for what's
   booked.** Cal.com decides which times exist; the partial unique indexes on
   `tour_bookings` (see sql/schema.sql) are what actually make double-booking
   impossible, because they're atomic and Cal.com's HTTP call is not.
2. **Never offer a time we can't book.** When Cal.com is unreachable we return *no*
   slots rather than falling back to invented business-hours times - offering a slot
   that doesn't exist is the fabrication docs/rules.md SS3 forbids. The business-hours
   generator survives only as the no-Cal.com-account path (docs/phases.md: $0 until
   outreach), where it's the declared source of truth rather than a guess.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from psycopg import errors
from psycopg.rows import dict_row

from app.config import (
    CALCOM_ATTENDEE_EMAIL_DOMAIN,
    TOUR_BUSINESS_HOURS,
    TOUR_MIN_LEAD_HOURS,
    TOUR_SLOT_DURATION_MIN,
    TOUR_SLOTS_LOOKAHEAD_DAYS,
    TOUR_SLOTS_RETURNED,
)
from app.logging import log_event
from app.services import calcom

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _matches_preference(slot_local: datetime, preference: str | None) -> bool:
    if not preference:
        return True
    pref = preference.lower()
    for i, name in enumerate(_WEEKDAYS):
        if name in pref and slot_local.weekday() != i:
            return False
    if "morning" in pref and not (0 <= slot_local.hour < 12):
        return False
    if "afternoon" in pref and not (12 <= slot_local.hour < 17):
        return False
    if "evening" in pref and slot_local.hour < 17:
        return False
    return True


def generate_mock_slots(tz_name: str) -> list[datetime]:
    """Every business-hours slot in the lookahead window, as UTC datetimes.

    Used only when no Cal.com event type is configured. Returns all candidates -
    preference filtering, lead time and count are applied uniformly by list_open_slots
    so the mock and the real calendar go through identical downstream logic.
    """
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)

    candidates: list[datetime] = []
    for day_offset in range(TOUR_SLOTS_LOOKAHEAD_DAYS + 1):
        day = (now_local + timedelta(days=day_offset)).date()
        hours = TOUR_BUSINESS_HOURS.get(day.weekday())
        if not hours:
            continue
        start_hour, end_hour = hours
        slot = datetime(day.year, day.month, day.day, start_hour, 0, tzinfo=tz)
        end = datetime(day.year, day.month, day.day, end_hour, 0, tzinfo=tz)
        while slot < end:
            candidates.append(slot.astimezone(timezone.utc))
            slot += timedelta(minutes=TOUR_SLOT_DURATION_MIN)
    return candidates


def _booked_slots(conn, property_id: str) -> set[datetime]:
    """Slots this property already holds. Cal.com availability normally reflects these
    already (we book into it), but a booking whose calendar write degraded exists only
    here - so this stays a belt-and-braces filter over both sources."""
    with conn.cursor() as cur:
        cur.execute(
            "select slot_start from tour_bookings "
            "where property_id = %(property_id)s::uuid and status = 'booked'",
            {"property_id": property_id},
        )
        return {row[0] for row in cur.fetchall()}


def list_open_slots(
    conn,
    *,
    client: dict,
    property_id: str,
    date_preference: str | None = None,
    count: int = TOUR_SLOTS_RETURNED,
) -> list[datetime]:
    """The next `count` bookable slots (UTC), honouring the caller's stated preference."""
    tz_name = client["timezone"]
    event_type_id = calcom.event_type_id_for(client)

    if calcom.is_configured(event_type_id):
        start, end = calcom.default_window(TOUR_SLOTS_LOOKAHEAD_DAYS)
        candidates = calcom.get_slots(
            event_type_id=event_type_id, start=start, end=end, tz_name=tz_name
        )
        if candidates is None:
            log_event(
                event="tour_slots_degraded", client_id=client["id"], reason="calcom_unavailable"
            )
            return []  # honest empty: the agent offers to take a message instead
    else:
        candidates = generate_mock_slots(tz_name)

    tz = ZoneInfo(tz_name)
    earliest = datetime.now(timezone.utc) + timedelta(hours=TOUR_MIN_LEAD_HOURS)
    booked = _booked_slots(conn, property_id)

    usable = [s for s in sorted(candidates) if s >= earliest and s not in booked]
    preferred = [s for s in usable if _matches_preference(s.astimezone(tz), date_preference)]
    # A stated preference is a preference, not a filter - if Thursday is full, the agent
    # should still have something to offer rather than dead-ending the call.
    return (preferred or usable)[:count]


def get_property(conn, client_id: str, property_ref: str) -> dict | None:
    """Resolve a property by its LLM-facing short code (e.g. '2A'), case-insensitively.

    Also accepts a raw UUID as a fallback. Neither branch casts the caller's string to
    ::uuid, so a mangled value the LLM might send (e.g. '2') can't raise - it simply
    matches nothing and returns None, letting the tool degrade to a clean not_found.
    Returns the real uuid as `id` for downstream writes; `property_id` echoes the code.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select p.id::text as id, p.code as property_id, p.label, p.address,
                   p.status, c.timezone
            from properties p join clients c on c.id = p.client_id
            where p.client_id = %(client_id)s::uuid
              and (lower(p.code) = lower(%(ref)s) or p.id::text = %(ref)s)
            """,
            {"client_id": client_id, "ref": property_ref},
        )
        return cur.fetchone()


def _attendee_email(client: dict, prospect_phone: str) -> str:
    """Cal.com requires an attendee email; a caller on the phone will never spell one.

    Preferred: a plus-tagged form of the client's notify address, so the tour invite
    lands in the PM's own inbox and stays filterable. Failing that, a reserved .invalid
    address (RFC 2606) - deliberately undeliverable, so we never imply we emailed a
    prospect who only ever gave us a phone number.
    """
    digits = "".join(ch for ch in prospect_phone if ch.isdigit())[-10:] or "unknown"
    notify = (client.get("notify_email") or "").strip()
    if notify and "@" in notify and "+" not in notify.split("@", 1)[0]:
        local, domain = notify.split("@", 1)
        return f"{local}+tour-{digits}@{domain}"
    return f"tour-{digits}@{CALCOM_ATTENDEE_EMAIL_DOMAIN}"


def _find_existing(
    conn, *, retell_call_id: str | None, property_id: str, slot_start: datetime
) -> dict | None:
    """An active booking for this exact call+property+slot, i.e. a retry of the same
    intent rather than a new one. Scoped to status='booked' so a slot we previously
    released (rescheduled/cancelled) is never mistaken for a live booking."""
    if not retell_call_id:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select id::text as booking_id, slot_start, cal_booking_id
            from tour_bookings
            where retell_call_id = %(retell_call_id)s
              and property_id = %(property_id)s::uuid
              and slot_start = %(slot_start)s
              and status = 'booked'
            """,
            {
                "retell_call_id": retell_call_id,
                "property_id": property_id,
                "slot_start": slot_start,
            },
        )
        return cur.fetchone()


def _find_reschedulable(
    conn, *, client_id: str, property_id: str, prospect_phone: str, slot_start: datetime
) -> dict | None:
    """This prospect's existing tour for this same unit at a *different* time.

    Matched on phone rather than call id so "actually, can we do Thursday?" works both
    mid-call and when they ring back later. Scoped to the same property on purpose:
    booking a *different* unit is a second tour, not a reschedule. This only ever touches
    a booking made by the same phone number - it can't overwrite anyone else's
    (docs/rules.md SS3).
    """
    if not prospect_phone:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select id::text as booking_id, slot_start, cal_booking_id
            from tour_bookings
            where client_id = %(client_id)s::uuid
              and property_id = %(property_id)s::uuid
              and prospect_phone = %(prospect_phone)s
              and slot_start <> %(slot_start)s
              and status = 'booked'
            order by created_at desc
            limit 1
            """,
            {
                "client_id": client_id,
                "property_id": property_id,
                "prospect_phone": prospect_phone,
                "slot_start": slot_start,
            },
        )
        return cur.fetchone()


def _release(conn, *, booking_id: str, status: str) -> None:
    """Free a slot we own by moving it out of status='booked' (the partial indexes key
    off that), keeping the row as an audit trail rather than deleting history."""
    with conn.cursor() as cur:
        cur.execute(
            "update tour_bookings set status = %(status)s where id = %(id)s::uuid",
            {"status": status, "id": booking_id},
        )
    conn.commit()


def book_tour(
    conn,
    *,
    client: dict,
    retell_call_id: str | None,
    property_id: str,
    property_label: str | None,
    slot_start: datetime,
    prospect_name: str,
    prospect_phone: str,
    sms_consent: bool,
) -> dict:
    """Book a tour: DB row first (the atomic guard), then the calendar.

    Order matters. The insert is what makes double-booking impossible, and it's cheap,
    so it happens before the ~seconds-long HTTP call rather than inside it - no lock is
    ever held across the network.

    Returns {"ok": True, booking_id, calendar, rescheduled_from} or
    {"ok": False, "conflict": True} when the slot is genuinely gone.
    `calendar` is one of: booked | degraded (DB has it, Cal.com doesn't) | skipped (no Cal.com).
    """
    client_id = client["id"]

    existing = _find_existing(
        conn, retell_call_id=retell_call_id, property_id=property_id, slot_start=slot_start
    )
    if existing:
        # Idempotent re-call for the same tour (e.g. the agent re-books to record SMS
        # consent given after the first call): keep the one booking, but let the latest
        # explicit consent win - it's the TCPA audit value (docs/rules.md SS6).
        with conn.cursor() as cur:
            cur.execute(
                "update tour_bookings set sms_consent = %(c)s where id = %(id)s::uuid",
                {"c": sms_consent, "id": existing["booking_id"]},
            )
        conn.commit()
        return {
            "ok": True,
            "booking_id": existing["booking_id"],
            "conflict": False,
            "calendar": "booked" if existing["cal_booking_id"] else "degraded",
            "rescheduled_from": None,
        }

    previous = _find_reschedulable(
        conn,
        client_id=client_id,
        property_id=property_id,
        prospect_phone=prospect_phone,
        slot_start=slot_start,
    )

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                insert into tour_bookings
                    (client_id, retell_call_id, property_id, prospect_name,
                     prospect_phone, slot_start, sms_consent, status)
                values
                    (%(client_id)s::uuid, %(retell_call_id)s, %(property_id)s::uuid, %(prospect_name)s,
                     %(prospect_phone)s, %(slot_start)s, %(sms_consent)s, 'booked')
                returning id::text as booking_id
                """,
                {
                    "client_id": client_id,
                    "retell_call_id": retell_call_id,
                    "property_id": property_id,
                    "prospect_name": prospect_name,
                    "prospect_phone": prospect_phone,
                    "slot_start": slot_start,
                    "sms_consent": sms_consent,
                },
            )
            booking_id = cur.fetchone()["booking_id"]
        conn.commit()
    except errors.UniqueViolation:
        conn.rollback()
        return {"ok": False, "conflict": True}

    calendar = _write_to_calendar(
        conn,
        client=client,
        booking_id=booking_id,
        property_id=property_id,
        property_label=property_label,
        slot_start=slot_start,
        prospect_name=prospect_name,
        prospect_phone=prospect_phone,
    )
    if calendar == "slot_taken":
        # The calendar says that time is gone (booked outside PropTalk). Release the row
        # we just took so the slot isn't dead, and let the agent offer another time.
        _release(conn, booking_id=booking_id, status="cancelled")
        return {"ok": False, "conflict": True}

    if previous:
        # New booking is secured before the old one is released - the caller can never
        # end up with neither.
        _release(conn, booking_id=previous["booking_id"], status="rescheduled")
        if previous["cal_booking_id"]:
            calcom.cancel_booking(cal_booking_id=previous["cal_booking_id"])
        log_event(
            event="tour_rescheduled",
            client_id=client_id,
            retell_call_id=retell_call_id,
            booking_id=booking_id,
        )

    return {
        "ok": True,
        "booking_id": booking_id,
        "conflict": False,
        "calendar": calendar,
        "rescheduled_from": previous["slot_start"] if previous else None,
    }


def _write_to_calendar(
    conn,
    *,
    client: dict,
    booking_id: str,
    property_id: str,
    property_label: str | None,
    slot_start: datetime,
    prospect_name: str,
    prospect_phone: str,
) -> str:
    """Mirror a committed booking onto Cal.com. Returns: booked | degraded | skipped | slot_taken."""
    event_type_id = calcom.event_type_id_for(client)
    if not calcom.is_configured(event_type_id):
        return "skipped"

    result = calcom.create_booking(
        event_type_id=event_type_id,
        start=slot_start,
        tz_name=client["timezone"],
        attendee_name=prospect_name,
        attendee_email=_attendee_email(client, prospect_phone),
        attendee_phone=prospect_phone,
        metadata={"unit": (property_label or "")[:100], "booking_id": booking_id},
    )
    if result["ok"]:
        with conn.cursor() as cur:
            cur.execute(
                "update tour_bookings set cal_booking_id = %(cal)s where id = %(id)s::uuid",
                {"cal": result["cal_booking_id"], "id": booking_id},
            )
        conn.commit()
        return "booked"

    if result["reason"] == "slot_taken":
        return "slot_taken"

    # Cal.com is down/unreachable, but the caller is on the line and the tour is real:
    # keep the booking (our DB is the source of truth) and make the gap loud. The PM's
    # summary email flags it so a human can put it on the calendar by hand.
    log_event(
        event="tour_booked_without_calendar",
        client_id=client["id"],
        booking_id=booking_id,
        property_id=property_id,
    )
    return "degraded"
