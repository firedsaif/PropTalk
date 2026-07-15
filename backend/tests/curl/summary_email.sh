#!/usr/bin/env bash
# Phase 4 exit proof, minus the voice minute: a tour booked *during* a call must show up
# in *that call's* summary email.
#
# This is the join the money loop depends on - book_tour writes a row tagged with the
# retell_call_id, and the call_analyzed webhook has to find it again. It's easy to get
# wrong and invisible until a client emails asking why their summary said "nothing to
# follow up" about the tour they just got booked.
#
#   1) book a tour, tagged with a known call_id
#   2) fire call_analyzed for that same call_id
#   3) the webhook must answer outcome=tour_booked and a subject naming the unit
#
# `emailed` is false until RESEND_API_KEY + FROM_EMAIL are set - that's expected, and the
# rest of the assertion still holds.
set -euo pipefail
cd "$(dirname "$0")" && source _env.sh

PROPERTY_ID="2A"
CALL_ID="curl-test-summary-1"

SLOT=$(curl -sS -X POST "${BASE_URL}/tools/check_tour_slots?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{\"args\": {\"property_id\": \"${PROPERTY_ID}\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['slots'][0])" | tr -d '\r')

echo "--- 1) book a tour on call ${CALL_ID} (slot ${SLOT}) ---"
curl -sS -w '\n%{http_code}\n' -X POST "${BASE_URL}/tools/book_tour?client_id=${CLIENT_ID}" \
  -H 'Content-Type: application/json' \
  -d "{\"call\": {\"call_id\": \"${CALL_ID}\"}, \"args\": {
        \"property_id\": \"${PROPERTY_ID}\",
        \"slot_start_iso\": \"${SLOT}\",
        \"prospect_name\": \"Summary Sam\",
        \"prospect_phone\": \"+18135550164\",
        \"sms_consent\": true
      }}"

NOW_MS=$(($(date +%s) * 1000))
START_MS=$((NOW_MS - 190000))
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat > "$BODY_FILE" <<EOF
{"event":"call_analyzed","call":{"call_id":"${CALL_ID}","from_number":"+18135550164","start_timestamp":${START_MS},"end_timestamp":${NOW_MS},"duration_ms":190000,"transcript":"Agent: Thanks for calling Willowbrook, this is Maya.\nUser: Do you have any two bedrooms?\nAgent: We do - Unit 2A at \$1795. Would you like to see it?\nUser: Yes please.","recording_url":"https://example.com/recording.mp3","call_analysis":{"call_summary":"Summary Sam asked about two-bedroom availability and booked a tour of Unit 2A."}}}
EOF

SIG="$(ENV_FILE="../../../.env" BODY_FILE="$BODY_FILE" TS="$NOW_MS" python3 - <<'PY'
import hashlib, hmac, os, pathlib, re
key = ""
for line in pathlib.Path(os.environ["ENV_FILE"]).read_text(encoding="utf-8").splitlines():
    m = re.match(r'\s*RETELL_API_KEY\s*=\s*"?([^"#\s]+)', line)
    if m:
        key = m.group(1)
        break
if not key:
    print("")
else:
    body = pathlib.Path(os.environ["BODY_FILE"]).read_bytes()
    ts = os.environ["TS"]
    print(f"v={ts},d={hmac.new(key.encode(), body + ts.encode(), hashlib.sha256).hexdigest()}")
PY
)"
HDR=(-H 'Content-Type: application/json')
if [ -n "$SIG" ]; then HDR+=(-H "X-Retell-Signature: ${SIG}"); fi

echo; echo "--- 2) call_analyzed for the same call (expect outcome=tour_booked, subject naming Unit 2A) ---"
RESP="$(curl -sS -X POST "${BASE_URL}/webhooks/retell?client_id=${CLIENT_ID}" \
  "${HDR[@]}" --data-binary "@${BODY_FILE}")"
echo "$RESP"

echo
if echo "$RESP" | grep -q '"outcome":"tour_booked"' && echo "$RESP" | grep -q 'Unit 2A'; then
  echo "PASS — the booking reached the summary."
  echo "200"
else
  echo "FAIL — the call's booking did not reach the summary."
  echo "500"
fi
