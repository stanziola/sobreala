"""The auth_events collection: one row per attempt to register, sign in, or ask
for another confirmation link.

This is an audit trail, not a screen. It records what actually happened,
`already_registered` included, which the interface must never reveal. Rule 7 in
CLAUDE.md governs what the visitor is told; it does not require the platform to
be ignorant of its own traffic.

The password is never written here, in any form: not in the clear, not
truncated, not hashed. Nothing on this document can be replayed as a credential.

No TTL index. The history is kept until someone decides otherwise, which is a
deliberate choice: these rows are how an abuse complaint or a "I can't get in"
report gets investigated weeks later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from models.account import normalize_email

# What was attempted.
REGISTER = "register"
LOGIN = "login"
RESEND = "resend"
CONFIRM = "confirm"
LOGOUT = "logout"

# How it went. Which ones are possible depends on the kind.
CREATED = "created"                    # register: a new account exists
ALREADY_REGISTERED = "already_registered"  # register: address was taken
INVALID = "invalid"                    # the form did not validate
RATE_LIMITED = "rate_limited"          # over budget, nothing was done
CSRF_FAILED = "csrf_failed"            # stale or forged form
OK = "ok"                              # login, logout: went through
BAD_CREDENTIALS = "bad_credentials"    # login: wrong address or password
SENT = "sent"                          # resend: a fresh link went out
NO_ACCOUNT = "no_account"              # resend: nothing to send to
ALREADY_CONFIRMED = "already_confirmed"  # resend: address was verified already
MAIL_FAILED = "mail_failed"            # the account is fine, the email did not go out

# The confirm route reports the same four states it shows the visitor.
CONFIRM_OUTCOMES = ("ok", "already", "expired", "unknown")

# Long enough to identify a browser, short enough that a hostile client cannot
# grow the collection with one header.
USER_AGENT_MAX = 300


def now() -> datetime:
    return datetime.now(timezone.utc)


def record(db, *, kind: str, outcome: str, email: str = "",
           account_id: Any = None, ip: str = "", user_agent: str = "") -> Any:
    """Write one row. Returns the new document's id."""
    doc = {
        "kind": kind,
        "outcome": outcome,
        "email": email,
        "email_normalized": normalize_email(email) if email else "",
        "account_id": account_id,
        "ip": ip,
        "user_agent": (user_agent or "")[:USER_AGENT_MAX],
        "created_at": now(),
    }
    return db.auth_events.insert_one(doc).inserted_id
