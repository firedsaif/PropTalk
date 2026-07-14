#!/usr/bin/env bash
# Verifies /tools/escalate_emergency: must be fast (fire-and-return) and never block on notify.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/escalate_emergency?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "escalate_emergency",
        "call": {"call_id": "curl-test-emergency-1"},
        "args": {
          "unit": "Unit 5C",
          "issue": "Tenant reports no heat, freezing temperatures overnight",
          "callback_number": "+18135550177",
          "caller_safe": true
        }
      }'
