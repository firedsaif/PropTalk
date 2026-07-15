#!/usr/bin/env bash
# Run every tool + webhook curl check and summarize pass/fail.
# Local:          bash run_all.sh
# Through tunnel:  BASE_URL=https://xxx.trycloudflare.com bash run_all.sh
#
# Proves Retell's mid-call requests will succeed against this exact base URL -
# BEFORE spending a voice minute. Every check must print 200.
set -uo pipefail
cd "$(dirname "$0")"
export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
echo "Base URL: $BASE_URL"
echo

fail=0
for script in get_available_listings check_tour_slots book_tour reschedule_tour \
              create_maintenance_ticket escalate_emergency take_message \
              webhooks_retell summary_email; do
    echo "=== ${script} ==="
    out="$(bash "${script}.sh" 2>&1)"
    echo "$out"
    # Every check ends each request with its HTTP code on its own line; flag any non-2xx.
    if echo "$out" | grep -qE '^(4|5)[0-9]{2}$'; then
        echo "  ^^ FAIL (non-2xx above)"
        fail=1
    fi
    echo
done

if [ "$fail" -eq 0 ]; then
    echo "ALL CHECKS PASSED — safe to make a web test call."
else
    echo "SOME CHECKS FAILED — fix before calling (a failed call wastes a credit)."
    exit 1
fi
