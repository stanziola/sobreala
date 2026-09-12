"""The mail_log collection: one document per system email that was attempted.

Body included, on purpose. When someone says a confirmation never arrived, the
useful question is what exactly left the server, and the answer has to be
readable months later: same subject, same HTML, same link. Storing only metadata
answers "we tried" and nothing more.

Failures are recorded too, with the reason. From the outside "the mail never
arrived" and "sending raised an exception" look identical, and they need
completely different fixes.

These are TRANSACTIONAL messages only: confirmation and account notices. Client
campaigns are a different path with its own accounting, and the unsubscribe and
watermark rules in CLAUDE.md apply there, not here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from models.account import normalize_email

SENT = "sent"
FAILED = "failed"

# What the message was for. Keeps the log readable without parsing subjects.
CONFIRM = "confirm"
EXISTS = "exists"
WELCOME = "welcome"
PASSWORD_CHANGED = "password_changed"
RECOVER = "recover"
NEW_LOGIN = "new_login"
TWO_FACTOR = "two_factor"
# Los avisos de la cuenta, que compone services/notices.py.
PLAN_PAID = "plan_paid"
PLAN_EXPIRING = "plan_expiring"
PLAN_EXPIRED = "plan_expired"
SENDING_CLEARED = "sending_cleared"
SUSPENDED = "suspended"
REINSTATED = "reinstated"
ADMIN_PAYMENT = "admin_payment"
ADMIN_SIGNUP = "admin_signup"
ADMIN_PLAN_END = "admin_plan_end"
# Cambiar el correo de la cuenta: el código va a la dirección nueva y el aviso
# a la vieja, así que son dos mensajes distintos y a dos sitios distintos.
EMAIL_CHANGE_CODE = "email_change_code"
EMAIL_CHANGED = "email_changed"
# Sent by hand from check_mail.py, never by the application.
CHECK = "check"


def now() -> datetime:
    return datetime.now(timezone.utc)


def record(db, *, to: str, subject: str, backend: str, status: str,
           html: str = "", text: str = "", purpose: str = "",
           provider_id: str | None = None, error: str | None = None,
           account_id: Any = None) -> Any:
    """Write one row. Returns the new document's id."""
    doc = {
        "to": to,
        # Same normalisation as accounts and contacts, so a search for an
        # address finds its mail whatever case it was typed in.
        "to_normalized": normalize_email(to) if to else "",
        "subject": subject,
        "backend": backend,
        "status": status,
        "purpose": purpose,
        "provider_id": provider_id,
        "error": error,
        "account_id": account_id,
        "html": html,
        "text": text,
        "created_at": now(),
    }
    return db.mail_log.insert_one(doc).inserted_id
