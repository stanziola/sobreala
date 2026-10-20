"""Lo que está pasando, para la pantalla Eventos de administración (octubre de 2026).

Junta en una sola lista, del más nuevo al más viejo, dos clases de cosas:

  * **de los correos**, lo que contó Amazon de cada campaña (`events`):
    entregado, rebote, queja, rechazo, apertura y clic;
  * **de las cuentas**: un registro, una demostración pedida, un pago cobrado,
    una pausa automática o un límite (`accounts`, `payments`, `admin_events`).

**Del destinatario se enseña solo el dominio** («gmail.com»), nunca la
dirección: la administración no hojea los contactos de un cliente. El dominio es
lo que sirve aquí, para ver si un proveedor rechaza en masa.

Cada fila lleva una clave única (`key`) para que la pantalla, que se pide lo
nuevo cada pocos segundos, no pinte dos veces lo mismo: se pide con un margen
hacia atrás (`OVERLAP`), porque un aviso de Amazon puede llegar un rato después
de la hora que trae.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from i18n import MONTHS, t
from models import account as accounts
from models import admin_event as decisions
from models import event as events
from models import payment as payments
from models import suppression as suppressions
from services import clock, plans

# Lo que se ve de una vez, y hasta dónde se mira hacia atrás sin `after`.
LIMIT = 100
SINCE_DAYS = 7
# El margen hacia atrás al pedir lo nuevo: lo que llegó tarde con una hora
# anterior a la última que tiene la pantalla.
OVERLAP = timedelta(minutes=10)

MAIL_KINDS = (events.DELIVERED, events.BOUNCE, events.COMPLAINT, events.REJECT,
              events.OPEN, events.CLICK, events.DOWNLOAD)
# Lo de las cuentas, con nombres propios porque no son eventos de Amazon.
SIGNUP, DEMO, PAYMENT, PAUSE, LIMIT_ON, LIMIT_OFF = (
    "signup", "demo", "payment", "pause", "limit", "unlimit")
ACCOUNT_KINDS = (SIGNUP, DEMO, PAYMENT, PAUSE, LIMIT_ON, LIMIT_OFF)

# Los filtros de la pantalla. «Lo que pide atención» es el de siempre.
FILTERS = {
    "attention": (events.BOUNCE, events.COMPLAINT, events.REJECT, PAUSE),
    "mail": MAIL_KINDS,
    "accounts": ACCOUNT_KINDS,
    "all": MAIL_KINDS + ACCOUNT_KINDS,
}
DEFAULT_FILTER = "attention"

# Las que piden mirar, en rojo; las que conviene notar, en ámbar.
BAD = (events.BOUNCE, events.COMPLAINT, events.REJECT, PAUSE)
NOTE = (LIMIT_ON,)


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(when: datetime | None) -> datetime | None:
    if when is not None and when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when


def domain_of(email: str) -> str:
    return (email or "").rsplit("@", 1)[-1] if "@" in (email or "") else ""


def latest(db, *, wanted: str = DEFAULT_FILTER, account_id=None,
           after: datetime | None = None, limit: int = LIMIT) -> list[dict[str, Any]]:
    """Las filas, de la más nueva a la más vieja.

    `after` es la hora de la más nueva que ya tiene la pantalla: llega lo
    posterior, con el margen de `OVERLAP`. Sin ella, los últimos `SINCE_DAYS`.
    """
    kinds = FILTERS.get(wanted, FILTERS[DEFAULT_FILTER])
    since = (after - OVERLAP) if after else now() - timedelta(days=SINCE_DAYS)
    rows: list[dict[str, Any]] = []
    rows += _mail(db, [k for k in kinds if k in MAIL_KINDS], account_id, since, limit)
    rows += _accounts(db, [k for k in kinds if k in ACCOUNT_KINDS], account_id,
                      since, limit)
    rows.sort(key=lambda row: row["at"], reverse=True)
    rows = rows[:limit]
    names = accounts.names_of(db, [row["account_id"] for row in rows])
    for row in rows:
        row["company"] = names.get(row["account_id"], "")
    return rows


def _mail(db, kinds, account_id, since, limit) -> list[dict[str, Any]]:
    if not kinds:
        return []
    query: dict[str, Any] = {"kind": {"$in": kinds}, "created_at": {"$gte": since}}
    if account_id is not None:
        query["account_id"] = account_id
    found = list(db.events.find(query).sort("created_at", -1).limit(limit))
    # El asunto de cada campaña y si cada rebote fue permanente, en una
    # consulta cada uno: la supresión por rebote permanente es lo que lo dice.
    ids = list({row.get("campaign_id") for row in found} - {None})
    subjects = {one["_id"]: one.get("subject", "") for one in db.campaigns.find(
        {"_id": {"$in": ids}}, {"subject": 1})}
    # Los correos de la API (octubre de 2026) no son campañas: su asunto está en
    # `messages`, sin llenar, que es lo único que se guarda de él.
    subjects.update({one["_id"]: one.get("subject", "") for one in db.messages.find(
        {"_id": {"$in": [one for one in ids if one not in subjects]}}, {"subject": 1})})
    bounced = [row for row in found if row["kind"] == events.BOUNCE]
    hard = {(one["account_id"], one["email_normalized"]) for one in db.suppressions.find(
        {"account_id": {"$in": list({row["account_id"] for row in bounced})},
         "email_normalized": {"$in": list({row.get("email_normalized", "")
                                            for row in bounced})},
         "reason": suppressions.HARD_BOUNCE},
        {"account_id": 1, "email_normalized": 1})} if bounced else set()
    out = []
    for row in found:
        email = row.get("email_normalized", "")
        detail = subjects.get(row.get("campaign_id"), "")
        if row["kind"] == events.BOUNCE:
            label = t("activity_bounce_hard" if (row["account_id"], email) in hard
                      else "activity_bounce_soft")
        else:
            label = t("activity_kind_" + row["kind"])
        out.append({"key": f"e{row['_id']}", "at": aware(row["created_at"]),
                    "kind": row["kind"], "group": "mail", "label": label,
                    "account_id": row["account_id"], "detail": detail,
                    "domain": domain_of(email)})
    return out


def _accounts(db, kinds, account_id, since, limit) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    owners: dict[str, Any] = {"role": {"$ne": accounts.ADMIN},
                              "owner_id": {"$exists": False}}
    if account_id is not None:
        owners["_id"] = account_id
    if SIGNUP in kinds:
        # Al confirmar el correo: lo que no se confirma se borra a las 24 horas.
        for one in db.accounts.find({**owners, "email_confirmed_at": {"$gte": since}},
                                    {"email_confirmed_at": 1, "email": 1}
                                    ).sort("email_confirmed_at", -1).limit(limit):
            out.append({"key": f"s{one['_id']}", "at": aware(one["email_confirmed_at"]),
                        "kind": SIGNUP, "group": "accounts",
                        "label": t("activity_kind_signup"),
                        "account_id": one["_id"], "detail": one.get("email", ""),
                        "domain": ""})
    if DEMO in kinds:
        for one in db.accounts.find({**owners, "demo_requested_at": {"$gte": since}},
                                    {"demo_requested_at": 1}
                                    ).sort("demo_requested_at", -1).limit(limit):
            out.append({"key": f"d{one['_id']}", "at": aware(one["demo_requested_at"]),
                        "kind": DEMO, "group": "accounts",
                        "label": t("activity_kind_demo"),
                        "account_id": one["_id"], "detail": "", "domain": ""})
    if PAYMENT in kinds:
        query: dict[str, Any] = {"status": payments.COMPLETED,
                                 "completed_at": {"$gte": since}}
        if account_id is not None:
            query["account_id"] = account_id
        for one in db.payments.find(query).sort("completed_at", -1).limit(limit):
            out.append({"key": f"p{one['_id']}", "at": aware(one["completed_at"]),
                        "kind": PAYMENT, "group": "accounts",
                        "label": t("activity_kind_payment"),
                        "account_id": one["account_id"],
                        "detail": t("activity_payment_detail",
                                    plan=(one.get("plan") or "").capitalize(),
                                    amount=plans.money(one.get("amount", ""))),
                        "domain": ""})
    limits = [k for k in kinds if k in (PAUSE, LIMIT_ON, LIMIT_OFF)]
    if limits:
        query = {"kind": decisions.LIMIT, "created_at": {"$gte": since}}
        if account_id is not None:
            query["account_id"] = account_id
        for one in db.admin_events.find(query).sort("created_at", -1).limit(limit):
            if one.get("after") is None:
                kind = LIMIT_OFF
            elif one.get("after") in accounts.PAUSE_REASONS and one.get("admin_id") is None:
                kind = PAUSE
            else:
                kind = LIMIT_ON
            if kind not in limits:
                continue
            out.append({"key": f"a{one['_id']}", "at": aware(one["created_at"]),
                        "kind": kind, "group": "accounts",
                        "label": t("activity_kind_" + kind),
                        "account_id": one["account_id"],
                        "detail": one.get("reason", ""), "domain": ""})
    return out


def moment(when: datetime) -> str:
    """La hora de una fila, corta: solo la hora si es de hoy."""
    here = clock.local(when)
    if here.date() == clock.local(now()).date():
        return f"{here:%H:%M:%S}"
    return f"{here.day} {MONTHS[here.month - 1][:3]} {here:%H:%M}"


def level(kind: str) -> str:
    if kind in BAD:
        return "bad"
    if kind in NOTE:
        return "note"
    return "plain"
