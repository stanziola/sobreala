"""The devices that do not have to ask for the code every time.

Asking for six digits on every sign-in from the same computer is how two-step
verification ends up switched off. So a device that has already answered once
is remembered for a month, in its own cookie: it has to outlive signing out,
which is precisely when the session cookie goes away.

Same rules as models/session.py, and for the same reasons: only the hash of what
travels in the cookie is stored, and Mongo sweeps what expires.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services.security import hash_token, new_token

REMEMBER_DAYS = 30
COOKIE = "pm_td"


def now() -> datetime:
    return datetime.now(timezone.utc)


def remember(db, account_id, *, ip: str = "", user_agent: str = "") -> str:
    """Trust this device for a month. Returns the value for the cookie."""
    raw, digest = new_token()
    moment = now()
    db.trusted_devices.insert_one({
        "account_id": account_id,
        "token_hash": digest,
        "created_at": moment,
        "expires_at": moment + timedelta(days=REMEMBER_DAYS),
        "ip": ip,
        "user_agent": (user_agent or "")[:300],
    })
    return raw


def is_trusted(db, account_id, raw: str | None) -> bool:
    """Whether this cookie vouches for this account, right now.

    The account is part of the question on purpose: a cookie from one account is
    not a reason to skip the code on another.
    """
    if not raw:
        return False
    return db.trusted_devices.count_documents({
        "account_id": account_id,
        "token_hash": hash_token(raw),
        "expires_at": {"$gt": now()},
    }, limit=1) > 0


def forget_all(db, account_id) -> int:
    """Stop trusting every device of this account.

    Turning two-step verification off and on again, or regenerating the recovery
    codes, has to leave nothing behind: otherwise a device someone else trusted
    keeps walking in without a code.
    """
    return db.trusted_devices.delete_many({"account_id": account_id}).deleted_count


def for_account(db, account_id) -> list[dict[str, Any]]:
    return list(db.trusted_devices.find({
        "account_id": account_id, "expires_at": {"$gt": now()},
    }).sort("created_at", -1))
