"""Catch-all messages for the office (rent questions, complaints, wants-a-human, etc.)."""
from __future__ import annotations

from psycopg.rows import dict_row


def create_message(
    conn, *, client_id: str, caller_name: str, callback_number: str, reason: str, message: str
) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into messages (client_id, caller_name, callback_number, reason, body)
            values (%(client_id)s::uuid, %(caller_name)s, %(callback_number)s, %(reason)s, %(message)s)
            returning id::text as message_id
            """,
            {
                "client_id": client_id,
                "caller_name": caller_name,
                "callback_number": callback_number,
                "reason": reason,
                "message": message,
            },
        )
        row = cur.fetchone()
    conn.commit()
    return row["message_id"]
