"""Los correos de la API: uno a una persona, transaccional o promocional
(octubre de 2026).

  * **Transaccional**: un recibo, un código, un aviso de su pedido. A cualquier
    dirección, sin baja ni marca de agua y sin contar clics. Solo lo frenan un
    rebote permanente o una queja en esta cuenta: quien se dio de baja de las
    promociones sigue necesitando su recibo (la excepción a la regla 1).
  * **Promocional**: una campaña de una persona. Solo a un contacto completo y
    sin ninguna supresión, con su baja y la marca de agua de su plan.

Los dos gastan cuota, respetan la pausa y la demostración, y salen de un
remitente de la cuenta. Lo arma y lo manda `sender.send_one()`, que sigue
siendo el único sitio que le escribe a alguien. Con una llave de prueba se
revisa y se arma todo, pero no sale nada ni se guarda nada.
"""

from __future__ import annotations

from flask import request

from blueprints.api.core import (Fields, account, api_route, body, fail, is_test, iso,
                                 key, ok, one_line, page_cursor, page_limit, paged,
                                 parse_id, path_id)
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import design as designs
from models import event as events
from models import message as messages
from models.account import normalize_email
from services import canvas, importer, sender

SUBJECT_MAX = campaigns.SUBJECT_MAX
TEXT_MAX = campaigns.BODY_MAX

# Lo que `send_one` dice que no puede salir, y con qué estado HTTP.
REFUSED = {"not_a_contact": 422, "contact_incomplete": 422, "suppressed": 422,
           "undeliverable": 422, "demo_address": 422, "missing_data": 422,
           "bad_subject": 422, "template_draft": 422}


def message_shape(one: dict) -> dict:
    return {"id": str(one["_id"]), "type": one.get("kind"), "to": one.get("to", ""),
            "contact_id": str(one["contact_id"]) if one.get("contact_id") else None,
            "subject": one.get("subject", ""),
            "template_id": str(one["template_id"]) if one.get("template_id") else None,
            "from": one.get("from", ""), "reply_to": one.get("reply_to", ""),
            "status": one.get("status"), "error": one.get("error"),
            "created_at": iso(one.get("created_at")), "sent_at": iso(one.get("sent_at"))}


def replayed(found: dict):
    response = ok(message_shape(found), 201 if found.get("status") == messages.SENT else 202)
    response.headers["Idempotent-Replayed"] = "true"
    return response


def chosen_design(company, data: dict, fields: Fields) -> dict:
    """De dónde sale lo que dice: una plantilla de la cuenta o un texto, con
    «Sale de» y «Responder a» si llegaron (solo de la cuenta)."""
    if fields.has("template_id") == fields.has("text"):
        fields.errors["template_id"] = t("api_emails_one_body")
        return {}
    design: dict = {}
    if fields.has("template_id"):
        found_id = fields.object_id("template_id", required=True)
        found = designs.by_id(get_db(), company["_id"], found_id) if found_id else None
        if found_id and found is None:
            fields.errors["template_id"] = t("api_field_ref")
        elif designs.is_draft(found):
            fields.errors["template_id"] = t("api_template_draft")
        if fields.has("logo"):
            fields.errors["logo"] = t("api_emails_logo")
        design = dict(found or {})
    else:
        text = fields.text("text", max_len=TEXT_MAX, required=True)
        design = {"source": sender.WRITTEN, "body": text}
    if fields.has("from_id"):
        raw = data.get("from_id")
        picked = accounts.from_of(company, parse_id(raw)) if isinstance(raw, str) else None
        if picked is None or not picked["ready"]:
            fields.errors["from_id"] = t("api_templates_send_from")
        else:
            design["send_from"] = picked["id"]
    if fields.has("reply_to"):
        raw = data.get("reply_to")
        if not isinstance(raw, str) or raw not in accounts.reply_tos_of(company):
            fields.errors["reply_to"] = t("api_templates_reply_to")
        else:
            design["reply_to"] = raw
    return design


@api_route("/emails", methods=("POST",), scope="emails:send", limit="emails",
           idempotent=True)
