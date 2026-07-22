"""One-command health check for the whole path, no bash needed.

    python scripts/smoke_test.py [base_url]

Defaults to the tunnel URL saved in scripts/retell_state.json (falls back to localhost).
Hits the real get_available_listings endpoint and checks Unit 2A comes back - proving
backend + DB + (if a tunnel URL) the tunnel are all working end to end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

CID = "11111111-1111-1111-1111-111111111111"
STATE = Path(__file__).resolve().parent / "retell_state.json"


def _base_url() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].rstrip("/")
    if STATE.exists():
        url = json.loads(STATE.read_text(encoding="utf-8")).get("base_url")
        if url:
            return url.rstrip("/")
    return "http://127.0.0.1:8000"


def main() -> None:
    base = _base_url()
    print(f"Smoke test against {base}")
    try:
        r = httpx.post(
            f"{base}/tools/get_available_listings?client_id={CID}",
            json={"args": {"beds": 2, "max_rent": 1800, "pets": True}},
            timeout=20,
        )
        d = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL - could not reach backend: {type(exc).__name__}: {exc}")
        sys.exit(1)

    ok = r.status_code == 200 and d.get("ok") and any(
        l.get("property_id") == "2A" for l in d.get("listings", [])
    )
    print(f"{'PASS' if ok else 'FAIL'} - HTTP {r.status_code}, {d.get('count')} listing(s) returned")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
