"""Plantillas, carpetas y fotos por la API (octubre de 2026).

Las mismas reglas que el Lienzo, porque son las mismas funciones
(`services/pieces.py`):

  * **Un lienzo se guarda solo si arma bien el correo y pasa la revisión
    antispam**, igual que con Guardar, y del JSON no se fía nada
    (`canvas.parse`). Las fotos que nombra tienen que ser de la cuenta: se
    suben antes con `POST /images`.
  * **El ZIP del Lienzo** se carga y se baja igual que en el editor.
  * **De quién sale y a dónde se responde** solo puede ser un remitente listo y
    un «Responder a» confirmado de la cuenta; otro es un error, nunca el
    predeterminado en silencio.
  * **Como mucho 300 plantillas por cuenta**: cada lienzo guarda sus imágenes
    fundidas, que no cuentan contra el tope de fotos.
  * Lo pesado (guardar un lienzo, cargar o bajar un ZIP) va de uno en uno por
    cuenta.

Las cargadas en HTML y las prediseñadas de antes se leen, se arman, se mueven,
se duplican y se borran, pero no se crean ni se les cambia el contenido: eso ya
no se ofrece tampoco en el panel.
"""

from __future__ import annotations

from contextlib import contextmanager

from flask import Response, request

from blueprints.api.account import TEMPLATE_LIMIT
from blueprints.api.core import (LIMITS, UPLOAD_MAX, Fields, account, api_route, body,
                                 fail, iso, ok, one_line, page_cursor, page_limit, paged,
                                 parse_id, path_id)
from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import lock as locks
from services import canvas, imaging, pieces, sender
from services import fields as columns
from services.security import rate_state

TRANSACTIONAL = "transactional"
PROMOTIONAL = "promotional"
TYPES = (TRANSACTIONAL, PROMOTIONAL)
SOURCES = (designs.CANVAS, designs.UPLOAD, designs.BUILT_IN)
SUBJECT_MAX = 150
MOVE_MAX = 200
LOCK_SECONDS = 90
# El enlace de baja de la vista armada: el de verdad es uno por destinatario.
UNSUBSCRIBE_EXAMPLE = Config.APP_BASE_URL + "/unsubscribe/ejemplo"
# Lo que se lee de cada plantilla para listarla: ni su lienzo ni su HTML.
LISTED = {"name": 1, "source": 1, "folder_id": 1, "send_from": 1, "reply_to": 1,
          "created_at": 1, "updated_at": 1}


# ------------------------------------------------------------ cómo salen

def folder_shown(company, folder_id) -> str | None:
    """La carpeta de una plantilla, si todavía existe."""
    found = designs.folder_of(company, folder_id)
    return str(found["id"]) if found else None


def template_shape(company, one) -> dict:
    return {"id": str(one["_id"]), "name": one.get("name", ""),
            "source": one.get("source"),
            "folder_id": folder_shown(company, one.get("folder_id")),
            "send_from": str(one["send_from"]) if one.get("send_from") else None,
            "reply_to": one.get("reply_to") or None,
            "created_at": iso(one.get("created_at")),
            "updated_at": iso(designs.changed_at(one))}


def full_shape(company, one) -> dict:
    """Una plantilla entera: lo de la lista, qué marcas sueltas y qué bloques
    nombra, y lo que tiene dentro según su clase."""
    html = sender.Piece(one, single=True).html(plan=None, unsubscribe_url="")
    marks, blocks = columns.marks_in(html, accounts.fields_of(company))
    shown = {**template_shape(company, one), "marks": marks, "blocks": blocks}
    if one.get("source") == designs.CANVAS:
        doc = canvas.read(one.get("canvas")) or canvas.blank()
        shown["canvas"] = doc
        shown["images"] = {name: imaging.url_of(name) for name in canvas.images_of(doc)}
    elif one.get("source") == designs.UPLOAD:
        shown["html"] = one.get("html", "")
    else:
        shown["template"] = one.get("template", "")
        shown["fields"] = dict(one.get("fields") or {})
    return shown