def send_email():
    data = body({"to", "type", "subject", "template_id", "text", "logo", "data",
                 "from_id", "reply_to"}, required=("to", "type", "subject"))
    fields = Fields(data)
    company = account()
    raw_to = fields.text("to", max_len=254, required=True)
    to = importer.clean(raw_to) if raw_to else None
    if raw_to and not to:
        fields.errors["to"] = t("api_contacts_email")
    kind = fields.text("type", max_len=20, required=True)
    if kind and kind not in messages.TYPES:
        fields.errors["type"] = t("api_emails_type", types=", ".join(messages.TYPES))
    subject = fields.text("subject", max_len=SUBJECT_MAX, required=True)
    if subject and "subject" not in fields.errors and not one_line(subject):
        fields.errors["subject"] = t("api_field_one_line")
    logo = fields.boolean("logo")
    values = fields.fill_data()
    design = chosen_design(company, data, fields)
    fields.check()

    db = get_db()
    test = is_test()
    wanted = request.headers.get("Idempotency-Key") if not test else None
    if wanted:
        # Uno que se quedó a medias (o salió) no se manda otra vez, aunque la
        # respuesta guardada de la puerta ya haya vencido.
        found = messages.by_request(db, company["_id"], key()["_id"], wanted)
        if found is not None and found.get("status") != messages.FAILED:
            return replayed(found)
        if found is not None:
            messages.forget(db, found["_id"])
    if (not test and design.get("source") == designs.CANVAS
            and (design.get("canvas") or {}).get("v") != canvas.VERSION):
        # Guardada cuando el lienzo iba por diapositivas, como en una campaña.
        design = {**designs.upgrade_canvas(db, company["_id"], design),
                  **{name: design[name] for name in ("send_from", "reply_to")
                     if name in design}}

    done = sender.send_one(db, company, kind=kind, to=to, design=design,
                           subject=" ".join(subject.split()), data=values, logo=logo,
                           key_id=key()["_id"], request_key=wanted, simulate=test)
    refused = done.get("refused")
    if refused == "cannot_send":
        fail("cannot_send", 409, extra={"blocked": [
            {"code": why, "message": t("send_blocked_" + why)} for why in done["blocked"]]})
    if refused == "throttled":
        fail("throttled", 503, retry_after=2)
    if refused == "replay":
        return replayed(messages.by_request(db, company["_id"], key()["_id"], wanted))
    if refused:
        extra = {"missing": done["missing"]} if done.get("missing") else None
        fail(refused, REFUSED[refused], extra=extra)
    if done["status"] == "simulated":
        return ok({"status": "simulated", "type": kind, "to": to,
                   "preview": done["preview"]})
    if done["status"] == messages.FAILED:
        fail("delivery_failed", 502, extra={"email": message_shape(done["message"])})
    return ok(message_shape(done["message"]), 201)


@api_route("/emails", scope="emails:send")
def list_emails():
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"]}
    status = request.args.get("status", "")
    if status:
        if status not in messages.STATUSES:
            fail("validation_failed", 422, fields={"status": t(
                "api_emails_status", statuses=", ".join(messages.STATUSES))})
        query["status"] = status
    kind = request.args.get("type", "")
    if kind:
        if kind not in messages.TYPES:
            fail("validation_failed", 422, fields={"type": t(
                "api_emails_type", types=", ".join(messages.TYPES))})
        query["kind"] = kind
    to = request.args.get("to", "")[:254]
    if to:
        query["to_normalized"] = normalize_email(to)
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.messages.find(query).sort("_id", -1).limit(limit + 1))
    return ok(paged(rows, limit, message_shape))


@api_route("/emails/<email_id>", scope="emails:send")
def get_email(email_id):
    """Uno, con lo que pasó después de salir: cuándo se entregó, se abrió,
    se pulsó, rebotó o se marcó como spam (lo primero de cada cosa)."""
    company = account()
    db = get_db()
    found = messages.by_id(db, company["_id"], path_id(email_id))
    if found is None:
        fail("not_found", 404)
    _, page = events.recipients(db, company["_id"], found["_id"], limit=1)
    happened = page[0]["at"] if page else {}
    return ok({**message_shape(found),
               "events": {kind: iso(when) for kind, when in sorted(happened.items())}})
