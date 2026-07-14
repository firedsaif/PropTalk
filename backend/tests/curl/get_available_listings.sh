#!/usr/bin/env bash
# Verifies /tools/get_available_listings: pet-friendly, 2+ beds, budget $2000.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/get_available_listings?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "get_available_listings",
        "call": {"call_id": "curl-test-listings-1"},
        "args": {"beds": 2, "max_rent": 2000, "pets": true}
      }'