def find_template(db, company, raw: str) -> dict:
    found = designs.by_id(db, company["_id"], path_id(raw))
    if found is None:
        fail("not_found", 404)
    return found


# ------------------------------------------------------------ lo que llega

def folder_from(company, data: dict, fields: Fields):
    """La carpeta que llegó: una de la cuenta, o None (null) para ninguna."""
    raw = data.get("folder_id")
    if raw is None:
        return None
    found = designs.folder_of(company, parse_id(raw) if isinstance(raw, str) else None)
    if found is None:
        fields.errors["folder_id"] = t("api_field_ref")
        return None
    return found["id"]


def sending_from(company, data: dict, fields: Fields, current: dict | None = None) -> dict | None:
    """«Sale de» y «Responder a», si llegaron (null es el predeterminado). Lo
    que no llega se queda como estaba. None si no llegó ninguno."""
    if "send_from" not in data and "reply_to" not in data:
        return None
    choice = {"send_from": (current or {}).get("send_from"),
              "reply_to": (current or {}).get("reply_to")}
    if "send_from" in data:
        raw = data["send_from"]
        found = (accounts.from_of(company, parse_id(raw)) if isinstance(raw, str)
                 else None)
        if raw is None:
            choice["send_from"] = None
        elif found is None or not found["ready"]:
            fields.errors["send_from"] = t("api_templates_send_from")
        else:
            choice["send_from"] = found["id"]
    if "reply_to" in data:
        raw = data["reply_to"]
        if raw is None:
            choice["reply_to"] = None
        elif not isinstance(raw, str) or raw not in accounts.reply_tos_of(company):
            fields.errors["reply_to"] = t("api_templates_reply_to")
        else:
            choice["reply_to"] = raw
    return choice


def name_from(fields: Fields, *, required: bool) -> str:
    name = designs.clean_name(fields.text("name", max_len=designs.NAME_MAX,
                                          required=required))
    if required and not name and "name" not in fields.errors:
        fields.errors["name"] = t("api_field_required")
    return name


def room_for(db, company, wanted: int = 1) -> None:
    if designs.count(db, company["_id"]) + wanted > TEMPLATE_LIMIT:
        fail("limit_reached", 409, what=t("api_limit_templates"), n=TEMPLATE_LIMIT)


@contextmanager
def heavy(db, company):
    """Guardar un lienzo o cargar y bajar un ZIP: de uno en uno por cuenta."""
    name = f"templates:{company['_id']}"
    token = locks.acquire(db, name, LOCK_SECONDS)
    if token is None:
        fail("busy", 409, retry_after=5)
    try:
        yield
    finally:
        locks.release(db, name, token)


def canvas_ready(db, company, raw):
    """Un lienzo que llegó en JSON, revisado como al guardar. Devuelve el
    documento y sus imágenes fundidas, o responde 422 con el porqué."""
    doc = canvas.parse(raw) if isinstance(raw, dict) else None
    if doc is None:
        fail("validation_failed", 422,
             fields={"canvas": pieces.canvas_explain(["broken"])})
    refused = pieces.canvas_refused(db, company, doc)
    if refused:
        fail("validation_failed", 422, fields={"canvas": refused})
    fused = pieces.canvas_fused(db, company, doc)
    if fused is None:
        fail("validation_failed", 422,
             fields={"canvas": pieces.canvas_explain(["too_big"])})
    return doc, fused


