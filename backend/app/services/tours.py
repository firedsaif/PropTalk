"""Tour scheduling.

Phase 2: check_tour_slots returns synthetic slots generated from business hours
(no Cal.com account yet - Phase 4 swaps `generate_mock_slots` for a real Cal.com
availability call and `book_tour`'s insert for a real Cal.com booking call; the
DB shape and idempotency/conflict logic below do not change).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from psycopg import errors
from psycopg.rows import dict_row

from app.config import (
    TOUR_BUSINESS_HOURS,
    TOUR_SLOT_DURATION_MIN,
    TOUR_SLOTS_LOOKAHEAD_DAYS,
    TOUR_SLOTS_RETURNED,
)

MIN_LEAD_TIME = timedelta(hours=2)

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


def generate_mock_slots(
    tz_name: str, date_preference: str | None = None, count: int = TOUR_SLOTS_RETURNED
) -> list[datetime]:
    """Business-hours slots for the next TOUR_SLOTS_LOOKAHEAD_DAYS days, as UTC datetimes."""
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    earliest = now_local + MIN_LEAD_TIME

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
            if slot >= earliest:
                candidates.append(slot)
            slot += timedelta(minutes=TOUR_SLOT_DURATION_MIN)

    preferred = [s for s in candidates if _matches_preference(s, date_preference)]
    chosen = preferred if preferred else candidates
    return [s.astimezone(timezone.utc) for s in chosen[:count]]


def list_open_slots(
    conn, property_id: str, tz_name: str, date_preference: str | None = None,
    count: int = TOUR_SLOTS_RETURNED,
) -> list[datetime]:
    """generate_mock_slots, minus any already booked for this property."""
    candidates = generate_mock_slots(tz_name, date_preference, count=count * 6)
    with conn.cursor() as cur:
        cur.execute(
            "select slot_start from tour_bookings where property_id = %(property_id)s::uuid and status = 'booked'",
            {"property_id": property_id},
        )
        booked = {row[0] for row in cur.fetchall()}
    open_slots = [s for s in candidates if s not in booked]
    return open_slots[:count]


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


def book_tour(
    conn,
    *,
    client_id: str,
    retell_call_id: str | None,
    property_id: str,
    slot_start: datetime,
    prospect_name: str,
    prospect_phone: str,
    sms_consent: bool,
) -> dict:
    """Insert a booking. Idempotent on (retell_call_id, property_id, slot_start);
    on a genuine conflict (slot already booked by someone else) returns the next
    available slots instead of overwriting anything."""
    with conn.cursor(row_factory=dict_row) as cur:
        if retell_call_id:
            cur.execute(
                """
                select id::text as booking_id, slot_start
                from tour_bookings
                where retell_call_id = %(retell_call_id)s
                  and property_id = %(property_id)s::uuid
                  and slot_start = %(slot_start)s
                """,
                {
                    "retell_call_id": retell_call_id,
                    "property_id": property_id,
                    "slot_start": slot_start,
                },
            )
            existing = cur.fetchone()
            if existing:
                # Idempotent re-call for the same tour (e.g. the agent re-books to record
                # SMS consent given after the first call): keep the one booking, but let the
                # latest explicit consent win - it's the TCPA audit value (docs/rules.md SS6).
                cur.execute(
                    "update tour_bookings set sms_consent = %(c)s where id = %(id)s::uuid",
                    {"c": sms_consent, "id": existing["booking_id"]},
                )
                conn.commit()
                return {"ok": True, "booking_id": existing["booking_id"], "conflict": False}

        try:
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
            row = cur.fetchone()
            conn.commit()
            return {"ok": True, "booking_id": row["booking_id"], "conflict": False}
        except errors.UniqueViolation:
            conn.rollback()
            return {"ok": False, "conflict": True}
