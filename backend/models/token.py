"""Single-use confirmation codes with an expiry, for what is sent by email.

Only the hash of the code is stored, and it is a keyed hash: see hash_code() in
services/security.py for why six digits cannot be protected by a plain digest.
Someone holding a copy of the database cannot confirm an address with what is
in it.

Six digits are guessable in a way a 32-byte token never was, so two things
carry the weight instead: the code dies after MAX_ATTEMPTS wrong tries, and it
lives for minutes rather than hours.

Written generically on purpose: password reset and email change will need
exactly the same thing and only add a new `purpose`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from config import Config
from services.security import (CODE_DIGITS, clean_code, codes_match,
                               hash_code, hash_token, new_code, new_token)

EMAIL_CONFIRMATION = "email_confirmation"
# Written generically from the start, so recovering a password only needed a
# name: same keyed hash, same five tries, same expiry.
PASSWORD_RESET = "password_reset"
# Closing a session from the email that announced it. A link and not a code:
# nobody types six digits to put out a fire, and the value travels in the URL.
SESSION_REVOKE = "session_revoke"
# Cambiar el correo de una cuenta que ya está confirmada. El código va a la
# dirección **nueva**: es lo que prueba que existe y que es de quien la escribió.
EMAIL_CHANGE = "email_change"
# La invitación a entrar como usuario de una cuenta. Un enlace y no un código:
# quien lo recibe todavía no tiene contraseña, así que lo que el enlace prueba
# es que esa dirección es suya, y al otro lado pone la suya.
INVITE = "invite"
# Confirmar el «Responder a» de las campañas. El código va a esa dirección:
# es lo que prueba que es de quien la escribió y no de un tercero que
# recibiría las respuestas de toda una lista.
REPLY_TO = "reply_to"
# Confirmar una dirección de prueba de la demostración (octubre de 2026). Un
# enlace a esa dirección: prueba que es de quien la puso, y que acepta recibir
# los correos de prueba.
TEST_ADDRESS = "test_address"

# Why a code was refused, so the visitor gets a useful message instead of a
# generic error. UNKNOWN is "there is no code waiting for this account"; INVALID
# is "there is one and this is not it".
VALID = "valid"
INVALID = "invalid"
UNKNOWN = "unknown"
EXPIRED = "expired"
USED = "used"
TOO_MANY = "too_many"

# A million combinations divided by five tries is not a lottery worth playing.
MAX_ATTEMPTS = 5


def now() -> datetime:
    return datetime.now(timezone.utc)


def issue(db, account_id, purpose: str = EMAIL_CONFIRMATION,
          minutes: int | None = None) -> str:
    """Replace any earlier code for this account and purpose, and return the new
    one to put in the email."""
    # Every earlier one goes, used or not, so a lookup by account and purpose can
    # only ever find a single document.
    db.account_tokens.delete_many({"account_id": account_id, "purpose": purpose})
    code = new_code()
    moment = now()
    expires_at = moment + timedelta(minutes=minutes or Config.CONFIRMATION_CODE_MINUTES)
    db.account_tokens.insert_one({
        "account_id": account_id,
        "purpose": purpose,
        "code_hash": hash_code(code),
        "attempts": 0,
        "created_at": moment,
        "expires_at": expires_at,
        "used_at": None,
        # Mongo deletes the document at this point. The gap after expiry is what
        # lets an expired code be answered with "it expired" rather than
        # "no such code".
        "purge_at": expires_at + timedelta(days=Config.TOKEN_GRACE_DAYS),
    })
    return code


def issue_link(db, account_id, purpose: str, data: dict[str, Any],
               days: int = 7) -> str:
    """A single-use link. Returns the value that goes in the URL.

    Only its hash is stored, like the codes: what travels in the email cannot be
    read back out of the database. `data` carries what the link is about —which
    session to close— so the route does not have to trust the URL for anything
    but identity.
    """
    raw, digest = new_token()
    moment = now()
    expires_at = moment + timedelta(days=days)
    db.account_tokens.insert_one({
        "account_id": account_id,
        "purpose": purpose,
        "token_hash": digest,
        "data": data,
        "created_at": moment,
        "expires_at": expires_at,
        "used_at": None,
        "purge_at": expires_at + timedelta(days=Config.TOKEN_GRACE_DAYS),
    })
    return raw


def find_link(db, raw: str | None, purpose: str) -> dict[str, Any] | None:
    """The live link behind this URL, or None.

    Spent and expired answer the same: whoever holds the link does not get to
    learn which of the two happened.
    """
    if not raw:
        return None
    doc = db.account_tokens.find_one({"token_hash": hash_token(raw),
                                      "purpose": purpose})
    if doc is None or doc.get("used_at") or doc["expires_at"] <= now():
        return None
    return doc


def check(db, account_id, typed: str,
          purpose: str = EMAIL_CONFIRMATION) -> tuple[str, dict[str, Any] | None]:
    """Compare what was typed against this account's code. Returns (reason, doc).

    A wrong try is counted before anything is said about it: the attempt has to
    cost something, or five hundred thousand guesses would get in on average.
    """
    doc = db.account_tokens.find_one({"account_id": account_id, "purpose": purpose})
    if doc is None:
        return UNKNOWN, None
    if doc.get("used_at"):
        return USED, doc
    if doc["expires_at"] <= now():
        return EXPIRED, doc
    if doc.get("attempts", 0) >= MAX_ATTEMPTS:
        return TOO_MANY, doc

    if codes_match(doc.get("code_hash"), hash_code(typed)):
        return VALID, doc

    spent = db.account_tokens.find_one_and_update(
        {"_id": doc["_id"]}, {"$inc": {"attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if spent and spent.get("attempts", 0) >= MAX_ATTEMPTS:
        return TOO_MANY, spent
    return INVALID, spent or doc


def spend(db, token_doc: dict[str, Any]) -> bool:
    """Mark the code as used. False if someone else got there first."""
    result = db.account_tokens.update_one(
        {"_id": token_doc["_id"], "used_at": None},
        {"$set": {"used_at": now()}},
    )
    return result.modified_count == 1


def discard(db, account_id, purpose: str = EMAIL_CONFIRMATION) -> None:
    """Throw the code away. Used when a registration is undone because the email
    could not be sent: the account is going, and its code goes with it."""
    db.account_tokens.delete_many({"account_id": account_id, "purpose": purpose})


def looks_complete(typed: str) -> bool:
    """Whether what was typed even has the shape of a code."""
    return len(clean_code(typed)) == CODE_DIGITS
