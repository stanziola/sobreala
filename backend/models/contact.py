"""The contacts collection: one document per address, per account.

Two rules from CLAUDE.md shape everything here.

  * **Nobody is duplicated.** The unique index on {account_id,
    email_normalized} is what enforces it, and every write is an upsert against
    that pair, so importing the same file twice changes nothing.
  * **Lists are tags on the document**, not collections of their own. A contact
    in three lists is still one document: it counts once against the limit,
    receives one email, and spends one unit of quota.

Whether an address is suppressed is NOT stored here. It lives in its own
collection and is asked in bulk, so the two can never drift apart: a contact
that was deleted and imported again comes back suppressed, because the
suppression never went anywhere.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo import UpdateMany, UpdateOne
from pymongo.errors import DuplicateKeyError

from models.account import normalize_email
from services import fields

# Where a list came from. Asked at import time and written on every contact,
# because it is what has to be shown when somebody complains, and it cannot be
# filled in afterwards: a list uploaded without it has no origin, ever.
OWN_FORM = "own_form"
MEMBERS = "members"
CUSTOMERS = "customers"
EVENT = "event"
OTHER = "other"
SOURCES = (OWN_FORM, MEMBERS, CUSTOMERS, EVENT, OTHER)

# How many go in one bulkWrite. Big enough that a thousand rows is one round
# trip or two, small enough that a document never grows past Mongo's limit.
BATCH = 500


def now() -> datetime:
    return datetime.now(timezone.utc)


def consent_of(source: str, note: str = "") -> dict[str, Any]:
    """The origin record that goes on every contact of an import."""
    return {
        "source": source if source in SOURCES else OTHER,
        "note": note.strip()[:300],
        "recorded_at": now(),
    }


def added_between(db, account_id, start, end=None) -> int:
    """Cuántos contactos entraron en ese tramo, para el crecimiento de la lista.

    Usa el índice `{account_id, created_at}` que ya existe. Lo que **no** se
    puede contar es lo borrado a mano, que no deja rastro: por eso la pantalla
    enseña altas y bajas y no el total de cada mes.
    """
    when: dict[str, Any] = {"$gte": start}
    if end is not None:
        when["$lt"] = end
    return db.contacts.count_documents({"account_id": account_id,
                                        "created_at": when})


def count(db, account_id) -> int:
    """Todos los que hay, anulados incluidos. Es lo que enseña la pantalla."""
    return db.contacts.count_documents({"account_id": account_id})


def active_count(db, account_id) -> int:
    """Los que sí pueden recibir algo. Es el número que va contra el límite.

    Un anulado no puede recibir nada, así que cobrar capacidad de plan por él
    sería cobrar por peso muerto: es la misma lógica que la regla 1, donde un
    suprimido tampoco consume cuota al enviar. Se sigue guardando, eso sí,
    porque la regla 2 dice que borrarlo lo resucitaría en la próxima
    importación.

    Una consulta que cruza las dos colecciones, no una por contacto.
    """
    found = list(db.contacts.aggregate(
        [{"$match": {"account_id": account_id}}] + _drop_suppressed() +
        [{"$count": "n"}]))
    return found[0]["n"] if found else 0


def delete_suppressed(db, account_id) -> int:
    """Borrar los contactos anulados. Sus supresiones se quedan donde están.

    La confusión natural es creer que esto levanta la baja: no. La dirección
    sigue sin poder recibir nada, y si vuelve a entrar en una importación
    volverá a entrar marcada. Eso es la regla 2.
    """
    blocked = [d["email_normalized"] for d in
               db.suppressions.find({"account_id": account_id},
                                    {"email_normalized": 1})]
    if not blocked:
        return 0
    result = db.contacts.delete_many({"account_id": account_id,
                                      "email_normalized": {"$in": blocked}})
    return result.deleted_count


# ------------------------------------------------------ direcciones inválidas
#
# Las de un dominio que no recibe correo (`services/address_check.py`, octubre
# de 2026). Entran marcadas con `invalid` y se ven en la lista, pero al enviar
# se saltan como un suprimido: un rebote seguro no gasta cuota. Se borran de una
# vez desde Contactos.

INVALID_DOMAIN = "domain"


def mark_invalid(db, account_id, emails_normalized: list[str], *,
                 reason: str = INVALID_DOMAIN) -> int:
    """Marcar esas direcciones de la cuenta. Devuelve cuántas son. Una sola
    escritura en lote, como toda escritura de contactos (regla 10)."""
    if not emails_normalized:
        return 0
    result = db.contacts.bulk_write([UpdateMany(
        {"account_id": account_id, "email_normalized": {"$in": emails_normalized}},
        {"$set": {"invalid": {"reason": reason, "at": now()}}})])
    return result.matched_count


def invalid_count(db, account_id) -> int:
    return db.contacts.count_documents({"account_id": account_id,
                                        "invalid": {"$exists": True}})


def delete_invalid(db, account_id) -> int:
    """Borrar los contactos con una dirección inválida. No toca supresiones."""
    return db.contacts.delete_many({"account_id": account_id,
                                    "invalid": {"$exists": True}}).deleted_count


def _complete(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las condiciones que cumple un contacto con todas sus columnas llenas.

    Una por columna: el campo existe y no está vacío. Con diez columnas son
    diez condiciones sobre el mismo documento, no diez consultas. Las listas
    (octubre de 2026) pueden ir vacías y no cuentan.
    """
    return [{f"fields.{one['key']}": {"$exists": True, "$nin": ["", None]}}
            for one in fields.scalars(definitions)]


