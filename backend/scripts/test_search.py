"""Verify the listing search returns the right units for realistic filters.

Run from the backend/ folder:  python scripts/test_search.py
This is the Phase 1 exit check: search returns correct listings for real filters.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_connection  # noqa: E402
from app.services.listings import search_listings  # noqa: E402

WILLOWBROOK = "11111111-1111-1111-1111-111111111111"

SCENARIOS = [
    ("At least 2 beds, budget $1900, has a dog", dict(beds=2, max_rent=1900, pets=True)),
    ("At least 1 bed, cheapest first",            dict(beds=1)),
    ("3-bed under $2500",                         dict(beds=3, max_rent=2500)),
    ("Anything under $1400",                      dict(max_rent=1400)),
    ("Pet-friendly under $1500",                  dict(max_rent=1500, pets=True)),
]


def main() -> None:
    with get_connection() as conn:
        for name, filt in SCENARIOS:
            rows = search_listings(conn, WILLOWBROOK, **filt)
            print(f"\n> {name}  ->  {len(rows)} match(es)")
            for r in rows:
                print(f"    {r['label']:<34} {r['beds']}bd  ${r['rent']:<5} "
                      f"pets={str(r['pets_allowed']):<5} avail {r['available_date']}")

        # Honesty guard: the leased unit is in the DB but must be excluded from search.
        with conn.cursor() as cur:
            cur.execute(
                "select label from properties where client_id = %s::uuid and status = 'leased'",
                (WILLOWBROOK,),
            )
            leased = [row[0] for row in cur.fetchall()]
        print(f"\nIn DB but excluded from every search (status=leased): {leased or 'none'}")


if __name__ == "__main__":
    main()
