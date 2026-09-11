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

from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo import UpdateOne
from pymongo.errors import DuplicateKeyError

from models.account import normalize_email

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
    found = list(db.contacts.aggregate([
        {"$match": {"account_id": account_id}},
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
        {"$count": "n"},
    ]))
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


def _matching(account_id, search: str, tag: str) -> dict[str, Any]:
    """La consulta de la tabla, en un solo sitio.

    La usan la exportación y el conteo que la confirma, para que el número que
    se enseña antes de descargar sea el del archivo y no una cuenta aparte que
    un día se desincroniza.
    """
    query: dict[str, Any] = {"account_id": account_id}
    if tag:
        query["tags"] = tag
    if search:
        query["email_normalized"] = {"$regex": f"^{_escape(normalize_email(search))}"}
    return query


def matching_count(db, account_id, *, search: str = "", tag: str = "") -> int:
    """Cuántos saldrían con ese buscador y ese filtro."""
    return db.contacts.count_documents(_matching(account_id, search, tag))


def batch_for_sending(db, account_id, *, tag: str = "", skip: int = 0,
                      limit: int = 100) -> list[dict[str, Any]]:
    """Un tramo de la lista, en orden fijo, para mandarle una campaña.

    Por `_id` y no por fecha, que es como ordena la pantalla: es el único orden
    que no se mueve si alguien importa contactos mientras la campaña va por la
    mitad, y de eso depende que la posición guardada signifique lo mismo en la
    tanda siguiente.
    """
    return list(db.contacts.find(_matching(account_id, "", tag))
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


def tags_in_use(db, account_id) -> list[str]:
    """Las etiquetas que de verdad lleva puestas algún contacto.

    No es la lista que se enseña —esa es el registro de la cuenta, que incluye
    las recién creadas y todavía vacías— sino la que hace falta para rellenar
    ese registro la primera vez.
    """
    return sorted(db.contacts.distinct("tags", {"account_id": account_id}))


def count_by_tag(db, account_id) -> dict[str, int]:
    """Cuántos contactos lleva cada etiqueta, en una sola consulta."""
    found = db.contacts.aggregate([
        {"$match": {"account_id": account_id}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "n": {"$sum": 1}}},
    ])
    return {row["_id"]: row["n"] for row in found}


def page(db, account_id, *, search: str = "", tag: str = "",
         limit: int = 50, skip: int = 0) -> tuple[list[dict], int]:
    """One screenful of contacts, and how many match in total.

    The search is a plain prefix on the normalised address, which the unique
    index already covers: no regular expression walks the whole collection.
    """
    query: dict[str, Any] = {"account_id": account_id}
    if tag:
        query["tags"] = tag
    if search:
        cleaned = normalize_email(search)
        query["email_normalized"] = {"$regex": f"^{_escape(cleaned)}"}
    total = db.contacts.count_documents(query)
    found = list(db.contacts.find(query).sort("created_at", -1).skip(skip).limit(limit))
    return found, total


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


def upsert_many(db, account_id, rows: Iterable[tuple[str, str]], *,
                tags: list[str], consent: dict[str, Any],
                added_by: str = IMPORT) -> tuple[int, int]:
    """Write one batch. Returns (added, updated).

    An upsert and not an insert, so a second import of the same file adds
    nobody. What an existing contact keeps is its tags —the new one is added to
    them, never replacing— its name if the file brings none, and the origin it
    was first recorded with: the first answer is the true one.
    """
    moment = now()
    operations = []
    for email, name in rows:
        normalized = normalize_email(email)
        fresh = {"email": email.strip(), "updated_at": moment}
        if name:
            fresh["name"] = name.strip()[:120]
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
           tags: list[str] | None = None, consent: dict[str, Any]) -> bool:
    """Add one by hand. False if that address is already in the account."""
    added, _ = upsert_many(db, account_id, [(email, name)],
                           tags=tags or [], consent=consent, added_by=MANUAL)
    return added == 1


def by_id(db, account_id, contact_id) -> dict[str, Any] | None:
    """Un contacto de esta cuenta. El account_id va en la consulta, no en una
    comprobación aparte: un id de otra cuenta no encuentra nada."""
    return db.contacts.find_one({"_id": contact_id, "account_id": account_id})


def update(db, account_id, contact_id, *, email: str, name: str,
           tags: list[str]) -> bool:
    """Cambiar la dirección, el nombre y las etiquetas. False si esa dirección
    ya la tiene otro contacto de la cuenta.

    Lo que no toca: cuándo entró, por dónde entró y el origen que se declaró.
    Eso es historia, y si se pudiera editar dejaría de servir para lo único que
    sirve, que es responder cuando alguien reclame.

    El choque de direcciones lo responde el índice único y no una consulta
    previa: entre preguntar y escribir hay sitio para otra escritura, y solo el
    índice ve las dos a la vez.
    """
    try:
        result = db.contacts.update_one(
            {"_id": contact_id, "account_id": account_id},
            {"$set": {"email": email.strip(),
                      "email_normalized": normalize_email(email),
                      "name": name.strip()[:120],
                      "tags": tags,
                      "updated_at": now()}})
    except DuplicateKeyError:
        return False
    return result.matched_count == 1


def delete(db, account_id, email: str) -> bool:
    """Remove a contact. Its suppression, if it has one, stays where it is."""
    result = db.contacts.delete_one({"account_id": account_id,
                                     "email_normalized": normalize_email(email)})
    return result.deleted_count == 1


def drop_tag(db, account_id, tag: str) -> int:
    """Take a tag off every contact that carries it. Returns how many."""
    result = db.contacts.update_many({"account_id": account_id, "tags": tag},
                                     {"$pull": {"tags": tag},
                                      "$set": {"updated_at": now()}})
    return result.modified_count
