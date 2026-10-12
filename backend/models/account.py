"""The accounts collection: one document per client company."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from config import Config
from services import fields
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
#
# Esa mirada también se quitó (octubre de 2026): la hace la demostración, que es
# uno de los dos caminos que abren la cuenta (ver `is_open()`).
REGISTERED = "registered"   # se registró; hasta que se abre, solo su bienvenida
                            # y Configuración, y puede comprar
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
MEMBER = "member"
ROLES = (CLIENT, ADMIN, MEMBER)

# --------------------------------------------------- los usuarios de una cuenta
#
# Un usuario es **su propio documento de cuenta** con `owner_id` apuntando a la
# empresa. Así entra con su correo y su contraseña, tiene sus dispositivos y su
# propio segundo factor, y nada de eso hubo que escribirlo dos veces. Lo que ve
# y toca sigue siendo de la empresa: los datos cuelgan del dueño
# (`current_workspace()` en las rutas), y aquí solo se guarda quién es y qué
# puede.
#
# El dueño lo puede todo, siempre, y no lleva permisos escritos: lo que decide
# es no tener `owner_id`. Una cuenta de administrador de Sobreala no tiene
# ninguno de estos permisos, porque esas pantallas no son suyas.
STATS = "stats"          # Estadísticas
CAMPAIGNS = "campaigns"  # ver las campañas y el detalle de cada envío
SEND = "send"            # guardar, editar y mandar campañas
CONTACTS = "contacts"    # la lista, importar, etiquetas, columnas, supresiones
DESIGNS = "designs"      # crear, editar y borrar plantillas
PERMISSIONS = (STATS, CAMPAIGNS, SEND, CONTACTS, DESIGNS)

# Mandar es también mirar: quien puede enviar una campaña puede abrir la
# pantalla donde está el botón.
IMPLIES = {SEND: (CAMPAIGNS,)}

# Un usuario al que se le quitó la entrada sin borrarlo: lo suyo se queda, pero
# no abre sesión.
DISABLED = "disabled"


def normalize_email(email: str) -> str:
    """Same rule the contacts collection uses: no spaces, lowercase."""
    return "".join(email.split()).lower()


def now() -> datetime:
    return datetime.now(timezone.utc)


def create(db, *, company_name: str, contact_name: str, email: str,
           password: str, phone: str = "", company_phones: list[str] | None = None,
           postal_address: str = "") -> dict[str, Any] | None:
    """Insert a new account. Returns None if the address is already taken.

    The caller must not tell the visitor which of the two happened: both cases
    lead to the same screen, so the site does not reveal who has an account.

    Desde octubre de 2026 el registro trae también el teléfono personal, los de
    la empresa y la dirección, ya limpios. La identificación personal no se
    escribe: se sube como documento.
    """
    moment = now()
    doc = {
        "company_name": company_name.strip(),
        "contact_name": contact_name.strip(),
        "phone": phone.strip(),
        "company_phones": list(company_phones or []),
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
    if postal_address:
        doc["postal_address"] = postal_address
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


def start_email_change(db, account_id, email: str) -> None:
    """Anotar la dirección a la que se quiere mover la cuenta.

    Se guarda aparte y **no toca `email`**: hasta que no llegue el código que se
    mandó a esa dirección, la cuenta sigue entrando y recibiendo por la de
    siempre. Un cambio a medias dejaría a alguien sin ninguna de las dos.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "pending_email": email.strip(),
        "pending_email_at": now(),
        "updated_at": now(),
    }})


def pending_email(account: dict[str, Any] | None) -> str:
    return (account or {}).get("pending_email") or ""


def cancel_email_change(db, account_id) -> None:
    db.accounts.update_one({"_id": account_id}, {
        "$unset": {"pending_email": "", "pending_email_at": ""},
        "$set": {"updated_at": now()}})


def finish_email_change(db, account_id, email: str) -> bool:
    """Escribir por fin la dirección nueva. False si se la llevó otra cuenta.

    El índice único es quien responde, como en `change_email()`: entre pedir el
    código y escribirlo hay tiempo de sobra para que alguien se registre con esa
    misma dirección.

    No se toca `email_confirmed_at`: la dirección nueva acaba de probarse con un
    código, así que la cuenta sigue tan confirmada como estaba.
    """
    if not change_email(db, account_id, email):
        return False
    cancel_email_change(db, account_id)
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


# ------------------------------------------- las columnas propias del contacto

# Viven aquí, en la cuenta, y no deducidas de los contactos, por lo mismo que
# las etiquetas: una columna recién creada se puede usar desde ese momento
# aunque todavía no tenga un solo valor escrito.


