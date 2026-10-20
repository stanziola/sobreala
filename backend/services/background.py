"""Lo que hace el proceso en segundo plano en cada vuelta (octubre de 2026).

`worker.py` es el bucle; esto es lo que hace cada vez, aparte para poder
probarlo sin bucle:

  * **Las campañas**: las que tienen `auto_send` y les llegó la hora, una
    tanda por campaña y vuelta, así las de varias cuentas se turnan. Cada tanda
    la manda quien tiene el turno (`campaigns.take`); una que no puede salir
    (sin cuota, en pausa, cuenta suspendida) anota por qué y se reintenta más
    tarde.
  * **El latido** en `worker_state`: cuándo dio la última vuelta. Lo enseñan
    `/health` y Clientes en administración, que es como se nota que se cayó.
  * **La misma llave que el web.** El worker firma los enlaces de baja con
    `SECRET_KEY`; con otra, cada enlace saldría muerto (regla 3). El web deja en
    la base una huella de su llave (no la llave) y el worker no manda nada si
    la suya no coincide.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config import Config
from models import account as accounts
from models import campaign as campaigns
from services import sender

log = logging.getLogger(__name__)

# Pasado esto sin latido, el proceso se da por caído.
STALE = timedelta(seconds=90)
WEB = "web"
WORKER = "worker"


def now() -> datetime:
    return datetime.now(timezone.utc)


def fingerprint() -> str:
    """Una huella de `SECRET_KEY` que no sirve para sacar la llave."""
    return hmac.new(Config.SECRET_KEY.encode("utf-8"), b"sobreala:worker-key",
                    hashlib.sha256).hexdigest()[:16]


def publish_web_key(db) -> None:
    """Lo llama el web al arrancar: su huella, para que el worker compare."""
    db.worker_state.update_one({"_id": WEB},
                               {"$set": {"fingerprint": fingerprint(), "at": now()}},
                               upsert=True)


def key_ok(db) -> bool | None:
    """Si el worker tiene la misma llave que el web. None si el web todavía no
    dejó la suya (recién desplegado y sin una sola visita)."""
    found = db.worker_state.find_one({"_id": WEB})
    if not found:
        return None
    return hmac.compare_digest(found.get("fingerprint", ""), fingerprint())


def beat(db, name: str, *, key: bool | None, sent: int = 0) -> None:
    changes: dict[str, Any] = {"at": now(), "name": name, "key_ok": key}
    update: dict[str, Any] = {"$set": changes}
    if sent:
        changes["last_sent_at"] = now()
        update["$inc"] = {"sent": sent}
    db.worker_state.update_one({"_id": WORKER}, update, upsert=True)


def status(db) -> dict[str, Any]:
    """Cómo está el proceso: `up`, `down` (sin latido reciente) o `never`, y si
    su llave coincide. Para `/health` y administración; no dice nada secreto."""
    found = db.worker_state.find_one({"_id": WORKER})
    if not found:
        return {"worker": "never", "worker_key": "unknown"}
    seen = found["at"] if found["at"].tzinfo else found["at"].replace(tzinfo=timezone.utc)
    return {"worker": "up" if now() - seen < STALE else "down",
            "worker_seen_at": seen.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "worker_key": {True: "ok", False: "mismatch"}.get(found.get("key_ok"), "unknown")}


def campaigns_tick(db, by: str, *, stop=None, pace: float = 0.0, limit: int = 20) -> int:
    """Una tanda de cada campaña que toca. Devuelve cuántos correos salieron."""
    sent = 0
    for found in campaigns.ready_to_go(db, limit=limit):
        if stop is not None and stop():
            break
        account_id = found["account_id"]
        if not campaigns.take(db, account_id, found["_id"], by):
            continue
        try:
            account = accounts.by_id(db, account_id)
            fresh = campaigns.by_id(db, account_id, found["_id"])
            if (account is None or fresh is None or not fresh.get("auto_send")
                    or fresh["status"] not in (campaigns.SCHEDULED, campaigns.SENDING)):
                continue
            if accounts.is_suspended(account) or not accounts.is_open(account):
                # El panel no la deja entrar; tampoco sale nada suyo por detrás.
                campaigns.wait(db, account_id, found["_id"], ["suspended"])
                continue
            result = sender.run(db, account, fresh, lease_by=by, stop=stop, pace=pace)
            if result["blocked"] and result["blocked"] != ["busy"]:
                campaigns.wait(db, account_id, found["_id"], result["blocked"])
            elif not result["blocked"]:
                campaigns.clear_wait(db, account_id, found["_id"])
            sent += result.get("sent", 0)
        except Exception:  # noqa: BLE001 - una campaña rota no frena a las demás
            log.exception("campaña %s: la tanda falló", found["_id"])
        finally:
            campaigns.release(db, account_id, found["_id"], by)
    return sent
