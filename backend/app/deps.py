"""Client resolution: every tool call is scoped to one client_id, always.

Retell is configured (Phase 3) to pass client_id as a query param on each
tool/webhook URL via a dynamic variable, e.g. .../tools/take_message?client_id={{client_id}}.
There is no default/global client - an unresolvable client_id is a 404, not a fallback.
"""
from __future__ import annotations

from fastapi import HTTPException
from psycopg.rows import dict_row

CLIENT_FIELDS = (
    "id::text as id, company_name, agent_name, timezone, escalation_phone, "
    "notify_email, cal_event_type_id, plan, minutes_cap, minutes_used"
)


def resolve_client(conn, client_id: str) -> dict:
    """Load the client row or raise 404."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"select {CLIENT_FIELDS} from clients where id = %(id)s::uuid",
            {"id": client_id},
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="unknown client_id")
    return row
