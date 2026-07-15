"""Call row upsert for the Retell webhook: idempotent on retell_call_id, tolerates
duplicate/out-of-order deliveries (call_started / call_ended / call_analyzed all
land here), and enforces the pilot minutes_cap exactly once per call.
"""
from __future__ import annotations

import math

from psycopg.rows import dict_row

from app.logging import log_event


def upsert_call(
    conn,
    *,
    client_id: str,
    retell_call_id: str,
    from_number: str | None,
    started_at,
    ended_at,
    duration_sec: int | None,
    transcript: str | None,
    recording_url: str | None,
    summary: str | None,
) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("select duration_sec from calls where retell_call_id = %(id)s", {"id": retell_call_id})
        prev = cur.fetchone()
        old_duration = prev["duration_sec"] if prev else None

        cur.execute(
            """
            insert into calls
                (client_id, retell_call_id, from_number, started_at, ended_at,
                 duration_sec, intent, outcome, summary, transcript, recording_url)
            values
                (%(client_id)s::uuid, %(retell_call_id)s, %(from_number)s, %(started_at)s, %(ended_at)s,
                 %(duration_sec)s, null, null, %(summary)s, %(transcript)s, %(recording_url)s)
            on conflict (retell_call_id) do update set
                from_number = coalesce(excluded.from_number, calls.from_number),
                started_at = coalesce(excluded.started_at, calls.started_at),
                ended_at = coalesce(excluded.ended_at, calls.ended_at),
                duration_sec = coalesce(excluded.duration_sec, calls.duration_sec),
                summary = coalesce(excluded.summary, calls.summary),
                transcript = coalesce(excluded.transcript, calls.transcript),
                recording_url = coalesce(excluded.recording_url, calls.recording_url)
            """,
            {
                "client_id": client_id,
                "retell_call_id": retell_call_id,
                "from_number": from_number,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_sec": duration_sec,
                "summary": summary,
                "transcript": transcript,
                "recording_url": recording_url,
            },
        )
    conn.commit()

    # Only the first delivery that carries a duration increments minutes_used -
    # every later retry/event for the same call sees old_duration already set.
    if old_duration is None and duration_sec is not None:
        _apply_minutes_used(conn, client_id=client_id, minutes=math.ceil(duration_sec / 60))


def set_call_outcome(conn, *, retell_call_id: str, outcome: str) -> None:
    """Stamp what the call produced (Phase 4). Kept out of upsert_call because it's
    derived from rows written *during* the call, so it's only knowable once those are
    committed - i.e. at call_analyzed, not at call_started."""
    with conn.cursor() as cur:
        cur.execute(
            "update calls set outcome = %(outcome)s where retell_call_id = %(id)s",
            {"outcome": outcome, "id": retell_call_id},
        )
    conn.commit()


def _apply_minutes_used(conn, *, client_id: str, minutes: int) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            update clients set minutes_used = minutes_used + %(minutes)s
            where id = %(client_id)s::uuid
            returning minutes_used, minutes_cap
            """,
            {"client_id": client_id, "minutes": minutes},
        )
        row = cur.fetchone()
    conn.commit()
    if row and row["minutes_used"] > row["minutes_cap"]:
        log_event(
            event="minutes_cap_breached",
            client_id=client_id,
            minutes_used=row["minutes_used"],
            minutes_cap=row["minutes_cap"],
        )
