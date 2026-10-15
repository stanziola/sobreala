"""Lo que enseña la pantalla de estadísticas, de una cuenta cualquiera.

Vive aquí y no en un blueprint porque la miran dos: el cliente en `/dashboard`, con
la suya, y el administrador en `/admin/`, con la de quien elija. Una sola
función que llena una sola plantilla; si la pantalla cambia, cambia para los
dos a la vez y no hay forma de que una se quede atrás.

**Las horas son las del dispositivo de quien mira** (`services/clock.py`): los
tramos de las gráficas empiezan en punto o a medianoche de su zona, y las marcas
del eje se escriben en ella.

Enseña envíos, aperturas, porcentajes y, al final, cuántos correos del mes lleva
gastados la cuenta. Los contactos, las importaciones y el plan viven en sus
propias pantallas.
"""

from __future__ import annotations

import math
from datetime import timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from i18n import MONTHS, t
from models import account as accounts
from models import campaign_run as campaign_runs
from models import event as events
from models import suppression as suppressions
from services import clock, plans

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


# Qué cifras son mejores cuanto más bajas: subir de rebotes, de quejas o de
# bajas es malo, así que la pastilla va roja aunque la flecha suba.
WORSE_UP = ("bounce", "complaint", "leave")


def _counted(counted: dict[str, int], leaves: int | None = None) -> list[dict[str, Any]]:
    """Cada cifra con su porcentaje y de cuántos, sin comparar con nada.

    `leaves` son las bajas del tramo, que no salen de `events` sino de
    `suppressions`: el enlace de baja firma el contacto y no la campaña, así que
    con un filtro puesto no se pueden atribuir y llegan como None.
    """
    sent, delivered = counted[events.SENT], counted[events.DELIVERED]
    rows = [
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
    if leaves is not None:
        rows.append({"key": "leave", "n": leaves,
                     "pct": _share(leaves, delivered), "of": delivered})
    return rows


def _ratio(one: dict[str, Any]) -> float | None:
    """La proporción exacta de una fila, sin el redondeo que se enseña."""
    return one["n"] / one["of"] if one["of"] else None


def _change(key: str, now_value, before_value) -> dict[str, Any] | None:
    """Cuánto cambió contra el periodo anterior, en por ciento.

    Se compara lo mismo con lo mismo: en «Enviados», cuántos; en el resto, su
    porcentaje. Sin nada antes no se devuelve nada, que es mejor que inventar
    un «+100 %» donde no había con qué comparar. Y **el color lo decide si
    mejoró, no si subió**: más rebotes es rojo aunque la flecha apunte arriba.
    """
    if not before_value or now_value is None:
        return None
    pct = round((now_value - before_value) * 100 / before_value)
    if pct == 0:
        return None
    up = pct > 0
    return {"pct": abs(pct), "up": up, "good": up != (key in WORSE_UP)}


def rates(counted: dict[str, int], before: dict[str, int] | None = None,
          *, leaves: int | None = None,
          leaves_before: int | None = None) -> list[dict[str, Any]]:
    """Cómo le fue: cada cifra con su porcentaje, de cuántos y su cambio.

    Rebotes y entregados se miden contra lo que salió; abiertos, clics, quejas y
    bajas contra lo que llegó, que es a quien le pudo pasar. `before` son las
    mismas cuentas del periodo anterior, para la pastilla.
    """
    rows = _counted(counted, leaves)
    if before is None:
        return rows
    old = {one["key"]: one for one in _counted(before, leaves_before)}
    for one in rows:
        was = old.get(one["key"])
        if was is None:
            one["change"] = None
            continue
        # Los enviados se comparan en cuántos; los demás, en su proporción, y
        # **sin redondear antes**: con el 12.5 % de rebotes redondeado a 12, un
        # 25 % se leía como «+108 %» en vez de como el doble que es.
        if one["pct"] is None:
            one["change"] = _change(one["key"], one["n"], was["n"])
        else:
            one["change"] = _change(one["key"], _ratio(one), _ratio(was))
    return rows


# ------------------------------------------------------------- la cuota

# Desde aquí la barra se pone ámbar: es cuando docs/pricing.md dice que se avisa.
QUOTA_WARN = 80


def quota(whose: dict[str, Any]) -> dict[str, Any] | None:
    """Cuántos correos del mes lleva y cuántos trae su plan. None sin plan.

    El mes es el de `accounts.quota_month()`. No se dice cuándo vuelve a cero:
    todavía no hay renovación automática del plan, y anunciar una fecha haría
    pensar que la hay.
    """
    allowed = plans.emails_a_month(accounts.plan_of(whose))
    if not allowed:
        return None
    # Lo que cuenta contra la cuota: tras mejorar de plan, el mes empieza de nuevo.
    used = accounts.used_this_month(whose)
    pct = min(100, round(used * 100 / allowed))
    return {"used": f"{used:,}", "allowed": f"{allowed:,}",
            "pct": pct, "level": ("full" if used >= allowed
                                  else "high" if pct >= QUOTA_WARN else "")}


# ------------------------------------------- las tarjetas que no son cifras

# Cuántas campañas y cuántos meses se enseñan.
TOP_RUNS = 8
GROWTH_MONTHS = 12


def best_runs(db, account_id, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Los envíos del periodo, del que más abrieron al que menos.

    Las cifras las pone `events.counts_by_run()`, la misma consulta que usa
    Enviados: las dos pantallas no pueden decir cosas distintas.
    """
    if not runs:
        return []
    counted = events.counts_by_run(db, account_id, [one["_id"] for one in runs])
    out = []
    for one in runs:
        seen = counted.get(one["_id"], {})
        delivered = seen.get(events.DELIVERED, 0)
        out.append({
            "_id": one["_id"],
            "subject": one.get("subject", ""),
            "at": one.get("finished_at"),
            "sent": one.get("sent", 0),
            "delivered": delivered,
            "open": _share(seen.get(events.OPEN, 0), delivered),
            "click": _share(seen.get(events.CLICK, 0), delivered),
        })
    # Sin entregados no hay porcentaje, y esos van al final.
    out.sort(key=lambda one: (one["open"] is None, -(one["open"] or 0),
                              -(one["click"] or 0)))
    return out[:TOP_RUNS]


def _chart_of(rows: list[dict[str, Any]], kinds, shape: str) -> dict[str, Any]:
    """Una gráfica con la forma que espera `_bars.html`, ya armada.

    La misma plantilla que dibuja los envíos dibuja estas: una gráfica más es
    una consulta, no un dibujo nuevo.
    """
    top = max((max(row["values"][kind["key"]] for kind in kinds)
               for row in rows), default=0)
    ceiling, lines = nice_top(top)
    return {"kinds": kinds, "shape": shape, "rows": rows,
            "top": ceiling, "lines": lines}


def when_open(db, account_id, zone) -> dict[str, Any]:
    """Cuándo abre la lista: por día de la semana y por hora, en su zona."""
    found = events.when_opened(db, account_id, zone)
    total = sum(found["days"])
    kinds = [{"key": "open", "css": "open"}]
    days = [{"values": {"open": n}, "tip": WEEKDAYS[i].capitalize(),
             "tick": DAYS[i]} for i, n in enumerate(found["days"])]
    # Una marca cada tres horas: veinticuatro números seguidos no se leen.
    hours = [{"values": {"open": n}, "tip": f"{i}:00",
              "tick": str(i) if i % 3 == 0 else ""}
             for i, n in enumerate(found["hours"])]
    return {
        "total": total,
        "days": _chart_of(days, kinds, "bars"),
        "hours": _chart_of(hours, kinds, "bars"),
        "top_day": (WEEKDAYS[found["days"].index(max(found["days"]))]
                    if total else ""),
        "top_hour": (f"{found['hours'].index(max(found['hours']))}:00"
                     if total else ""),
        "days_counted": events.WHEN_DAYS,
    }


def growth(db, account_id, zone) -> dict[str, Any]:
    """Altas y bajas por mes, los últimos doce.

    **No es el total de cada mes**: un contacto borrado a mano no deja rastro,
    así que lo que se puede contar es quién entró y a quién se dejó de escribir.
    Las bajas son todas las supresiones, no solo las voluntarias: un rebote duro
    también es alguien a quien ya no se le manda nada.
    """
    from models import contact as contacts
    from models import suppression as suppressions

    here = clock.local(events.now(), zone)
    first = here.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    edges = []
    for _ in range(GROWTH_MONTHS):
        edges.append(first)
        first = (first - timedelta(days=1)).replace(day=1)
    edges.reverse()

    rows = []
    for at, nxt in zip(edges, edges[1:] + [None]):
        start = at.astimezone(timezone.utc)
        end = nxt.astimezone(timezone.utc) if nxt else None
        rows.append({
            "tick": MONTHS[at.month - 1][:3],
            "tip": f"{MONTHS[at.month - 1]} {at.year}",
            "values": {"added": contacts.added_between(db, account_id, start, end),
                       "left": suppressions.count_between(db, account_id, start, end)},
        })
    # En líneas y no en barras apiladas: altas y bajas una encima de otra
    # sumarían un total que no significa nada.
    return _chart_of(rows, [{"key": "added", "css": "added"},
                            {"key": "left", "css": "left"}], "lines")


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

    # Las bajas no salen de `events`: el enlace de baja firma el contacto y no
    # la campaña (services/unsubscribe.py), así que con un filtro puesto no se
    # pueden atribuir y la tarjeta no se dibuja, en vez de enseñar las de toda
    # la cuenta como si fueran las del filtro.
    leaves = leaves_before = None
    filtered = bool(tag) or chosen is not None
    if not filtered:
        start, end = events.window(period, zone)
        leaves = suppressions.count_between(db, whose["_id"], start, end,
                                            reason=suppressions.UNSUBSCRIBE)
        was_start, was_end = events.window(period, zone, back=1)
        leaves_before = suppressions.count_between(db, whose["_id"], was_start,
                                                   was_end,
                                                   reason=suppressions.UNSUBSCRIBE)

    start, end = events.window(period, zone)
    runs = campaign_runs.between(db, whose["_id"], start, end, tag=tag,
                                 campaign=chosen)
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
        "rates": rates(events.people(db, whose["_id"], **where),
                       events.people(db, whose["_id"], back=1, **where),
                       leaves=leaves, leaves_before=leaves_before),
        # Contra qué compara la pastilla, con el nombre del periodo puesto.
        "before": t("stats_before_" + period),
        "leaves_off": filtered,
        "best": best_runs(db, whose["_id"], runs),
        "links": events.top_links(db, whose["_id"], **where),
        "when": when_open(db, whose["_id"], zone),
        "growth": growth(db, whose["_id"], zone),
        "quota": quota(whose),
    }
