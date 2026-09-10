"""Lo que enseña la pantalla de estadísticas, de una cuenta cualquiera.

Vive aquí y no en un blueprint porque la miran dos: el cliente en `/panel`, con
la suya, y el administrador en `/admin/`, con la de quien elija. Una sola
función que llena una sola plantilla; si la pantalla cambia, cambia para los
dos a la vez y no hay forma de que una se quede atrás.

Las gráficas salen de `events`, que todavía no existe: hoy devuelve ceros y la
plantilla dibuja el cuadro vacío diciéndolo.
"""

from __future__ import annotations

from typing import Any

from models import account as accounts
from models import contact as contacts
from models import event as events
from models import import_job as imports
from services import plans


def screen(db, whose: dict[str, Any], *, period: str = "",
           tag: str = "") -> dict[str, Any]:
    """Todo lo que la plantilla necesita para una cuenta.

    El periodo y la etiqueta llegan de la dirección, así que se limpian aquí:
    un periodo que no existe cae en el de por omisión, y una etiqueta que no es
    de esta cuenta no filtra por nada, en vez de filtrar por algo ajeno.
    """
    period = events.clean_period(period)
    known = accounts.tags_of(whose)
    tag = tag if tag in known else ""

    total = contacts.count(db, whose["_id"])
    active = contacts.active_count(db, whose["_id"])
    series = events.series(db, whose["_id"], period=period, tag=tag)
    return {
        "whose": whose,
        "confirmed": accounts.is_confirmed(whose),
        "period": period,
        "periods": list(events.PERIODS),
        "tag": tag,
        "tags": known,
        "series": series,
        "top": events.busiest(series, (events.SENT, events.BOUNCE)),
        "totals": events.totals(db, whose["_id"], period=period, tag=tag),
        "active": active,
        "blocked": total - active,
        "limit": accounts.contact_limit(whose),
        "imports": imports.for_account(db, whose["_id"], limit=10),
        "plan": accounts.plan_of(whose),
        "plan_until": accounts.plan_until(whose),
        "emails_limit": plans.emails_a_month(accounts.plan_of(whose)),
    }
