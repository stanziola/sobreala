"""El ritmo de envío de todo Sobreala (octubre de 2026).

Amazon le da a la cuenta un límite de correos por segundo y otro por día: en el
sandbox, 1 y 200; en producción, lo que apruebe (lo normal, 14 y 50,000). Hasta
este mes solo el proceso en segundo plano respetaba un ritmo, y era fijo; el
web, la API y los correos del sistema mandaban todo lo rápido que podían, y
entre todos se pasaban. Una campaña aguanta (reintenta); un código de
confirmación se perdía.

Lo de aquí lo usa **todo lo que le escribe a Amazon**:

  * **Los límites se leen de Amazon** (`GetSendQuota`) cada 5 minutos y se
    guardan en la base, así que suben solos el día de la producción. Encima de
    lo de Amazon, cada proceso aplica sus variables: `SES_MAX_PER_SECOND` y
    `SES_MAX_PER_DAY` solo bajan el límite, nunca lo suben. Si Amazon no
    contesta (falta `ses:GetSendQuota` en IAM), vale lo último guardado, o las
    variables, o 1 por segundo y 200 al día.
  * **Un solo reloj para todos** (`take()`): un documento en la base con la
    hora del próximo turno libre, que se corre de forma atómica. Vale entre el
    web y el worker y entre los hilos de gunicorn. Cada envío toma el suyo y
    espera a que llegue.
  * **Prioridad sencilla**: las campañas toman turnos del 80 % del ritmo (más
    largos), así que siempre quedan huecos para un código del sistema o un
    correo de la API, que esperan como mucho un turno o dos. El sistema espera
    hasta 10 segundos, la API y el individual hasta 5; las campañas, lo que
    haga falta.
  * **El tope del día** (`day_room()`): lo enviado según Amazon más lo que se
    contó desde entonces. Las campañas y la API se paran antes del final y le
    dejan al sistema una reserva (el 5 % del día, mínimo 20), para que un código
    de confirmación siga llegando aunque el día se haya llenado de campañas.

Sin `MAIL_BACKEND=ses` no se limita nada: en desarrollo y en las pruebas los
correos van a disco.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from config import Config

log = logging.getLogger(__name__)

SYSTEM, API, SINGLE, CAMPAIGN = "system", "api", "single", "campaign"
# Cuánto espera cada uno su turno, como mucho. None es lo que haga falta.
WAITS = {SYSTEM: 10.0, API: 5.0, SINGLE: 5.0, CAMPAIGN: None}
# La parte del ritmo que usan las campañas: lo demás queda para el sistema y la
# API.
CAMPAIGN_SHARE = 0.8
# Cada cuánto se le vuelve a preguntar a Amazon.
REFRESH = timedelta(minutes=5)
# Sin nada mejor, lo del sandbox: lo más prudente.
DEFAULT_RATE, DEFAULT_DAY = 1.0, 200
# La reserva del día para los correos del sistema.
RESERVE_SHARE, RESERVE_MIN = 0.05, 20

LIMITS, CLOCK = "limits", "clock"
_warned = {"quota": False}


class Busy(Exception):
    """No hubo turno dentro de lo que ese envío puede esperar. Se trata como
    cuando Amazon pide esperar: no es un fallo del correo."""


def enabled() -> bool:
    return Config.MAIL_BACKEND == "ses"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ask_amazon() -> dict[str, Any] | None:
    """Lo que Amazon le permite a la cuenta, o None si no contesta."""
    try:
        from services import aws

        answer = aws.client("ses").get_send_quota()
        return {"rate": float(answer["MaxSendRate"]), "day": int(answer["Max24HourSend"]),
                "sent": int(answer["SentLast24Hours"])}
    except Exception as exc:  # noqa: BLE001 - se sigue con lo que haya
        if not _warned["quota"]:
            _warned["quota"] = True
            print(f"  [ritmo] no se pudo leer el límite de Amazon ({type(exc).__name__}): "
                  "se usan las variables. ¿Falta ses:GetSendQuota en IAM?", flush=True)
        return None


def limits(db, *, now: datetime | None = None) -> dict[str, Any]:
    """Los límites que rigen ahora, con lo enviado en las últimas 24 horas."""
    moment = now or utcnow()
    doc = db.ses_limits.find_one({"_id": LIMITS})
    if doc is None or moment - doc["at"] >= REFRESH:
        fresh = _ask_amazon()
        if fresh is not None:
            values, source, used = fresh, "amazon", 0
        elif doc is not None:
            values = {key: doc[key] for key in ("rate", "day", "sent")}
            source, used = doc.get("source", "default"), doc.get("used", 0)
        else:
            values = {"rate": float(Config.SES_MAX_PER_SECOND or DEFAULT_RATE),
                      "day": int(Config.SES_MAX_PER_DAY or DEFAULT_DAY), "sent": 0}
            source, used = "config", 0
        doc = {"_id": LIMITS, **values, "source": source, "used": used, "at": moment}
        db.ses_limits.replace_one({"_id": LIMITS}, doc, upsert=True)
    per_second, per_day = float(doc["rate"]), int(doc["day"])
    if Config.SES_MAX_PER_SECOND:
        per_second = min(per_second, float(Config.SES_MAX_PER_SECOND))
    if Config.SES_MAX_PER_DAY:
        per_day = min(per_day, int(Config.SES_MAX_PER_DAY))
    return {"per_second": max(per_second, 0.01), "per_day": per_day,
            "sent": int(doc["sent"]) + int(doc.get("used", 0)), "source": doc["source"],
            "amazon_rate": float(doc["rate"]), "amazon_day": int(doc["day"])}


def day_room(db, kind: str) -> int | None:
    """Cuántos correos de esa clase caben todavía hoy. None si no se limita."""
    if not enabled():
        return None
    found = limits(db)
    left = found["per_day"] - found["sent"]
    if kind == SYSTEM:
        return left
    return left - max(RESERVE_MIN, int(found["per_day"] * RESERVE_SHARE))


def take(db, kind: str, *, clock=None, sleep=None) -> None:
    """Esperar el turno de un correo. Levanta `Busy` si no llega a tiempo."""
    if not enabled():
        return
    rate = limits(db)["per_second"] * (CAMPAIGN_SHARE if kind == CAMPAIGN else 1.0)
    moment = (clock or time.time)()
    before = db.ses_limits.find_one_and_update(
        {"_id": CLOCK},
        [{"$set": {"next_at": {"$add": [{"$max": [{"$ifNull": ["$next_at", 0]}, moment]},
                                        1.0 / rate]}}}],
        upsert=True, return_document=ReturnDocument.BEFORE)
    wait = max(float((before or {}).get("next_at") or 0), moment) - moment
    limit = WAITS.get(kind)
    if limit is not None and wait > limit:
        raise Busy(kind)
    if wait > 0:
        (sleep or time.sleep)(wait)
    db.ses_limits.update_one({"_id": LIMITS}, {"$inc": {"used": 1}})


def status(db) -> dict[str, Any]:
    """Lo que enseñan `/health` y Administración. Vacío sin envío de verdad."""
    if not enabled():
        return {}
    found = limits(db)
    return {"ses_rate": found["per_second"], "ses_day": found["per_day"],
            "ses_day_left": max(0, found["per_day"] - found["sent"]),
            "ses_limits_from": found["source"]}
