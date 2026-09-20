"""The suppressions collection: addresses an account may never write to again.

A collection of its own, and never part of the contact. That is the whole
point: deleting a contact does not delete its suppression, and importing the
address again does not bring it back. Somebody who asked not to be written to
stays asked, whatever happens to the list they were on.

Scoped to the account, always. A person who unsubscribed from a cooperative has
said nothing about the school that also has their address, and a global
suppression would answer for them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo.errors import DuplicateKeyError

from models.account import normalize_email

# Why the address is here. Only one of them can ever be lifted.
UNSUBSCRIBE = "unsubscribe"      # asked to stop; comes back only by opting in again
HARD_BOUNCE = "hard_bounce"      # the address does not exist. Never lifted.
COMPLAINT = "complaint"          # marked as spam. Never lifted.
MANUAL = "manual"                # the client put it here, and can take it out
REASONS = (UNSUBSCRIBE, HARD_BOUNCE, COMPLAINT, MANUAL)
LIFTABLE = (MANUAL,)


def now() -> datetime:
    return datetime.now(timezone.utc)


def add(db, account_id, email: str, *, reason: str = MANUAL,
        source: str = "") -> bool:
    """Suppress one address. False if it already was.

    Never raises on a repeat: the unique index is what answers, and suppressing
    twice is not an error, it is the same fact stated again.
    """
    try:
        db.suppressions.insert_one({
            "account_id": account_id,
            "email": email.strip(),
            "email_normalized": normalize_email(email),
            "reason": reason if reason in REASONS else MANUAL,
            # Where it came from: a screen, a webhook, an unsubscribe link.
            "source": source[:120],
            "created_at": now(),
        })
    except DuplicateKeyError:
        return False
    return True


def among(db, account_id, emails: Iterable[str]) -> set[str]:
    """Which of these addresses are suppressed, asked in one query.

    Rule 10 of CLAUDE.md lives here: the import and the list screen both call
    this with a whole batch, and never once per contact.
    """
    wanted = [normalize_email(e) for e in emails]
    if not wanted:
        return set()
    found = db.suppressions.find(
        {"account_id": account_id, "email_normalized": {"$in": wanted}},
        {"email_normalized": 1})
    return {doc["email_normalized"] for doc in found}


def has(db, account_id, email: str) -> bool:
    return db.suppressions.count_documents(
        {"account_id": account_id, "email_normalized": normalize_email(email)},
        limit=1) == 1


def count(db, account_id) -> int:
    return db.suppressions.count_documents({"account_id": account_id})


def count_between(db, account_id, start, end=None, *, reason: str | None = None) -> int:
    """Cuántas se anotaron en ese tramo. Es lo que cuenta las bajas del periodo
    en Estadísticas, y las altas y bajas por mes.

    `end` abierto cuenta hasta ahora. Con `reason` se piden solo las de un
    motivo, que es como se cuentan las bajas de verdad (`unsubscribe`) aparte de
    las que puso un rebote.
    """
    when: dict[str, Any] = {"$gte": start}
    if end is not None:
        when["$lt"] = end
    query: dict[str, Any] = {"account_id": account_id, "created_at": when}
    if reason:
        query["reason"] = reason
    return db.suppressions.count_documents(query)


def for_account(db, account_id, *, limit: int = 200) -> list[dict[str, Any]]:
    return list(db.suppressions.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))


def lift(db, account_id, email: str) -> bool:
    """Take an address off the list. Only what the client put there by hand.

    A bounce or a complaint is a fact about the address, not a preference: it
    does not stop being true because somebody presses a button.
    """
    result = db.suppressions.delete_one({
        "account_id": account_id,
        "email_normalized": normalize_email(email),
        "reason": {"$in": list(LIFTABLE)},
    })
    return result.deleted_count == 1
