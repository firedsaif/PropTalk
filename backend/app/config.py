"""All tunables that aren't secrets. Never hardcode these in handlers.

Per-client differences (company name, agent name, office hours, timezone,
escalation phone, minutes cap) live on the `clients` row, not here — this
file is for cross-client defaults and knobs.
"""

# --- check_tour_slots ---
# Phase 4: real Cal.com availability when a key + event type are configured; these
# business hours remain the fallback so the product still demos with no Cal.com account.
TOUR_SLOT_DURATION_MIN = 30
TOUR_SLOTS_LOOKAHEAD_DAYS = 7
TOUR_SLOTS_RETURNED = 3
# Don't offer a tour the PM can't physically get to. Applied to real Cal.com slots too,
# on top of whatever minimum notice the event type itself enforces.
TOUR_MIN_LEAD_HOURS = 2
TOUR_BUSINESS_HOURS = {
    # weekday() -> (start_hour, end_hour) in the client's local timezone, 24h. Sunday closed.
    0: (10, 17),  # Mon
    1: (10, 17),  # Tue
    2: (10, 17),  # Wed
    3: (10, 17),  # Thu
    4: (10, 17),  # Fri
    5: (10, 14),  # Sat
}

# --- Cal.com (Phase 4) ---
CALCOM_API_BASE = "https://api.cal.com/v2"
# Cal.com pins breaking changes to this header, not the URL. Bump deliberately, and
# re-check the parsers in services/calcom.py when you do.
CALCOM_SLOTS_API_VERSION = "2024-09-04"
CALCOM_BOOKINGS_API_VERSION = "2024-08-13"
# Hard ceiling well under the 800ms product budget's patience: a slow calendar must
# fail fast into the mock/degraded path rather than hang a caller mid-sentence.
CALCOM_TIMEOUT_SEC = 4.0
# Cal.com requires an attendee email, but nobody spells one out over the phone. We mint a
# per-booking address instead: it keeps the event on the PM's calendar (which is the point),
# and it is deliberately undeliverable so we never imply we emailed the prospect.
CALCOM_ATTENDEE_EMAIL_DOMAIN = "tours.proptalk.invalid"

# --- Post-call summary email (Phase 4) ---
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SEC = 6.0  # post-call, off the voice path - can afford more than a tool
# Transcript is the proof, but a 40-minute call would make an unreadable email.
SUMMARY_TRANSCRIPT_MAX_TURNS = 40

# --- maintenance / escalation ---
MAINTENANCE_SEVERITY_ROUTINE = "routine"
MAINTENANCE_SEVERITY_EMERGENCY = "emergency"

# --- tool response shape ---
TOOL_RESPONSE_MAX_BYTES = 1024
