"""Routine (non-emergency) maintenance tickets."""
from __future__ import annotations

from psycopg.rows import dict_row

from app.config import MAINTENANCE_SEVERITY_ROUTINE


def create_ticket(
    conn,
    *,
    client_id: str,
    unit: str,
    issue_type: str,
    description: str,
    callback_number: str,
    permission_to_enter: bool | None,
) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into maintenance_tickets
                (client_id, unit, issue_type, severity, description, callback_number, permission_to_enter)
            values
                (%(client_id)s::uuid, %(unit)s, %(issue_type)s, %(severity)s, %(description)s,
                 %(callback_number)s, %(permission_to_enter)s)
            returning id::text as ticket_id
            """,
            {
                "client_id": client_id,
                "unit": unit,
                "issue_type": issue_type,
                "severity": MAINTENANCE_SEVERITY_ROUTINE,
                "description": description,
                "callback_number": callback_number,
                "permission_to_enter": permission_to_enter,
            },
        )
        row = cur.fetchone()
    conn.commit()
    return row["ticket_id"]
