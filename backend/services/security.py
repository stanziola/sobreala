"""Passwords, CSRF tokens and rate limiting."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import session
from pymongo import ReturnDocument

from config import Config

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
    """Return the reason a password is unacceptable, or None if it is fine.

    Length first, because it is the one that matters most and the one the person
    can fix without reading the rest. Only the first problem is returned; the
    form lists every rule underneath the field, so nobody has to discover them
    one refusal at a time.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return "too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "too_long"
    if not any(ch.isupper() for ch in password):
        return "no_upper"
    if not any(ch.isdigit() for ch in password):
        return "no_digit"
    if not any(is_symbol(ch) for ch in password):
        return "no_symbol"
    return None


def is_symbol(ch: str) -> bool:
    """Anything that is not a letter, a digit or a space.

    Written as "not the others" rather than as a list of allowed characters, so
    a keyboard from another language is not punished for its punctuation.
    """
    return not ch.isalnum() and not ch.isspace()


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


# --------------------------------------------------------------------- codes

CODE_DIGITS = 6


def new_code() -> str:
    """A confirmation code, leading zeros included."""
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def clean_code(typed: str | None) -> str:
    """Digits only. People paste "48 12 09" and type dashes between them."""
    return "".join(ch for ch in (typed or "") if ch.isdigit())


def hash_keyed(value: str) -> str:
    """Keyed hash of a short secret, not a bare digest.

    A plain SHA-256 of six digits protects nothing: a million guesses is a
    fraction of a second on any laptop. Under HMAC with SECRET_KEY a copy of the
    database is not enough to turn the stored value back into what was typed;
    the server's key is needed too.
    """
    return hmac.new(Config.SECRET_KEY.encode("utf-8"),
                    value.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def hash_code(code: str) -> str:
    """The keyed hash of a confirmation code. Rule 6: the code is never stored."""
    return hash_keyed(clean_code(code))


def codes_match(stored: str | None, submitted: str) -> bool:
    if not stored:
        return False
    return secrets.compare_digest(stored, submitted)


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


def rate_state(db, key: str, limit: int, per_seconds: int,
               amount: int = 1) -> tuple[bool, int, int]:
    """Lo mismo que `rate_limit()`, diciendo además cuántos quedan y en cuántos
    segundos vuelve a empezar. Es lo que la API pone en `Retry-After`. `amount`
    cuenta varios de una vez (las filas de una carga de contactos)."""
    moment = now()
    doc = db.rate_limits.find_one_and_update(
        {"key": key, "expires_at": {"$gt": moment}},
        {"$inc": {"count": amount}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        db.rate_limits.insert_one({
            "key": key,
            "count": amount,
            "expires_at": moment + timedelta(seconds=per_seconds),
        })
        return amount <= limit, max(0, limit - amount), per_seconds
    expires = doc["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    reset = max(1, int((expires - moment).total_seconds()) + 1)
    return doc["count"] <= limit, max(0, limit - doc["count"]), reset