def fields_of(account: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((account or {}).get("contact_fields") or [])


def field_limit(account: dict[str, Any] | None) -> int:
    """Cuántas columnas propias puede tener esta cuenta, según su plan."""
    return plans.field_limit(plan_of(account))


def field_by_key(account: dict[str, Any] | None, key: str):
    return next((one for one in fields_of(account) if one["key"] == key), None)


def add_field(db, account_id, *, label: str, kind: str) -> str | None:
    """Crear una columna. Devuelve su clave, o None si no se pudo.

    No se pudo quiere decir: sin nombre, un nombre que da la misma clave que
    otra, o que ya no caben más en el plan. El límite se mira aquí y no solo en
    la pantalla, porque un formulario se puede escribir a mano.
    """
    name = fields.clean_label(label)
    key = fields.key_from(name)
    if not name or not key:
        return None
    account = by_id(db, account_id)
    existing = fields_of(account)
    if len(existing) >= field_limit(account):
        return None
    if any(one["key"] == key for one in existing) or key in fields.BUILT_IN:
        # Una columna «Nombre» o «Correo» chocaría con los datos que ya trae
        # todo contacto.
        return None
    db.accounts.update_one(
        {"_id": account_id},
        {"$push": {"contact_fields": {"key": key, "label": name,
                                      "type": fields.clean_kind(kind)}},
         "$set": {"updated_at": now()}})
    return key


def set_field_type(db, account_id, key: str, kind: str) -> bool:
    """Cambiarle el tipo a una columna. False si esa columna no es de la cuenta.

    Lo único que se puede corregir de una columna ya creada. El nombre no: es lo
    que se escribe dentro de las piezas, y cambiarlo dejaría a las que la
    nombran escribiendo en blanco. Que los valores encajen en el tipo nuevo lo
    comprueba quien llama, antes de tocar nada.
    """
    return db.accounts.update_one(
        {"_id": account_id, "contact_fields.key": key},
        {"$set": {"contact_fields.$.type": fields.clean_kind(kind),
                  "updated_at": now()}}).matched_count == 1


def remove_field(db, account_id, key: str) -> None:
    """Sacar la columna del registro. Borrar lo que los contactos tenían
    escrito en ella es cosa de models/contact.py, y el que borra hace las
    dos."""
    db.accounts.update_one({"_id": account_id},
                           {"$pull": {"contact_fields": {"key": key}},
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


# ------------------------------------------------- los usuarios de una cuenta

def is_member(account: dict[str, Any] | None) -> bool:
    """Si esta cuenta es un usuario que alguien creó, y no una empresa."""
    return bool((account or {}).get("owner_id"))


def owner_id_of(account: dict[str, Any] | None) -> Any:
    """De quién son los datos que esta cuenta mira: de su dueño, o suyos."""
    one = account or {}
    return one.get("owner_id") or one.get("_id")


def owner_of(db, account: dict[str, Any] | None) -> dict[str, Any] | None:
    """La cuenta de la empresa: la del dueño si esto es un usuario, o la misma.

    Es lo que hace que un usuario vea los contactos, las plantillas y las
    campañas de su empresa sin que ninguna consulta cambie: todas siguen
    preguntando por un `account_id`, y aquí se decide cuál.
    """
    if account is None or not is_member(account):
        return account
    return by_id(db, account["owner_id"])


def clean_permissions(wanted) -> list[str]:
    """Los permisos que llegan de un formulario, dejados en los que existen.

    Mandar arrastra ver: quien puede enviar una campaña puede abrir la pantalla
    donde está el botón, y guardarlo al revés dejaría un usuario que manda pero
    no ve lo que mandó.
    """
    found = {one for one in (wanted or []) if one in PERMISSIONS}
    for name, implied in IMPLIES.items():
        if name in found:
            found.update(implied)
    return [one for one in PERMISSIONS if one in found]


def can(account: dict[str, Any] | None, permission: str) -> bool:
    """Si esta cuenta puede hacer eso.

    El dueño lo puede todo: su cuenta es la empresa. Un administrador de
    Sobreala, nada de esto: no tiene contactos a los que escribirle. Un usuario,
    lo que el dueño le marcó.
    """
    one = account or {}
    if not one or is_admin(one):
        return False
    if not is_member(one):
        return True
    if one.get("status") == DISABLED:
        return False
    return permission in (one.get("permissions") or [])


def members_of(db, owner_id) -> list[dict[str, Any]]:
    """Los usuarios de esa empresa, el más antiguo primero."""
    return list(db.accounts.find({"owner_id": owner_id}).sort("created_at", 1))


def member_of(db, owner_id, member_id) -> dict[str, Any] | None:
    """Uno de esa empresa. El dueño va en la consulta, así que el usuario de
    otra no encuentra nada."""
    return db.accounts.find_one({"_id": member_id, "owner_id": owner_id})


def add_member(db, owner, *, contact_name: str, email: str,
               permissions: list[str]) -> dict[str, Any] | None:
    """Crear un usuario de esa empresa, **sin contraseña**: la pone él con el
    enlace de la invitación. None si esa dirección ya tiene cuenta.

    No se copia el nombre de la empresa: sale del dueño, así que cambiarlo no
    deja usuarios con el nombre viejo.
    """
    moment = now()
    doc = {
        "owner_id": owner["_id"],
        "role": MEMBER,
        "contact_name": contact_name.strip(),
        "email": email.strip(),
        "email_normalized": normalize_email(email),
        "password_hash": "",
        "email_confirmed_at": None,
        "status": REGISTERED,
        "permissions": clean_permissions(permissions),
        "invited_by": owner["_id"],
        "invited_at": moment,
        "created_at": moment,
        "updated_at": moment,
        "last_login_at": None,
        "password_history": [],
    }
    try:
        result = db.accounts.insert_one(doc)
    except DuplicateKeyError:
        return None
    doc["_id"] = result.inserted_id
    return doc


def set_permissions(db, owner_id, member_id, permissions: list[str]) -> bool:
    """Cambiar lo que puede hacer un usuario. El dueño va en la consulta."""
    return db.accounts.update_one(
        {"_id": member_id, "owner_id": owner_id},
        {"$set": {"permissions": clean_permissions(permissions),
                  "updated_at": now()}}).matched_count == 1


def set_member_status(db, owner_id, member_id, *, disabled: bool) -> bool:
    """Quitarle o devolverle la entrada sin borrarlo.

    Quien vuelve queda como estaba: si ya había puesto su contraseña, activo; y
    si todavía no aceptó la invitación, esperando a aceptarla.
    """
    found = member_of(db, owner_id, member_id)
    if found is None:
        return False
    if disabled:
        status = DISABLED
    else:
        status = ACTIVE if found.get("password_hash") else REGISTERED
    db.accounts.update_one({"_id": member_id},
                           {"$set": {"status": status, "updated_at": now()}})
    return True


def remove_member(db, owner_id, member_id) -> bool:
    """Borrar un usuario. Lo que hizo se queda en `auth_events`, que no se
    borra: lo que pasó, pasó."""
    return db.accounts.delete_one({"_id": member_id,
                                   "owner_id": owner_id}).deleted_count == 1


def accept_invitation(db, member_id, password: str) -> None:
    """La contraseña que acaba de poner quien aceptó la invitación.

    El correo queda confirmado: el enlace llegó a esa dirección, que es
    exactamente lo que probaría un código.
    """
    moment = now()
    db.accounts.update_one(
        {"_id": member_id},
        {"$set": {"password_hash": hash_password(password),
                  "email_confirmed_at": moment, "status": ACTIVE,
                  "updated_at": moment},
         "$push": {"password_history": hash_password(password)}})


def seats_used(db, owner_id) -> int:
    """Cuántos sitios ocupa esta cuenta: el dueño y sus usuarios.

    Los invitados que todavía no aceptaron cuentan: si no, se podrían mandar
    veinte invitaciones y llenarse la cuenta al día siguiente.
    """
    return 1 + db.accounts.count_documents({"owner_id": owner_id})


def seats_left(db, owner: dict[str, Any] | None) -> int:
    """Cuántos usuarios más caben. Nunca negativo: un cambio de plan puede
    dejar a una cuenta con más de los que le tocan, y a nadie se le quita la
    entrada por eso."""
    if owner is None:
        return 0
    return max(0, plans.users(plan_of(owner)) - seats_used(db, owner["_id"]))


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


# ------------------------------------------------------------ abrir la cuenta

def is_open(account: dict[str, Any] | None) -> bool:
    """Si la empresa ya puede usar el panel: contactos, plantillas, campañas y
    Estadísticas.

    Una cuenta nueva nace cerrada. Cualquiera puede registrarse y las imágenes
    viven en la base, así que unas cuantas cuentas falsas la llenarían. Se abre
    por uno de dos caminos, y ninguno lo recorre un desconocido:

      * **La demostración**: la pide desde su bienvenida y el administrador la
        abre desde la ficha. `opened_by` dice quién.
      * **El pago**: `activate_plan()` la abre sola, sin `opened_by`. Una
        cuenta falsa no paga.

    `plan` y `sending_cleared_at` son de antes de que esto existiera: una cuenta
    que ya había pagado, o que ya se había habilitado para enviar, estaba
    revisada, y así no hubo nada que migrar.
    """
    found = account or {}
    return bool(found.get("opened_at") or found.get("plan")
                or found.get("sending_cleared_at"))


def open_account(db, account_id, admin_id=None) -> bool:
    """Abrir la cuenta. False si ya lo estaba.

    Escritura condicional sobre la ausencia del campo, así que pulsar dos veces
    no anota dos decisiones ni mueve la fecha de la primera. Sin `admin_id` es
    que la abrió un pago.
    """
    changes: dict[str, Any] = {"opened_at": now(), "updated_at": now()}
    if admin_id is not None:
        changes["opened_by"] = admin_id
    result = db.accounts.update_one(
        {"_id": account_id, "opened_at": {"$exists": False}}, {"$set": changes})
    return result.modified_count == 1


# Los teléfonos: el personal, que es al que se le escribe por la demostración,
# y los de la empresa. El número sin su prefijo mide de 4 a 14 dígitos, y con él
# no más de 15, que es lo más largo que mide un número internacional.
NATIONAL_DIGITS = (4, 14)
PHONE_DIGITS = 15
# Cuántos números de la empresa caben, además del personal.
COMPANY_PHONES_MAX = 3


def clean_phone(raw: str, country: str = "PA") -> str | None:
    """El número como se guarda, con su prefijo («+50760807972»), o None si no
    es un teléfono.

    `country` es el código ISO que se eligió en el selector; si el número ya
    viene con `+`, manda lo escrito. Se aceptan los separadores que la gente
    escribe (espacios, guiones, paréntesis y puntos). El 0 con que se marca
    dentro de muchos países no va en el número internacional, así que se quita
    (menos en Italia, donde sí va).
    """
    from services import countries

    text = (raw or "").strip()
    if not re.fullmatch(r"\+?[\d\s\-().]+", text):
        return None
    digits = re.sub(r"\D", "", text)
    if text.startswith("+"):
        full = digits
    else:
        dial = countries.dial_of(country)
        if dial is None:
            return None
        if country.upper() != "IT":
            digits = digits.lstrip("0")
        if not NATIONAL_DIGITS[0] <= len(digits) <= NATIONAL_DIGITS[1]:
            return None
        full = dial + digits
    if not 7 <= len(full) <= PHONE_DIGITS:
        return None
    return "+" + full


def clean_phones(numbers: list[str], countries_chosen: list[str]) -> tuple[list[str], bool]:
    """Los números de la empresa: los que se escribieron, limpios, hasta tres.

    Un campo vacío no cuenta. Devuelve la lista y si alguno estaba mal escrito,
    para que la pantalla lo diga en lugar de perderlo en silencio.
    """
    kept: list[str] = []
    bad = False
    for number, country in zip(numbers, countries_chosen):
        if not (number or "").strip():
            continue
        clean = clean_phone(number, country)
        if clean is None:
            bad = True
        elif clean not in kept:
            kept.append(clean)
    return kept[:COMPANY_PHONES_MAX], bad


def set_phones(db, account_id, *, phone: str, company_phones: list[str]) -> None:
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "phone": phone, "company_phones": company_phones, "updated_at": now()}})


