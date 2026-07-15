"""Emergency escalation: log the ticket, then fire-and-return the on-call alert."""
from __future__ import annotations

from psycopg.rows import dict_row

from app.config import MAINTENANCE_SEVERITY_EMERGENCY
from app.services.notify import alert_escalation


def create_emergency_ticket(
    conn,
    *,
    client_id: str,
    retell_call_id: str | None,
    escalation_phone: str | None,
    unit: str,
    issue: str,
    callback_number: str,
    caller_safe: bool | None,
) -> dict:
    description = issue if caller_safe is not False else f"{issue} (caller advised to call 911)"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into maintenance_tickets
                (client_id, retell_call_id, unit, issue_type, severity, description, callback_number)
            values
                (%(client_id)s::uuid, %(retell_call_id)s, %(unit)s, 'emergency', %(severity)s,
                 %(description)s, %(callback_number)s)
            returning id::text as ticket_id
            """,
            {
                "client_id": client_id,
                "retell_call_id": retell_call_id,
                "unit": unit,
                "severity": MAINTENANCE_SEVERITY_EMERGENCY,
                "description": description,
                "callback_number": callback_number,
            },
        )
        row = cur.fetchone()
    conn.commit()
    notified = alert_escalation(
        client_id=client_id, escalation_phone=escalation_phone, unit=unit, issue=issue
    )
    return {"ticket_id": row["ticket_id"], "notified": notified}
