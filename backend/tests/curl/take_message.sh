#!/usr/bin/env bash
# Verifies /tools/take_message for a catch-all inquiry (rent question).
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/take_message?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "take_message",
        "call": {"call_id": "curl-test-message-1"},
        "args": {
          "caller_name": "Pat Renter",
          "callback_number": "+18135550166",
          "reason": "rent question",
          "message": "Wants to know if rent can be paid in two installments this month"
        }
      }'