def whatsapp_url(phone: str | None) -> str:
    """El enlace que abre un chat de WhatsApp con ese número, o vacío.

    WhatsApp lo quiere con su código de país y sin `+`. Uno de 8 dígitos sin
    código se lee como panameño, que es de donde son casi todos.
    """
    text = (phone or "").strip()
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if len(digits) == 8 and not text.startswith("+"):
        digits = "507" + digits
    return f"https://wa.me/{digits}"


# La identificación personal ya no se escribe (octubre de 2026): se sube como
# documento y la comprueba una persona (ver «Las verificaciones», más abajo). El
# `tax_id` de las cuentas de antes se conserva, y la ficha lo enseña si existe.
def tax_id_of(account: dict[str, Any] | None) -> str:
    return str((account or {}).get("tax_id") or "")


# Las dos respuestas de la demostración: a qué se dedica y para qué la usará.
DEMO_ANSWER = (10, 500)


def clean_answer(raw: str) -> str | None:
    """Una respuesta de la demostración, sin espacios de sobra, o None si es
    muy corta o muy larga. Los saltos de línea se respetan."""
    text = "\n".join(" ".join(line.split()) for line in str(raw or "").splitlines())
    text = text.strip()
    if not DEMO_ANSWER[0] <= len(text) <= DEMO_ANSWER[1]:
        return None
    return text


