"""The accounts collection: one document per client company."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from config import Config
from services.security import hash_password, verify_password

# States defined in CLAUDE.md. Email confirmation is NOT one of them: these
# describe the commercial approval Luis does by hand, while confirming the
# address is a separate fact, kept in its own field.
REGISTERED = "registered"
APPROVED = "approved"
ACTIVE = "active"
SUSPENDED = "suspended"
STATUSES = (REGISTERED, APPROVED, ACTIVE, SUSPENDED)

# Quien administra la plataforma. Una cuenta corriente no tiene el campo; al
# primer administrador se lo pone make_admin.py a mano, porque nadie puede
# aprobarse a sí mismo el primer día.
ADMIN = "admin"


def normalize_email(email: str) -> str:
    """Same rule the contacts collection uses: no spaces, lowercase."""
    return "".join(email.split()).lower()


def now() -> datetime:
    return datetime.now(timezone.utc)


def create(db, *, company_name: str, contact_name: str, email: str,
           password: str, phone: str = "") -> dict[str, Any] | None:
    """Insert a new account. Returns None if the address is already taken.

    The caller must not tell the visitor which of the two happened: both cases
    lead to the same screen, so the site does not reveal who has an account.
    """
    moment = now()
    doc = {
        "company_name": company_name.strip(),
        "contact_name": contact_name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "email_normalized": normalize_email(email),
        "password_hash": hash_password(password),
        "email_confirmed_at": None,
        "status": REGISTERED,
        "created_at": moment,
        "updated_at": moment,
        "last_login_at": None,
        # Every password this account has used, oldest first, so none of them
        # can be set again. Hashes, like the current one: nothing readable.
        "password_history": [],
        # Mongo deletes the document when this passes. confirm_email() removes
        # the field, and what has no field is never swept.
        "purge_at": moment + timedelta(hours=Config.UNCONFIRMED_HOURS),
    }
    try:
        result = db.accounts.insert_one(doc)
    except DuplicateKeyError:
        return None
    doc["_id"] = result.inserted_id
    return doc


def delete(db, account_id) -> None:
    """Remove an account. Only used to undo a registration whose confirmation
    email could not be sent: half an account is worse than none."""
    db.accounts.delete_one({"_id": account_id})


def by_email(db, email: str) -> dict[str, Any] | None:
    return db.accounts.find_one({"email_normalized": normalize_email(email)})


def by_id(db, account_id) -> dict[str, Any] | None:
    return db.accounts.find_one({"_id": account_id})


def change_email(db, account_id, email: str) -> bool:
    """Point an account at another address. False if that one is taken.

    The unique index is what answers, not a look-up beforehand: between asking
    and writing there is room for another registration, and only the index sees
    both at once.
    """
    try:
        db.accounts.update_one(
            {"_id": account_id},
            {"$set": {"email": email.strip(),
                      "email_normalized": normalize_email(email),
                      "updated_at": now()}},
        )
    except DuplicateKeyError:
        return False
    return True


def confirm_email(db, account_id) -> bool:
    """Mark the address as verified. False if it already was.

    Confirming is also what takes the account off the sweep: with no purge_at,
    the TTL index has nothing to look at.
    """
    result = db.accounts.update_one(
        {"_id": account_id, "email_confirmed_at": None},
        {"$set": {"email_confirmed_at": now(), "updated_at": now()},
         "$unset": {"purge_at": ""}},
    )
    return result.modified_count == 1


def touch_login(db, account_id) -> None:
    db.accounts.update_one({"_id": account_id}, {"$set": {"last_login_at": now()}})


# ------------------------------------------------------------- administration

def is_admin(account: dict[str, Any] | None) -> bool:
    return (account or {}).get("role") == ADMIN


def is_suspended(account: dict[str, Any] | None) -> bool:
    return (account or {}).get("status") == SUSPENDED


def set_role(db, account_id, role: str | None) -> None:
    """Give or take the administrator role. Only make_admin.py calls this."""
    if role == ADMIN:
        db.accounts.update_one({"_id": account_id},
                               {"$set": {"role": ADMIN, "updated_at": now()}})
    else:
        db.accounts.update_one({"_id": account_id},
                               {"$unset": {"role": ""},
                                "$set": {"updated_at": now()}})


def set_status(db, account_id, status: str) -> str | None:
    """Move an account to another state. Returns the one it had, or None.

    The previous state is what makes the record in admin_events readable: "de
    registered a approved" dice algo, "a approved" no dice nada.
    """
    if status not in STATUSES:
        return None
    before = by_id(db, account_id)
    if before is None or before.get("status") == status:
        return None
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"status": status, "updated_at": now()}})
    return before.get("status")


def set_plan(db, account_id, plan: str | None) -> str | None:
    """Put an account on a plan, or take it off one. Returns the previous."""
    if plan is not None and plan not in PLAN_CONTACTS:
        return None
    before = by_id(db, account_id)
    if before is None or (before.get("plan") or None) == plan:
        return None
    change = {"$set": {"plan": plan, "updated_at": now()}} if plan else              {"$unset": {"plan": ""}, "$set": {"updated_at": now()}}
    db.accounts.update_one({"_id": account_id}, change)
    return before.get("plan")


def by_status(db) -> dict[str, int]:
    """How many accounts sit in each state, for the admin front page."""
    counted = {name: 0 for name in STATUSES}
    for row in db.accounts.aggregate([{"$group": {"_id": "$status",
                                                  "n": {"$sum": 1}}}]):
        if row["_id"] in counted:
            counted[row["_id"]] = row["n"]
    return counted


def search(db, *, status: str = "", text: str = "", limit: int = 100,
           skip: int = 0) -> tuple[list[dict[str, Any]], int]:
    """The admin table: filter by state, search by address or company."""
    import re

    query: dict[str, Any] = {}
    if status in STATUSES:
        query["status"] = status
    if text:
        safe = re.escape(text.strip())
        query["$or"] = [
            {"email_normalized": {"$regex": f"^{re.escape(normalize_email(text))}"}},
            {"company_name": {"$regex": safe, "$options": "i"}},
        ]
    total = db.accounts.count_documents(query)
    found = list(db.accounts.find(query).sort("created_at", -1)
                 .skip(skip).limit(limit))
    return found, total


# ---------------------------------------------------------------- notifications

# The messages an account can choose not to receive. Security notices are NOT
# here on purpose: the confirmation code, the recovery code, "your password
# changed" and "two-step was turned on or off" are what warns somebody that
# another person is inside their account, and a switch for them would be a
# switch for turning the alarm off.
NEW_LOGIN = "new_login"
BILLING = "billing"
IMPORTS = "imports"
CAMPAIGNS = "campaigns"
MONTHLY = "monthly"
NOTICES = (NEW_LOGIN, BILLING, IMPORTS, CAMPAIGNS, MONTHLY)


def wants(account: dict[str, Any] | None, notice: str) -> bool:
    """Whether this account still wants that message.

    Anything not written counts as yes: an account that never opened the screen
    —every account there is today— keeps getting everything, which is the safe
    way round for a preference nobody has expressed.
    """
    return (account or {}).get("notifications", {}).get(notice, True) is not False


def set_notifications(db, account_id, wanted: dict[str, bool]) -> None:
    """Write the whole set from what the form said.

    Only the names this module knows are written. A form field for anything
    else —a security notice, say— is dropped here rather than stored, so no
    request can invent a preference that turns one of them off.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "notifications": {name: bool(wanted.get(name)) for name in NOTICES},
        "updated_at": now(),
    }})


