"""Contactos, etiquetas, columnas y supresiones por la API (octubre de 2026).

Las mismas reglas que en el panel, porque son las mismas funciones:

  * **Nadie se duplica** (regla 5): cargar es un upsert por la dirección, en
    lote (`importer.write_batch`, el mismo motor que importar un CSV, con
    `bulkWrite`: regla 10). Un contacto nuevo necesita sitio en el plan y todas
    sus columnas; uno que ya está se actualiza. Cada carga dice de dónde salieron
    (`consent`), que es lo que hay que enseñar si alguien reclama.
  * **El id de su sistema** (`external_id`) es la otra forma de encontrar a un
    contacto: si una fila lo trae y existe, se actualiza ese contacto aunque
    cambie su correo. Es único en la cuenta.
  * **Las listas** (transacciones, pedidos) viven dentro de cada contacto: se
    reemplazan enteras, se les agregan filas, o se cambia o se borra una por su
    id. Con topes, porque pesan en la base.
  * **Las etiquetas y las columnas se crean antes de usarse**: una etiqueta o
    una columna que no existe es un error, no algo que se crea de paso.
  * **Borrar un contacto no borra su supresión** (regla 2), y las supresiones
    solo se miran: ni se ponen ni se quitan desde fuera.
  * **Una carga a la vez por cuenta** (candado), y no mientras corre una
    importación del panel: dos a la vez se pasarían del tope del plan.

La cuenta va en cada consulta: un id de otra cuenta responde 404, igual que uno
que no existe.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from flask import request
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from blueprints.api.core import (Fields, account, api_route, body, fail, iso, ok,
                                 one_line, page_cursor, page_limit, paged, path_id)
from db import get_db
from i18n import t
from models import account as accounts
from models import contact as contacts
from models import import_job as imports
from models import lock as locks
from models import suppression as suppressions
from models.account import normalize_email
from services import fields as columns
from services import importer
from services.security import rate_state

ROWS_MAX = 1000
ROWS_PER_MINUTE = 5000
LOCK_SECONDS = 90
# Cuántos dominios nuevos se le preguntan al DNS en una carga: lo demás queda
# como bueno, igual que el importador pasados los suyos. Cada pregunta puede
# tardar, y esto corre dentro de la petición.
DOMAINS_PER_LOAD = 20
NAME_MAX = 120
TAGS_PER_ROW = 20
ROW_FIELDS = {"email", "name", "tags", "fields", "external_id"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def blocked_for(db, account_id, emails: list[str]) -> dict[str, dict]:
    """Las supresiones de esas direcciones, en una consulta (regla 10)."""
    if not emails:
        return {}
    return {one["email_normalized"]: one for one in db.suppressions.find(
        {"account_id": account_id, "email_normalized": {"$in": emails}},
        {"email_normalized": 1, "reason": 1, "created_at": 1})}


def contact_shape(one: dict, blocked: dict[str, dict], definitions: list[dict]) -> dict:
    """Cómo sale un contacto: sus datos, sus listas, si puede recibir y de dónde
    salió."""
    block = blocked.get(one.get("email_normalized", ""))
    values = columns.values_of(one)
    consent = one.get("consent") or None
    shown: dict = {}
    for d in definitions:
        if columns.is_list(d):
            shown[d["key"]] = [row for row in (values.get(d["key"]) or [])
                               if isinstance(row, dict)]
        else:
            shown[d["key"]] = values.get(d["key"], "")
    return {
        "id": str(one["_id"]),
        "external_id": one.get("external_id"),
        "email": one.get("email", ""),
        "name": one.get("name", ""),
        "tags": list(one.get("tags") or []),
        "fields": shown,
        "status": ("suppressed" if block else "invalid" if one.get("invalid")
                   else "active"),
        "suppression": ({"reason": block.get("reason"), "at": iso(block.get("created_at"))}
                        if block else None),
        "complete": not columns.missing(one, definitions),
        "consent": ({"source": consent.get("source"), "note": consent.get("note", ""),
                     "recorded_at": iso(consent.get("recorded_at"))} if consent else None),
        "added_by": one.get("added_by"),
        "created_at": iso(one.get("created_at")),
        "updated_at": iso(one.get("updated_at")),
    }


def shaped(db, company, rows: list[dict]) -> list[dict]:
    definitions = accounts.fields_of(company)
    blocked = blocked_for(db, company["_id"], [one["email_normalized"] for one in rows])
    return [contact_shape(one, blocked, definitions) for one in rows]


def find_contact(db, company, raw: str) -> dict:
    found = contacts.by_id(db, company["_id"], path_id(raw))
    if found is None:
        fail("not_found", 404)
    return found


def read_values(raw_values, definitions: list[dict]):
    """Las columnas que llegaron, por su clave y revisadas por su tipo; las
    listas, enteras. Devuelve (valores, listas, motivo, cuál); un motivo es que
    no se pudo."""
    by_key = {one["key"]: one for one in definitions}
    if not isinstance(raw_values, dict):
        return {}, {}, "bad_fields", ""
    values: dict[str, str] = {}
    lists: dict[str, list] = {}
    for key, raw in raw_values.items():
        one = by_key.get(key)
        if one is None:
            return {}, {}, "unknown_field", str(key)[:40]
        if columns.is_list(one):
            rows, wrong = columns.parse_rows(raw, one.get("items") or [])
            if rows is None:
                return {}, {}, "bad_list", f"{key} ({wrong})"
            lists[key] = rows
            continue
        if raw is None:
            values[key] = ""
            continue
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            return {}, {}, "bad_value", key
        parsed = columns.parse(str(raw), one.get("type", columns.TEXT))
        if parsed is None:
            return {}, {}, "bad_value", key
        values[key] = parsed
    return values, lists, "", ""


def clean_external(raw) -> tuple[str | None, bool]:
    """El id de su sistema que llegó: (valor, si es válido). None es «no vino»."""
    if raw is None:
        return None, True
    if isinstance(raw, str) and contacts.EXTERNAL_ID.match(raw):
        return raw, True
    return None, False


# ------------------------------------------------------------ los contactos

@api_route("/contacts", scope="contacts:read")
def list_contacts():
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"]}
    email = request.args.get("email", "")[:254]
    search = request.args.get("search", "")[:120]
    tag = request.args.get("tag", "")[:accounts.TAG_LENGTH]
    external = request.args.get("external_id", "")[:64]
    if email:
        query["email_normalized"] = normalize_email(email)
    elif search:
        query["email_normalized"] = {"$regex": "^" + re.escape(normalize_email(search))}
    if external:
        query["external_id"] = external
    if tag:
        query["tags"] = tag
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.contacts.find(query).sort("_id", -1).limit(limit + 1))
    shown = {str(row["_id"]): one for row, one in zip(rows, shaped(db, company, rows))}
    return ok(paged(rows, limit, lambda one: shown[str(one["_id"])]))


@api_route("/contacts/<contact_id>", scope="contacts:read")
def get_contact(contact_id):
    company = account()
    db = get_db()
    return ok(shaped(db, company, [find_contact(db, company, contact_id)])[0])


def check_row(row, index: int, *, known_tags: list[str], definitions: list[dict],
              seen: set[str], seen_external: set[str]):
    """Revisar una fila de una carga. Devuelve (rechazo, preparada): el rechazo
    es el resultado de esa fila; la preparada, lo que se escribe."""
    raw_email = row.get("email") if isinstance(row, dict) else None
    shown_email = raw_email if isinstance(raw_email, str) else ""

    def rejected(reason: str, detail: str = ""):
        entry = {"index": index, "email": shown_email[:254], "result": "rejected",
                 "reason": reason}
        if detail:
            entry["detail"] = detail
        return entry, None

    if not isinstance(row, dict) or set(row) - ROW_FIELDS:
        return rejected("bad_row")
    address = (importer.clean(raw_email) if isinstance(raw_email, str)
               and len(raw_email) <= 254 else None)
    name = row.get("name", "")
    row_tags = row.get("tags", [])
    if not address:
        return rejected("invalid_email")
    if normalize_email(address) in seen:
        return rejected("duplicate")
    # En una línea: el nombre puede ir en el asunto (`*|NOMBRE|*`), que es una
    # cabecera.
    if not isinstance(name, str) or len(name) > NAME_MAX or not one_line(name):
        return rejected("bad_name")
    if (not isinstance(row_tags, list) or len(row_tags) > TAGS_PER_ROW
            or not all(isinstance(one, str) for one in row_tags)):
        return rejected("bad_tags")
    missing_tag = next((one for one in row_tags if one not in known_tags), None)
    if missing_tag is not None:
        return rejected("unknown_tag", missing_tag[:40])
    external, good = clean_external(row.get("external_id"))
    if not good:
        return rejected("bad_external_id")
    if external is not None and external in seen_external:
        return rejected("duplicate", external)
    values, lists, reason, detail = read_values(row.get("fields", {}), definitions)
    if reason:
        return rejected(reason, detail)
    seen.add(normalize_email(address))
    if external is not None:
        seen_external.add(external)
    return None, {"index": index, "address": address, "name": name.strip(),
                  "tags": row_tags, "values": {k: v for k, v in values.items() if v},
                  "lists": lists, "external": external}


@api_route("/contacts", methods=("POST",), scope="contacts:write", limit="contacts",
           max_bytes=2 * 1024 * 1024, idempotent=True)
def upsert_contacts():
    """Cargar de 1 a 1,000 contactos: los nuevos entran, los que ya están se
    actualizan, y cada fila dice qué le pasó."""
    data = body({"contacts", "consent", "tags"}, required=("contacts", "consent"))
    fields = Fields(data)
    rows = data.get("contacts")
    if not isinstance(rows, list) or not 1 <= len(rows) <= ROWS_MAX:
        fields.errors["contacts"] = t("api_contacts_rows", n=ROWS_MAX)
    consent = data.get("consent")
    note = consent.get("note", "") if isinstance(consent, dict) else ""
    if (not isinstance(consent, dict) or set(consent) - {"source", "note"}
            or consent.get("source") not in contacts.SOURCES
            or not isinstance(note, str) or len(note) > 300):
        fields.errors["consent"] = t("api_contacts_consent",
                                     sources=", ".join(contacts.SOURCES))
    batch_tags = fields.strings("tags", max_items=TAGS_PER_ROW,
                                max_len=accounts.TAG_LENGTH) or []
    fields.check()

    company = account()
    db = get_db()
    known_tags = accounts.tags_of(company)
    unknown = [one for one in batch_tags if one not in known_tags]
    if unknown:
        fail("unknown_tag", 422, extra={"tags": unknown})
    allowed, _, reset = rate_state(db, f"api:contact_rows:{company['_id']}",
                                   ROWS_PER_MINUTE, 60, amount=len(rows))
    if not allowed:
        fail("rate_limited", 429, retry_after=reset)

    definitions = accounts.fields_of(company)
    results: list[dict | None] = [None] * len(rows)
    prepared: list[dict] = []
    seen: set[str] = set()
    seen_external: set[str] = set()
    for index, row in enumerate(rows):
        entry, ready = check_row(row, index, known_tags=known_tags,
                                 definitions=definitions, seen=seen,
                                 seen_external=seen_external)
        if entry is not None:
            results[index] = entry
        else:
            prepared.append(ready)

    lock_name = f"contacts:{company['_id']}"
    token = locks.acquire(db, lock_name, LOCK_SECONDS)
    if token is None or imports.running(db, company["_id"]):
        locks.release(db, lock_name, token)
        fail("busy", 409, retry_after=5)
    try:
        write_rows(db, company, prepared, results, definitions=definitions,
                   batch_tags=batch_tags, consent=contacts.consent_of(consent["source"], note))
    finally:
        locks.release(db, lock_name, token)

    done_rows = [one for one in results if one]
    return ok({
        "added": sum(1 for one in done_rows if one["result"] == importer.ADDED),
        "updated": sum(1 for one in done_rows if one["result"] == importer.UPDATED),
        "rejected": sum(1 for one in done_rows if one["result"] == "rejected"),
        "results": done_rows,
    })


def write_rows(db, company, prepared: list[dict], results: list, *, definitions,
               batch_tags: list[str], consent: dict) -> None:
    """Escribir las filas buenas de una carga y anotar qué le pasó a cada una.

    Las que traen un `external_id` que ya existe actualizan **ese** contacto
    por su id (en un solo `bulkWrite`); las demás pasan por el motor de
    importar, por su dirección."""
    account_id = company["_id"]
    keys = [normalize_email(one["address"]) for one in prepared]
    existing = {one["email_normalized"]: one for one in db.contacts.find(
        {"account_id": account_id, "email_normalized": {"$in": keys}},
        {"email_normalized": 1, "external_id": 1})} if keys else {}
    externals = [one["external"] for one in prepared if one["external"]]
    by_external = {one["external_id"]: one for one in db.contacts.find(
        {"account_id": account_id, "external_id": {"$in": externals}},
        {"external_id": 1, "email_normalized": 1})} if externals else {}
    suppressed = suppressions.among(db, account_id, keys)

    def note(entry: dict, key: str) -> dict:
        if key in suppressed:
            entry["warning"] = "suppressed"
        results[entry["index"]] = entry
        return entry

    def list_sets(one: dict) -> dict:
        return {f"fields.{key}": rows for key, rows in one["lists"].items()}

    # Las que encuentran su contacto por el id de su sistema.
    by_id_ops, by_id_rows, by_email = [], [], []
    for one in prepared:
        key = normalize_email(one["address"])
        target = by_external.get(one["external"]) if one["external"] else None
        if target is None:
            mine = existing.get(key)
            if (one["external"] and mine is not None and mine.get("external_id")
                    and mine["external_id"] != one["external"]):
                note({"index": one["index"], "email": one["address"],
                      "result": "rejected", "reason": "external_id_conflict"}, key)
                continue
            by_email.append(one)
            continue
        owner = existing.get(key)
        if owner is not None and owner["_id"] != target["_id"]:
            note({"index": one["index"], "email": one["address"], "result": "rejected",
                  "reason": "email_taken"}, key)
            continue
        changes = {"email": one["address"], "email_normalized": key,
                   "updated_at": now(), **list_sets(one),
                   **{f"fields.{name}": value for name, value in one["values"].items()}}
        if one["name"]:
            changes["name"] = one["name"][:NAME_MAX]
        update: dict = {"$set": changes}
        tags = list(dict.fromkeys(list(one["tags"]) + list(batch_tags)))
        if tags:
            update["$addToSet"] = {"tags": {"$each": tags}}
        by_id_ops.append(UpdateOne({"_id": target["_id"], "account_id": account_id}, update))
        by_id_rows.append(one)
    if by_id_ops:
        failed: set[int] = set()
        try:
            db.contacts.bulk_write(by_id_ops, ordered=False)
        except BulkWriteError as exc:
            failed = {error["index"] for error in exc.details.get("writeErrors", [])}
        for position, one in enumerate(by_id_rows):
            key = normalize_email(one["address"])
            note({"index": one["index"], "email": one["address"],
                  **({"result": "rejected", "reason": "email_taken"} if position in failed
                     else {"result": importer.UPDATED})}, key)

    # Las demás, por su dirección, con las reglas de importar.
    if not by_email:
        return
    # Quién está se vuelve a mirar si arriba alguien cambió de correo: la
    # dirección que dejó libre ahora es de alguien nuevo, y ese sí ocupa sitio.
    left = [normalize_email(one["address"]) for one in by_email]
    present = ({one["email_normalized"] for one in db.contacts.find(
        {"account_id": account_id, "email_normalized": {"$in": left}},
        {"email_normalized": 1})} if by_id_ops else set(existing))
    # El conteo de activos cruza dos colecciones: solo si entra alguien nuevo.
    room = (max(0, accounts.contact_limit(company) - contacts.active_count(db, account_id))
            if any(key not in present for key in left) else 0)
    counts = importer.new_counts()
    required = [one["key"] for one in columns.scalars(definitions)]
    domains_seen: set[str] = set()
    groups: dict[tuple, list[dict]] = {}
    for one in by_email:
        groups.setdefault(tuple(sorted(set(one["tags"]) | set(batch_tags))), []).append(one)
    for group_tags, items in groups.items():
        batch = [(one["address"], one["name"], one["values"],
                  {**list_sets(one), **({"external_id": one["external"]}
                                        if one["external"] else {})})
                 for one in items]
        try:
            done = importer.write_batch(
                db, account_id, batch, tags=list(group_tags), consent=consent,
                required=required, room=room, counts=counts, domains_seen=domains_seen,
                added_by=contacts.API, stop_when_full=False, max_domains=DOMAINS_PER_LOAD)
        except BulkWriteError:
            # Alguien del panel escribió ese correo o ese id a la vez. Lo demás
            # quedó escrito, y repetir la carga entera da lo mismo: es un upsert.
            fail("busy", 409, retry_after=1)
        room = done["room"]
        bad = {normalize_email(one) for one in done["bad"]}
        typos = {normalize_email(one): better for one, better in done["typos"]}
        for one in items:
            key = normalize_email(one["address"])
            what = done["outcome"].get(key, importer.NO_ROOM)
            entry = {"index": one["index"], "email": one["address"]}
            if what in (importer.ADDED, importer.UPDATED):
                entry["result"] = what
            else:
                entry["result"] = "rejected"
                entry["reason"] = what
                if what == importer.INCOMPLETE:
                    entry["missing"] = [d for d in required if not one["values"].get(d)]
            if key in bad and key not in suppressed:
                entry["warning"] = "undeliverable"
            if key in typos:
                entry["suggestion"] = typos[key]
            note(entry, key)


@api_route("/contacts/<contact_id>", methods=("PATCH",), scope="contacts:write")
def update_contact(contact_id):
    """Cambiar el correo, el nombre, el id de su sistema, las etiquetas (se
    reemplazan), las columnas (se mezclan) o las listas (se reemplaza la que
    llegue). Como en el panel, el contacto queda con todas sus columnas
    llenas."""
    data = body({"email", "name", "tags", "fields", "external_id"})
    company = account()
    db = get_db()
    found = find_contact(db, company, contact_id)
    fields = Fields(data)
    email = found.get("email", "")
    if fields.has("email"):
        raw = fields.text("email", max_len=254, required=True)
        email = importer.clean(raw) if raw else None
        if raw and not email:
            fields.errors["email"] = t("api_contacts_email")
    name = (fields.text("name", max_len=NAME_MAX, default=found.get("name", ""))
            if fields.has("name") else found.get("name", ""))
    if fields.has("name") and "name" not in fields.errors and not one_line(name):
        fields.errors["name"] = t("api_field_one_line")
    tags = list(found.get("tags") or [])
    if fields.has("tags"):
        wanted = fields.strings("tags", max_items=TAGS_PER_ROW, max_len=accounts.TAG_LENGTH)
        if wanted is not None:
            known_tags = accounts.tags_of(company)
            unknown = [one for one in wanted if one not in known_tags]
            if unknown:
                fields.errors["tags"] = t("api_contacts_unknown_tags",
                                          what=", ".join(unknown[:5]))
            tags = list(dict.fromkeys(wanted))
    extra: dict = {}
    unset: tuple[str, ...] = ()
    if fields.has("external_id"):
        external, good = clean_external(data.get("external_id"))
        if not good:
            fields.errors["external_id"] = t("contacts_external_bad")
        elif external is None:
            unset = ("external_id",)
        else:
            other = contacts.by_external_id(db, company["_id"], external)
            if other is not None and other["_id"] != found["_id"]:
                fail("external_id_taken", 409)
            extra["external_id"] = external
    definitions = accounts.fields_of(company)
    values = dict(columns.values_of(found))
    if fields.has("fields"):
        given, lists, reason, detail = read_values(data.get("fields"), definitions)
        if reason:
            fields.errors["fields"] = t("api_contacts_field_" + reason, what=detail)
        values.update(given)
        extra.update({f"fields.{key}": rows for key, rows in lists.items()})
    scalar_keys = {one["key"] for one in columns.scalars(definitions)}
    values = {key: value for key, value in values.items() if value and key in scalar_keys}
    missing = [key for key in scalar_keys if not values.get(key)]
    if missing and not fields.errors:
        fields.errors["fields"] = t("api_contacts_missing", what=", ".join(sorted(missing)))
    fields.check()
    if not contacts.update(db, company["_id"], found["_id"], email=email, name=name,
                           tags=tags, values=values, extra=extra, unset=unset):
        fail("email_taken", 409)
    return ok(shaped(db, company, [contacts.by_id(db, company["_id"], found["_id"])])[0])


@api_route("/contacts/<contact_id>", methods=("DELETE",), scope="contacts:write")
def delete_contact(contact_id):
    """Borrarlo. Su supresión, si tiene, se queda (regla 2)."""
    company = account()
    db = get_db()
    found = find_contact(db, company, contact_id)
    contacts.delete(db, company["_id"], found["email"])
    return ok({"id": str(found["_id"]), "deleted": True})


# ------------------------------------------------------------ las listas

def find_list(company, key: str) -> dict:
    found = accounts.field_by_key(company, key)
    if not columns.is_list(found):
        fail("not_found", 404)
    return found


def rows_now(found: dict, key: str) -> list[dict]:
    return [row for row in (columns.values_of(found).get(key) or []) if isinstance(row, dict)]


def list_shape(definition: dict, rows: list[dict]) -> dict:
    return {"key": definition["key"], "label": definition.get("label", ""),
            "items": [{"key": one["key"], "label": one.get("label", ""),
                       "type": one.get("type", columns.TEXT)}
                      for one in definition.get("items") or []],
            "rows": rows}


def rows_from(data, definition: dict, name: str = "rows") -> list[dict]:
    rows, wrong = columns.parse_rows(data.get(name), definition.get("items") or [])
    if rows is None:
        fail("validation_failed", 422, fields={name: t("api_lists_rows_bad", what=wrong,
                                                       n=columns.LIST_ROWS_MAX)})
    return rows


@api_route("/contacts/<contact_id>/lists/<key>", scope="contacts:read")
def get_list(contact_id, key):
    company = account()
    db = get_db()
    definition = find_list(company, key)
    found = find_contact(db, company, contact_id)
    return ok(list_shape(definition, rows_now(found, key)))


@api_route("/contacts/<contact_id>/lists/<key>", methods=("PUT",), scope="contacts:write")
def replace_list(contact_id, key):
    """Cambiar la lista entera por la que llega."""
    data = body({"rows"}, required=("rows",))
    company = account()
    db = get_db()
    definition = find_list(company, key)
    found = find_contact(db, company, contact_id)
    rows = rows_from(data, definition)
    contacts.set_rows(db, company["_id"], found["_id"], key, rows)
    return ok(list_shape(definition, rows))


@api_route("/contacts/<contact_id>/lists/<key>", methods=("POST",), scope="contacts:write")
def append_list(contact_id, key):
    """Agregar filas al final. Si pasan del tope, se van las más viejas."""
    data = body({"rows", "keep_last"}, required=("rows",))
    fields = Fields(data)
    keep = fields.integer("keep_last", low=1, high=columns.LIST_ROWS_MAX,
                          default=columns.LIST_ROWS_MAX)
    fields.check()
    company = account()
    db = get_db()
    definition = find_list(company, key)
    found = find_contact(db, company, contact_id)
    fresh = rows_from(data, definition)
    current = rows_now(found, key)
    taken = {row.get("id") for row in current}
    for row in fresh:
        while row["id"] in taken:
            row["id"] = columns.new_row_id()
        taken.add(row["id"])
    after = (current + fresh)[-keep:]
    if columns.rows_size(after) > columns.LIST_BYTES_MAX:
        fail("validation_failed", 422, fields={"rows": t("api_lists_too_big")})
    contacts.append_rows(db, company["_id"], found["_id"], key, fresh, keep=keep)
    return ok(list_shape(definition, after), 201)


@api_route("/contacts/<contact_id>/lists/<key>/<row_id>", methods=("PATCH",),
           scope="contacts:write")
def update_list_row(contact_id, key, row_id):
    """Cambiar una fila: los datos que lleguen, sobre los que tenía."""
    company = account()
    db = get_db()
    definition = find_list(company, key)
    data = body({one["key"] for one in definition.get("items") or []})
    found = find_contact(db, company, contact_id)
    current = rows_now(found, key)
    before = next((row for row in current if row.get("id") == row_id), None)
    if before is None:
        fail("not_found", 404)
    merged = {**{k: v for k, v in before.items() if k != "id"}, **data}
    row, wrong = columns.parse_row(merged, definition.get("items") or [], keep_id=row_id)
    if row is None:
        fail("validation_failed", 422, fields={"row": t("api_lists_rows_bad", what=wrong,
                                                        n=columns.LIST_ROWS_MAX)})
    after = [row if one.get("id") == row_id else one for one in current]
    if columns.rows_size(after) > columns.LIST_BYTES_MAX:
        fail("validation_failed", 422, fields={"row": t("api_lists_too_big")})
    if not contacts.update_row(db, company["_id"], found["_id"], key, row):
        fail("not_found", 404)
    return ok(row)


@api_route("/contacts/<contact_id>/lists/<key>/<row_id>", methods=("DELETE",),
           scope="contacts:write")
def delete_list_row(contact_id, key, row_id):
    company = account()
    db = get_db()
    find_list(company, key)
    found = find_contact(db, company, contact_id)
    if not contacts.remove_row(db, company["_id"], found["_id"], key, row_id):
        fail("not_found", 404)
    return ok({"id": row_id, "deleted": True})


# ------------------------------------------------------------ las etiquetas

@api_route("/tags", scope="contacts:read")
def list_tags():
    company = account()
    counted = contacts.count_by_tag(get_db(), company["_id"])
    return ok({"data": [{"name": one, "contacts": counted.get(one, 0)}
                        for one in accounts.tags_of(company)],
               "limit": accounts.tag_limit(company)})


@api_route("/tags", methods=("POST",), scope="contacts:write")
def create_tag():
    data = body({"name"}, required=("name",))
    fields = Fields(data)
    name = accounts.clean_tag(fields.text("name", max_len=accounts.TAG_LENGTH, required=True))
    fields.check()
    company = account()
    existing = accounts.tags_of(company)
    if any(one.lower() == name.lower() for one in existing):
        fail("tag_exists", 409)
    if len(existing) >= accounts.tag_limit(company):
        fail("limit_reached", 409, what=t("api_limit_tags"), n=accounts.tag_limit(company))
    if not name or not accounts.add_tag(get_db(), company["_id"], name):
        fail("tag_exists", 409)
    return ok({"name": name, "contacts": 0}, 201)


@api_route("/tags/<path:name>", methods=("DELETE",), scope="contacts:write")
def delete_tag(name):
    """Borrar una etiqueta: sale de la cuenta y de los contactos que la
    llevaban. Los contactos se quedan."""
    company = account()
    if name not in accounts.tags_of(company):
        fail("not_found", 404)
    db = get_db()
    accounts.remove_tag(db, company["_id"], name)
    return ok({"name": name, "deleted": True,
               "contacts": contacts.drop_tag(db, company["_id"], name)})


# ------------------------------------------------------------ las columnas

def field_shape(one: dict, filled: dict[str, int]) -> dict:
    shown = {"key": one["key"], "label": one.get("label", ""),
             "type": one.get("type", columns.TEXT), "filled": filled.get(one["key"], 0)}
    if columns.is_list(one):
        shown["items"] = [{"key": item["key"], "label": item.get("label", ""),
                           "type": item.get("type", columns.TEXT)}
                          for item in one.get("items") or []]
    return shown


@api_route("/fields", scope="contacts:read")
def list_fields():
    company = account()
    definitions = accounts.fields_of(company)
    filled = contacts.count_by_field(get_db(), company["_id"], definitions)
    return ok({"data": [field_shape(one, filled) for one in definitions],
               "limit": accounts.field_limit(company), "lists_max": columns.LISTS_MAX})


def read_items(raw, fields: Fields, name: str = "items") -> list[tuple[str, str]]:
    """Los datos de una lista que llegaron: nombre y tipo de cada uno."""
    if (not isinstance(raw, list) or not all(
            isinstance(one, dict) and set(one) <= {"label", "type"}
            and isinstance(one.get("label"), str) and one.get("type") in columns.TYPES
            for one in raw)):
        fields.errors[name] = t("api_fields_items", n=columns.LIST_ITEMS_MAX,
                                types=", ".join(columns.TYPES))
        return []
    return [(one["label"], one["type"]) for one in raw]


@api_route("/fields", methods=("POST",), scope="contacts:write")
def create_field():
    data = body({"label", "type", "items"}, required=("label", "type"))
    fields = Fields(data)
    label = fields.text("label", max_len=columns.LABEL_MAX, required=True)
    kind = fields.text("type", max_len=10, required=True)
    items: list[tuple[str, str]] = []
    if kind and kind not in columns.TYPES + (columns.LIST,):
        fields.errors["type"] = t("api_fields_type",
                                  types=", ".join(columns.TYPES + (columns.LIST,)))
    elif kind == columns.LIST:
        items = read_items(data.get("items"), fields)
        if "items" not in fields.errors and accounts.list_items(items) is None:
            fields.errors["items"] = t("api_fields_items", n=columns.LIST_ITEMS_MAX,
                                       types=", ".join(columns.TYPES))
    elif fields.has("items"):
        fields.errors["items"] = t("api_field_unknown")
    fields.check()
    company = account()
    definitions = accounts.fields_of(company)
    if len(definitions) >= accounts.field_limit(company):
        fail("limit_reached", 409, what=t("api_limit_fields"),
             n=accounts.field_limit(company))
    if kind == columns.LIST and sum(1 for one in definitions
                                    if columns.is_list(one)) >= columns.LISTS_MAX:
        fail("limit_reached", 409, what=t("api_limit_lists"), n=columns.LISTS_MAX)
    key = accounts.add_field(get_db(), company["_id"], label=label, kind=kind, items=items)
    if key is None:
        fail("field_exists", 409)
    created = accounts.field_by_key(accounts.by_id(get_db(), company["_id"]), key)
    return ok(field_shape(created, {}), 201)


def find_field(company, key: str) -> dict:
    found = accounts.field_by_key(company, key)
    if found is None:
        fail("not_found", 404)
    return found


@api_route("/fields/<key>", methods=("PATCH",), scope="contacts:write")
def update_field(key):
    """Cambiarle el tipo a una columna, si todos sus valores encajan en el
    nuevo; a una lista, agregarle (`add`) o quitarle (`remove`) un dato. El
    nombre no se cambia: es lo que nombran las plantillas."""
    company = account()
    found = find_field(company, key)
    db = get_db()
    if columns.is_list(found):
        # Uno de los dos por vez: si el segundo no se pudiera, el primero ya
        # habría quedado hecho.
        data = body({"add", "remove"})
        fields = Fields(data)
        if fields.has("add") == fields.has("remove"):
            fields.errors["add"] = t("api_fields_add_or_remove")
            fields.check()
        if fields.has("add"):
            pairs = read_items([data.get("add")], fields, "add")
            fields.check()
            if accounts.add_list_item(db, company["_id"], found["key"],
                                      label=pairs[0][0], kind=pairs[0][1]) is None:
                fail("validation_failed", 422, fields={"add": t(
                    "api_fields_items", n=columns.LIST_ITEMS_MAX,
                    types=", ".join(columns.TYPES))})
        else:
            removing = fields.text("remove", max_len=columns.KEY_MAX, required=True)
            fields.check()
            if not accounts.remove_list_item(db, company["_id"], found["key"], removing):
                fail("validation_failed", 422, fields={"remove": t("api_fields_remove")})
            contacts.drop_list_item(db, company["_id"], found["key"], removing)
        fresh = accounts.field_by_key(accounts.by_id(db, company["_id"]), found["key"])
        return ok(field_shape(fresh, contacts.count_by_field(db, company["_id"], [fresh])))

    data = body({"type"}, required=("type",))
    fields = Fields(data)
    kind = fields.text("type", max_len=10, required=True)
    if kind and kind not in columns.TYPES:
        fields.errors["type"] = t("api_fields_type", types=", ".join(columns.TYPES))
    fields.check()
    wrong = contacts.values_not_of_type(db, company["_id"], found["key"], kind)
    if wrong:
        fail("field_values", 409, extra={"contacts": wrong}, n=wrong)
    if accounts.set_field_type(db, company["_id"], found["key"], kind):
        contacts.normalize_field(db, company["_id"], found["key"], kind)
    filled = contacts.count_by_field(db, company["_id"], [found])
    return ok(field_shape({**found, "type": kind}, filled))


@api_route("/fields/<key>", methods=("DELETE",), scope="contacts:write")
def delete_field(key):
    """Borrar una columna y lo que los contactos tenían escrito en ella."""
    company = account()
    found = find_field(company, key)
    db = get_db()
    accounts.remove_field(db, company["_id"], found["key"])
    return ok({"key": found["key"], "deleted": True,
               "contacts": contacts.drop_field(db, company["_id"], found["key"])})


# ------------------------------------------------------------ las supresiones

@api_route("/suppressions", scope="contacts:read")
def list_suppressions():
    """A quién ya no se le escribe y por qué. Solo para mirar."""
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"]}
    reason = request.args.get("reason", "")
    if reason:
        if reason not in suppressions.REASONS:
            fail("validation_failed", 422, fields={"reason": t(
                "api_suppressions_reason", reasons=", ".join(suppressions.REASONS))})
        query["reason"] = reason
    email = request.args.get("email", "")[:254]
    if email:
        query["email_normalized"] = normalize_email(email)
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.suppressions.find(query).sort("_id", -1).limit(limit + 1))
    return ok(paged(rows, limit, lambda one: {
        "email": one.get("email", ""), "reason": one.get("reason"),
        "source": one.get("source", ""), "created_at": iso(one.get("created_at"))}))
