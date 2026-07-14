#!/usr/bin/env bash
# Verifies /tools/create_maintenance_ticket for a routine (non-emergency) issue.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/tools/create_maintenance_ticket?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "create_maintenance_ticket",
        "call": {"call_id": "curl-test-maint-1"},
        "args": {
          "unit": "Unit 2A",
          "issue_type": "plumbing",
          "description": "Kitchen faucet has been dripping for about a week",
          "callback_number": "+18135550199",
          "permission_to_enter": true
        }
      }'