def request_demo(db, account_id, *, business: str, purpose: str) -> None:
    """Dejar pedida la demostración, con a qué se dedica el negocio y para qué
    usará Sobreala.

    Se le escribe al teléfono personal del registro: hasta octubre de 2026 se
    pedía aquí un WhatsApp, que era el mismo número. Pedirla otra vez corrige
    las respuestas y mueve la fecha.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "demo_business": business, "demo_purpose": purpose,
        "demo_requested_at": now(), "updated_at": now()}})


# La dirección postal de la empresa, que va al pie de sus campañas.
POSTAL_MIN = 10
POSTAL_MAX = 200


def postal_of(account: dict[str, Any] | None) -> str:
    """La dirección física de la empresa, o vacío si todavía no la escribió.

    La ley CAN-SPAM la pide en todo correo publicitario, y es la de quien
    anuncia: la de cada cliente, no la de Sobreala.
    """
    return str((account or {}).get("postal_address") or "")


def clean_postal(raw: str) -> str | None:
    """La dirección en una línea, o None si no es una dirección que se pueda
    guardar: vacía, muy corta o de más de 200 caracteres."""
    text = " ".join(str(raw or "").split())
    if not POSTAL_MIN <= len(text) <= POSTAL_MAX:
        return None
    return text


def set_postal(db, account_id, address: str) -> None:
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"postal_address": address, "updated_at": now()}})


# --------------------------------------------------------- las verificaciones
#
# Dos cosas que una persona de Sobreala comprueba a mano: la identificación
# personal y la dirección. El cliente sube un documento de cada una (la foto de
# su cédula o pasaporte; un recibo, su aviso de operación o un documento legal
# que certifique la dirección si la empresa no está constituida) y el
# administrador lo mira en la ficha y la da por verificada o la rechaza. El
# archivo vive en `verification_docs` y se borra al decidir: queda solo el
# resultado.
#
# Lo que no está escrito es `missing`. Cambiar el dato después de verificado
# vuelve a `missing`: lo que se miró era el de antes.

IDENTITY = "identity"
ADDRESS = "address"
VERIFY_KINDS = (IDENTITY, ADDRESS)

MISSING = "missing"      # falta el documento
REVIEW = "review"        # subió el documento y espera
VERIFIED = "verified"
REJECTED = "rejected"    # se rechazó, con su motivo; sube otro


def verification_of(account: dict[str, Any] | None, kind: str) -> dict[str, Any]:
    """El estado de una verificación, con su fecha, quién la decidió y el
    motivo si se rechazó. Lo que no está escrito es `missing`."""
    found = ((account or {}).get("verifications") or {}).get(kind) or {}
    return {"status": MISSING, **found}


def all_verified(account: dict[str, Any] | None) -> bool:
    return all(verification_of(account, kind)["status"] == VERIFIED
               for kind in VERIFY_KINDS)


def set_verification(db, account_id, kind: str, status: str, *, by=None,
                     reason: str = "") -> None:
    if kind not in VERIFY_KINDS:
        return
    value: dict[str, Any] = {"status": status, "at": now()}
    if by is not None:
        value["by"] = by
    if reason:
        value["reason"] = reason.strip()[:300]
    db.accounts.update_one({"_id": account_id}, {"$set": {
        f"verifications.{kind}": value, "updated_at": now()}})


def forget_verification(db, account_id, kind: str) -> None:
    """Volver a `missing` porque el dato cambió: lo verificado era el de antes."""
    db.accounts.update_one({"_id": account_id}, {"$unset": {
        f"verifications.{kind}": ""}, "$set": {"updated_at": now()}})


# --------------------------------------------------------------- el límite
#
# Limitar una cuenta no es suspenderla. Una cuenta limitada entra, prepara todo y
# puede pagar; lo único que no puede es enviar (`sender.blocked()` dice
# `limited`). Lo decide el administrador desde la ficha, con un motivo de esta
# lista y una nota, y queda en `admin_events`.

LIMIT_VERIFICATION = "verification"   # falta verificar la identidad y la dirección
LIMIT_REASONS = (LIMIT_VERIFICATION,)


def limited_of(account: dict[str, Any] | None) -> dict[str, Any] | None:
    """El límite de la cuenta (`reason`, `at`, `by`, `note`), o None."""
    return (account or {}).get("limited") or None


def limit(db, account_id, *, reason: str, admin_id, note: str = "") -> bool:
    """Limitar la cuenta. False si el motivo no es de la lista."""
    if reason not in LIMIT_REASONS:
        return False
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "limited": {"reason": reason, "at": now(), "by": admin_id,
                    "note": note.strip()[:300]},
        "updated_at": now()}})
    return True


def unlimit(db, account_id) -> bool:
    """Quitar el límite. False si no estaba limitada."""
    result = db.accounts.update_one(
        {"_id": account_id, "limited": {"$exists": True}},
        {"$unset": {"limited": ""}, "$set": {"updated_at": now()}})
    return result.modified_count == 1


# --------------------------------------------------------------- remitente
#
# De quién sale una campaña. Sin dominio propio, de `handle@SENDING_DOMAIN`;
# con uno verificado, de cualquier dirección de ese dominio. Nunca de la
# dirección del correo del sistema: ver services/sender.py.

HANDLE_MIN = 3
HANDLE_MAX = 30
# Los que suenan a la plataforma o a un buzón de servicio. Nadie puede firmar
# una campaña como «soporte@envios.sobreala.com».
RESERVED_HANDLES = frozenset({
    "info", "notifications", "notificaciones", "admin", "administrador",
    "postmaster", "abuse", "noreply", "no-reply", "soporte", "support",
    "sobreala", "envios", "hola", "contacto", "seguridad", "security",
    "billing", "facturacion", "mailer-daemon", "root", "webmaster",
})
# Dominios de correo gratis: nadie puede ponerles registros DNS, y enviar como
# ellos lo rechaza su propio DMARC.
FREE_MAIL = frozenset({
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.es", "outlook.com",
    "outlook.es", "live.com", "msn.com", "yahoo.com", "yahoo.es", "ymail.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com",
    "gmx.com", "zoho.com", "mail.com", "yandex.com",
})
SENDER_FIELDS = ("handle", "reply_to", "domain", "domain_local")
DOMAIN_PENDING = "pending"
DOMAIN_VERIFIED = "verified"
DOMAIN_FAILED = "failed"


def sender_of(account: dict[str, Any] | None) -> dict[str, Any]:
    """El remitente guardado, o vacío."""
    return dict((account or {}).get("sender") or {})


def clean_handle(raw: str) -> str | None:
    """El usuario de envío, o None si no se puede usar.

    Minúsculas, números, punto y guion; ni empieza ni termina en punto o
    guion, ni lleva dos puntos seguidos, que es lo que un servidor de correo
    rechaza en la parte de antes de la @."""
    text = str(raw or "").strip().lower()
    if not HANDLE_MIN <= len(text) <= HANDLE_MAX:
        return None
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", text) or ".." in text:
        return None
    if text in RESERVED_HANDLES:
        return None
    return text


def clean_local(raw: str) -> str | None:
    """Lo de antes de la @ en el dominio del cliente. Su dominio es suyo, así
    que aquí no hay reservados: solo la forma."""
    text = str(raw or "").strip().lower()
    if not 1 <= len(text) <= 64:
        return None
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9._+-]*[a-z0-9])?", text) or ".." in text:
        return None
    return text


def clean_domain(raw: str) -> str | None:
    """El dominio que escribió el cliente, limpio, o None.

    Acepta que lo peguen con `https://`, con `www.` o con una ruta detrás,
    porque así es como lo copia la gente de su navegador."""
    text = str(raw or "").strip().lower()
    text = re.sub(r"^[a-z]+://", "", text).split("/")[0].split("@")[-1]
    if text.startswith("www."):
        text = text[4:]
    text = text.rstrip(".")
    labels = text.split(".")
    if len(text) > 253 or len(labels) < 2 or not re.fullmatch(r"[a-z]{2,63}", labels[-1]):
        return None
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", one)
               for one in labels):
        return None
    # Nuestro dominio y todo lo que cuelga de él no es de ningún cliente.
    ours = Config.SENDING_DOMAIN.split(".", 1)[-1]
    if text in FREE_MAIL or text == ours or text.endswith("." + ours):
        return None
    return text


def suggest_handle(db, company_name: str) -> str:
    """El usuario que se le ofrece al entrar: el nombre de la empresa sin
    espacios ni tildes, y con un número si otra cuenta ya lo tiene."""
    plain = unicodedata.normalize("NFKD", str(company_name or "")).encode(
        "ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "", plain)[:HANDLE_MAX - 2]
    if len(base) < HANDLE_MIN or base in RESERVED_HANDLES:
        base = (base + "envios")[:HANDLE_MAX - 2]
    wanted = base
    for n in range(2, 100):
        if not db.accounts.find_one({"sender.handle": wanted}, {"_id": 1}):
            return wanted
        wanted = f"{base}{n}"
    return wanted


def set_handle(db, account_id, handle: str) -> bool:
    """Guardar el usuario. False si otra cuenta lo tiene: lo decide el índice
    único, así que dos que lo piden a la vez no se lo llevan los dos."""
    try:
        db.accounts.update_one({"_id": account_id},
                               {"$set": {"sender.handle": handle, "updated_at": now()}})
    except DuplicateKeyError:
        return False
    return True


def set_reply_to(db, account_id, address: str) -> None:
    """El «Responder a», ya probado. Borra lo que estuviera esperando código."""
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"sender.reply_to": address, "updated_at": now()},
                            "$unset": {"sender.reply_to_pending": ""}})


def start_reply_to(db, account_id, address: str) -> None:
    """La dirección nueva espera su código aparte: la de antes sigue valiendo."""
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"sender.reply_to_pending": address,
                                     "updated_at": now()}})


def clear_reply_to(db, account_id) -> None:
    """Volver a que las respuestas lleguen al correo del dueño."""
    db.accounts.update_one({"_id": account_id},
                           {"$unset": {"sender.reply_to": ""}})


def set_domain(db, account_id, domain: str, tokens: list[str]) -> bool:
    """Empezar a conectar un dominio. False si otra cuenta ya lo tiene."""
    try:
        db.accounts.update_one({"_id": account_id}, {"$set": {
            "sender.domain": domain, "sender.domain_status": DOMAIN_PENDING,
            "sender.dkim_tokens": list(tokens), "sender.domain_checked_at": now(),
            "updated_at": now()}, "$unset": {"sender.domain_local": "",
                                             "sender.domain_verified_at": ""}})
    except DuplicateKeyError:
        return False
    return True


def set_domain_status(db, account_id, status: str) -> None:
    changes: dict[str, Any] = {"sender.domain_status": status,
                               "sender.domain_checked_at": now()}
    if status == DOMAIN_VERIFIED:
        changes["sender.domain_verified_at"] = now()
    db.accounts.update_one({"_id": account_id, "sender.domain": {"$exists": True}},
                           {"$set": changes})


def set_domain_local(db, account_id, local: str) -> None:
    db.accounts.update_one({"_id": account_id},
                           {"$set": {"sender.domain_local": local, "updated_at": now()}})


def clear_domain(db, account_id) -> None:
    db.accounts.update_one({"_id": account_id}, {"$unset": {
        "sender.domain": "", "sender.domain_status": "", "sender.dkim_tokens": "",
        "sender.domain_local": "", "sender.domain_checked_at": "",
        "sender.domain_verified_at": ""}})


def domain_ready(account: dict[str, Any] | None) -> bool:
    """Si las campañas ya pueden salir de su dominio: verificado y con la
    dirección elegida."""
    mine = sender_of(account)
    return bool(mine.get("domain") and mine.get("domain_local")
                and mine.get("domain_status") == DOMAIN_VERIFIED)


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


def activate_plan(db, account_id, plan: str, until, cycle: str | None = None,
                  fresh_month: bool = False) -> None:
    """Dejar la cuenta pagada: su plan, activa, hasta cuándo y en qué ciclo.

    Es el único sitio que escribe `active`: estar activa es el efecto de un
    pago cobrado, no una decisión que alguien tome a mano.

    `fresh_month` es para una mejora: el mes empieza de nuevo, así que lo que
    ya se envió este mes deja de contar contra la cuota nueva. Se guarda cuánto
    iba (`quota_base`) y `used_this_month()` lo resta.

    Y abre la cuenta, si no lo estaba: pagar es uno de los dos caminos, y quien
    paga entra con todo de una vez, sin esperar a nadie.
    """
    changes: dict[str, Any] = {"plan": plan, "status": ACTIVE, "plan_until": until,
                               "updated_at": now()}
    if cycle:
        changes["plan_cycle"] = cycle
    if fresh_month:
        found = by_id(db, account_id)
        changes["quota_base"] = {"month": quota_month(),
                                 "sent": sent_this_month(found)}
    db.accounts.update_one({"_id": account_id}, {"$set": changes})
    open_account(db, account_id)


def plan_until(account: dict[str, Any] | None):
    return (account or {}).get("plan_until")


def plan_cycle(account: dict[str, Any] | None) -> str:
    """En qué ciclo se pagó el plan: «monthly» o «yearly». Lo de antes de que
    se anotara se lee como mensual, que era lo que casi todos pagaban."""
    cycle = (account or {}).get("plan_cycle")
    return cycle if cycle in ("monthly", "yearly") else "monthly"


def current_plan(account: dict[str, Any] | None) -> str | None:
    """El plan mientras está vigente: con su fecha pasada ya no cuenta, y se
    puede volver a contratar. Sin fecha cuenta como vigente, como siempre."""
    plan = plan_of(account)
    until = plan_until(account)
    if plan and until is not None and until <= now():
        return None
    return plan


def mark_plan_notice(db, account_id, which: str, until) -> None:
    """Dejar escrito **para qué vencimiento** se avisó ya.

    Se guarda la fecha y no un simple sí, y eso es lo que hace que renovar
    devuelva el aviso para el ciclo siguiente: al cambiar `plan_until`, la marca
    deja de coincidir sola. Un booleano habría que acordarse de limpiarlo, y
    olvidarlo significa no volver a avisar nunca.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        f"plan_notices.{which}": until, "updated_at": now(),
    }})


