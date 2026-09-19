"""Lo que Amazon SES cuenta de cada correo que sale.

Un documento por evento —enviado, entregado, rebote, queja, apertura, clic— con
la cuenta a la que pertenece, la campaña, cuándo pasó y, cuando el evento lo
trae, la dirección normalizada. Es lo que más crece de todo el producto: unos
tres eventos por correo.

La llenan dos: `services/sender.py`, con un `sent` por cada correo que sale,
y el aviso de SES (`blueprints/webhooks/`), con todo lo que pasa después.
Mientras SES no esté configurado para avisar, solo hay `sent`, y las lecturas
de lo demás devuelven cero: un cuadro vacío que dice que aún no ha pasado nada
informa; un hueco no.
"""

from __future__ import annotations

from bson import ObjectId

from datetime import datetime, timedelta, timezone
from typing import Any

# Lo que manda SES. Los nombres son los suyos, en minúscula.
SENT = "sent"
DELIVERED = "delivery"
BOUNCE = "bounce"
COMPLAINT = "complaint"
OPEN = "open"
CLICK = "click"
REJECT = "reject"
KINDS = (SENT, DELIVERED, BOUNCE, COMPLAINT, OPEN, CLICK, REJECT)

# Lo que se cuenta de un envío, en personas y no en eventos: quien abre tres
# veces cuenta una.
RUN_KINDS = (DELIVERED, BOUNCE, OPEN, CLICK, COMPLAINT)

# Los periodos que ofrece la pantalla, en el orden en que se ofrecen, y en qué
# tramos se parte cada uno. Una hora se mira cada cinco minutos, un día por
# horas, un mes por días y tres meses por semanas: se lee una barra por tramo, y
# setecientas veinte no.
#
# `unit` dice dónde empieza el primer tramo: en punto (la hora en punto de
# quien mira) o a medianoche de su zona. Así un día empieza a las 00:00 en
# Panamá y no a las 19:00, que es la medianoche de UTC.
PERIODS = {
    "1h": {"step": timedelta(minutes=5), "count": 12, "unit": "minute"},
    "hoy": {"step": timedelta(hours=1), "count": None, "unit": "midnight"},
    "24h": {"step": timedelta(hours=1), "count": 24, "unit": "hour"},
    "7d": {"step": timedelta(days=1), "count": 7, "unit": "day"},
    "30d": {"step": timedelta(days=1), "count": 30, "unit": "day"},
    "90d": {"step": timedelta(days=7), "count": 13, "unit": "day"},
}
DEFAULT_PERIOD = "24h"


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_period(raw: str | None) -> str:
    return raw if raw in PERIODS else DEFAULT_PERIOD


def slots(period: str, zone=None) -> list[datetime]:
    """Dónde empieza cada tramo del periodo, en UTC y en orden.

    Se cuentan en la hora de la zona (la del dispositivo de quien mira) y se
    pasan a UTC al final, que es como están guardados los eventos. El último
    tramo es el que contiene ahora.
    """
    from services import clock

    zone = zone or clock.current()
    spec = PERIODS[clean_period(period)]
    here = now().astimezone(zone)
    step = spec["step"]
    if spec["unit"] == "minute":
        last = here.replace(minute=here.minute - here.minute % 5, second=0,
                            microsecond=0)
    elif spec["unit"] == "hour":
        last = here.replace(minute=0, second=0, microsecond=0)
    else:
        last = here.replace(hour=0, minute=0, second=0, microsecond=0)

    if spec["unit"] == "midnight":
        # Hoy: una por hora desde la medianoche hasta la hora de ahora.
        first = last
        count = here.hour + 1
    else:
        count = spec["count"]
        if step > timedelta(days=1):
            # Por semanas: la última termina hoy, no empieza hoy.
            first = last + timedelta(days=1) - step * count
        else:
            first = last - step * (count - 1)
    out = []
    for n in range(count):
        # En la hora de la pared de esa zona, para que un cambio de horario no
        # corra los días.
        wall = (first.replace(tzinfo=None) + step * n).replace(tzinfo=zone)
        out.append(wall.astimezone(timezone.utc))
    return out


def since(period: str, zone=None) -> datetime:
    return slots(period, zone)[0]


def record(db, account_id, *, kind: str, campaign_id=None, run_id=None,
           email: str = "", at: datetime | None = None) -> Any:
    """Anotar un evento.

    La dirección se guarda normalizada: es lo que permite contar personas y no
    eventos, y el aviso de SES no la escribe igual que la escribió el cliente.

    **Uno por envío, persona y tipo.** Quien abre el mismo correo mil veces deja
    una apertura, la primera; un clic en dos enlaces del mismo correo es un
    clic. Se escribe solo si no existe (`$setOnInsert`), así que las cifras no
    se inflan y la colección, que es la que más crece, no crece con cada
    reapertura. Sin envío o sin dirección no hay a quién atarlo, y se anota
    tal cual.
    """
    email = (email or "").strip().lower()
    doc = {"account_id": account_id, "campaign_id": campaign_id, "run_id": run_id,
           "kind": kind, "email_normalized": email, "created_at": at or now()}
    if run_id is None or not email:
        return db.events.insert_one(doc).inserted_id
    key = {"account_id": account_id, "run_id": run_id, "email_normalized": email,
           "kind": kind}
    found = db.events.find_one_and_update(
        key, {"$setOnInsert": doc}, upsert=True, projection={"_id": 1},
        return_document=True)
    return found["_id"]


