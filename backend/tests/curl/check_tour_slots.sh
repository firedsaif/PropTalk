#!/usr/bin/env bash
# Verifies /tools/check_tour_slots for Unit 2A (available), preferring a weekday morning.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

PROPERTY_ID="22222222-0000-0000-0000-000000000001"   # Unit 2A - Willowbrook Apartments

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/check_tour_slots?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{
        \"name\": \"check_tour_slots\",
        \"call\": {\"call_id\": \"curl-test-slots-1\"},
        \"args\": {\"property_id\": \"${PROPERTY_ID}\", \"date_preference\": \"weekday morning\"}
      }"
