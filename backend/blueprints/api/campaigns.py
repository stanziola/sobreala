"""Las campañas por la API (octubre de 2026): las mismas de Masivo.

Una campaña sale a tus contactos (todos, o los de unas etiquetas, y si se
quiere solo a los que cumplan unas condiciones sobre sus columnas) con una
plantilla o un texto, y se manda las veces que haga falta. Por la API se arma,
se cambia y se borra, y se manda ya o se programa: **la manda el proceso en
segundo plano**, por tandas, así la respuesta llega enseguida (202) y la
campaña dice cómo va. Las reglas de siempre siguen: la baja y la marca de agua
van en cada correo, los suprimidos se saltan sin gastar cuota, y a un contacto
sin todas sus columnas no se le manda nada.

Mientras está saliendo no se cambia, no se borra ni se reprograma.
"""

from __future__ import annotations

from flask import request

from blueprints.api.core import (Fields, account, api_route, body, fail, is_test, iso,
                                 ok, one_line, page_cursor, page_limit, paged, path_id,
                                 when_of)
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import contact as contacts
from models import design as designs
from services import audience as conditions
from services import sender

TAGS_MAX = 20


def blocked_shape(reasons) -> list[dict]:
    return [{"code": why, "message": t("send_blocked_" + why)} for why in reasons or []]


def campaign_shape(one: dict) -> dict:
    return {"id": str(one["_id"]), "subject": one.get("subject", ""),
            "source": "text" if campaigns.written(one) else "template",
            "template_id": str(one["design_id"]) if one.get("design_id") else None,
            "text": one.get("body") or None, "logo": bool(one.get("logo")),
            "tags": campaigns.tags_of(one),
            "filters": campaigns.filters_of(one),
            "filters_text": one.get("filters_text") or None,
            "status": one.get("status"),
            "auto_send": bool(one.get("auto_send")),
            "scheduled_at": iso(one.get("scheduled_at")),
            "progress": {"position": one.get("position", 0), "total": one.get("total", 0),
                         "sent": one.get("sent", 0), "skipped": one.get("skipped", 0),
                         "failed": one.get("failed", 0)},
            "waiting": blocked_shape(one.get("waiting")),
            "send_id": str(one["run_id"]) if one.get("run_id") else None,
            "created_at": iso(one.get("created_at")),
            "started_at": iso(one.get("started_at")),
            "finished_at": iso(one.get("finished_at"))}


def find_campaign(db, company, raw: str) -> dict:
    found = campaigns.by_id(db, company["_id"], path_id(raw))
    if found is None or found.get("kind") == campaigns.SINGLE:
        fail("not_found", 404)
    return found


def chosen(company, found):
    """La condición de Mongo de sus condiciones. `conditions.Stale` si una ya
    no vale con las columnas de hoy."""
    return conditions.query(campaigns.filters_of(found), accounts.fields_of(company))


def stale(company, found) -> bool:
    try:
        chosen(company, found)
    except conditions.Stale:
        return True
    return False


def audience(db, company, found) -> int:
    """A cuántos saldría hoy. Con una condición que ya no vale, a nadie."""
    try:
        wanted = chosen(company, found)
    except conditions.Stale:
        return 0
    return contacts.matching_count(db, company["_id"], tags=campaigns.tags_of(found),
                                   complete=accounts.fields_of(company), audience=wanted)


def blocked_for(company, found) -> list[str]:
    """Lo que la frenaría: lo de la cuenta y, de ella, una condición vieja."""
    return sender.blocked(company) + (["filters"] if stale(company, found) else [])


def not_sending(found) -> None:
    if found.get("status") == campaigns.SENDING:
        fail("campaign_sending", 409)