def counts_by_run(db, account_id, run_ids: list) -> dict[Any, dict[str, int]]:
    """Cuántas **personas** entregadas, rebotadas, que abrieron, pulsaron o se
    quejaron, por envío. Una consulta para toda la lista, no una por fila.
    """
    wanted = [one for one in run_ids if isinstance(one, ObjectId)]
    found: dict[Any, dict[str, int]] = {
        one: {kind: 0 for kind in RUN_KINDS} for one in wanted}
    if not wanted:
        return found
    for row in db.events.aggregate([
            {"$match": {"account_id": account_id, "run_id": {"$in": wanted},
                        "kind": {"$in": list(RUN_KINDS)}}},
            # Primero una fila por persona y tipo, después se cuentan: así quien
            # abre tres veces es una apertura.
            {"$group": {"_id": {"run": "$run_id", "kind": "$kind",
                                "who": "$email_normalized"}}},
            {"$group": {"_id": {"run": "$_id.run", "kind": "$_id.kind"},
                        "n": {"$sum": 1}}}]):
        run = row["_id"]["run"]
        if run in found:
            found[run][row["_id"]["kind"]] = row["n"]
    return found


def _match(db, account_id, period: str, tag: str = "", campaign=None,
           zone=None) -> dict[str, Any]:
    """La consulta que comparten la serie, los totales y los porcentajes.

    En un solo sitio para que el número de arriba y la barra de abajo no puedan
    contar cosas distintas.

    **La etiqueta se busca en los envíos, no en los eventos**, que no la llevan:
    un evento es de un envío (`run_id`), y el envío guarda a qué etiquetas
    salió. Antes se buscaba en el evento y el filtro no encontraba nada.
    """
    query: dict[str, Any] = {"account_id": account_id,
                             "created_at": {"$gte": since(period, zone)}}
    if campaign is not None:
        query["campaign_id"] = campaign
    if tag:
        runs = [one["_id"] for one in db.campaign_runs.find(
            {"account_id": account_id, "tags": tag}, {"_id": 1})]
        query["run_id"] = {"$in": runs}
    return query


def totals(db, account_id, *, period: str = DEFAULT_PERIOD, tag: str = "",
           campaign=None, zone=None) -> dict[str, int]:
    """Cuántos de cada tipo en ese periodo. Todos a cero mientras no haya nada.

    Se devuelven las claves siempre, aunque valgan cero: la pantalla las dibuja
    todas y no tiene que andar preguntando si existen.
    """
    counted = {kind: 0 for kind in KINDS}
    for row in db.events.aggregate([
            {"$match": _match(db, account_id, period, tag, campaign, zone)},
            {"$group": {"_id": "$kind", "n": {"$sum": 1}}}]):
        if row["_id"] in counted:
            counted[row["_id"]] = row["n"]
    return counted


def people(db, account_id, *, period: str = DEFAULT_PERIOD, tag: str = "",
           campaign=None, zone=None) -> dict[str, int]:
    """Cuántas **personas** de cada tipo, contadas por envío.

    Quien abre tres veces el mismo envío es una apertura; quien recibe dos
    envíos de la misma campaña cuenta en los dos. Es la misma cuenta que
    «Campañas enviadas», para que los porcentajes digan lo mismo.
    """
    counted = {kind: 0 for kind in KINDS}
    for row in db.events.aggregate([
            {"$match": _match(db, account_id, period, tag, campaign, zone)},
            {"$group": {"_id": {"run": "$run_id", "kind": "$kind",
                                "who": "$email_normalized"}}},
            {"$group": {"_id": "$_id.kind", "n": {"$sum": 1}}}]):
        if row["_id"] in counted:
            counted[row["_id"]] = row["n"]
    return counted


