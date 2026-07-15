"""Post-call summary: what Retell concluded + what we actually did.

The prose summary is Retell's own (`call_analysis.call_summary` on the call_analyzed
event) - no second LLM bill, no extra latency (docs/architecture.md SS2). But prose alone
doesn't sell: the client's email leads with the *rows we wrote*, which are facts we can
stand behind, and uses Retell's paragraph as colour underneath.
"""
from __future__ import annotations

from psycopg.rows import dict_row


def extract_summary(call_analysis: dict | None) -> str | None:
    if not call_analysis:
        return None
    return call_analysis.get("call_summary")


def extract_outcome(call_analysis: dict | None, outcomes: dict) -> str:
    """One-word outcome for the calls row + the email's badge.

    Derived from what the call actually produced, not from the model's opinion - a
    booking row is evidence, a summary sentence is a claim. Ordered by what the PM
    cares about most if a call did several things.
    """
    if outcomes.get("emergencies"):
        return "escalated"
    if outcomes.get("bookings"):
        return "tour_booked"
    if outcomes.get("tickets"):
        return "ticket_created"
    if outcomes.get("messages"):
        return "message_taken"
    return "info_only"


def collect_outcomes(conn, *, client_id: str, retell_call_id: str) -> dict:
    """Everything this call produced, scoped to one client and one call.

    Emergencies are split out of tickets so the email can lead with them - a flooded
    unit and a dripping tap are not the same email.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select tb.prospect_name, tb.prospect_phone, tb.slot_start, tb.sms_consent,
                   tb.cal_booking_id, tb.status, p.label, p.address, p.rent
            from tour_bookings tb
            left join properties p on p.id = tb.property_id
            where tb.client_id = %(client_id)s::uuid
              and tb.retell_call_id = %(retell_call_id)s
              and tb.status = 'booked'
            order by tb.created_at
            """,
            {"client_id": client_id, "retell_call_id": retell_call_id},
        )
        bookings = cur.fetchall()

        cur.execute(
            """
            select unit, issue_type, severity, description, callback_number, permission_to_enter
            from maintenance_tickets
            where client_id = %(client_id)s::uuid and retell_call_id = %(retell_call_id)s
            order by created_at
            """,
            {"client_id": client_id, "retell_call_id": retell_call_id},
        )
        all_tickets = cur.fetchall()

        cur.execute(
            """
            select caller_name, callback_number, reason, body
            from messages
            where client_id = %(client_id)s::uuid and retell_call_id = %(retell_call_id)s
            order by created_at
            """,
            {"client_id": client_id, "retell_call_id": retell_call_id},
        )
        msgs = cur.fetchall()

    return {
        "bookings": bookings,
        "emergencies": [t for t in all_tickets if t["severity"] == "emergency"],
        "tickets": [t for t in all_tickets if t["severity"] != "emergency"],
        "messages": msgs,
    }
