"""Phase 4 preflight: prove the Cal.com + Resend keys work, before any voice minute.

Both vendors are free-tier here, and neither call below costs anything: Cal.com is a
read (`/me`) plus an availability lookup, Resend is one real email to your own address.

    python scripts\\test_integrations.py            # check config + Cal.com (no email sent)
    python scripts\\test_integrations.py --send     # also send one real summary email

Run this after pasting keys into the repo-root .env. If it's green, the only thing left
that can fail on a real call is the agent itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402
from app.deps import resolve_client  # noqa: E402
from app.services import calcom  # noqa: E402
from app.services.email_template import render_summary_email  # noqa: E402
from app.services.notify import send_summary_email  # noqa: E402
from app.settings import settings  # noqa: E402
from scripts.preview_summary_email import BOOKING, CASES, _call  # noqa: E402

WILLOWBROOK = "11111111-1111-1111-1111-111111111111"
OK, NO = "[ok]", "[--]"


def _line(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {OK if ok else NO} {label:28} {detail}")


def main() -> None:
    send = "--send" in sys.argv
    print("PropTalk Phase 4 preflight\n")

    print("Config (repo-root .env):")
    _line("CALCOM_API_KEY", bool(settings.calcom_api_key))
    _line("CALCOM_EVENT_TYPE_ID", bool(settings.calcom_event_type_id), settings.calcom_event_type_id or "")
    _line("RESEND_API_KEY", bool(settings.resend_api_key))
    _line("FROM_EMAIL", bool(settings.from_email), settings.from_email or "")
    _line("FEATURE_SMS_ENABLED", not settings.feature_sms_enabled, "off (correct until Phase 7)")

    with get_connection() as conn:
        client = resolve_client(conn, WILLOWBROOK)
    print(f"\nClient: {client['company_name']}  tz={client['timezone']}  notify={client['notify_email']}")

    print("\nCal.com:")
    event_type_id = calcom.event_type_id_for(client)
    if not calcom.is_configured(event_type_id):
        _line("configured", False, "no key/event type - tours fall back to mock business hours")
    else:
        probe = calcom.probe()
        _line("api key", probe["ok"], probe.get("username") or probe.get("reason", ""))
        if probe["ok"]:
            start, end = calcom.default_window(7)
            slots = calcom.get_slots(
                event_type_id=event_type_id, start=start, end=end, tz_name=client["timezone"]
            )
            if slots is None:
                _line("availability", False, f"event type {event_type_id} did not return slots")
            else:
                preview = ", ".join(s.astimezone().strftime("%a %H:%M") for s in slots[:3])
                _line("availability", bool(slots), f"{len(slots)} slots in 7 days  [{preview}]")
                if not slots:
                    print("       (no slots: check the event type's schedule/availability in Cal.com)")

    print("\nResend:")
    if not settings.resend_api_key or not settings.from_email:
        _line("configured", False, "no key/from address - summary emails will log as stubs")
    elif not client["notify_email"]:
        _line("recipient", False, "clients.notify_email is empty for Willowbrook")
    elif not send:
        _line("ready", True, "pass --send to send one real test email")
    else:
        case = CASES["tour_booked"]
        subject, html, text = render_summary_email(
            client=client,
            call=_call(),
            outcomes={"bookings": [BOOKING], "emergencies": [], "tickets": [], "messages": []},
            outcome="tour_booked",
            summary_text=case["summary_text"],
        )
        sent = send_summary_email(
            client_id=client["id"],
            notify_email=client["notify_email"],
            subject=f"[TEST] {subject}",
            html=html,
            text=text,
        )
        _line("test send", sent, f"-> {client['notify_email']}" if sent else "see email_send_failed log above")
        if not sent:
            print(
                "       On Resend's free tier without a verified domain you can only send\n"
                "       FROM onboarding@resend.dev TO the address you signed up with."
            )


if __name__ == "__main__":
    main()
