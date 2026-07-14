#!/usr/bin/env bash
# Verifies POST /webhooks/retell end to end, INCLUDING signature verification.
# Builds the exact body Retell sends, signs it with RETELL_API_KEY the way Retell does
# (v={ts_ms},d=HMAC-SHA256(body + ts_ms, api_key)), and posts it. Run twice - the second
# run must not double-count minutes_used (idempotent upsert on retell_call_id).
#
# If RETELL_API_KEY isn't set in the repo-root .env, the server skips verification and
# this still works (it just sends no signature header).
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

ENV_FILE="../../../.env"
NOW_MS=$(($(date +%s) * 1000))
START_MS=$((NOW_MS - 240000))
CALL_ID="curl-test-webhook-1"

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat > "$BODY_FILE" <<EOF
{"event":"call_analyzed","call":{"call_id":"${CALL_ID}","from_number":"+18135551234","start_timestamp":${START_MS},"end_timestamp":${NOW_MS},"duration_ms":240000,"transcript":"Caller asked about 2-bedroom units under \$2000 and booked a tour.","recording_url":"https://example.com/recording.mp3","call_analysis":{"call_summary":"Caller booked a tour of Unit 2A for Saturday."}}}
EOF

# Sign the exact bytes we will send. Reads RETELL_API_KEY straight from .env (this runs
# under system python3, so no venv/dotenv dependency - just grep the line).
SIG="$(ENV_FILE="$ENV_FILE" BODY_FILE="$BODY_FILE" TS="$NOW_MS" python3 - <<'PY'
import hashlib, hmac, os, pathlib, re
key = ""
for line in pathlib.Path(os.environ["ENV_FILE"]).read_text(encoding="utf-8").splitlines():
    m = re.match(r'\s*RETELL_API_KEY\s*=\s*"?([^"#\s]+)', line)
    if m:
        key = m.group(1)
        break
if not key:
    print("")  # no key -> caller sends no signature header
else:
    body = pathlib.Path(os.environ["BODY_FILE"]).read_bytes()
    ts = os.environ["TS"]
    digest = hmac.new(key.encode(), body + ts.encode(), hashlib.sha256).hexdigest()
    print(f"v={ts},d={digest}")
PY
)"

HDR=(-H 'Content-Type: application/json')
if [ -n "$SIG" ]; then HDR+=(-H "X-Retell-Signature: ${SIG}"); fi

curl -sS -w '\n%{http_code}\n' -X POST \
  "${BASE_URL}/webhooks/retell?client_id=${CLIENT_ID}" \
  "${HDR[@]}" --data-binary "@${BODY_FILE}"
