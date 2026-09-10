"""Lo que Amazon SES cuenta de cada correo que sale.

Un documento por evento —enviado, entregado, rebote, queja, apertura, clic— con
la cuenta a la que pertenece, la campaña, cuándo pasó y, cuando el evento lo
trae, la dirección normalizada. Es lo que más crece de todo el producto: unos
tres eventos por correo.

**Todavía no lo llena nadie.** La colección se crea cuando entre el primer
evento, y hasta entonces todas las lecturas de aquí devuelven cero. Eso es a
propósito y es lo que la pantalla de estadísticas tiene que saber dibujar: un
cuadro vacío que dice que aún no ha pasado nada informa; un hueco no.

Quien la va a llenar es el webhook de SNS (`blueprints/webhooks/`), que es lo
primero que hay que montar antes de la primera campaña real.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# Lo que manda SES. Los nombres son los suyos, en minúscula.
SENT = "sent"
DELIVERED = "delivery"
BOUNCE = "bounce"
COMPLAINT = "complaint"
OPEN = "open"
CLICK = "click"
KINDS = (SENT, DELIVERED, BOUNCE, COMPLAINT, OPEN, CLICK)

# Los periodos que ofrece la pantalla, y en cuántos tramos se parte cada uno.
# Un día se mira por horas y un mes por días: veinticuatro barras se leen, y
# setecientas veinte no.
PERIODS = {
    "24h": {"hours": 24, "step": timedelta(hours=1)},
    "7d": {"hours": 24 * 7, "step": timedelta(days=1)},
    "30d": {"hours": 24 * 30, "step": timedelta(days=1)},
}
DEFAULT_PERIOD = "24h"


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_period(raw: str | None) -> str:
    return raw if raw in PERIODS else DEFAULT_PERIOD


def since(period: str) -> datetime:
    return now() - timedelta(hours=PERIODS[clean_period(period)]["hours"])


def record(db, account_id, *, kind: str, campaign_id=None, email: str = "",
           at: datetime | None = None) -> Any:
    """Anotar un evento. Lo llamará el webhook cuando exista."""
    return db.events.insert_one({
        "account_id": account_id,
        "campaign_id": campaign_id,
        "kind": kind,
        "email_normalized": email,
        "created_at": at or now(),
    }).inserted_id


def _match(account_id, period: str, tag: str) -> dict[str, Any]:
    """La consulta que comparten la serie y los totales.

    En un solo sitio para que el número de arriba y la barra de abajo no puedan
    contar cosas distintas.
    """
    query: dict[str, Any] = {"account_id": account_id,
                             "created_at": {"$gte": since(period)}}
    if tag:
        query["tags"] = tag
    return query


def totals(db, account_id, *, period: str = DEFAULT_PERIOD,
           tag: str = "") -> dict[str, int]:
    """Cuántos de cada tipo en ese periodo. Todos a cero mientras no haya nada.

    Se devuelven las seis claves siempre, aunque valgan cero: la pantalla
    dibuja las seis y no tiene que andar preguntando si existen.
    """
    counted = {kind: 0 for kind in KINDS}
    for row in db.events.aggregate([
            {"$match": _match(account_id, period, tag)},
            {"$group": {"_id": "$kind", "n": {"$sum": 1}}}]):
        if row["_id"] in counted:
            counted[row["_id"]] = row["n"]
    return counted


def series(db, account_id, *, period: str = DEFAULT_PERIOD, tag: str = "",
           kinds: tuple[str, ...] = (SENT, BOUNCE)) -> list[dict[str, Any]]:
    """Cuántos de cada tipo en cada tramo del periodo, en orden.

    Devuelve **todos** los tramos, también los que no tienen nada: una gráfica
    con huecos donde no pasó nada miente sobre la forma del tiempo.
    """
    step = PERIODS[clean_period(period)]["step"]
    start = since(period)
    tramos: list[dict[str, Any]] = []
    at = start
    while at < now():
        tramos.append({"at": at, **{kind: 0 for kind in kinds}})
        at += step

    if not tramos:
        return tramos

    for row in db.events.aggregate([
            {"$match": {**_match(account_id, period, tag),
                        "kind": {"$in": list(kinds)}}},
            {"$group": {"_id": {"kind": "$kind", "at": "$created_at"},
                        "n": {"$sum": 1}}}]):
        kind = row["_id"]["kind"]
        at = row["_id"]["at"]
        # A qué barra le toca: cuántos pasos cabe desde el principio.
        index = int((at - start) / step)
        if 0 <= index < len(tramos):
            tramos[index][kind] += row["n"]
    return tramos


def busiest(rows: list[dict[str, Any]], kinds: tuple[str, ...]) -> int:
    """El tramo más alto, que es lo que fija la altura de la gráfica."""
    return max((sum(row[kind] for kind in kinds) for row in rows), default=0)
