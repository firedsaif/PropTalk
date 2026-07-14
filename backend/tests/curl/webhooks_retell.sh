#!/usr/bin/env bash
# Verifies POST /webhooks/retell: upserts the call row and is safe to replay
# (run this script twice - the second run must not double-count minutes_used).
# No X-Retell-Signature header is sent: RETELL_API_KEY isn't set until Phase 3,
# so the handler logs "webhook_signature_skipped" and proceeds (see app/retell.py).
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

NOW_MS=$(($(date +%s) * 1000))
START_MS=$((NOW_MS - 240000))
CALL_ID="curl-test-webhook-1"

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/webhooks/retell?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{
        \"event\": \"call_analyzed\",
        \"call\": {
          \"call_id\": \"${CALL_ID}\",
          \"from_number\": \"+18135551234\",
          \"start_timestamp\": ${START_MS},
          \"end_timestamp\": ${NOW_MS},
          \"duration_ms\": 240000,
          \"transcript\": \"Caller asked about 2-bedroom units under \$2000 and booked a tour.\",
          \"recording_url\": \"https://example.com/recording.mp3\",
          \"call_analysis\": {\"call_summary\": \"Caller booked a tour of Unit 2A for Saturday.\"}
        }
      }"
