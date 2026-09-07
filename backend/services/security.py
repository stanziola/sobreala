"""Passwords, CSRF tokens and rate limiting."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import session
from pymongo import ReturnDocument

# bcrypt only looks at the first 72 bytes and silently ignores the rest, so two
# different long passwords could open the same account. Longer input is refused
# rather than truncated.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 10

CSRF_SESSION_KEY = "_csrf"


def now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------- passwords

def password_problem(password: str) -> str | None:
    """Return the reason a password is unacceptable, or None if it is fine."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return "too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "too_long"
    return None


def hash_password(password: str) -> str:
    if password_problem(password):
        raise ValueError("password rejected by password_problem()")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time check that also tolerates a missing hash.

    When the account does not exist the caller still calls this with None, so
    that a wrong address and a wrong password take a similar amount of time and
    cannot be told apart.
    """
    encoded = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    if not password_hash:
        # Spend roughly the same effort as a real check.
        bcrypt.hashpw(encoded, bcrypt.gensalt())
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
    except ValueError:
        return False


# ------------------------------------------------------------------------ tokens

def new_token() -> tuple[str, str]:
    """Return (token for the link, hash to store). The raw token is never saved."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# -------------------------------------------------------------------------- CSRF

def csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_ok(submitted: str | None) -> bool:
    expected = session.get(CSRF_SESSION_KEY)
    if not expected or not submitted:
        return False
    return secrets.compare_digest(expected, submitted)


# ------------------------------------------------------------------ rate limiting

def rate_limit(db, key: str, limit: int, per_seconds: int) -> bool:
    """Count one attempt for `key`. False once the window is over budget.

    Backed by Mongo with a TTL index so the counters clean themselves up. This
    is the second layer; Cloudflare filters in front of the application.
    """
    moment = now()
    doc = db.rate_limits.find_one_and_update(
        {"key": key, "expires_at": {"$gt": moment}},
        {"$inc": {"count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        db.rate_limits.insert_one({
            "key": key,
            "count": 1,
            "expires_at": moment + timedelta(seconds=per_seconds),
        })
        return True
    return doc["count"] <= limit