def upload(allowed: set[str]) -> tuple[bytes, dict[str, str]]:
    """Un archivo en multipart (`file`) y los campos de texto que la ruta
    conoce. Otra cosa es un error, como en el JSON."""
    if request.mimetype != "multipart/form-data":
        fail("unsupported_media_type", 415)
    unknown = [name for name in list(request.form) + list(request.files)
               if name != "file" and name not in allowed]
    if unknown:
        fail("validation_failed", 422,
             fields={name: t("api_field_unknown") for name in unknown})
    archivo = request.files.get("file")
    if archivo is None or not archivo.filename:
        fail("validation_failed", 422, fields={"file": t("api_field_required")})
    return archivo.read(imaging.MAX_UPLOAD + 1), {
        name: request.form.get(name, "") for name in allowed if name in request.form}


# ------------------------------------------------------------ las plantillas

@api_route("/templates", scope="templates:read")
def list_templates():
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"]}
    wanted = request.args.get("folder_id", "")
    if wanted == "none":
        query["folder_id"] = {"$exists": False}
    elif wanted:
        found = designs.folder_of(company, parse_id(wanted))
        if found is None:
            fail("validation_failed", 422, fields={"folder_id": t("api_field_ref")})
        query["folder_id"] = found["id"]
    source = request.args.get("source", "")
    if source:
        if source not in SOURCES:
            fail("validation_failed", 422, fields={"source": t(
                "api_templates_source", sources=", ".join(SOURCES))})
        query["source"] = source
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.designs.find(query, LISTED).sort("_id", -1).limit(limit + 1))
    return ok({**paged(rows, limit, lambda one: template_shape(company, one)),
               "limit": TEMPLATE_LIMIT})


@api_route("/templates/<template_id>", scope="templates:read")
def get_template(template_id):
    company = account()
    return ok(full_shape(company, find_template(get_db(), company, template_id)))


@api_route("/templates/<template_id>/render", methods=("POST",), scope="templates:read")
def template_render(template_id):
    """El correo tal como saldría, con los datos de un contacto o los que
    lleguen: transaccional (sin baja ni marca de agua) o promocional. No envía
    ni guarda nada."""
    data = body({"type", "contact_id", "subject", "data"})
    fields = Fields(data)
    kind = fields.text("type", max_len=20, default=PROMOTIONAL) or PROMOTIONAL
    if kind not in TYPES:
        fields.errors["type"] = t("api_emails_type", types=", ".join(TYPES))
    subject = fields.text("subject", max_len=SUBJECT_MAX) if fields.has("subject") else None
    if subject and not fields.errors.get("subject") and not one_line(subject):
        fields.errors["subject"] = t("api_field_one_line")
    contact_id = fields.object_id("contact_id")
    values = fields.fill_data()
    fields.check()

    company = account()
    db = get_db()
    found = find_template(db, company, template_id)
    person = None
    if contact_id is not None:
        person = contacts.by_id(db, company["_id"], contact_id)
        if person is None:
            fail("validation_failed", 422, fields={"contact_id": t("api_field_ref")})
    definitions = accounts.fields_of(company)
    html = sender.Piece(found, single=kind == TRANSACTIONAL).html(
        plan=accounts.plan_of(company), unsubscribe_url=UNSUBSCRIBE_EXAMPLE,
        postal=accounts.postal_of(company))
    named = html + "\n" + (subject or "")
    marks, blocks = columns.marks_in(named, definitions, values)
    filled = columns.fill(html, person, definitions, data=values)
    return ok({
        "type": kind,
        "subject": (columns.single_line(columns.fill(subject, person, definitions,
                                                     html=False, data=values))
                    if subject is not None else None),
        "html": filled, "text": sender.plain_text(filled),
        "bytes": len(filled.encode("utf-8")),
        "marks": marks, "blocks": blocks,
        "missing": columns.lacking(named, person, definitions, values),
    })


@api_route("/templates/check", methods=("POST",), scope="templates:read")
def check_template():
    """La revisión de un lienzo sin guardarlo: la misma que pide el editor. El
    nombre es opcional, y es la primera regla de la lista."""
    data = body({"canvas", "name"}, required=("canvas",))
    fields = Fields(data)
    name = fields.text("name", max_len=designs.NAME_MAX)
    fields.check()
    raw = data.get("canvas")
    doc = canvas.parse(raw) if isinstance(raw, dict) else None
    return ok(pieces.review(get_db(), account(), doc,
                            named=bool(designs.clean_name(name))))