def renews_from(account: dict[str, Any] | None, plan: str):
    """Desde cuándo cuenta lo que se acaba de pagar.

    Renovar antes de tiempo el mismo plan suma al final de lo que quedaba, no
    tira los días que faltaban. Cambiar de plan empieza hoy.
    """
    current = plan_until(account)
    if plan_of(account) == plan and current and current > now():
        return current
    return now()


# ------------------------------------------------- la renovación automática
#
# Una suscripción de PayPal por cuenta (octubre de 2026): el cliente la aprueba
# una vez y PayPal cobra cada periodo. Se guarda en `subscription`:
# `id` (el de PayPal), `status`, `plan`, `cycle`, `created_at` y, si ya se supo,
# `next` (cuándo cobra la próxima). De PayPal no se guarda nada más que ese
# identificador: ni tarjeta ni cuenta (regla 9).

SUB_PENDING = "approval_pending"   # creada, el cliente todavía no la aprobó
SUB_ACTIVE = "active"
SUB_SUSPENDED = "suspended"        # PayPal la suspendió (cobros fallidos)
SUB_CANCELLED = "cancelled"        # la canceló el cliente, PayPal o nosotros


def subscription_of(account: dict[str, Any] | None) -> dict[str, Any] | None:
    return (account or {}).get("subscription") or None


