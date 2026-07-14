"""Client resolution: every tool call is scoped to one client_id, always.

Retell is configured (Phase 3) to pass client_id as a query param on each
tool/webhook URL via a dynamic variable, e.g. .../tools/take_message?client_id={{client_id}}.
There is no default/global client - an unresolvable client_id is a 404, not a fallback.
"""
from __future__ import annotations

import time

from fastapi import HTTPException
from psycopg.rows import dict_row

CLIENT_FIELDS = (
    "id::text as id, company_name, agent_name, timezone, escalation_phone, "
    "notify_email, cal_event_type_id, plan, minutes_cap, minutes_used"
)

# Every tool call resolves its client first - without a cache that's a second full DB
# round trip per call (painful when the DB is a continent away in dev). The client row
# is near-static (company/agent/hours/escalation), so a short TTL is safe. The one
# volatile field, minutes_used, is never read from here - the webhook updates it with
# its own RETURNING query (see services/calls.py), so a stale cached value can't
# mis-enforce the cap.
_CLIENT_CACHE: dict[str, tuple[float, dict]] = {}
_CLIENT_CACHE_TTL = 60.0  # seconds


def resolve_client(conn, client_id: str) -> dict:
    """Load the client row (cached up to TTL) or raise 404."""
    hit = _CLIENT_CACHE.get(client_id)
    if hit is not None and (time.monotonic() - hit[0]) < _CLIENT_CACHE_TTL:
        return hit[1]

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"select {CLIENT_FIELDS} from clients where id = %(id)s::uuid",
            {"id": client_id},
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="unknown client_id")
    _CLIENT_CACHE[client_id] = (time.monotonic(), row)
    return row