@api_route("/templates/<template_id>/zip", scope="templates:read", limit="templates")
def template_zip(template_id):
    """El ZIP del Lienzo, el mismo que baja el editor."""
    company = account()
    db = get_db()
    found = find_template(db, company, template_id)
    if found.get("source") != designs.CANVAS:
        fail("not_found", 404)
    with heavy(db, company):
        name, data = pieces.canvas_zip(db, company, found)
    return Response(data, mimetype="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{name}"'})


@api_route("/templates", methods=("POST",), scope="templates:write", limit="templates")
def create_template():
    data = body({"name", "canvas", "folder_id", "send_from", "reply_to"},
                required=("name", "canvas"))
    fields = Fields(data)
    company = account()
    name = name_from(fields, required=True)
    folder_id = folder_from(company, data, fields)
    choice = sending_from(company, data, fields)
    fields.check()
    db = get_db()
    room_for(db, company)
    with heavy(db, company):
        doc, (grounds, shades) = canvas_ready(db, company, data.get("canvas"))
        new_id = designs.save_canvas(db, company["_id"], name=name, doc=doc,
                                     backgrounds=grounds, shades=shades, folder_id=folder_id)
    if choice is not None:
        designs.set_sending(db, company["_id"], new_id, **choice)
    return ok(full_shape(company, designs.by_id(db, company["_id"], new_id)), 201)


@api_route("/templates/import", methods=("POST",), scope="templates:write",
           limit="templates", max_bytes=UPLOAD_MAX)
def import_template():
    """Cargar el ZIP que baja el Lienzo (multipart: `file`, y si quieres `name`
    y `folder_id`). Pasa lo mismo que al cargarlo en el panel."""
    raw, given = upload({"name", "folder_id"})
    if len(raw) > imaging.MAX_UPLOAD:
        fail("too_large", 413)
    fields = Fields(given)
    company = account()
    name = name_from(fields, required=False)
    folder_id = folder_from(company, {"folder_id": given.get("folder_id") or None}, fields)
    if not imaging.is_zip(raw):
        fields.errors["file"] = t("designs_only_zip")
    fields.check()
    db = get_db()
    room_for(db, company)
    with heavy(db, company):
        new_id, wrong = pieces.canvas_from_pack(db, company, raw, name=name,
                                                filename="plantilla", folder_id=folder_id)
    if new_id is None:
        fail("validation_failed", 422, fields={"file": wrong})
    return ok(full_shape(company, designs.by_id(db, company["_id"], new_id)), 201)


@api_route("/templates/<template_id>", methods=("PATCH",), scope="templates:write")
def update_template(template_id):
    """Su nombre, su carpeta, de quién sale y a dónde se responde, y en una del
    lienzo, el lienzo entero."""
    data = body({"name", "canvas", "folder_id", "send_from", "reply_to"})
    company = account()
    db = get_db()
    found = find_template(db, company, template_id)
    fields = Fields(data)
    name = name_from(fields, required=False) if fields.has("name") else None
    if fields.has("name") and not name and "name" not in fields.errors:
        fields.errors["name"] = t("api_field_required")
    folder_id = folder_from(company, data, fields) if fields.has("folder_id") else designs.KEEP
    choice = sending_from(company, data, fields, current=found)
    if fields.has("canvas") and found.get("source") != designs.CANVAS:
        fields.errors["canvas"] = t("api_templates_not_canvas")
    fields.check()

    if fields.has("canvas"):
        if limit_hit(db, company):
            fail("rate_limited", 429, retry_after=60)
        with heavy(db, company):
            doc, (grounds, shades) = canvas_ready(db, company, data.get("canvas"))
            designs.update_canvas(db, company["_id"], found["_id"], name=name, doc=doc,
                                  backgrounds=grounds, shades=shades, folder_id=folder_id)
            # Lo que la versión de antes nombraba y esta ya no.
            pieces.drop_unused(db, company["_id"], pieces.images_in(found))
    else:
        changes: dict = {}
        if name is not None:
            changes["name"] = name
        update: dict = {}
        if folder_id is None:
            update["$unset"] = {"folder_id": ""}
        elif folder_id is not designs.KEEP:
            changes["folder_id"] = folder_id
        if changes:
            update["$set"] = {**changes, "updated_at": designs.now()}
        if update:
            db.designs.update_one({"_id": found["_id"], "account_id": company["_id"]}, update)
    if choice is not None:
        designs.set_sending(db, company["_id"], found["_id"], **choice)
    return ok(full_shape(company, designs.by_id(db, company["_id"], found["_id"])))


def limit_hit(db, company) -> bool:
    """Cambiar el lienzo cuenta como guardar uno: el mismo límite por minuto,
    que la puerta no pone porque cambiar un nombre no lo gasta."""
    allowed, _, _ = rate_state(db, f"api:templates:{company['_id']}", *LIMITS["templates"])
    return not allowed


@api_route("/templates/<template_id>/duplicate", methods=("POST",),
           scope="templates:write")
def duplicate_template(template_id):
    data = body({"name"})
    fields = Fields(data)
    name = name_from(fields, required=False)
    fields.check()
    company = account()
    db = get_db()
    found = find_template(db, company, template_id)
    room_for(db, company)
    new_id = designs.duplicate(db, company["_id"], found["_id"], name=name or t(
        "designs_copy_name", name=found.get("name", "")))
    return ok(full_shape(company, designs.by_id(db, company["_id"], new_id)), 201)


@api_route("/templates/<template_id>", methods=("DELETE",), scope="templates:write")
def delete_template(template_id):
    """Borrarla, y con ella las imágenes que ninguna otra nombra. Una foto que
    salió en un envío se retira y no se borra."""
    company = account()
    db = get_db()
    found = find_template(db, company, template_id)
    gone = designs.remove(db, company["_id"], found["_id"])
    if gone:
        pieces.drop_unused(db, company["_id"], pieces.images_in(gone))
    return ok({"id": str(found["_id"]), "deleted": True})


@api_route("/templates/move", methods=("POST",), scope="templates:write")
def move_templates():
    """Pasar plantillas a una carpeta (o a ninguna, con null). Las que no son
    de la cuenta no se tocan."""
    data = body({"ids", "folder_id"}, required=("ids",))
    fields = Fields(data)
    raw = data.get("ids")
    ids = []
    if (not isinstance(raw, list) or not 1 <= len(raw) <= MOVE_MAX
            or not all(isinstance(one, str) and parse_id(one) for one in raw)):
        fields.errors["ids"] = t("api_templates_ids", n=MOVE_MAX)
    else:
        ids = [parse_id(one) for one in raw]
    company = account()
    if "folder_id" not in data:
        fields.errors["folder_id"] = t("api_field_required")
    folder_id = folder_from(company, data, fields)
    fields.check()
    moved = designs.move_many(get_db(), company, ids, folder_id)
    return ok({"moved": moved})


# ------------------------------------------------------------ las carpetas

def folder_shape(one, counted: dict) -> dict:
    return {"id": str(one["id"]), "name": one.get("name", ""),
            "color": one.get("color", ""), "templates": counted.get(one["id"], 0)}


def find_folder(company, raw: str) -> dict:
    found = designs.folder_of(company, path_id(raw))
    if found is None:
        fail("not_found", 404)
    return found


FOLDER_ERRORS = {"required": "api_field_required", "taken": "api_folders_taken",
                 "color": "api_folders_color"}


def folder_failed(wrong: str, field: str) -> None:
    if wrong == "full":
        fail("limit_reached", 409, what=t("api_limit_folders"), n=designs.FOLDER_LIMIT)
    fail("validation_failed", 422, fields={field: t(
        FOLDER_ERRORS.get(wrong, "api_field_required"), colors=", ".join(designs.FOLDER_COLORS))})


@api_route("/folders", scope="templates:read")
def list_folders():
    company = account()
    counted = {row["_id"]: row["n"] for row in get_db().designs.aggregate([
        {"$match": {"account_id": company["_id"], "folder_id": {"$exists": True}}},
        {"$group": {"_id": "$folder_id", "n": {"$sum": 1}}}])}
    return ok({"data": [folder_shape(one, counted) for one in designs.folders_of(company)],
               "limit": designs.FOLDER_LIMIT, "colors": list(designs.FOLDER_COLORS)})


@api_route("/folders", methods=("POST",), scope="templates:write")
def create_folder():
    data = body({"name", "color"}, required=("name",))
    fields = Fields(data)
    name = fields.text("name", max_len=designs.FOLDER_NAME_MAX, required=True)
    color = fields.text("color", max_len=10, default="gray") or "gray"
    fields.check()
    company = account()
    new_id, wrong = designs.add_folder(get_db(), company, name, color)
    if new_id is None:
        folder_failed(wrong, "color" if wrong == "color" else "name")
    return ok(folder_shape({"id": new_id, "name": designs.clean_folder_name(name),
                            "color": color}, {}), 201)


@api_route("/folders/<folder_id>", methods=("PATCH",), scope="templates:write")
def update_folder(folder_id):
    """Cambiarle el nombre o el color. Lo mismo que tenía no es un error."""
    data = body({"name", "color"})
    fields = Fields(data)
    name = fields.text("name", max_len=designs.FOLDER_NAME_MAX) if fields.has("name") else None
    color = fields.text("color", max_len=10) if fields.has("color") else None
    fields.check()
    company = account()
    db = get_db()
    found = find_folder(company, folder_id)
    if name is not None:
        wrong = designs.rename_folder(db, company, found["id"], name)
        if wrong not in ("", "same"):
            folder_failed(wrong, "name")
        company = accounts.by_id(db, company["_id"])
    if color is not None:
        wrong = designs.recolor_folder(db, company, found["id"], color)
        if wrong not in ("", "same"):
            folder_failed(wrong, "color")
        company = accounts.by_id(db, company["_id"])
    counted = {found["id"]: db.designs.count_documents(
        {"account_id": company["_id"], "folder_id": found["id"]})}
    return ok(folder_shape(designs.folder_of(company, found["id"]), counted))


@api_route("/folders/<folder_id>", methods=("DELETE",), scope="templates:write")
def delete_folder(folder_id):
    """Eliminarla. Sus plantillas no se borran: quedan sin carpeta."""
    company = account()
    found = find_folder(company, folder_id)
    designs.remove_folder(get_db(), company, found["id"])
    return ok({"id": str(found["id"]), "deleted": True})


# ------------------------------------------------------------ las fotos

@api_route("/images", methods=("POST",), scope="templates:write", limit="images",
           max_bytes=UPLOAD_MAX)
def upload_image():
    """Una foto para un lienzo (multipart: `file`). Devuelve el nombre que se
    pone en el `name` de una imagen del lienzo. Cuenta contra el tope de fotos
    de tu plan."""
    raw, _ = upload(set())
    company = account()
    db = get_db()
    if not pieces.photo_room(db, company):
        fail("limit_reached", 409, what=t("api_limit_images"), n=pieces.photo_limit(company))
    photo, wrong = pieces.save_photo(db, company, raw)
    if photo is None:
        fail("validation_failed", 422, fields={"file": wrong})
    return ok(photo, 201)