def _matching(account_id, search: str, tag: str,
              tags: list[str] | None = None,
              complete: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """La consulta de la tabla, en un solo sitio.

    La usan la exportación y el conteo que la confirma, para que el número que
    se enseña antes de descargar sea el del archivo y no una cuenta aparte que
    un día se desincroniza.

    `tag` es una sola, que es como filtra la pantalla de contactos. `tags` son
    varias, que es como sale una campaña: **quien lleve cualquiera de ellas**.
    Nadie sale dos veces porque un contacto es un solo documento con sus
    etiquetas dentro, así que llevar tres de las marcadas no lo duplica.
    """
    query: dict[str, Any] = {"account_id": account_id}
    wanted = [one for one in (tags or []) if one] or ([tag] if tag else [])
    if len(wanted) == 1:
        query["tags"] = wanted[0]
    elif wanted:
        query["tags"] = {"$in": wanted}
    if search:
        query["email_normalized"] = {"$regex": f"^{_escape(normalize_email(search))}"}
    # Solo lo encienden los caminos de envío: la lista sí los enseña, porque
    # para completarlos hay que verlos.
    conditions = _complete(complete or [])
    if conditions:
        query["$and"] = conditions
    return query


def matching_count(db, account_id, *, search: str = "", tag: str = "",
                   tags: list[str] | None = None,
                   complete: list[dict[str, Any]] | None = None) -> int:
    """Cuántos saldrían con ese buscador y ese filtro."""
    return db.contacts.count_documents(
        _matching(account_id, search, tag, tags, complete))


def batch_for_sending(db, account_id, *, tag: str = "",
                      tags: list[str] | None = None,
                      complete: list[dict[str, Any]] | None = None,
                      skip: int = 0,
                      limit: int = 100) -> list[dict[str, Any]]:
    """Un tramo de la lista, en orden fijo, para mandarle una campaña.

    Por `_id` y no por fecha, que es como ordena la pantalla: es el único orden
    que no se mueve si alguien importa contactos mientras la campaña va por la
    mitad, y de eso depende que la posición guardada signifique lo mismo en la
    tanda siguiente.
    """
    return list(db.contacts.find(_matching(account_id, "", tag, tags, complete))
                .sort("_id", 1).skip(skip).limit(limit))


def all_of(db, account_id, *, search: str = "", tag: str = ""):
    """Todos los que coinciden, uno a uno, para exportarlos.

    Un cursor y no una lista: el archivo se escribe fila por fila, por la misma
    razón por la que el importador lee así.
    """
    return db.contacts.find(_matching(account_id, search, tag)).sort("created_at", -1)


# Cómo entró un contacto. Los que existían antes de que este campo existiera no
# lo tienen, y la pantalla enseña una raya: no se puede saber hacia atrás por
# dónde entró cada uno, y una raya es mejor que inventarlo.
MANUAL = "manual"
IMPORT = "import"
# Cargado por la API pública (octubre de 2026).
API = "api"


def tags_in_use(db, account_id) -> list[str]:
    """Las etiquetas que de verdad lleva puestas algún contacto.

    No es la lista que se enseña —esa es el registro de la cuenta, que incluye
    las recién creadas y todavía vacías— sino la que hace falta para rellenar
    ese registro la primera vez.
    """
    return sorted(db.contacts.distinct("tags", {"account_id": account_id}))


def incomplete_count(db, account_id,
                     definitions: list[dict[str, Any]]) -> int:
    """Cuántos no tienen todas sus columnas llenas.

    Son los que no van a recibir nada, así que la pantalla lo dice: crear una
    columna nueva deja incompleta a toda la lista hasta que se complete.
    """
    conditions = _complete(definitions)
    if not conditions:
        return 0
    return db.contacts.count_documents(
        {"account_id": account_id, "$nor": [{"$and": conditions}]})


def count_by_field(db, account_id,
                   definitions: list[dict[str, Any]]) -> dict[str, int]:
    """Cuántos contactos tienen llena cada columna.

    Una consulta por columna, no por contacto: con diez columnas son diez
    conteos sobre un índice, y es lo que deja ver de un vistazo cuál es la que
    está dejando gente fuera de los envíos.
    """
    return {one["key"]: db.contacts.count_documents(
        {"account_id": account_id,
         # De una lista, los que tienen al menos una fila.
         **({f"fields.{one['key']}.0": {"$exists": True}} if fields.is_list(one) else
            {f"fields.{one['key']}": {"$exists": True, "$nin": ["", None]}})})
        for one in definitions}


def values_not_of_type(db, account_id, key: str, kind: str) -> int:
    """Cuántos contactos tienen en esa columna algo que no es de ese tipo.

    Se piden los valores distintos —no un documento por contacto— y se prueban
    aquí, porque quien sabe si «15/03/2026» es una fecha es `services/fields.py`
    y no la base. Es lo que se mira antes de dejar cambiar el tipo.
    """
    wrong = [value for value in
             db.contacts.distinct(f"fields.{key}", {"account_id": account_id})
             if fields.parse(value, kind) is None]
    if not wrong:
        return 0
    return db.contacts.count_documents({"account_id": account_id,
                                        f"fields.{key}": {"$in": wrong}})


def count_by_tag(db, account_id,
                 definitions: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Cuántos contactos lleva cada etiqueta, en una sola consulta.

    Con las columnas de la cuenta cuenta solo a los que las tienen llenas, que
    son los que van a recibir algo: es la cifra que la pantalla de envíos pone
    al lado de cada etiqueta.
    """
    wanted: dict[str, Any] = {"account_id": account_id}
    conditions = _complete(definitions or [])
    if conditions:
        wanted["$and"] = conditions
    found = db.contacts.aggregate([
        {"$match": wanted},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "n": {"$sum": 1}}},
    ])
    return {row["_id"]: row["n"] for row in found}


def page(db, account_id, *, search: str = "", tag: str = "",
         limit: int = 50, skip: int = 0,
         invalid_only: bool = False) -> tuple[list[dict], int]:
    """One screenful of contacts, and how many match in total.

    The search is a plain prefix on the normalised address, which the unique
    index already covers: no regular expression walks the whole collection.

    **Los anulados no salen aquí.** No pueden recibir nada, así que mezclarlos
    con los demás era enseñar una lista que no es a la que se le escribe; se
    miran en Supresiones, que es su pantalla, y desde ahí se borran.
    """
    query: dict[str, Any] = {"account_id": account_id}
    if tag:
        query["tags"] = tag
    if search:
        cleaned = normalize_email(search)
        query["email_normalized"] = {"$regex": f"^{_escape(cleaned)}"}
    if invalid_only:
        query["invalid"] = {"$exists": True}

    stages = [{"$match": query}] + _drop_suppressed()
    counted = list(db.contacts.aggregate(stages + [{"$count": "n"}]))
    found = list(db.contacts.aggregate(
        stages + [{"$sort": {"created_at": -1}},
                  {"$skip": skip}, {"$limit": limit}]))
    return found, (counted[0]["n"] if counted else 0)


def _drop_suppressed() -> list[dict[str, Any]]:
    """Los pasos que sacan de una consulta a los que están suprimidos.

    La supresión vive en su propia colección y no se marca en el contacto, así
    que la única forma de saberlo es cruzar las dos. Se cruzan **en la misma
    consulta**, no una por contacto, que es la regla 10.
    """
    return [
        {"$lookup": {
            "from": "suppressions",
            "let": {"correo": "$email_normalized", "cuenta": "$account_id"},
            "pipeline": [{"$match": {"$expr": {"$and": [
                {"$eq": ["$account_id", "$$cuenta"]},
                {"$eq": ["$email_normalized", "$$correo"]},
            ]}}}, {"$limit": 1}],
            "as": "anulado",
        }},
        {"$match": {"anulado": {"$size": 0}}},
        {"$unset": "anulado"},
    ]


def _escape(text: str) -> str:
    """Everything a regular expression could read as syntax, escaped.

    The search box is typed by a visitor, and an unescaped ".*" there would ask
    Mongo to scan the whole collection.
    """
    import re
    return re.escape(text)


def by_email(db, account_id, email: str) -> dict[str, Any] | None:
    return db.contacts.find_one({"account_id": account_id,
                                 "email_normalized": normalize_email(email)})


def upsert_many(db, account_id, rows: Iterable[tuple], *,
                tags: list[str], consent: dict[str, Any],
                added_by: str = IMPORT) -> tuple[int, int]:
    """Write one batch. Returns (added, updated).

    An upsert and not an insert, so a second import of the same file adds
    nobody. What an existing contact keeps is its tags —the new one is added to
    them, never replacing— its name if the file brings none, and the origin it
    was first recorded with: the first answer is the true one.

    Cada fila es `(correo, nombre)` o `(correo, nombre, columnas)`. Las
    columnas se escriben una por una y no como un bloque: así una importación
    que trae la ciudad no le borra el monto a quien ya lo tenía.

    Una cuarta parte, `(…, otros)`, son más campos que escribir tal cual: el id
    de su sistema y las listas enteras que trae la API (octubre de 2026), ya
    revisados por quien llama.
    """
    moment = now()
    operations = []
    for row in rows:
        email, name = row[0], row[1]
        values = row[2] if len(row) > 2 else {}
        extra = row[3] if len(row) > 3 else {}
        normalized = normalize_email(email)
        fresh = {"email": email.strip(), "updated_at": moment}
        if name:
            fresh["name"] = name.strip()[:120]
        for key, value in (values or {}).items():
            if value != "":
                fresh[f"fields.{key}"] = value
        fresh.update(extra or {})
        born = {"account_id": account_id, "email_normalized": normalized,
                "consent": consent, "added_by": added_by, "created_at": moment}
        update: dict[str, Any] = {"$set": fresh, "$setOnInsert": born}
        if tags:
            update["$addToSet"] = {"tags": {"$each": tags}}
        else:
            # The field has to exist either way, or filtering by tag would not
            # see the document at all. It cannot be set in both places at once.
            born["tags"] = []
        operations.append(UpdateOne(
            {"account_id": account_id, "email_normalized": normalized},
            update, upsert=True))
    if not operations:
        return 0, 0
    result = db.contacts.bulk_write(operations, ordered=False)
    return len(result.upserted_ids), result.modified_count


def create(db, account_id, *, email: str, name: str = "",
           tags: list[str] | None = None, consent: dict[str, Any],
           values: dict[str, str] | None = None) -> bool:
    """Add one by hand. False if that address is already in the account."""
    added, _ = upsert_many(db, account_id, [(email, name, values or {})],
                           tags=tags or [], consent=consent, added_by=MANUAL)
    return added == 1


def emails_matching(db, account_id, *, tag: str = "", text: str = "") -> list[str]:
    """Las direcciones de los contactos que llevan esa etiqueta y cuyo correo o
    nombre contienen ese texto. Para filtrar el detalle de un envío."""
    query: dict[str, Any] = {"account_id": account_id}
    if tag:
        query["tags"] = tag
    if text:
        pattern = {"$regex": re.escape(text), "$options": "i"}
        query["$or"] = [{"email_normalized": pattern}, {"name": pattern}]
    return [one["email_normalized"] for one in
            db.contacts.find(query, {"email_normalized": 1})]


def by_emails(db, account_id, emails: list[str]) -> dict[str, dict[str, Any]]:
    """Los contactos de esas direcciones, por dirección. Una consulta con `$in`."""
    if not emails:
        return {}
    return {one["email_normalized"]: one for one in db.contacts.find(
        {"account_id": account_id, "email_normalized": {"$in": emails}},
        {"email": 1, "email_normalized": 1, "name": 1, "tags": 1})}


def for_preview(db, account_id, *, limit: int = 100) -> list[dict[str, Any]]:
    """Los primeros por dirección, para elegir con quién ver una plantilla."""
    return list(db.contacts.find({"account_id": account_id}, {"email": 1, "name": 1})
                .sort("email_normalized", 1).limit(limit))


def by_id(db, account_id, contact_id) -> dict[str, Any] | None:
    """Un contacto de esta cuenta. El account_id va en la consulta, no en una
    comprobación aparte: un id de otra cuenta no encuentra nada."""
    return db.contacts.find_one({"_id": contact_id, "account_id": account_id})


def update(db, account_id, contact_id, *, email: str, name: str,
           tags: list[str], values: dict[str, str] | None = None,
           extra: dict[str, Any] | None = None,
           unset: tuple[str, ...] = ()) -> bool:
    """Cambiar la dirección, el nombre y las etiquetas. False si esa dirección
    ya la tiene otro contacto de la cuenta.

    Lo que no toca: cuándo entró, por dónde entró y el origen que se declaró.
    Eso es historia, y si se pudiera editar dejaría de servir para lo único que
    sirve, que es responder cuando alguien reclame.

    El choque de direcciones lo responde el índice único y no una consulta
    previa: entre preguntar y escribir hay sitio para otra escritura, y solo el
    índice ve las dos a la vez.
    """
    changes: dict[str, Any] = {"email": email.strip(),
                               "email_normalized": normalize_email(email),
                               "name": name.strip()[:120],
                               "tags": tags,
                               "updated_at": now()}
    # Columna por columna y no el bloque entero (octubre de 2026): dentro
    # viven también las listas, que este formulario no trae y no puede borrar.
    for key, value in (values or {}).items():
        changes[f"fields.{key}"] = value
    # Lo que trae la API además (octubre de 2026): listas enteras y el id de su
    # sistema, ya revisados por quien llama, en la misma escritura.
    changes.update(extra or {})
    update: dict[str, Any] = {"$set": changes}
    if unset:
        update["$unset"] = {field: "" for field in unset}
    try:
        result = db.contacts.update_one(
            {"_id": contact_id, "account_id": account_id}, update)
    except DuplicateKeyError:
        return False
    return result.matched_count == 1


# ------------------------------------------------------ las listas (octubre de 2026)
#
# Varias filas dentro de un mismo contacto (`fields.<LISTA>`), cada una con su
# id. Las revisa `services/fields.py` antes de llegar aquí; aquí se escriben, y
# siempre con la cuenta en la consulta.

def set_rows(db, account_id, contact_id, key: str, rows: list[dict[str, Any]]) -> bool:
    """Reemplazar la lista entera."""
    return db.contacts.update_one(
        {"_id": contact_id, "account_id": account_id},
        {"$set": {f"fields.{key}": rows, "updated_at": now()}}).matched_count == 1


def append_rows(db, account_id, contact_id, key: str, rows: list[dict[str, Any]], *,
                keep: int) -> bool:
    """Agregar filas al final, dejando las `keep` más nuevas: las de antes se
    van solas, en la misma escritura."""
    return db.contacts.update_one(
        {"_id": contact_id, "account_id": account_id},
        {"$push": {f"fields.{key}": {"$each": rows, "$slice": -keep}},
         "$set": {"updated_at": now()}}).matched_count == 1


def update_row(db, account_id, contact_id, key: str, row: dict[str, Any]) -> bool:
    """Cambiar una fila por su id. False si ya no está."""
    return db.contacts.update_one(
        {"_id": contact_id, "account_id": account_id, f"fields.{key}.id": row["id"]},
        {"$set": {f"fields.{key}.$": row, "updated_at": now()}}).matched_count == 1


def remove_row(db, account_id, contact_id, key: str, row_id: str) -> bool:
    """Borrar una fila por su id. False si no estaba."""
    return db.contacts.update_one(
        {"_id": contact_id, "account_id": account_id, f"fields.{key}.id": row_id},
        {"$pull": {f"fields.{key}": {"id": row_id}},
         "$set": {"updated_at": now()}}).modified_count == 1


def drop_list_item(db, account_id, key: str, item_key: str) -> int:
    """Quitar un dato de todas las filas de una lista, en todos los contactos."""
    return db.contacts.update_many(
        {"account_id": account_id, f"fields.{key}.{item_key}": {"$exists": True}},
        {"$unset": {f"fields.{key}.$[].{item_key}": ""},
         "$set": {"updated_at": now()}}).modified_count


# ------------------------------------------- el id de su sistema (octubre de 2026)

EXTERNAL_ID = re.compile(r"^[A-Za-z0-9._:@-]{1,64}$")


def by_external_id(db, account_id, external_id: str) -> dict[str, Any] | None:
    """Ponerlo y quitarlo va en `update()`, con lo demás del contacto: el
    índice único dice si ya es de otro."""
    return db.contacts.find_one({"account_id": account_id, "external_id": external_id})


def delete(db, account_id, email: str) -> bool:
    """Remove a contact. Its suppression, if it has one, stays where it is."""
    result = db.contacts.delete_one({"account_id": account_id,
                                     "email_normalized": normalize_email(email)})
    return result.deleted_count == 1


def drop_field(db, account_id, key: str) -> int:
    """Borrar lo que todos los contactos tenían escrito en esa columna."""
    result = db.contacts.update_many(
        {"account_id": account_id, f"fields.{key}": {"$exists": True}},
        {"$unset": {f"fields.{key}": ""}, "$set": {"updated_at": now()}})
    return result.modified_count


def drop_tag(db, account_id, tag: str) -> int:
    """Take a tag off every contact that carries it. Returns how many."""
    result = db.contacts.update_many({"account_id": account_id, "tags": tag},
                                     {"$pull": {"tags": tag},
                                      "$set": {"updated_at": now()}})
    return result.modified_count
