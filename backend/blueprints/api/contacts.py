"""Contactos, etiquetas, columnas y supresiones por la API (octubre de 2026).

Las mismas reglas que en el panel, porque son las mismas funciones:

  * **Nadie se duplica** (regla 5): cargar es un upsert por la dirección, en
    lote (`importer.write_batch`, el mismo motor que importar un CSV, con
    `bulkWrite`: regla 10). Un contacto nuevo necesita sitio en el plan y todas
    sus columnas; uno que ya está se actualiza. Cada carga dice de dónde salieron
    (`consent`), que es lo que hay que enseñar si alguien reclama.
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

from flask import request

from blueprints.api.core import (Fields, account, api_route, body, fail, iso, ok,
                                 page_cursor, page_limit, paged, path_id)
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
ROW_FIELDS = {"email", "name", "tags", "fields"}


def blocked_for(db, account_id, emails: list[str]) -> dict[str, dict]:
    """Las supresiones de esas direcciones, en una consulta (regla 10)."""
    if not emails:
        return {}
    return {one["email_normalized"]: one for one in db.suppressions.find(
        {"account_id": account_id, "email_normalized": {"$in": emails}},
        {"email_normalized": 1, "reason": 1, "created_at": 1})}


def contact_shape(one: dict, blocked: dict[str, dict], definitions: list[dict]) -> dict:
    """Cómo sale un contacto: sus datos, si puede recibir y de dónde salió."""
    block = blocked.get(one.get("email_normalized", ""))
    values = columns.values_of(one)
    consent = one.get("consent") or None
    return {
        "id": str(one["_id"]),
        "email": one.get("email", ""),
        "name": one.get("name", ""),
        "tags": list(one.get("tags") or []),
        "fields": {d["key"]: values.get(d["key"], "") for d in definitions},
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


def read_values(raw_values, definitions: list[dict]) -> tuple[dict[str, str], str, str]:
    """Las columnas que llegaron, por su clave y revisadas por su tipo.
    Devuelve (valores, motivo, cuál); un motivo es que no se pudo."""
    by_key = {one["key"]: one for one in definitions}
    if not isinstance(raw_values, dict):
        return {}, "bad_fields", ""
    values: dict[str, str] = {}
    for key, raw in raw_values.items():
        one = by_key.get(key)
        if one is None:
            return {}, "unknown_field", str(key)[:40]
        if raw is None:
            values[key] = ""
            continue
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            return {}, "bad_value", key
        parsed = columns.parse(str(raw), one.get("type", columns.TEXT))
        if parsed is None:
            return {}, "bad_value", key
        values[key] = parsed
    return values, "", ""


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
    if email:
        query["email_normalized"] = normalize_email(email)
    elif search:
        query["email_normalized"] = {"$regex": "^" + re.escape(normalize_email(search))}
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
    groups: dict[tuple, list] = {}
    seen: set[str] = set()
    for index, row in enumerate(rows):
        reason, detail = "", ""
        raw_email = row.get("email") if isinstance(row, dict) else None
        shown_email = raw_email if isinstance(raw_email, str) else ""
        if not isinstance(row, dict) or set(row) - ROW_FIELDS:
            reason = "bad_row"
        else:
            address = (importer.clean(raw_email) if isinstance(raw_email, str)
                       and len(raw_email) <= 254 else None)
            name = row.get("name", "")
            row_tags = row.get("tags", [])
            values: dict[str, str] = {}
            if not address:
                reason = "invalid_email"
            elif normalize_email(address) in seen:
                reason = "duplicate"
            elif not isinstance(name, str) or len(name) > NAME_MAX:
                reason = "bad_name"
            elif (not isinstance(row_tags, list) or len(row_tags) > TAGS_PER_ROW
                  or not all(isinstance(one, str) for one in row_tags)):
                reason = "bad_tags"
            elif any(one not in known_tags for one in row_tags):
                reason = "unknown_tag"
                detail = next(one for one in row_tags if one not in known_tags)[:40]
            else:
                values, reason, detail = read_values(row.get("fields", {}), definitions)
        if reason:
            entry = {"index": index, "email": shown_email[:254], "result": "rejected",
                     "reason": reason}
            if detail:
                entry["detail"] = detail
            results[index] = entry
            continue
        seen.add(normalize_email(address))
        tags_here = tuple(sorted(set(row_tags) | set(batch_tags)))
        groups.setdefault(tags_here, []).append(
            (index, (address, name.strip(), {k: v for k, v in values.items() if v})))

    token = locks.acquire(db, f"contacts:{company['_id']}", LOCK_SECONDS)
    if token is None or imports.running(db, company["_id"]):
        locks.release(db, f"contacts:{company['_id']}", token)
        fail("busy", 409, retry_after=5)
    try:
        counts = importer.new_counts()
        prepared = [item for items in groups.values() for item in items]
        keys = [normalize_email(item[1][0]) for item in prepared]
        existing = {one["email_normalized"] for one in db.contacts.find(
            {"account_id": company["_id"], "email_normalized": {"$in": keys}},
            {"email_normalized": 1})} if keys else set()
        # El conteo de activos cruza dos colecciones: solo si entra alguien nuevo.
        room = (max(0, accounts.contact_limit(company)
                    - contacts.active_count(db, company["_id"]))
                if any(key not in existing for key in keys) else 0)
        suppressed = suppressions.among(db, company["_id"], keys)
        consent_doc = contacts.consent_of(consent["source"], note)
        required = [one["key"] for one in definitions]
        domains_seen: set[str] = set()
        for group_tags, items in groups.items():
            done = importer.write_batch(
                db, company["_id"], [item[1] for item in items], tags=list(group_tags),
                consent=consent_doc, required=required, room=room, counts=counts,
                domains_seen=domains_seen, added_by=contacts.API, stop_when_full=False,
                max_domains=DOMAINS_PER_LOAD)
            room = done["room"]
            bad = {normalize_email(one) for one in done["bad"]}
            typos = {normalize_email(one): better for one, better in done["typos"]}
            for index, item in items:
                address, _, values = item
                key = normalize_email(address)
                what = done["outcome"].get(key, importer.NO_ROOM)
                entry = {"index": index, "email": address}
                if what in (importer.ADDED, importer.UPDATED):
                    entry["result"] = what
                else:
                    entry["result"] = "rejected"
                    entry["reason"] = what
                    if what == importer.INCOMPLETE:
                        entry["missing"] = [one["key"] for one in definitions
                                            if not values.get(one["key"])]
                if key in suppressed:
                    entry["warning"] = "suppressed"
                elif key in bad:
                    entry["warning"] = "undeliverable"
                if key in typos:
                    entry["suggestion"] = typos[key]
                results[index] = entry
    finally:
        locks.release(db, f"contacts:{company['_id']}", token)

    done_rows = [one for one in results if one]
    return ok({
        "added": sum(1 for one in done_rows if one["result"] == importer.ADDED),
        "updated": sum(1 for one in done_rows if one["result"] == importer.UPDATED),
        "rejected": sum(1 for one in done_rows if one["result"] == "rejected"),
        "results": done_rows,
    })


@api_route("/contacts/<contact_id>", methods=("PATCH",), scope="contacts:write")
def update_contact(contact_id):
    """Cambiar el correo, el nombre, las etiquetas (se reemplazan) o las
    columnas (se mezclan). Como en el panel, el contacto queda con todas sus
    columnas llenas."""
    data = body({"email", "name", "tags", "fields"})
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
    name = fields.text("name", max_len=NAME_MAX, default=found.get("name", "")) \
        if fields.has("name") else found.get("name", "")
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
    definitions = accounts.fields_of(company)
    values = dict(columns.values_of(found))
    if fields.has("fields"):
        given, reason, detail = read_values(data.get("fields"), definitions)
        if reason:
            fields.errors["fields"] = t("api_contacts_field_" + reason, what=detail)
        values.update(given)
    values = {key: value for key, value in values.items()
              if value and any(one["key"] == key for one in definitions)}
    missing = [one["key"] for one in definitions if not values.get(one["key"])]
    if missing and not fields.errors:
        fields.errors["fields"] = t("api_contacts_missing", what=", ".join(missing))
    fields.check()
    if not contacts.update(db, company["_id"], found["_id"], email=email, name=name,
                           tags=tags, values=values):
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
    return {"key": one["key"], "label": one.get("label", ""),
            "type": one.get("type", columns.TEXT), "filled": filled.get(one["key"], 0)}


@api_route("/fields", scope="contacts:read")
def list_fields():
    company = account()
    definitions = accounts.fields_of(company)
    filled = contacts.count_by_field(get_db(), company["_id"], definitions)
    return ok({"data": [field_shape(one, filled) for one in definitions],
               "limit": accounts.field_limit(company)})


@api_route("/fields", methods=("POST",), scope="contacts:write")
def create_field():
    data = body({"label", "type"}, required=("label", "type"))
    fields = Fields(data)
    label = fields.text("label", max_len=columns.LABEL_MAX, required=True)
    kind = fields.text("type", max_len=10, required=True)
    if kind and kind not in columns.TYPES:
        fields.errors["type"] = t("api_fields_type", types=", ".join(columns.TYPES))
    fields.check()
    company = account()
    if len(accounts.fields_of(company)) >= accounts.field_limit(company):
        fail("limit_reached", 409, what=t("api_limit_fields"),
             n=accounts.field_limit(company))
    key = accounts.add_field(get_db(), company["_id"], label=label, kind=kind)
    if key is None:
        fail("field_exists", 409)
    return ok({"key": key, "label": columns.clean_label(label), "type": kind,
               "filled": 0}, 201)


def find_field(company, key: str) -> dict:
    found = accounts.field_by_key(company, key)
    if found is None:
        fail("not_found", 404)
    return found


@api_route("/fields/<key>", methods=("PATCH",), scope="contacts:write")
def update_field(key):
    """Cambiarle el tipo, si todos sus valores encajan en el nuevo. El nombre no
    se cambia: es lo que nombran las plantillas."""
    data = body({"type"}, required=("type",))
    fields = Fields(data)
    kind = fields.text("type", max_len=10, required=True)
    if kind and kind not in columns.TYPES:
        fields.errors["type"] = t("api_fields_type", types=", ".join(columns.TYPES))
    fields.check()
    company = account()
    found = find_field(company, key)
    db = get_db()
    wrong = contacts.values_not_of_type(db, company["_id"], found["key"], kind)
    if wrong:
        fail("field_values", 409, extra={"contacts": wrong}, n=wrong)
    accounts.set_field_type(db, company["_id"], found["key"], kind)
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
