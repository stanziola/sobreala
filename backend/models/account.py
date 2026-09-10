"""The accounts collection: one document per client company."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from config import Config
from services import plans
from services.security import hash_password, verify_password

# Los estados de CLAUDE.md. Confirmar el correo NO es uno: eso es otro hecho y
# vive en su propio campo.
#
# Hubo un cuarto, `approved`, entre registrada y activa: una aprobación
# comercial a mano sin la cual no se podía comprar. Se quitó. Esperar a que
# alguien te apruebe para poder pagar no protegía nada que valiera esa espera, y
# la mirada que sí importa —de dónde salió esa lista— se hace ahora justo antes
# del primer envío, que es donde puede hacer daño.
REGISTERED = "registered"   # se registró; explora, importa y puede comprar
ACTIVE = "active"           # pagó; su plan corre hasta plan_until
SUSPENDED = "suspended"     # corte por rebotes o quejas. No es una aprobación
STATUSES = (REGISTERED, ACTIVE, SUSPENDED)

# Quién es cada cuenta. Toda cuenta lleva el campo, también las corrientes: uno
# que a veces está y a veces no es difícil de leer en la base y fácil de
# equivocar en una consulta.
#
# Lo que decide quién manda es la comparación exacta contra ADMIN, así que una
# cuenta sin campo, con el valor mal escrito o con cualquier otra cosa no es
# administradora. Al primero se lo pone make_admin.py a mano, porque nadie puede
# aprobarse a sí mismo el primer día.
CLIENT = "client"
ADMIN = "admin"
ROLES = (CLIENT, ADMIN)


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
        "role": CLIENT,
        "contact_tags": [],
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


# ------------------------------------------------------------- contact tags

# El registro de qué etiquetas existen en esta cuenta. Vive aquí y no en cada
# contacto porque una etiqueta recién creada todavía no tiene a nadie dentro, y
# preguntándole a los contactos no aparecería hasta que lo tuviera.
#
# Quién lleva qué sigue siendo el arreglo del contacto. Esto solo dice cuáles
# se pueden asignar, que es lo que impide que se escriban a mano y acaben
# «Socios» y «socios» como dos.
TAG_LENGTH = 40


def clean_tag(name: str) -> str:
    """Un nombre de etiqueta, sin espacios de más y con un largo razonable."""
    return " ".join((name or "").split())[:TAG_LENGTH]


def tags_of(account: dict[str, Any] | None) -> list[str]:
    return list((account or {}).get("contact_tags") or [])


def tag_limit(account: dict[str, Any] | None) -> int:
    """Cuántas etiquetas puede tener esta cuenta, según su plan."""
    return plans.tag_limit(plan_of(account))


def add_tag(db, account_id, name: str) -> bool:
    """Crear una etiqueta. False si el nombre está vacío, repetido o si ya no
    caben más.

    La comparación es sin mayúsculas, que es justamente lo que evita el par
    «Socios» y «socios».
    """
    tag = clean_tag(name)
    if not tag:
        return False
    account = by_id(db, account_id)
    existing = tags_of(account)
    if len(existing) >= tag_limit(account):
        return False
    if any(tag.lower() == other.lower() for other in existing):
        return False
    db.accounts.update_one({"_id": account_id},
                           {"$push": {"contact_tags": tag},
                            "$set": {"updated_at": now()}})
    return True


def remove_tag(db, account_id, name: str) -> None:
    """Sacar la etiqueta del registro. Quitársela a los contactos que la
    llevaban es cosa de models/contact.py, y el que borra hace las dos."""
    db.accounts.update_one({"_id": account_id},
                           {"$pull": {"contact_tags": name},
                            "$set": {"updated_at": now()}})


# ------------------------------------------------------------- administration

def names_of(db, ids) -> dict[Any, str]:
    """El nombre de cada empresa, por id, en una sola consulta.

    Es para las tablas que enseñan filas de varias cuentas a la vez: pedir cada
    nombre por separado sería una consulta por fila.
    """
    wanted = [one for one in set(ids) if one is not None]
    if not wanted:
        return {}
    found = db.accounts.find({"_id": {"$in": wanted}}, {"company_name": 1})
    return {doc["_id"]: doc.get("company_name", "") for doc in found}


def is_admin(account: dict[str, Any] | None) -> bool:
    return (account or {}).get("role") == ADMIN


def status_of(account: dict[str, Any] | None) -> str:
    """El estado de esa cuenta, siempre uno de los que el código conoce.

    Un valor escrito por una versión anterior —`approved`, que existió hasta que
    se quitó la aprobación de cuentas— no puede convertir una pantalla en una
    página de error: la interfaz busca su texto por el nombre del estado, y uno
    que no está en la tabla de traducciones revienta la página entera. Se lee
    como `registered`, que es donde nace toda cuenta, y la siguiente escritura
    lo deja bien.
    """
    found = (account or {}).get("status")
    return found if found in STATUSES else REGISTERED


def can_buy(account: dict[str, Any] | None) -> bool:
    """Si esta cuenta puede contratar un plan.

    Dos condiciones y ninguna la decide una persona. El correo confirmado,
    porque es a donde va el comprobante y los avisos del plan, y cobrarle a una
    dirección escrita mal deja a alguien pagando sin recibir nada. Y no estar
    suspendida, que es lo contrario de vender más.

    Una cuenta activa también puede: si no, el primer pago sería el último y
    nadie podría renovar ni cambiar de plan.
    """
    return is_confirmed(account) and not is_suspended(account)


def is_suspended(account: dict[str, Any] | None) -> bool:
    return (account or {}).get("status") == SUSPENDED


def set_role(db, account_id, role: str | None) -> None:
    """Give or take the administrator role. Only make_admin.py calls this.

    Quitarlo deja `client`, no deja la cuenta sin campo: el rol es una
    propiedad de toda cuenta, y su ausencia no debería significar nada.
    """
    db.accounts.update_one(
        {"_id": account_id},
        {"$set": {"role": role if role in ROLES else CLIENT,
                  "updated_at": now()}})


def set_status(db, account_id, status: str) -> str | None:
    """Move an account to another state. Returns the one it had, or None.

    The previous state is what makes the record in admin_events readable: "de
    registered a suspended" dice algo, "a suspended" no dice nada.
    """
    if status not in STATUSES:
        return None
    before = by_id(db, account_id)
    if before is None or before.get("status") == status:
        return None
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"status": status, "updated_at": now()}})
    return before.get("status")


def can_send(account: dict[str, Any] | None) -> bool:
    """Si de esta cuenta puede salir una campaña.

    Es la única puerta que queda con una persona detrás, y está donde hace
    falta: todos los clientes envían desde el mismo dominio, así que comparten
    una sola reputación, y una lista comprada la quema para todos. Se mira una
    vez, antes del primer envío; después la cuenta queda habilitada.

    Registrarse, importar y pagar no la necesitan: nada de eso le llega a
    nadie.
    """
    return bool(account and account.get("sending_cleared_at"))


def clear_sending(db, account_id, admin_id) -> bool:
    """Habilitar el envío. False si ya lo estaba.

    Escritura condicional sobre la ausencia del campo, así que pulsar dos veces
    no anota dos decisiones ni mueve la fecha de la primera.
    """
    result = db.accounts.update_one(
        {"_id": account_id, "sending_cleared_at": {"$exists": False}},
        {"$set": {"sending_cleared_at": now(), "sending_cleared_by": admin_id,
                  "updated_at": now()}})
    return result.modified_count == 1


def waiting_to_send(db, *, limit: int = 20) -> list[dict[str, Any]]:
    """Las cuentas que ya pagaron y todavía no pueden enviar.

    Es la cola del administrador: lo único que espera una decisión suya. Las
    más antiguas primero, que son las que llevan más tiempo esperando.
    """
    return list(db.accounts.find(
        {"plan": {"$exists": True, "$ne": None},
         "sending_cleared_at": {"$exists": False},
         "role": {"$ne": ADMIN}}).sort("updated_at", 1).limit(limit))


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


def activate_plan(db, account_id, plan: str, until) -> None:
    """Dejar la cuenta pagada: su plan, activa, y hasta cuándo.

    Es el único sitio que escribe `active`: estar activa es el efecto de un
    pago cobrado, no una decisión que alguien tome a mano.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "plan": plan, "status": ACTIVE, "plan_until": until,
        "updated_at": now(),
    }})


def plan_until(account: dict[str, Any] | None):
    return (account or {}).get("plan_until")


def renews_from(account: dict[str, Any] | None, plan: str):
    """Desde cuándo cuenta lo que se acaba de pagar.

    Renovar antes de tiempo el mismo plan suma al final de lo que quedaba, no
    tira los días que faltaban. Cambiar de plan empieza hoy.
    """
    current = plan_until(account)
    if plan_of(account) == plan and current and current > now():
        return current
    return now()


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
