"""Single-use tokens with an expiry, for links sent by email.

Only the hash of the token is stored. Someone holding a copy of the database
cannot confirm an address or, later, reset a password with what is in it.

Written generically on purpose: password reset and email change will need
exactly the same thing and only add a new `purpose`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config import Config
from services.security import hash_token, new_token

EMAIL_CONFIRMATION = "email_confirmation"

# Why a link was refused, so the visitor gets a useful message instead of a
# generic error. UNKNOWN also covers a token whose grace window has passed.
VALID = "valid"
UNKNOWN = "unknown"
EXPIRED = "expired"
USED = "used"


def now() -> datetime:
    return datetime.now(timezone.utc)


def issue(db, account_id, purpose: str = EMAIL_CONFIRMATION,
          hours: int | None = None) -> str:
    """Invalidate any previous token for this account and purpose, issue a new
    one, and return the raw value to put in the link."""
    db.account_tokens.delete_many({"account_id": account_id, "purpose": purpose,
                                   "used_at": None})
    raw, digest = new_token()
    moment = now()
    expires_at = moment + timedelta(hours=hours or Config.CONFIRMATION_TOKEN_HOURS)
    db.account_tokens.insert_one({
        "account_id": account_id,
        "purpose": purpose,
        "token_hash": digest,
        "created_at": moment,
        "expires_at": expires_at,
        "used_at": None,
        # Mongo deletes the document at this point. The gap after expiry is what
        # lets an expired link be answered with "it expired" rather than
        # "no such link".
        "purge_at": expires_at + timedelta(days=Config.TOKEN_GRACE_DAYS),
    })
    return raw


def check(db, raw: str, purpose: str = EMAIL_CONFIRMATION) -> tuple[str, dict[str, Any] | None]:
    """Look a token up by its hash. Returns (reason, document)."""
    if not raw:
        return UNKNOWN, None
    doc = db.account_tokens.find_one({"token_hash": hash_token(raw), "purpose": purpose})
    if doc is None:
        return UNKNOWN, None
    if doc.get("used_at"):
        return USED, doc
    if doc["expires_at"] <= now():
        return EXPIRED, doc
    return VALID, doc


def spend(db, token_doc: dict[str, Any]) -> bool:
    """Mark the token as used. False if someone else got there first."""
    result = db.account_tokens.update_one(
        {"_id": token_doc["_id"], "used_at": None},
        {"$set": {"used_at": now()}},
    )
    return result.modified_count == 1
