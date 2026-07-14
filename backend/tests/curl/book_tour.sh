#!/usr/bin/env bash
# Verifies /tools/book_tour's three danger paths (docs/rules.md SS7):
#   1) a normal booking succeeds
#   2) a retry with the same call_id + slot is idempotent (no duplicate row)
#   3) a different call trying to grab the now-taken slot gets next_available_slots,
#      never overwriting the existing booking.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

PROPERTY_ID="22222222-0000-0000-0000-000000000001"   # Unit 2A - Willowbrook Apartments

SLOT=$(curl -sS -X POST "${BASE_URL}/tools/check_tour_slots?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{\"args\": {\"property_id\": \"${PROPERTY_ID}\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['slots'][0])")
echo "Booking slot: ${SLOT}"

BODY="{\"call\": {\"call_id\": \"curl-test-book-1\"}, \"args\": {
        \"property_id\": \"${PROPERTY_ID}\",
        \"slot_start_iso\": \"${SLOT}\",
        \"prospect_name\": \"Jane Curl\",
        \"prospect_phone\": \"+18135550199\",
        \"sms_consent\": false
      }}"

echo; echo "--- 1) first booking ---"
curl -sS -w '\n%{http_code}\n' -X POST "${BASE_URL}/tools/book_tour?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' -d "${BODY}"

echo; echo "--- 2) retry with same call_id (must return the SAME booking_id, not a duplicate) ---"
curl -sS -w '\n%{http_code}\n' -X POST "${BASE_URL}/tools/book_tour?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' -d "${BODY}"

echo; echo "--- 3) a different caller tries the same slot (must be rejected, offered next slots) ---"
BODY2="{\"call\": {\"call_id\": \"curl-test-book-2\"}, \"args\": {
        \"property_id\": \"${PROPERTY_ID}\",
        \"slot_start_iso\": \"${SLOT}\",
        \"prospect_name\": \"Someone Else\",
        \"prospect_phone\": \"+18135550188\",
        \"sms_consent\": false
      }}"
curl -sS -w '\n%{http_code}\n' -X POST "${BASE_URL}/tools/book_tour?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' -d "${BODY2}"
