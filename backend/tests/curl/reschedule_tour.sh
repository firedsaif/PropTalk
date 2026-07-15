#!/usr/bin/env bash
# Phase 4: the reschedule path (docs/phases.md "Test: book, reschedule, double-book attempt").
#
# There is no reschedule *tool* - the agent just calls book_tour again with a new time when
# the caller changes their mind. The backend recognises the same prospect (matched on phone,
# same unit) and moves the tour instead of leaving them holding two.
#
#   1) book slot A
#   2) same prospect books slot B  -> new booking, slot A released ('rescheduled'), one tour live
#   3) slot A is now free again    -> a different caller can take it
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

PROPERTY_ID="2A"
PHONE="+18135550111"

# `tr -d '\r'` is load-bearing on Windows: python here prints CRLF, and unlike command
# substitution, `read` keeps the trailing CR - which then lands inside the JSON body below
# as a control character and gets rejected long before it reaches any interesting logic.
SLOTS=$(curl -sS -X POST "${BASE_URL}/tools/check_tour_slots?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{\"args\": {\"property_id\": \"${PROPERTY_ID}\"}}" \
  | python3 -c "import sys,json; s=json.load(sys.stdin)['slots']; print(s[0], s[1])" | tr -d '\r')
read -r SLOT_A SLOT_B <<< "${SLOTS}"
echo "Slot A: ${SLOT_A}"
echo "Slot B: ${SLOT_B}"

book() {  # book <call_id> <slot> <name> <phone>
  # -w prints the HTTP code on its own line: that's what run_all.sh greps for to decide
  # pass/fail, so without it a 500 here would scroll past unnoticed.
  curl -sS -w '\n%{http_code}\n' -X POST "${BASE_URL}/tools/book_tour?client_id=${CLIENT_ID}" \
    -H 'Content-Type: application/json' \
    -d "{\"call\": {\"call_id\": \"$1\"}, \"args\": {
          \"property_id\": \"${PROPERTY_ID}\",
          \"slot_start_iso\": \"$2\",
          \"prospect_name\": \"$3\",
          \"prospect_phone\": \"$4\",
          \"sms_consent\": true
        }}"
}

echo; echo "--- 1) Jane books slot A ---"
book "curl-resched-1" "${SLOT_A}" "Jane Reschedule" "${PHONE}"

echo; echo; echo "--- 2) Jane calls back and moves to slot B (must succeed with a NEW booking_id) ---"
book "curl-resched-2" "${SLOT_B}" "Jane Reschedule" "${PHONE}"

echo; echo; echo "--- 3) someone else takes the freed slot A (must succeed - the reschedule released it) ---"
book "curl-resched-3" "${SLOT_A}" "Opportunist Pete" "+18135550222"

echo; echo; echo "--- 4) slot B is Jane's; a stranger must be refused and offered other times ---"
book "curl-resched-4" "${SLOT_B}" "Stranger Sam" "+18135550333"
echo