def renewal_on(account: dict[str, Any] | None) -> bool:
    """Si la renovación automática está encendida: aprobada y sin cancelar."""
    one = subscription_of(account)
    return bool(one and one.get("status") == SUB_ACTIVE)


def set_subscription(db, account_id, **fields: Any) -> None:
    """Escribir lo que cambie de la suscripción, sin tocar el resto."""
    db.accounts.update_one({"_id": account_id}, {"$set": {
        **{f"subscription.{key}": value for key, value in fields.items()},
        "updated_at": now()}})


def start_subscription(db, account_id, *, sub_id: str, plan: str, cycle: str) -> None:
    """Dejar anotada una suscripción nueva, pendiente de que el cliente la apruebe."""
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "subscription": {"id": sub_id, "status": SUB_PENDING, "plan": plan,
                         "cycle": cycle, "created_at": now()},
        "updated_at": now()}})


def by_subscription(db, sub_id: str) -> dict[str, Any] | None:
    """La cuenta dueña de esa suscripción de PayPal."""
    if not sub_id:
        return None
    return db.accounts.find_one({"subscription.id": sub_id})


def by_status(db) -> dict[str, int]:
    """How many accounts sit in each state, for the admin front page."""
    counted = {name: 0 for name in STATUSES}
    for row in db.accounts.aggregate([
            {"$match": {"owner_id": {"$exists": False}}},
            {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        if row["_id"] in counted:
            counted[row["_id"]] = row["n"]
    return counted


def search(db, *, status: str = "", text: str = "", demo: bool = False,
           review: bool = False, limit: int = 100,
           skip: int = 0) -> tuple[list[dict[str, Any]], int]:
    """The admin table: filter by state, search by address or company.

    Nunca trae cuentas de administrador: no son clientes, no compran ni envían,
    y no hay nada que decidir sobre ellas. Salían en la lista y, como un
    administrador no paga nunca, se quedaban en «registrada» para siempre, que
    es lo que hacía que la columna de estado se leyera mal.

    **Ni los usuarios que una empresa creó**, por lo mismo: el cliente es la
    empresa, y su ficha ya dice quiénes entran a ella.

    `demo` es la cola que pide acción: pidieron la demostración y su cuenta
    sigue cerrada. Las mismas condiciones que `is_open()`, dichas al revés.
    """
    import re

    query: dict[str, Any] = {"role": {"$ne": ADMIN}, "owner_id": {"$exists": False}}
    if status in STATUSES:
        query["status"] = status
    if demo:
        query["demo_requested_at"] = {"$exists": True}
        query["opened_at"] = {"$exists": False}
        # None encuentra también a las que no tienen el campo.
        query["plan"] = None
        query["sending_cleared_at"] = {"$exists": False}
    clauses: list[dict[str, Any]] = []
    if review:
        # «Por verificar»: un documento subido que espera que alguien lo mire.
        clauses.append({"$or": [{f"verifications.{kind}.status": REVIEW}
                                for kind in VERIFY_KINDS]})
    if text:
        safe = re.escape(text.strip())
        clauses.append({"$or": [
            {"email_normalized": {"$regex": f"^{re.escape(normalize_email(text))}"}},
            {"company_name": {"$regex": safe, "$options": "i"}},
        ]})
    if clauses:
        query["$and"] = clauses
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
# Aparte de BILLING a propósito. Aquel es papeleo —el comprobante de lo que se
# cobró—; este es lo que explica por qué algo dejó de funcionar, que es otra
# cosa y se quiere apagar por otras razones.
PLAN_STATE = "plan_state"
IMPORTS = "imports"
CAMPAIGNS = "campaigns"
MONTHLY = "monthly"
NOTICES = (NEW_LOGIN, BILLING, PLAN_STATE, IMPORTS, CAMPAIGNS, MONTHLY)
# Los de partes que todavía no mandan nada. No se ofrecen: un interruptor de algo
# que no existe es dejar las cosas a medias. Y como sin interruptor `wants()` los
# da por sí, el día que empiecen a salir llegan sin que nadie encienda nada; ese
# día basta con sacarlos de aquí para que la pantalla los ofrezca.
PENDING = (IMPORTS, CAMPAIGNS, MONTHLY)

# Los de una cuenta de administrador, que son otros y por eso son otra tupla:
# no hablan de su cuenta sino de lo que pasa en las de los clientes. Una cuenta
# es cliente o administradora, así que nunca se mezclan en el mismo documento.
ADMIN_PAYMENT = "admin_payment"
ADMIN_SIGNUP = "admin_signup"
ADMIN_DEMO = "admin_demo"
ADMIN_PLAN_END = "admin_plan_end"
ADMIN_NOTICES = (ADMIN_PAYMENT, ADMIN_SIGNUP, ADMIN_DEMO, ADMIN_PLAN_END)

# Los dos avisos del estado del plan, que se mandan una sola vez cada uno.
EXPIRING = "expiring"
EXPIRED = "expired"


def wants(account: dict[str, Any] | None, notice: str) -> bool:
    """Whether this account still wants that message.

    Anything not written counts as yes: an account that never opened the screen
    —every account there is today— keeps getting everything, which is the safe
    way round for a preference nobody has expressed.
    """
    return (account or {}).get("notifications", {}).get(notice, True) is not False


def notices_for(account: dict[str, Any] | None) -> tuple[str, ...]:
    """Los avisos que esa cuenta puede elegir.

    Los de un administrador son de lo que hacen los clientes —quién pagó, quién
    se registró, a quién se le venció el plan—; los de un cliente son de su
    propia cuenta. Enseñarle a cada uno los del otro sería ofrecer interruptores
    de correos que no va a recibir nunca.
    """
    if is_admin(account):
        return ADMIN_NOTICES
    return tuple(name for name in NOTICES if name not in PENDING)


def set_notifications(db, account_id, wanted: dict[str, bool], *,
                      names: tuple[str, ...] = NOTICES) -> None:
    """Write the whole set from what the form said.

    Only the names this module knows are written. A form field for anything
    else —a security notice, say— is dropped here rather than stored, so no
    request can invent a preference that turns one of them off.
    """
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "notifications": {name: bool(wanted.get(name)) for name in names},
        "updated_at": now(),
    }})


