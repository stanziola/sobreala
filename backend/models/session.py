"""The sessions collection: one document per signed-in device.

Flask's cookie is a signed piece of paper. The server can tell that it is valid,
but it has no idea how many of them exist, on how many devices, or since when.
Keeping a document per session is what makes two things possible: showing
someone the list of devices their account is open on, and closing one of them
without touching the others.

Only the hash of the identifier that travels in the cookie is stored, the same
rule the confirmation codes follow: a copy of the database opens no session.

Expiry lives here and not only in the cookie. A cookie's lifetime is a request
the browser is free to ignore; the document is what the server checks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services.security import hash_token, new_token

# How long a session lives, depending on what the person asked for when they
# signed in. Without "keep me signed in" the cookie dies with the browser, and
# this is only so an abandoned document does not sit there for a month.
REMEMBERED_DAYS = 30
BROWSER_HOURS = 12

# last_seen_at is written at most this often. A write on every page load would
# turn reading the panel into writing to the database.
TOUCH_EVERY = timedelta(minutes=5)


def now() -> datetime:
    return datetime.now(timezone.utc)


def start(db, account_id, *, ip: str = "", user_agent: str = "",
          remember: bool = True) -> str:
    """Open a session and return the identifier to put in the cookie."""
    raw, digest = new_token()
    moment = now()
    lifetime = timedelta(days=REMEMBERED_DAYS) if remember else timedelta(hours=BROWSER_HOURS)
    db.sessions.insert_one({
        "account_id": account_id,
        "token_hash": digest,
        "created_at": moment,
        "last_seen_at": moment,
        # Mongo deletes the document when this passes, so nobody has to sweep.
        "expires_at": moment + lifetime,
        "remembered": remember,
        "ip": ip,
        "user_agent": (user_agent or "")[:300],
        "revoked_at": None,
    })
    return raw


def find(db, raw: str | None) -> dict[str, Any] | None:
    """The live session behind this cookie, or None if there is none.

    Revoked and expired are the same answer on purpose: whoever holds the cookie
    does not get to learn which of the two happened.
    """
    if not raw:
        return None
    doc = db.sessions.find_one({"token_hash": hash_token(raw)})
    if doc is None or doc.get("revoked_at") or doc["expires_at"] <= now():
        return None
    return doc


def touch(db, doc: dict[str, Any]) -> None:
    """Note that this session was used. Cheap by design: see TOUCH_EVERY."""
    last = doc.get("last_seen_at")
    if last and now() - last < TOUCH_EVERY:
        return
    db.sessions.update_one({"_id": doc["_id"]}, {"$set": {"last_seen_at": now()}})


def for_account(db, account_id) -> list[dict[str, Any]]:
    """Every live session of an account, the most recently used first."""
    return list(db.sessions.find({
        "account_id": account_id,
        "revoked_at": None,
        "expires_at": {"$gt": now()},
    }).sort("last_seen_at", -1))


def revoke(db, account_id, session_id) -> bool:
    """Close one session. False if it was not this account's, or was closed
    already: the id comes from a form, so it is never trusted on its own."""
    result = db.sessions.update_one(
        {"_id": session_id, "account_id": account_id, "revoked_at": None},
        {"$set": {"revoked_at": now()}},
    )
    return result.modified_count == 1


def revoke_others(db, account_id, keep_id) -> int:
    """Close every session of this account except the one in use. Returns how
    many were closed."""
    result = db.sessions.update_many(
        {"account_id": account_id, "_id": {"$ne": keep_id}, "revoked_at": None},
        {"$set": {"revoked_at": now()}},
    )
    return result.modified_count


# ------------------------------------------------------------------- devices

# Order matters twice over: Edge says it is Chrome, and Chrome says it is
# Safari, so the more specific name has to be found first.
BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Chrome/", "Chrome"),
            ("Firefox/", "Firefox"), ("Safari/", "Safari"))
SYSTEMS = (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
           ("Windows", "Windows"), ("Mac OS X", "macOS"), ("Macintosh", "macOS"),
           ("CrOS", "ChromeOS"), ("Linux", "Linux"))


def describe(user_agent: str | None) -> dict[str, str | None]:
    """Browser and system, or None for what cannot be told.

    Deliberately shallow: a proper user-agent parser is a library that needs
    updating forever, and this only has to help someone recognise their own
    phone in a list. Whatever it cannot name, it says it cannot name.
    """
    agent = user_agent or ""
    browser = next((name for token, name in BROWSERS if token in agent), None)
    system = next((name for token, name in SYSTEMS if token in agent), None)
    return {"browser": browser, "system": system}
