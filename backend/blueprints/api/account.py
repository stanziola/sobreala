"""La cuenta de la llave y sus remitentes, y la descripción de la API.

`/me` es lo primero que llama quien conecta su sistema: dice de quién es la
llave, qué puede hacer y si hoy se puede enviar. `/senders` dice desde qué
direcciones se puede mandar, que es lo que se elige en cada correo. Las dos
responden a cualquier llave, y ninguna enseña datos personales del dueño.
"""

from __future__ import annotations

from flask import jsonify

from blueprints.api.core import (ANY, PUBLIC, account, api_route, iso, key,
                                 key_shape, ok)
from i18n import t
from models import account as accounts
from services import plans, sender

# Las plantillas que caben por la API (`blueprints/api/templates.py`).
TEMPLATE_LIMIT = 300


def blocked_of(company) -> list[dict[str, str]]:
    """Por qué hoy no puede enviar, con la frase que ve en el panel."""
    return [{"code": why, "message": t("send_blocked_" + why)}
            for why in sender.blocked(company)]


@api_route("/me", scope=ANY)
def me():
    company = account()
    plan = accounts.plan_of(company)
    allowed = plans.emails_a_month(plan)
    demo = None
    if accounts.in_demo(company):
        demo = {"left": accounts.demo_left(company), "total": accounts.DEMO_SENDS,
                "addresses": sorted(accounts.confirmed_test_addresses(company))}
    blocked = blocked_of(company)
    return ok({
        "account": {"id": str(company["_id"]), "company": company.get("company_name", ""),
                    "plan": plan, "plan_until": iso(accounts.plan_until(company)),
                    "demo": demo},
        "quota": {"month": accounts.quota_month(), "allowed": allowed,
                  "used": accounts.used_this_month(company),
                  "left": accounts.quota_left(company)},
        "limits": {"contacts": accounts.contact_limit(company),
                   "tags": accounts.tag_limit(company),
                   "fields": accounts.field_limit(company),
                   "images": plans.image_limit(plan),
                   "templates": TEMPLATE_LIMIT},
        "can_send": not blocked,
        "blocked": blocked,
        "key": key_shape(key()),
    })


@api_route("/senders", scope=ANY)
def senders():
    company = account()
    default_from = accounts.default_from(company)
    default_reply = accounts.default_reply(company)
    return ok({
        "from": [{"id": str(one["id"]) if one.get("id") else None,
                  "name": one.get("label", ""), "address": one.get("address", ""),
                  "ready": bool(one.get("ready")), "shared": bool(one.get("shared")),
                  "default": bool(default_from and one.get("id") == default_from.get("id")
                                  and one.get("address") == default_from.get("address"))}
                 for one in accounts.froms_of(company)],
        "reply_to": [{"address": one, "default": one == default_reply}
                     for one in accounts.reply_tos_of(company)],
        "reply_to_default": default_reply,
        "domains": [{"name": one["name"], "status": one.get("status", "pending")}
                    for one in accounts.domains_of(company)],
    })


@api_route("/openapi.json", scope=PUBLIC)
def openapi():
    """La descripción de la API en OpenAPI 3.1: la misma de la que sale la
    página del sitio. Pública, como esa página."""
    import api_spec

    response = jsonify(api_spec.openapi())
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
