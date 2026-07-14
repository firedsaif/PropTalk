"""Reset the demo tenant to a pristine state for a clean test call / demo / gauntlet run.

Clears the transactional tables (calls, tour_bookings, maintenance_tickets, messages)
and resets clients.minutes_used to 0. NEVER touches clients or properties - the seed
(Willowbrook + 8 listings) stays intact. Safe to run repeatedly.

Run from backend/:  python scripts/reset_demo_state.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_connection  # noqa: E402

WILLOWBROOK = "11111111-1111-1111-1111-111111111111"


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # tour_bookings references calls(id); delete children first.
            cur.execute("delete from tour_bookings where client_id = %s::uuid", (WILLOWBROOK,))
            bookings = cur.rowcount
            cur.execute("delete from maintenance_tickets where client_id = %s::uuid", (WILLOWBROOK,))
            tickets = cur.rowcount
            cur.execute("delete from messages where client_id = %s::uuid", (WILLOWBROOK,))
            msgs = cur.rowcount
            cur.execute("delete from calls where client_id = %s::uuid", (WILLOWBROOK,))
            calls = cur.rowcount
            cur.execute("update clients set minutes_used = 0 where id = %s::uuid", (WILLOWBROOK,))
        conn.commit()
    print(
        f"Reset Willowbrook: cleared {calls} calls, {bookings} bookings, "
        f"{tickets} tickets, {msgs} messages; minutes_used -> 0. Seed data untouched."
    )


if __name__ == "__main__":
    main()
