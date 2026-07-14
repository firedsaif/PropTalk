"""Retell webhook signature verification.

docs.retellai.com/features/secure-webhook:
    header "X-Retell-Signature: v={timestamp_ms},d={hex_digest}"
    digest = HMAC-SHA256(raw_body + timestamp_ms, key=api_key).hexdigest()
    timestamp must be within 5 minutes of now.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import time

from app.settings import settings

SIGNATURE_RE = re.compile(r"v=(\d+),d=(.+)")
SIGNATURE_MAX_AGE_MS = 5 * 60 * 1000


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """True if the X-Retell-Signature header is a valid, fresh signature over raw_body."""
    key = settings.retell_api_key or settings.retell_webhook_secret
    if not key or not signature_header:
        return False
    match = SIGNATURE_RE.match(signature_header)
    if not match:
        return False
    timestamp_str, digest = match.group(1), match.group(2)
    if abs(time.time() * 1000 - int(timestamp_str)) > SIGNATURE_MAX_AGE_MS:
        return False
    expected = hmac.new(
        key.encode("utf-8"),
        raw_body + timestamp_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, digest)