# Contactos que caben en cada plan, copiados de docs/pricing.md, que es la
# fuente de verdad. El límite de correos es siempre 5x el de contactos, y se
# calculará desde aquí cuando haya envíos que contar.
PLAN_CONTACTS = {
    "basico": 1000,
    "negocio": 3000,
    "empresa": 10000,
}


def contact_limit(account: dict[str, Any] | None) -> int:
    """Cuántos contactos puede tener esta cuenta.

    Sin plan, los del plan más barato, como las etiquetas, las columnas y las
    imágenes: una cuenta que se abrió con la demostración tiene lo del Básico,
    y lo único que le falta es enviar.
    """
    cheapest = PLAN_CONTACTS.get(next(iter(plans.PLANS), ""), 0)
    return PLAN_CONTACTS.get(plan_of(account) or "", cheapest)


# --------------------------------------------------------- la cuota del mes

def quota_month(when: datetime | None = None) -> str:
    """La clave del mes, «2026-09».

    Un contador por mes y no uno solo que haya que poner a cero: el mes que
    viene empieza en cero porque es otra clave, sin que nadie tenga que pasar a
    barrer. Y lo del mes pasado queda ahí, que es lo que hace falta para
    responder cuánto envió alguien en marzo.
    """
    moment = when or now()
    return f"{moment.year:04d}-{moment.month:02d}"


