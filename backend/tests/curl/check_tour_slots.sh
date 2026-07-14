#!/usr/bin/env bash
# Verifies /tools/check_tour_slots for Unit 2A (available), preferring a weekday morning.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

PROPERTY_ID="2A"   # short code the agent gets from get_available_listings

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/check_tour_slots?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{
        \"name\": \"check_tour_slots\",
        \"call\": {\"call_id\": \"curl-test-slots-1\"},
        \"args\": {\"property_id\": \"${PROPERTY_ID}\", \"date_preference\": \"weekday morning\"}
      }"

echo; echo "--- regression: a mangled property_id ('2') must return not_found, NOT a 500 ---"
curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/check_tour_slots?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d '{"call": {"call_id": "curl-test-slots-bad"}, "args": {"property_id": "2"}}'