def content_from(db, company, data: dict, fields: Fields, found=None) -> dict:
    """El asunto, de dónde sale lo que dice y a quién va, revisados. En un
    cambio, lo que no llega se queda como estaba."""
    out = {"subject": (found or {}).get("subject", ""),
           "design_id": (found or {}).get("design_id"),
           "body": (found or {}).get("body", ""), "logo": bool((found or {}).get("logo")),
           "tags": campaigns.tags_of(found) if found else [],
           "filters": campaigns.filters_of(found)}
    if fields.has("subject") or found is None:
        subject = fields.text("subject", max_len=campaigns.SUBJECT_MAX, required=True)
        if subject and "subject" not in fields.errors and not one_line(subject):
            fields.errors["subject"] = t("api_field_one_line")
        out["subject"] = campaigns.clean_subject(subject)
    if fields.has("template_id") and fields.has("text"):
        fields.errors["template_id"] = t("api_emails_one_body")
    elif fields.has("template_id"):
        found_id = fields.object_id("template_id", required=True)
        if found_id and designs.by_id(db, company["_id"], found_id) is None:
            fields.errors["template_id"] = t("api_field_ref")
        out.update(design_id=found_id, body="", logo=False)
    elif fields.has("text"):
        out.update(design_id=None, body=fields.text("text", max_len=campaigns.BODY_MAX,
                                                    required=True))
    elif found is None:
        fields.errors["template_id"] = t("api_emails_one_body")
    if fields.has("logo"):
        logo = fields.boolean("logo")
        if logo and out["design_id"]:
            fields.errors["logo"] = t("api_emails_logo")
        out["logo"] = logo and bool(accounts.logo_of(company))
    if fields.has("tags"):
        wanted = fields.strings("tags", max_items=TAGS_MAX, max_len=accounts.TAG_LENGTH)
        if wanted is not None:
            unknown = [one for one in wanted if one not in accounts.tags_of(company)]
            if unknown:
                fields.errors["tags"] = t("api_contacts_unknown_tags", what=", ".join(unknown[:5]))
            out["tags"] = list(dict.fromkeys(wanted))
    if fields.has("filters"):
        # Las condiciones (octubre de 2026), validadas como en Masivo; `null`
        # las quita. Un problema por regla, con su número.
        clean, problems = conditions.parse(data.get("filters"), accounts.fields_of(company))
        for index, why in problems:
            name = f"filters.rules[{index}]" if index >= 0 else "filters"
            fields.errors.setdefault(name, conditions.problem_text(index, why))
        out["filters"] = clean
    return out


def future(raw, fields: Fields, name: str = "scheduled_at"):
    when = when_of(raw, name, fields)
    if when is not None and when <= accounts.now():
        fields.errors[name] = t("api_campaigns_past")
    return when


# ------------------------------------------------------------ leer

@api_route("/campaigns", scope="campaigns:read")
def list_campaigns():
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"], "kind": {"$ne": campaigns.SINGLE}}
    status = request.args.get("status", "")
    if status:
        if status not in campaigns.STATES:
            fail("validation_failed", 422, fields={"status": t(
                "api_emails_status", statuses=", ".join(campaigns.STATES))})
        query["status"] = status
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.campaigns.find(query).sort("_id", -1).limit(limit + 1))
    return ok(paged(rows, limit, campaign_shape))


@api_route("/campaigns/<campaign_id>", scope="campaigns:read")
def get_campaign(campaign_id):
    """Una, con a cuántos saldría hoy y qué la frenaría."""
    company = account()
    db = get_db()
    found = find_campaign(db, company, campaign_id)
    return ok({**campaign_shape(found), "audience": audience(db, company, found),
               "blocked": blocked_shape(blocked_for(company, found))})


# ------------------------------------------------------------ cambiar

@api_route("/campaigns", methods=("POST",), scope="campaigns:write", idempotent=True)
def create_campaign():
    """Guardarla. Con `scheduled_at` queda programada y sale sola a esa hora;
    sin él espera a que la mandes."""
    data = body({"subject", "template_id", "text", "logo", "tags", "filters",
                 "scheduled_at"}, required=("subject",))
    fields = Fields(data)
    company = account()
    db = get_db()
    made = content_from(db, company, data, fields)
    when = future(data.get("scheduled_at"), fields) if fields.has("scheduled_at") else None
    fields.check()
    new_id = campaigns.create(db, company["_id"], subject=made["subject"],
                              design_id=made["design_id"], tags=made["tags"],
                              scheduled_at=when or accounts.now(), body=made["body"],
                              logo=made["logo"], auto_send=when is not None,
                              filters=made["filters"],
                              filters_text=conditions.describe(
                                  made["filters"], accounts.fields_of(company)))
    return ok(campaign_shape(campaigns.by_id(db, company["_id"], new_id)), 201)


