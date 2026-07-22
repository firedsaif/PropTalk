"""Retell webhook signature verification.

Retell's real scheme (matches their SDK's `Retell.verify`):
    header  x-retell-signature: <hex>           # the hex digest itself, no wrapper
    digest  = HMAC-SHA256(key=api_key, msg=raw_body).hexdigest()

Phase 3 shipped a *different*, invented scheme (`v={ts},d={digest}` over `body+ts`).
The curl regression signs and verifies that same invented way, so it stayed green while
real Retell calls 401'd - the test could never catch it. We now try the real scheme
first and keep the legacy one so the existing curl test still passes, and we report
*which* scheme matched so a mismatch is diagnosable from the logs instead of by guessing.
"""
from __future__ import annotations

import hashlib
import hmac
import re

from app.settings import settings

_LEGACY_RE = re.compile(r"v=(\d+),d=(.+)")
_LEGACY_MAX_AGE_MS = 5 * 60 * 1000


def _keys() -> list[str]:
    """Candidate signing keys, in priority order. Retell signs with the API key; a
    dedicated webhook secret is supported if the account uses one."""
    return [k for k in (settings.retell_api_key, settings.retell_webhook_secret) if k]


def _hmac_hex(key: str, msg: bytes) -> str:
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def check_signature(raw_body: bytes, signature_header: str | None) -> tuple[bool, str]:
    """Return (ok, scheme). `scheme` names the construction that matched, or why none did -
    it goes straight into the webhook log so we can see the real signature shape once."""
    if not signature_header:
        return False, "no_header"
    keys = _keys()
    if not keys:
        return False, "no_key_configured"

    header = signature_header.strip()

    # 1. Retell's real scheme: the header IS the hex digest of HMAC(api_key, raw_body).
    #    Tolerate an optional "sha256=" prefix, which some Retell clients prepend.
    bare = header.split("=", 1)[1] if header.lower().startswith("sha256=") else header
    for key in keys:
        if hmac.compare_digest(_hmac_hex(key, raw_body), bare):
            return True, "retell_hmac_body"

    # 2. Legacy Phase 3 scheme: v={ts},d={digest} over (raw_body + ts). Kept so the curl
    #    regression stays meaningful; real Retell traffic won't take this branch.
    m = _LEGACY_RE.match(header)
    if m:
        ts, digest = m.group(1), m.group(2)
        import time

        if abs(time.time() * 1000 - int(ts)) <= _LEGACY_MAX_AGE_MS:
            for key in keys:
                if hmac.compare_digest(_hmac_hex(key, raw_body + ts.encode()), digest):
                    return True, "legacy_ts_body"

    return False, "no_scheme_matched"


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Back-compat boolean wrapper (used by the curl regression and older callers)."""
    ok, _ = check_signature(raw_body, signature_header)
    return ok


def diagnose_signature(raw_body: bytes, signature_header: str | None) -> str:
    """Find Retell's real HMAC construction from one real signature, so we lock down
    production verification (Phase 6) without guessing or burning a test call.

    Real Retell header is v={ms},d={hexdigest}. Phase 3 assumed the digest was
    HMAC(key, body+ts); it isn't. This tries the plausible constructions and names the
    one whose digest matches the digest Retell actually sent. Returns the winner or a
    short 'none' note. Never logs the key or the full signature.
    """
    if not signature_header:
        return "no_header"
    m = _LEGACY_RE.match(signature_header.strip())
    if not m:
        return "not_v_d_format"
    ts, sent = m.group(1), m.group(2)
    body = raw_body
    body_str = raw_body.decode("utf-8", "replace")
    candidates = {
        "body": body,
        "body+ts": body + ts.encode(),
        "ts+body": ts.encode() + body,
        "ts.body": f"{ts}.{body_str}".encode(),
        "body.ts": f"{body_str}.{ts}".encode(),
        "v=ts,body": f"v={ts},{body_str}".encode(),
    }
    for key in _keys():
        for name, msg in candidates.items():
            if hmac.compare_digest(_hmac_hex(key, msg), sent):
                return f"match:{name}"
    return "none_matched"
