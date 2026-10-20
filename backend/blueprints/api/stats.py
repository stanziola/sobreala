"""Lo que salió y cómo le fue, por la API (octubre de 2026): los envíos, sus
destinatarios, las estadísticas y los eventos crudos.

Las cifras son las de la pantalla de Estadísticas, contadas igual: **personas y
no eventos** (quien abre tres veces es una apertura), y por envío. Las fechas
salen en UTC; los tramos de una serie, los días de la semana y las horas se
cuentan en la zona que se pida (`tz`, un nombre como America/Panama), o en la
de la cuenta, nunca en la de un navegador.

Un envío (`send`) es una vuelta de una campaña que terminó: la que todavía está
saliendo se sigue en `/campaigns`. Los correos de la API cuentan en las
estadísticas y en los eventos, y se miran uno por uno en `/emails`.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from flask import request

from blueprints.api.core import (Fields, account, api_route, fail, iso, ok, page_cursor,
                                 page_limit, paged, parse_id, path_id, when_of)
from db import get_db
from i18n import t
from models import campaign_run as runs
from models import contact as contacts
from models import event as events
from models import suppression as suppressions
from services import clock, stats

# Los filtros de destinatarios, con los nombres de la API.
OUTCOMES = {"delivered": "entregados", "bounced": "rebotes", "rejected": "rechazados",
            "complained": "spam", "opened": "abrieron", "clicked": "pulsaron",
            "not_opened": "sin_abrir"}
RECIPIENTS_MAX = 100
LINKS_MAX = 20
GROWTH_MONTHS = 12


def zone_of(company):
    """La zona que se pidió, o la de la cuenta."""
    wanted = request.args.get("tz", "")
    if not wanted:
        return clock.for_account(company)
    found = clock.zone_named(wanted)
    if found is None:
        fail("validation_failed", 422, fields={"tz": t("api_stats_tz")})
    return found


def period_of() -> str:
    wanted = request.args.get("period", events.DEFAULT_PERIOD)
    if wanted not in events.PERIODS:
        fail("validation_failed", 422, fields={"period": t(
            "api_stats_period", periods=", ".join(events.PERIODS))})
    return wanted


def filters(company) -> dict:
    """La campaña (`campaign_id`) o la etiqueta (`tag`) por las que se filtra."""
    out: dict = {"tag": request.args.get("tag", "")[:40]}
    raw = request.args.get("campaign_id", "")
    if raw:
        found = parse_id(raw)
        if found is None:
            fail("validation_failed", 422, fields={"campaign_id": t("api_field_id")})
        out["campaign"] = found
    return out


# ------------------------------------------------------------ los envíos

def send_shape(one: dict, counted: dict) -> dict:
    return {"id": str(one["_id"]), "campaign_id": str(one["campaign_id"]),
            "subject": one.get("subject", ""), "tags": list(one.get("tags") or []),
            "single": bool(one.get("to")), "to": one.get("to") or None,
            "total": one.get("total", 0), "sent": one.get("sent", 0),
            "skipped": one.get("skipped", 0), "failed": one.get("failed", 0),
            "people": counted.get(one["_id"], {kind: 0 for kind in events.RUN_KINDS}),
            "started_at": iso(one.get("started_at")),
            "finished_at": iso(one.get("finished_at"))}


@api_route("/sends", scope="campaigns:read")
def list_sends():
    """Lo que salió, una línea por envío: de los más nuevos a los más viejos."""
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"]}
    raw = request.args.get("campaign_id", "")
    if raw:
        query["campaign_id"] = parse_id(raw)
        if query["campaign_id"] is None:
            fail("validation_failed", 422, fields={"campaign_id": t("api_field_id")})
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.campaign_runs.find(query, {"errors": 0}).sort("_id", -1).limit(limit + 1))
    counted = events.counts_by_run(db, company["_id"], [one["_id"] for one in rows[:limit]])
    return ok(paged(rows, limit, lambda one: send_shape(one, counted)))


@api_route("/sends/<send_id>", scope="campaigns:read")
def get_send(send_id):
    company = account()
    db = get_db()
    found = runs.by_id(db, company["_id"], path_id(send_id))
    if found is None:
        fail("not_found", 404)
    counted = events.counts_by_run(db, company["_id"], [found["_id"]])
    return ok({**send_shape(found, counted),
               "errors": [{"email": one.get("email", ""), "error": one.get("error", "")}
                          for one in found.get("errors") or []]})


@api_route("/sends/<send_id>/recipients", scope="campaigns:read")
def send_recipients(send_id):
    """A quién le salió y qué pasó con cada uno, por orden de dirección."""
    company = account()
    db = get_db()
    found = runs.by_id(db, company["_id"], path_id(send_id))
    if found is None:
        fail("not_found", 404)
    limit = page_limit()
    raw = request.args.get("offset", "0")
    if not raw.isdigit():
        fail("validation_failed", 422, fields={"offset": t("api_stats_offset")})
    offset = int(raw)
    wanted = request.args.get("outcome", "")
    if wanted and wanted not in OUTCOMES:
        fail("validation_failed", 422, fields={"outcome": t(
            "api_stats_outcome", outcomes=", ".join(OUTCOMES))})
    email = request.args.get("email", "")[:254].strip().lower()
    total, page = events.recipients(db, company["_id"], found["_id"],
                                    emails=[email] if email else None,
                                    outcome=OUTCOMES.get(wanted, ""), skip=offset,
                                    limit=limit)
    return ok({"total": total,
               "data": [{"email": one["email"], "reached": one["reached"],
                         "events": {kind: iso(when) for kind, when in sorted(one["at"].items())}}
                        for one in page],
               "next_offset": offset + limit if offset + limit < total else None})


# ------------------------------------------------------------ las estadísticas

@api_route("/stats", scope="stats:read", limit="stats")
def get_stats():
    """Cómo le fue en un periodo: cada cifra con su porcentaje y su cambio
    contra el periodo anterior del mismo largo."""
    company = account()
    db = get_db()
    period, zone, chosen = period_of(), zone_of(company), filters(company)
    counted = events.people(db, company["_id"], period=period, zone=zone, **chosen)
    before = events.people(db, company["_id"], period=period, zone=zone, back=1, **chosen)
    leaves = leaves_before = None
    if not chosen["tag"] and "campaign" not in chosen:
        # Las bajas firman el contacto, no la campaña: solo sin filtro.
        start, end = events.window(period, zone)
        leaves = suppressions.count_between(db, company["_id"], start, end)
        start, end = events.window(period, zone, back=1)
        leaves_before = suppressions.count_between(db, company["_id"], start, end)
    start, _ = events.window(period, zone)
    return ok({"period": period, "tz": zone.key, "from": iso(start),
               "rates": stats.rates(counted, before, leaves=leaves,
                                    leaves_before=leaves_before)})


@api_route("/stats/series", scope="stats:read", limit="stats")
def stats_series():
    """Personas de cada tipo en cada tramo del periodo, todos los tramos."""
    company = account()
    db = get_db()
    period, zone, chosen = period_of(), zone_of(company), filters(company)
    kinds = (events.SENT, events.DELIVERED, events.OPEN, events.CLICK, events.BOUNCE,
             events.COMPLAINT)
    rows = events.series(db, company["_id"], period=period, zone=zone, kinds=kinds, **chosen)
    return ok({"period": period, "tz": zone.key,
               "data": [{"at": iso(one["at"]), **{kind: one[kind] for kind in kinds}}
                        for one in rows]})


@api_route("/stats/links", scope="stats:read", limit="stats")
def stats_links():
    """Los enlaces que pulsó más gente en el periodo."""
    company = account()
    db = get_db()
    period, zone, chosen = period_of(), zone_of(company), filters(company)
    return ok({"period": period, "data": events.top_links(
        db, company["_id"], period=period, zone=zone, limit=LINKS_MAX, **chosen)})


@api_route("/stats/timing", scope="stats:read", limit="stats")
def stats_timing():
    """Cuándo abre tu lista: aperturas por día de la semana (lunes primero) y
    por hora, en la zona pedida, de los últimos 90 días."""
    company = account()
    zone = zone_of(company)
    found = events.when_opened(get_db(), company["_id"], zone)
    return ok({"tz": zone.key, "days": found["days"], "hours": found["hours"],
               "days_counted": events.WHEN_DAYS})


@api_route("/stats/growth", scope="stats:read", limit="stats")
def stats_growth():
    """Altas y bajas de contactos por mes, los últimos doce."""
    company = account()
    db = get_db()
    zone = zone_of(company)
    first = clock.local(events.now(), zone).replace(day=1, hour=0, minute=0, second=0,
                                                    microsecond=0)
    edges = []
    for _ in range(GROWTH_MONTHS):
        edges.append(first)
        first = (first - timedelta(days=1)).replace(day=1)
    edges.reverse()
    data = []
    for at, nxt in zip(edges, edges[1:] + [None]):
        start = at.astimezone(timezone.utc)
        end = nxt.astimezone(timezone.utc) if nxt else None
        data.append({"month": f"{at.year:04d}-{at.month:02d}",
                     "added": contacts.added_between(db, company["_id"], start, end),
                     "left": suppressions.count_between(db, company["_id"], start, end)})
    return ok({"tz": zone.key, "data": data})


# ------------------------------------------------------------ los eventos

@api_route("/events", scope="stats:read")
def list_events():
    """Los eventos crudos, de los más nuevos: uno por correo, persona y tipo."""
    company = account()
    db = get_db()
    limit = page_limit()
    query: dict = {"account_id": company["_id"]}
    kind = request.args.get("type", "")
    if kind:
        if kind not in events.KINDS:
            fail("validation_failed", 422, fields={"type": t(
                "api_stats_kind", kinds=", ".join(events.KINDS))})
        query["kind"] = kind
    for name, field in (("campaign_id", "campaign_id"), ("send_id", "run_id")):
        raw = request.args.get(name, "")
        if raw:
            found = parse_id(raw)
            if found is None:
                fail("validation_failed", 422, fields={name: t("api_field_id")})
            query[field] = found
    email = request.args.get("email", "")[:254].strip().lower()
    if email:
        query["email_normalized"] = email
    fields = Fields({})
    since = when_of(request.args.get("from") or None, "from", fields)
    until = when_of(request.args.get("to") or None, "to", fields)
    fields.check()
    if since or until:
        query["created_at"] = {**({"$gte": since} if since else {}),
                               **({"$lt": until} if until else {})}
    cursor = page_cursor()
    if cursor is not None:
        query["_id"] = {"$lt": cursor}
    rows = list(db.events.find(query).sort("_id", -1).limit(limit + 1))
    return ok(paged(rows, limit, lambda one: {
        "id": str(one["_id"]), "type": one.get("kind"),
        "email": one.get("email_normalized", ""),
        "campaign_id": str(one["campaign_id"]) if one.get("campaign_id") else None,
        "send_id": str(one["run_id"]) if one.get("run_id") else None,
        "links": list(one.get("links") or []), "at": iso(one.get("created_at"))}))
