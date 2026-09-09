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
PASSWORD_CHANGE = "password_change"
RECOVER = "recover"
CORRECT_EMAIL = "correct_email"
TWO_FACTOR = "two_factor"
SESSION_CLOSED = "session_closed"
RESEND = "resend"
CONFIRM = "confirm"
LOGOUT = "logout"
SETTINGS = "settings"
IMPORT = "import"

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
BAD_CURRENT = "bad_current"            # password change: the old one was wrong
TAKEN = "taken"                        # correcting: the new address has an account
SECOND_STEP = "second_step"            # login: the password was right, the code is missing
RECOVERY_USED = "recovery_used"        # login: got in with a backup code
DISABLED = "disabled"                  # two-step: turned off
REGENERATED = "regenerated"            # two-step: new recovery codes
MAIL_FAILED = "mail_failed"            # the account is fine, the email did not go out
FAILED = "failed"                      # import: the file could not be read
SUSPENDED = "suspended"                # login: la contraseña era buena, la cuenta no

# What the confirm route writes down, keyed by the reason models/token.py gave.
# The screen collapses most of these into one message, on purpose; the log keeps
# them apart, because "there was no code" and "the code was wrong" are different
# facts when a complaint has to be investigated.
CONFIRM_OUTCOMES = {
    "valid": OK,
    "invalid": "invalid_code",
    "unknown": "no_code",
    "expired": "expired",
    "used": "already",
    "too_many": "too_many",
}

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