def series(db, account_id, *, period: str = DEFAULT_PERIOD, tag: str = "",
           campaign=None, zone=None,
           kinds: tuple[str, ...] = (SENT, BOUNCE)) -> list[dict[str, Any]]:
    """Cuántas personas de cada tipo en cada tramo del periodo, en orden.

    **Personas y no eventos**, como `people()`: quien abre tres veces el mismo
    envío es una apertura, y cae en el tramo en que abrió por primera vez. Si
    no, la gráfica y «Cómo le fue» contarían cosas distintas.

    Devuelve **todos** los tramos, también los que no tienen nada: una gráfica
    con huecos donde no pasó nada miente sobre la forma del tiempo. Cada tramo
    lleva su comienzo en UTC (`at`); la pantalla lo escribe en la zona.
    """
    from bisect import bisect_right

    starts = slots(period, zone)
    tramos: list[dict[str, Any]] = [{"at": at, **{kind: 0 for kind in kinds}}
                                    for at in starts]
    if not tramos:
        return tramos

    for row in db.events.aggregate([
            {"$match": {**_match(db, account_id, period, tag, campaign, zone),
                        "kind": {"$in": list(kinds)}}},
            {"$group": {"_id": {"run": "$run_id", "kind": "$kind",
                                "who": "$email_normalized"},
                        "first": {"$min": "$created_at"}}},
            {"$group": {"_id": {"kind": "$_id.kind", "at": "$first"},
                        "n": {"$sum": 1}}}]):
        at = row["_id"]["at"]
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        # A qué barra le toca: la última que empezó antes que él.
        index = bisect_right(starts, at) - 1
        if 0 <= index < len(tramos):
            tramos[index][row["_id"]["kind"]] += row["n"]
    return tramos


# Lo que dice «Llegó» en el detalle de un envío, del más fuerte al más flojo:
# si Amazon contó una queja, eso es lo que hay que ver aunque antes dijera que
# lo entregó.
REACHED = (COMPLAINT, BOUNCE, REJECT, DELIVERED, SENT)


def _has(kind: str) -> dict[str, Any]:
    return {"kinds.k": kind}


def _lacks(*kinds: str) -> dict[str, Any]:
    return {"kinds.k": {"$nin": list(kinds)}}


# El filtro «Qué pasó» del detalle de un envío. Los de «Llegó» siguen el mismo
# orden que REACHED, así que filtrar por «Rebotó» trae justo a quien la columna
# enseña como rebotado, y no también a quien después lo marcó como spam.
OUTCOMES: dict[str, dict[str, Any]] = {
    "entregados": {"$and": [_has(DELIVERED), _lacks(COMPLAINT, BOUNCE, REJECT)]},
    "rebotes": {"$and": [_has(BOUNCE), _lacks(COMPLAINT)]},
    "rechazados": {"$and": [_has(REJECT), _lacks(COMPLAINT, BOUNCE)]},
    "spam": _has(COMPLAINT),
    "abrieron": _has(OPEN),
    "pulsaron": _has(CLICK),
    "sin_abrir": _lacks(OPEN),
}


def recipients(db, account_id, run_id, *, emails: list[str] | None = None,
               outcome: str = "", skip: int = 0,
               limit: int = 50) -> tuple[int, list[dict[str, Any]]]:
    """A quién le salió un envío, con lo que pasó con cada uno. Una página.

    Devuelve cuántos son en total y la página: cada persona con su dirección y,
    por tipo, la primera vez que pasó (`at`). `emails`, si viene, deja solo a
    esas personas: es el filtro de la pantalla, que se resuelve antes en
    Contactos para no traer la lista entera. `outcome` es una clave de
    `OUTCOMES`; una que no existe no filtra.
    """
    match: dict[str, Any] = {"account_id": account_id, "run_id": run_id}
    if emails is not None:
        match["email_normalized"] = {"$in": emails}
    rows = list(db.events.aggregate([
        {"$match": match},
        {"$group": {"_id": {"who": "$email_normalized", "kind": "$kind"},
                    "at": {"$min": "$created_at"}}},
        {"$group": {"_id": "$_id.who",
                    "kinds": {"$push": {"k": "$_id.kind", "v": "$at"}}}},
        {"$match": {"_id": {"$ne": ""}, **OUTCOMES.get(outcome, {})}},
        {"$sort": {"_id": 1}},
        {"$facet": {"total": [{"$count": "n"}],
                    "page": [{"$skip": skip}, {"$limit": limit}]}},
    ]))
    found = rows[0] if rows else {"total": [], "page": []}
    total = found["total"][0]["n"] if found["total"] else 0
    page = []
    for row in found["page"]:
        at = {one["k"]: one["v"] for one in row["kinds"]}
        page.append({"email": row["_id"], "at": at,
                     "reached": next((kind for kind in REACHED if kind in at), SENT)})
    return total, page


def campaigns_sent(db, account_id) -> list[dict[str, Any]]:
    """Las campañas que han salido alguna vez, con el asunto de su último envío.

    Salen de los envíos y no de las campañas: una campaña borrada sigue
    teniendo sus cifras, y hay que poder mirarlas.
    """
    return [{"_id": row["_id"], "subject": row["subject"]}
            for row in db.campaign_runs.aggregate([
                {"$match": {"account_id": account_id}},
                {"$sort": {"finished_at": -1}},
                {"$group": {"_id": "$campaign_id", "subject": {"$first": "$subject"},
                            "last": {"$first": "$finished_at"}}},
                {"$sort": {"last": -1}},
                {"$limit": 100}])]


def busiest(rows: list[dict[str, Any]], kinds: tuple[str, ...]) -> int:
    """El tramo más alto, que es lo que fija la altura de la gráfica."""
    return max((sum(row[kind] for kind in kinds) for row in rows), default=0)
