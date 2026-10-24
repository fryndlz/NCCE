"""Shared-passphrase access for one private NCCE instance."""
from __future__ import annotations

import hashlib
import hmac
import time

SESSION_MAX_AGE = 60 * 60 * 24 * 7


def configured_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def effective_session_key(access_password: str, session_secret: str) -> bytes:
    """Derive a signing key so rotating either secret revokes existing sessions."""
    return hmac.new(session_secret.encode("utf-8"), access_password.encode("utf-8"), hashlib.sha256).digest()


def make_session_token(key: bytes, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else int(now)
    expires = issued + SESSION_MAX_AGE
    payload = f"{issued}.{expires}"
    signature = hmac.new(key, payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def valid_session_token(token: str, key: bytes, now: int | None = None) -> bool:
    try:
        issued_text, expires_text, supplied_signature = token.split(".", 2)
        issued, expires = int(issued_text), int(expires_text)
    except (AttributeError, TypeError, ValueError):
        return False
    current = int(time.time()) if now is None else int(now)
    if issued > current + 60 or expires <= current or expires - issued != SESSION_MAX_AGE:
        return False
    expected = hmac.new(key, f"{issued}.{expires}".encode("ascii"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied_signature, expected)
