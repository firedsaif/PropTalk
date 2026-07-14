"""Listing search - the core query behind the get_available_listings tool.

All filters are optional. Returns at most 3 available listings with only the
compact fields the agent needs (see docs/RETELL_AGENT_CONFIG.md - tokens are
latency). `pets=True` means the caller HAS a pet, so restrict to pet-friendly
units; `pets` false/None does not filter (a pet-free caller can take any unit).
"""
from __future__ import annotations

from psycopg.rows import dict_row

SEARCH_SQL = """
select id::text as property_id, label, beds, baths, rent,
       available_date, pets_allowed, pet_policy, highlights, address
from properties
where client_id = %(client_id)s::uuid
  and status = 'available'
  and (%(beds)s::int is null or beds >= %(beds)s::int)
  and (%(max_rent)s::int is null or rent <= %(max_rent)s::int)
  and (coalesce(%(pets)s::boolean, false) = false or pets_allowed = true)
  and (%(move_in_by)s::date is null or available_date <= %(move_in_by)s::date)
order by rent asc, available_date asc
limit 3
"""


def search_listings(conn, client_id, beds=None, max_rent=None, pets=None, move_in_by=None):
    """Return up to 3 available listings matching the optional filters."""
    params = {
        "client_id": client_id,
        "beds": beds,
        "max_rent": max_rent,
        "pets": pets,
        "move_in_by": move_in_by,
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(SEARCH_SQL, params)
        return cur.fetchall()