# Contactos que caben en cada plan, copiados de docs/pricing.md, que es la
# fuente de verdad. El límite de correos es siempre 5x el de contactos, y se
# calculará desde aquí cuando haya envíos que contar.
PLAN_CONTACTS = {
    "basico": 1000,
    "negocio": 3000,
    "empresa": 10000,
    "corporativo": 50000,
}


def contact_limit(account: dict[str, Any] | None) -> int:
    """Cuántos contactos puede tener esta cuenta.

    Sin plan no hay cifra en docs/pricing.md, así que manda la del config: una
    cuenta recién creada puede probar con una lista de verdad antes de pagar.
    """
    from config import Config
    return PLAN_CONTACTS.get(plan_of(account) or "", Config.CONTACTS_FREE_LIMIT)


def plan_of(account: dict[str, Any] | None) -> str | None:
    """The plan this account pays for, or None while it pays for none.

    Nothing writes this field yet —billing is not built— so today it answers
    None for everybody, and the screen says so in words instead of leaving a
    blank where a plan should be.
    """
    return (account or {}).get("plan") or None


# ------------------------------------------------------- two-step verification

def two_factor_on(account: dict[str, Any] | None) -> bool:
    return bool((account or {}).get("two_factor", {}).get("enabled_at"))


def enable_two_factor(db, account_id, secret: str, recovery: list[str]) -> None:
    """Turn it on, with the secret the app scanned and the recovery codes.

    The secret goes in as it is because TOTP needs it that way —see
    services/totp.py— and the recovery codes go in hashed, like every other code
    in this project.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "two_factor": {
            "secret": secret,
            "enabled_at": now(),
            "recovery": recovery,
            "last_counter": 0,
        },
        "updated_at": now(),
    }})


def disable_two_factor(db, account_id) -> None:
    db.accounts.update_one({"_id": account_id},
                           {"$unset": {"two_factor": ""},
                            "$set": {"updated_at": now()}})


def set_recovery_codes(db, account_id, recovery: list[str]) -> None:
    """Replace the recovery codes. The old ones stop working at once."""
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"two_factor.recovery": recovery,
                                     "updated_at": now()}})


def use_counter(db, account_id, counter: int) -> bool:
    """Spend the 30-second window a code belonged to.

    False when that window, or a later one, was already used: a code someone
    read over a shoulder stops working the moment its owner types it.
    """
    result = db.accounts.update_one(
        {"_id": account_id, "two_factor.last_counter": {"$lt": counter}},
        {"$set": {"two_factor.last_counter": counter}},
    )
    return result.modified_count == 1


def use_recovery_code(db, account_id, hashed: str) -> bool:
    """Spend one recovery code. False if it was not there to spend."""
    result = db.accounts.update_one(
        {"_id": account_id, "two_factor.recovery": hashed},
        {"$pull": {"two_factor.recovery": hashed}},
    )
    return result.modified_count == 1


def password_was_used(account: dict[str, Any], password: str) -> bool:
    """Whether this account has ever had this password.

    Every hash is checked one by one because each carries its own salt: there is
    no index for this, and no shortcut. It costs what bcrypt costs, on an action
    that happens once in a long while.
    """
    for stored in [account.get("password_hash")] + list(account.get("password_history", [])):
        if stored and verify_password(password, stored):
            return True
    return False


def set_password(db, account_id, password_hash: str) -> None:
    """Write the new password and remember the one it replaces."""
    account = by_id(db, account_id)
    old = (account or {}).get("password_hash")
    update = {"$set": {"password_hash": password_hash, "updated_at": now()}}
    if old:
        update["$push"] = {"password_history": old}
    db.accounts.update_one({"_id": account_id}, update)


def is_confirmed(account: dict[str, Any] | None) -> bool:
    return bool(account and account.get("email_confirmed_at"))