def sent_this_month(account: dict[str, Any] | None,
                    when: datetime | None = None) -> int:
    counts = (account or {}).get("sent_counts") or {}
    return int(counts.get(quota_month(when), 0))


def used_this_month(account: dict[str, Any] | None,
                    when: datetime | None = None) -> int:
    """Los correos de este mes que cuentan contra la cuota: los enviados, menos
    los que iban cuando se mejoró de plan si fue este mismo mes."""
    sent = sent_this_month(account, when)
    base = (account or {}).get("quota_base") or {}
    if base.get("month") == quota_month(when):
        sent -= int(base.get("sent", 0))
    return max(0, sent)


def quota_left(account: dict[str, Any] | None,
               when: datetime | None = None) -> int:
    """Cuántos correos puede mandar todavía este mes.

    **Cero sin plan contratado**, que no es lo mismo que «no se sabe»: sin plan
    no hay correos incluidos, así que no sale ninguno. El número de cada plan
    sale de docs/pricing.md, como todo lo demás.
    """
    allowed = plans.emails_a_month(plan_of(account))
    if not allowed:
        return 0
    return max(0, allowed - used_this_month(account, when))


def add_sent(db, account_id, many: int, when: datetime | None = None) -> None:
    """Anotar los que acaban de salir. Se llama una vez por tanda, no por correo."""
    if many <= 0:
        return
    db.accounts.update_one(
        {"_id": account_id},
        {"$inc": {f"sent_counts.{quota_month(when)}": many},
         "$set": {"updated_at": now()}})


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
