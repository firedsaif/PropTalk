"""All tunables that aren't secrets. Never hardcode these in handlers.

Per-client differences (company name, agent name, office hours, timezone,
escalation phone, minutes cap) live on the `clients` row, not here — this
file is for cross-client defaults and knobs.
"""

# --- check_tour_slots (Phase 2 stub; replaced by real Cal.com availability in Phase 4) ---
TOUR_SLOT_DURATION_MIN = 30
TOUR_SLOTS_LOOKAHEAD_DAYS = 7
TOUR_SLOTS_RETURNED = 3
TOUR_BUSINESS_HOURS = {
    # weekday() -> (start_hour, end_hour) in the client's local timezone, 24h. Sunday closed.
    0: (10, 17),  # Mon
    1: (10, 17),  # Tue
    2: (10, 17),  # Wed
    3: (10, 17),  # Thu
    4: (10, 17),  # Fri
    5: (10, 14),  # Sat
}

# --- maintenance / escalation ---
MAINTENANCE_SEVERITY_ROUTINE = "routine"
MAINTENANCE_SEVERITY_EMERGENCY = "emergency"

# --- tool response shape ---
TOOL_RESPONSE_MAX_BYTES = 1024