@api_route("/campaigns/<campaign_id>", methods=("PATCH",), scope="campaigns:write")
def update_campaign(campaign_id):
    """Cambiar el asunto, lo que dice o a quién va. La hora se cambia con
    `schedule`. Una que ya salió se puede corregir para la próxima vez."""
    data = body({"subject", "template_id", "text", "logo", "tags", "filters"})
    company = account()
    db = get_db()
    found = find_campaign(db, company, campaign_id)
    not_sending(found)
    fields = Fields(data)
    made = content_from(db, company, data, fields, found)
    fields.check()
    # La frase se escribe otra vez con los nombres de hoy, también si las
    # condiciones no cambiaron.
    if not campaigns.update(db, company["_id"], found["_id"], subject=made["subject"],
                            design_id=made["design_id"], tags=made["tags"],
                            scheduled_at=found.get("scheduled_at") or accounts.now(),
                            body=made["body"], logo=made["logo"],
                            auto_send=bool(found.get("auto_send")),
                            filters=made["filters"],
                            filters_text=conditions.describe(
                                made["filters"], accounts.fields_of(company))):
        fail("campaign_sending", 409)
    return ok(campaign_shape(campaigns.by_id(db, company["_id"], found["_id"])))


@api_route("/campaigns/<campaign_id>", methods=("DELETE",), scope="campaigns:write")
def delete_campaign(campaign_id):
    """Borrarla. Lo que ya salió sigue en sus envíos (`/sends`)."""
    company = account()
    db = get_db()
    found = find_campaign(db, company, campaign_id)
    not_sending(found)
    if not campaigns.remove(db, company["_id"], found["_id"]):
        fail("campaign_sending", 409)
    return ok({"id": str(found["_id"]), "deleted": True})


# ------------------------------------------------------------ mandar

def simulated(db, company, found) -> dict:
    """Lo que diría una llave de verdad, sin cambiar nada."""
    return {"status": "simulated", "audience": audience(db, company, found),
            "blocked": blocked_shape(blocked_for(company, found))}


@api_route("/campaigns/<campaign_id>/send", methods=("POST",), scope="campaigns:send",
           idempotent=True)
def send_campaign(campaign_id):
    """Mandarla ya. Responde enseguida (202): la manda el proceso en segundo
    plano, por tandas, y la campaña dice cómo va. Una que ya salió sale otra
    vez entera (los suprimidos se siguen saltando)."""
    company = account()
    db = get_db()
    found = find_campaign(db, company, campaign_id)
    if is_test():
        return ok(simulated(db, company, found))
    not_sending(found)
    blocked = blocked_for(company, found)
    if blocked:
        fail("cannot_send", 409, extra={"blocked": blocked_shape(blocked)})
    moment = accounts.now()
    if found["status"] == campaigns.SENT:
        done = campaigns.restart(db, company["_id"], found["_id"], when=moment, auto_send=True)
    else:
        done = db.campaigns.update_one(
            {"_id": found["_id"], "account_id": company["_id"], "status": campaigns.SCHEDULED},
            {"$set": {"scheduled_at": moment, "auto_send": True, "updated_at": moment},
             "$unset": {"waiting": "", "retry_at": ""}}).matched_count == 1
    if not done:
        fail("campaign_sending", 409)
    return ok(campaign_shape(campaigns.by_id(db, company["_id"], found["_id"])), 202)


@api_route("/campaigns/<campaign_id>/schedule", methods=("POST",), scope="campaigns:send",
           idempotent=True)
def schedule_campaign(campaign_id):
    """Programarla para una hora: sale sola entonces. Una que ya salió queda
    lista para salir otra vez a esa hora."""
    data = body({"at"}, required=("at",))
    fields = Fields(data)
    when = future(data.get("at"), fields, "at")
    fields.check()
    company = account()
    db = get_db()
    found = find_campaign(db, company, campaign_id)
    if is_test():
        return ok(simulated(db, company, found))
    not_sending(found)
    if found["status"] == campaigns.SENT:
        done = campaigns.restart(db, company["_id"], found["_id"], when=when, auto_send=True)
    else:
        done = db.campaigns.update_one(
            {"_id": found["_id"], "account_id": company["_id"], "status": campaigns.SCHEDULED},
            {"$set": {"scheduled_at": when, "auto_send": True, "updated_at": accounts.now()},
             "$unset": {"waiting": "", "retry_at": ""}}).matched_count == 1
    if not done:
        fail("campaign_sending", 409)
    return ok(campaign_shape(campaigns.by_id(db, company["_id"], found["_id"])))


@api_route("/campaigns/<campaign_id>/schedule", methods=("DELETE",), scope="campaigns:send")
def unschedule_campaign(campaign_id):
    """Que no salga sola: vuelve a esperar a que la mandes."""
    company = account()
    db = get_db()
    found = find_campaign(db, company, campaign_id)
    if is_test():
        return ok(simulated(db, company, found))
    not_sending(found)
    campaigns.set_auto(db, company["_id"], found["_id"], False)
    return ok(campaign_shape(campaigns.by_id(db, company["_id"], found["_id"])))
