"""Lo que enseña la pantalla de estadísticas, de una cuenta cualquiera.

Vive aquí y no en un blueprint porque la miran dos: el cliente en `/panel`, con
la suya, y el administrador en `/admin/`, con la de quien elija. Una sola
función que llena una sola plantilla; si la pantalla cambia, cambia para los
dos a la vez y no hay forma de que una se quede atrás.

**Las horas son las del dispositivo de quien mira** (`services/clock.py`): los
tramos de las gráficas empiezan en punto o a medianoche de su zona, y las marcas
del eje se escriben en ella.

Solo enseña envíos, aperturas y porcentajes. Los contactos, las importaciones y
el plan viven en sus propias pantallas.
"""

from __future__ import annotations

import math
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from i18n import MONTHS, t
from models import account as accounts
from models import event as events
from services import clock

DAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado",
            "domingo")


# ------------------------------------------------------------- las horas

def _hour(when, *, minutes: bool = False) -> str:
    """«3 p. m.» o «3:15 p. m.», que es como se dice la hora aquí."""
    h = when.hour % 12 or 12
    part = "a. m." if when.hour < 12 else "p. m."
    return f"{h}:{when.minute:02d} {part}" if minutes else f"{h} {part}"


def tick_label(period: str, when) -> str:
    """La marca corta del eje de abajo."""
    unit = events.PERIODS[period]["unit"]
    if unit == "minute":
        return _hour(when, minutes=True)
    if unit in ("hour", "midnight"):
        return _hour(when)
    if period == "7d":
        return f"{DAYS[when.weekday()]} {when.day}"
    return f"{when.day} {MONTHS[when.month - 1][:3]}"


def tip_label(period: str, when) -> str:
    """Lo que dice el cuadrito de un tramo: cuál es, entero."""
    unit = events.PERIODS[period]["unit"]
    day = f"{WEEKDAYS[when.weekday()]} {when.day} de {MONTHS[when.month - 1]}"
    if unit == "minute":
        return _hour(when, minutes=True)
    if unit in ("hour", "midnight"):
        return f"{day}, {_hour(when)}"
    if period == "90d":
        return t("stats_week_of", day=f"{when.day} de {MONTHS[when.month - 1]}")
    return day


def _ticks(period: str, starts_local: list) -> list[str]:
    """La marca de cada tramo, o nada: hasta siete, repartidas."""
    every = max(1, math.ceil(len(starts_local) / 7))
    return [tick_label(period, when) if i % every == 0 else ""
            for i, when in enumerate(starts_local)]


# ------------------------------------------------------------- la escala

def nice_top(top: int) -> tuple[int, list[int]]:
    """El máximo redondeado hacia arriba y sus cinco rayas (0, ¼, ½, ¾, 1).

    El paso es 1, 2, 2,5 o 5 por una potencia de diez, así las rayas son
    números que se leen sin hacer cuentas.
    """
    if top <= 0:
        return 0, []
    raw = top / 4
    power = 10 ** math.floor(math.log10(raw)) if raw >= 1 else 1
    for factor in (1, 2, 2.5, 5, 10):
        step = factor * power
        if step >= raw and (step == int(step)):
            break
    step = int(step)
    return step * 4, [step * i for i in range(5)]


def chart(period: str, rows: list[dict[str, Any]], kinds, zone) -> dict[str, Any]:
    """Lo que dibuja `_bars.html`: los valores, la escala y las marcas."""
    local = [clock.local(row["at"], zone) for row in rows]
    stack = kinds[0][2] == "bars"
    top = max((sum(row[kind] for kind, _, _ in kinds) if stack
               else max(row[kind] for kind, _, _ in kinds)
               for row in rows), default=0)
    ceiling, lines = nice_top(top)
    return {
        "kinds": [{"key": kind, "css": css} for kind, css, _ in kinds],
        "shape": kinds[0][2],
        "rows": [{"values": {kind: row[kind] for kind, _, _ in kinds},
                  "tip": tip_label(period, when), "tick": tick}
                 for row, when, tick in zip(rows, local, _ticks(period, local))],
        "top": ceiling,
        "lines": lines,
    }


# ------------------------------------------------------------- porcentajes

def _share(part: int, whole: int) -> int | None:
    return round(part * 100 / whole) if whole else None


def rates(counted: dict[str, int]) -> list[dict[str, Any]]:
    """Cómo le fue: cada cifra con su porcentaje y de cuántos.

    Rebotes y entregados se miden contra lo que salió; abiertos, clics y quejas
    contra lo que llegó, que es a quien le pudo pasar.
    """
    sent, delivered = counted[events.SENT], counted[events.DELIVERED]
    return [
        {"key": "sent", "n": sent, "pct": None, "of": None},
        {"key": "delivery", "n": delivered, "pct": _share(delivered, sent), "of": sent},
        {"key": "bounce", "n": counted[events.BOUNCE],
         "pct": _share(counted[events.BOUNCE], sent), "of": sent},
        {"key": "open", "n": counted[events.OPEN],
         "pct": _share(counted[events.OPEN], delivered), "of": delivered},
        {"key": "click", "n": counted[events.CLICK],
         "pct": _share(counted[events.CLICK], delivered), "of": delivered},
        {"key": "complaint", "n": counted[events.COMPLAINT],
         "pct": _share(counted[events.COMPLAINT], delivered), "of": delivered},
    ]


def _campaign(raw: str, choices: list[dict[str, Any]]):
    """La campaña elegida, si es de esta cuenta. Una ajena no filtra por nada."""
    try:
        wanted = ObjectId(raw)
    except (InvalidId, TypeError):
        return None
    return wanted if any(one["_id"] == wanted for one in choices) else None


def screen(db, whose: dict[str, Any], *, period: str = "", tag: str = "",
           campaign: str = "") -> dict[str, Any]:
    """Todo lo que la plantilla necesita para una cuenta.

    El periodo, la etiqueta y la campaña llegan de la dirección, así que se
    limpian aquí: un periodo que no existe cae en el de por omisión, y una
    etiqueta o una campaña que no son de esta cuenta no filtran por nada, en vez
    de filtrar por algo ajeno.
    """
    zone = clock.current()
    period = events.clean_period(period)
    known = accounts.tags_of(whose)
    tag = tag if tag in known else ""
    choices = events.campaigns_sent(db, whose["_id"])
    chosen = _campaign(campaign, choices)
    where = {"period": period, "tag": tag, "campaign": chosen, "zone": zone}

    sending = events.series(db, whose["_id"], kinds=(events.SENT, events.BOUNCE),
                            **where)
    engaging = events.series(db, whose["_id"], kinds=(events.OPEN, events.CLICK),
                             **where)
    return {
        "whose": whose,
        "confirmed": accounts.is_confirmed(whose),
        "period": period,
        "periods": list(events.PERIODS),
        "tag": tag,
        "tags": known,
        "campaigns": choices,
        "campaign": chosen,
        "sending": chart(period, sending,
                         [(events.SENT, "sent", "bars"),
                          (events.BOUNCE, "bounce", "bars")], zone),
        "engaging": chart(period, engaging,
                          [(events.OPEN, "open", "lines"),
                           (events.CLICK, "click", "lines")], zone),
        "rates": rates(events.people(db, whose["_id"], **where)),
    }
