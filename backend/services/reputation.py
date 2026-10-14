"""La reputación de cada cliente, y la pausa automática (octubre de 2026).

Amazon mide la cuenta entera de Sobreala: con 5 % de rebotes la pone en
revisión, y con eso se para el envío de todos los clientes. Por eso el panel
mide a cada cliente por su lado y **pausa al que pasa del umbral antes de que
llegue a Amazon**. La pausa es un límite (`accounts.pause()`): entra, prepara y
paga, pero no envía, y solo la quita el administrador desde la ficha.

Se mira lo que la cuenta envió en los últimos `WINDOW_DAYS` días, y solo desde
un volumen mínimo: con veinte correos, un rebote es un 5 % y no dice nada de la
lista. Los rebotes son **permanentes** (la dirección no existe) y salen de las
supresiones que puso el aviso de SES, igual que las quejas: así cuentan
personas, y un rebote pasajero (buzón lleno) no pausa a nadie.

Lo usan dos: el aviso de SES (`ses_events.py`), que llama a `check()` después de
cada rebote permanente o queja, y la pantalla Clientes de administración, que
enseña las mismas cifras con `figures()`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from i18n import t
from models import account as accounts
from models import admin_event as decisions
from models import event as events
from models import suppression as suppressions
from services import notices

WINDOW_DAYS = 30
# Rebotes permanentes: más de 3 %, desde 100 enviados. Amazon revisa a 5 %.
BOUNCE_LIMIT = 0.03
BOUNCE_MIN_SENT = 100
# Quejas: más de 0.1 %, desde 1,000 enviados. Amazon revisa a 0.1 %; con menos
# volumen, una sola persona que pulsa «es spam» pausaría la cuenta.
COMPLAINT_LIMIT = 0.001
COMPLAINT_MIN_SENT = 1000
# Desde dónde Clientes lo pinta en ámbar: dos tercios del umbral.
BOUNCE_WARN = 0.02
COMPLAINT_WARN = 0.0007

# Las cifras de una cuenta, en personas.
EMPTY = {"sent": 0, "delivered": 0, "opened": 0, "bounces": 0, "complaints": 0}


def now() -> datetime:
    return datetime.now(timezone.utc)


def figures(db, account_ids: Iterable[Any], *, days: int = WINDOW_DAYS,
            since: datetime | None = None) -> dict[Any, dict[str, int]]:
    """Lo enviado, entregado, abierto, rebotado y quejado de cada cuenta.

    Una consulta a `events` y otra a `suppressions` para todas las cuentas
    juntas, no una por cuenta. Una cuenta sin nada sale con todo en cero.
    """
    ids = list(account_ids)
    since = since or now() - timedelta(days=days)
    out = {one: dict(EMPTY) for one in ids}
    if not ids:
        return out
    by_kind = {events.SENT: "sent", events.DELIVERED: "delivered",
               events.OPEN: "opened"}
    for row in db.events.aggregate([
            {"$match": {"account_id": {"$in": ids}, "kind": {"$in": list(by_kind)},
                        "created_at": {"$gte": since}}},
            {"$group": {"_id": {"account": "$account_id", "kind": "$kind"},
                        "n": {"$sum": 1}}}]):
        out[row["_id"]["account"]][by_kind[row["_id"]["kind"]]] = row["n"]
    by_reason = {suppressions.HARD_BOUNCE: "bounces",
                 suppressions.COMPLAINT: "complaints"}
    for row in db.suppressions.aggregate([
            {"$match": {"account_id": {"$in": ids}, "source": "ses",
                        "reason": {"$in": list(by_reason)},
                        "created_at": {"$gte": since}}},
            {"$group": {"_id": {"account": "$account_id", "reason": "$reason"},
                        "n": {"$sum": 1}}}]):
        out[row["_id"]["account"]][by_reason[row["_id"]["reason"]]] = row["n"]
    return out


def rate(part: int, sent: int) -> float:
    return part / sent if sent else 0.0


def verdict(numbers: dict[str, int]) -> str | None:
    """El motivo de pausa que toca con estas cifras, o None."""
    sent = numbers["sent"]
    if sent >= BOUNCE_MIN_SENT and rate(numbers["bounces"], sent) > BOUNCE_LIMIT:
        return accounts.PAUSE_BOUNCES
    if (sent >= COMPLAINT_MIN_SENT
            and rate(numbers["complaints"], sent) > COMPLAINT_LIMIT):
        return accounts.PAUSE_COMPLAINTS
    return None


def percent(value: float, digits: int = 1) -> str:
    """Una proporción como porcentaje legible: 0.042 → «4.2 %»."""
    return f"{value * 100:.{digits}f} %"


def describe(reason: str, numbers: dict[str, int]) -> str:
    """Las cifras que dispararon la pausa, para la ficha y los avisos."""
    sent = numbers["sent"]
    if reason == accounts.PAUSE_BOUNCES:
        return t("pause_note_bounces", rate=percent(rate(numbers["bounces"], sent)),
                 n=numbers["bounces"], sent=sent, days=WINDOW_DAYS)
    return t("pause_note_complaints",
             rate=percent(rate(numbers["complaints"], sent), 2),
             n=numbers["complaints"], sent=sent, days=WINDOW_DAYS)


def check(db, account_id) -> str | None:
    """Pausar la cuenta si pasó un umbral. Devuelve el motivo si la pausó.

    Una cuenta que ya está en pausa no se vuelve a pausar ni a avisar: los
    rebotes de una campaña llegan de a uno, y después del primero que pasa el
    umbral todos los demás también lo pasan.
    """
    account = accounts.by_id(db, account_id)
    if account is None or accounts.is_paused(account):
        return None
    numbers = figures(db, [account_id])[account_id]
    reason = verdict(numbers)
    if reason is None:
        return None
    note = describe(reason, numbers)
    before = (accounts.limited_of(account) or {}).get("reason")
    if not accounts.pause(db, account_id, reason=reason, note=note):
        return None
    decisions.record(db, kind=decisions.LIMIT, admin_id=None,
                     account_id=account_id, before=before, after=reason,
                     reason=t("pause_auto_reason", note=note))
    notices.paused(account, reason=reason, note=note)
    notices.pause_to_admins(db, account, reason=reason, note=note)
    return reason
