"""Render the post-call summary email to HTML files, offline.

The summary email is the #1 sales artifact, so it needs to be iterated on visually -
but a real render costs a Retell call plus a Resend send. This renders every outcome
variant from fixture data with no network, no database and no spend:

    python scripts\\preview_summary_email.py [outdir]

Then open the files in a browser. Run it after touching services/email_template.py.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.email_template import render_summary_email  # noqa: E402

CLIENT = {
    "id": "11111111-1111-1111-1111-111111111111",
    "company_name": "Willowbrook Apartments",
    "agent_name": "Maya",
    "timezone": "America/New_York",
    "notify_email": "manager@example.com",
}

TRANSCRIPT = """Agent: Thanks for calling Willowbrook Apartments, this is Maya. Just so you know, this call is recorded. How can I help?
User: Hi, I saw you had some two bedrooms available? I'm looking to move in the next couple of weeks.
Agent: We do. Can I ask what your budget looks like, and will any pets be joining you?
User: Around eighteen hundred, and I have a small dog. Is that alright?
Agent: It is. I have Unit 2A, a two bed two bath at seventeen ninety-five a month, available from the first. It's pet friendly, up to fifty pounds, and it's the one with the renovated kitchen and the balcony.
User: That sounds perfect, can I see it?
Agent: Absolutely. I have Thursday at two, Thursday at four, or Friday at eleven.
User: Thursday at two works.
Agent: Great. Can I get your name and the best number for you?
User: Jane Curran, eight one three, five five five, zero one nine nine.
Agent: Thank you Jane. Is it alright if we text you a confirmation and a reminder at that number?
User: Yeah that's fine.
Agent: Perfect. You're booked for Thursday at two for Unit 2A. You'll get a text shortly. Anything else I can help with?
User: Nope, thank you!
Agent: Have a great day, Jane."""


def _call(**over) -> dict:
    base = {
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=42),
        "duration_sec": 193,
        "from_number": "+18135550199",
        "transcript": TRANSCRIPT,
        "recording_url": "https://example.com/recording.wav",
    }
    base.update(over)
    return base


SLOT = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)

BOOKING = {
    "prospect_name": "Jane Curran",
    "prospect_phone": "+18135550199",
    "slot_start": SLOT,
    "sms_consent": True,
    "cal_booking_id": "cal_abc123",
    "status": "booked",
    "label": "Unit 2A — Willowbrook Apartments",
    "address": "1420 Willowbrook Ln, Tampa, FL 33607",
    "rent": 1795,
}

CASES: dict[str, dict] = {
    "tour_booked": {
        "outcome": "tour_booked",
        "outcomes": {"bookings": [BOOKING], "emergencies": [], "tickets": [], "messages": []},
        "summary_text": (
            "Jane Curran called about two-bedroom availability with a move-in in the next two "
            "weeks, a budget around $1,800 and one small dog. Maya offered Unit 2A at $1,795 "
            "and booked a tour for Thursday at 2:00 PM. Jane consented to text reminders."
        ),
    },
    # The degraded path deserves its own eyeball: this is the email a client gets when we
    # booked a real tour their calendar never heard about.
    "tour_booked_no_calendar": {
        "outcome": "tour_booked",
        "outcomes": {
            "bookings": [{**BOOKING, "cal_booking_id": None, "sms_consent": False}],
            "emergencies": [],
            "tickets": [],
            "messages": [],
        },
        "summary_text": "Jane Curran booked a tour of Unit 2A for Thursday at 2:00 PM.",
    },
    "emergency": {
        "outcome": "escalated",
        "outcomes": {
            "bookings": [],
            "emergencies": [
                {
                    "unit": "4B",
                    "issue_type": "emergency",
                    "severity": "emergency",
                    "description": "Water pouring from the ceiling in the kitchen, spreading fast",
                    "callback_number": "+18135550143",
                    "permission_to_enter": True,
                }
            ],
            "tickets": [],
            "messages": [],
        },
        "summary_text": (
            "Tenant in 4B reported water pouring from the kitchen ceiling. Maya confirmed the "
            "caller was safe, escalated to the on-call contact and advised shutting off the "
            "water at the main if reachable."
        ),
    },
    "maintenance": {
        "outcome": "ticket_created",
        "outcomes": {
            "bookings": [],
            "emergencies": [],
            "tickets": [
                {
                    "unit": "12C",
                    "issue_type": "appliance",
                    "severity": "routine",
                    "description": "Dishwasher isn't draining, standing water at the bottom",
                    "callback_number": "+18135550177",
                    "permission_to_enter": True,
                }
            ],
            "messages": [],
        },
        "summary_text": "Tenant in 12C reported a dishwasher that won't drain. Ticket logged; entry permission granted.",
    },
    "message": {
        "outcome": "message_taken",
        "outcomes": {
            "bookings": [],
            "emergencies": [],
            "tickets": [],
            "messages": [
                {
                    "caller_name": "Marcus Webb",
                    "callback_number": "+18135550122",
                    "reason": "Lease renewal",
                    "body": "Wants to know renewal terms for 8D before his lease ends next month.",
                }
            ],
        },
        "summary_text": "Marcus Webb asked about renewal terms for 8D. Maya took a message for the office.",
    },
    "info_only": {
        "outcome": "info_only",
        "outcomes": {"bookings": [], "emergencies": [], "tickets": [], "messages": []},
        "summary_text": "Caller asked whether parking was included and whether the office is open Saturdays. Both answered; no follow-up needed.",
        "call": _call(duration_sec=48, transcript=None, recording_url=None),
    },
}


def _say(line: str) -> None:
    """Subjects carry em-dashes and emoji; the Windows console is cp1252. Don't let a
    console codec turn a successful render into a traceback."""
    enc = sys.stdout.encoding or "utf-8"
    print(line.encode(enc, errors="replace").decode(enc, errors="replace"))


def main() -> None:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests" / "email_preview"
    outdir.mkdir(parents=True, exist_ok=True)

    index = ["<h1 style='font-family:sans-serif'>PropTalk summary email — previews</h1><ul>"]
    for name, case in CASES.items():
        subject, html, text = render_summary_email(
            client=CLIENT,
            call=case.get("call") or _call(),
            outcomes=case["outcomes"],
            outcome=case["outcome"],
            summary_text=case["summary_text"],
        )
        page = (
            "<!doctype html><meta charset='utf-8'>"
            f"<title>{subject}</title>"
            "<body style='margin:0;background:#eef2f6'>"
            f"<div style='font-family:sans-serif;font-size:12px;color:#64748b;padding:10px 14px'>"
            f"<b>Subject:</b> {subject}</div>{html}</body>"
        )
        (outdir / f"{name}.html").write_text(page, encoding="utf-8")
        (outdir / f"{name}.txt").write_text(f"Subject: {subject}\n\n{text}", encoding="utf-8")
        index.append(f"<li><a href='{name}.html'>{name}</a> — {subject}</li>")
        _say(f"{name:26} {subject}")

    index.append("</ul>")
    (outdir / "index.html").write_text("".join(index), encoding="utf-8")
    _say(f"\nWrote previews to {outdir}")


if __name__ == "__main__":
    main()
