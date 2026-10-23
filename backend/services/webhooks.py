"""Los avisos a su sistema (webhooks), octubre de 2026: anotarlos, firmarlos y
entregarlos.

  * **Se anotan sin romper a quien los produce**: el aviso de SES, la baja y el
    final de una campaña llaman a `emit()`, que nunca lanza. Y
    solo cuando el evento es nuevo, así mil aperturas son un aviso.
  * **La firma**: `Sobreala-Signature: t=<unix>,v1=<HMAC-SHA256 de "t.cuerpo">`
    con el secreto del destino, más `Sobreala-Event-Id` y `Sobreala-Event-Type`.
  * **El secreto no se guarda**: sale de `SECRET_KEY` con su propia etiqueta
    (no la de `hash_keyed`, que firma las bajas), el id del destino y su
    `salt`. Se enseña al crearlo y al cambiarlo.
  * **Los entrega el proceso en segundo plano**, en su propio hilo
    (`deliver_tick`), por `services/safe_http.py`: cinco segundos en total y
    nunca a la red interna. Si uno falla, los pendientes del mismo destino se
    corren con él; tras 72 horas fallando, el destino se apaga y se le avisa
    al dueño.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from config import Config
from models import event as events
from models import webhook as hooks
from services import safe_http

log = logging.getLogger(__name__)

# Qué evento de `events` es qué aviso.
FROM_EVENTS = {events.DELIVERED: hooks.EMAIL_DELIVERED, events.BOUNCE: hooks.EMAIL_BOUNCED,
               events.COMPLAINT: hooks.EMAIL_COMPLAINED, events.REJECT: hooks.EMAIL_REJECTED,
               events.OPEN: hooks.EMAIL_OPENED, events.CLICK: hooks.EMAIL_CLICKED}


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(when: datetime | None) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def secret_of(endpoint: dict[str, Any]) -> str:
    raw = hmac.new(Config.SECRET_KEY.encode("utf-8"),
                   f"sobreala:webhook-secret:{endpoint['_id']}:{endpoint['salt']}".encode(),
                   hashlib.sha256).digest()
    return "whsec_" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def sign(secret: str, body: bytes, stamp: int) -> str:
    return hmac.new(secret.encode("utf-8"), f"{stamp}.".encode("ascii") + body,
                    hashlib.sha256).hexdigest()


def event_id(key: str) -> str:
    return "evt_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


# ------------------------------------------------------------ anotar

def emit(db, account_id, kind: str, data: dict[str, Any], *, key: str) -> int:
    """Anotar un aviso para cada destino de la cuenta que lo quiere. Devuelve
    cuántos. Nunca lanza: quien llama está contando un evento o dando de baja
    a alguien, y eso ya pasó."""
    try:
        targets = hooks.listening(db, account_id, kind)
        if not targets:
            return 0
        payload = {"id": event_id(key), "type": kind, "created_at": iso(now()),
                   "data": data() if callable(data) else data}
        return sum(1 for one in targets
                   if hooks.queue(db, one, event_key=key, kind=kind, payload=payload))
    except Exception:  # noqa: BLE001 - un aviso no rompe lo que lo produjo
        log.exception("no se pudo anotar el aviso %s", kind)
        return 0


def email_event(db, account_id, *, kind: str, campaign_id, run_id, email: str,
                at: datetime | None = None, link: str = "", permanent: bool | None = None) -> int:
    """El aviso de lo que le pasó a un correo: de una campaña, de un correo
    individual o de la API, con sus ids."""
    hook = FROM_EVENTS.get(kind)
    if hook is None:
        return 0

    def data() -> dict[str, Any]:
        shown: dict[str, Any] = {"email": (email or "").strip().lower(), "at": iso(at or now())}
        message = db.messages.find_one({"_id": campaign_id}, {"kind": 1}) if campaign_id else None
        if message is not None:
            shown.update(source="api", email_id=str(campaign_id),
                         email_type=message.get("kind"))
        else:
            found = db.campaigns.find_one({"_id": campaign_id}, {"kind": 1}) if campaign_id else None
            shown.update(source="single" if (found or {}).get("kind") == "single" else "campaign",
                         campaign_id=str(campaign_id) if campaign_id else None,
                         send_id=str(run_id) if run_id else None)
        if link:
            shown["link"] = link
        if permanent is not None:
            shown["permanent"] = permanent
        return shown

    return emit(db, account_id, hook, data, key=f"{hook}:{run_id}:{(email or '').lower()}")


# ------------------------------------------------------------ entregar

def attempt(endpoint: dict[str, Any], payload: dict[str, Any], *,
            poster=safe_http.post) -> safe_http.Answer:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stamp = int(time.time())
    return poster(endpoint["url"], body, {
        "Content-Type": "application/json",
        "Sobreala-Signature": f"t={stamp},v1={sign(secret_of(endpoint), body, stamp)}",
        "Sobreala-Event-Id": payload.get("id", ""),
        "Sobreala-Event-Type": payload.get("type", "")})


def test_payload() -> dict[str, Any]:
    return {"id": event_id(f"test:{time.time_ns()}"), "type": hooks.TEST,
            "created_at": iso(now()), "data": {"message": "Aviso de prueba de Sobreala."}}


def deliver_tick(db, *, limit: int = 50, poster=safe_http.post) -> int:
    """Intentar los que tocan. Devuelve cuántos se intentaron."""
    tried = 0
    for one in hooks.due(db, limit=limit):
        endpoint = db.webhook_endpoints.find_one({"_id": one["endpoint_id"]})
        if endpoint is None:
            db.webhook_deliveries.delete_one({"_id": one["_id"]})
            continue
        waiting = hooks.aware(endpoint.get("next_try_at"))
        if not endpoint.get("enabled") or (waiting and waiting > now()):
            # Apagado, o esperando su reintento: este espera con él.
            db.webhook_deliveries.update_one({"_id": one["_id"]}, {"$set": {
                "next_at": waiting if waiting and waiting > now() else
                now().replace(microsecond=0) + hooks.BACKOFF_PAUSE}})
            continue
        claimed = hooks.claim(db, one["_id"])
        if claimed is None:
            continue
        tried += 1
        answer = attempt(endpoint, claimed["payload"], poster=poster)
        if answer.ok:
            hooks.delivered(db, claimed["_id"], status=answer.status, ms=answer.ms)
            hooks.update(db, endpoint["account_id"], endpoint["_id"], failing_since=None,
                         next_try_at=None, last_status=answer.status, last_at=now())
            continue
        since = hooks.aware(endpoint.get("failing_since")) or now()
        give_up = now() - since > hooks.GIVE_UP
        when = hooks.retry(db, claimed, status=answer.status, error=answer.error,
                           ms=answer.ms, give_up=give_up)
        hooks.update(db, endpoint["account_id"], endpoint["_id"], failing_since=since,
                     next_try_at=when, last_status=answer.status, last_at=now(),
                     last_error=answer.error)
        if give_up:
            switch_off(db, endpoint)
    return tried


def switch_off(db, endpoint: dict[str, Any]) -> None:
    """Apagar un destino que lleva 72 horas fallando, y decírselo al dueño."""
    from models import account as accounts
    from services import notices

    hooks.update(db, endpoint["account_id"], endpoint["_id"], enabled=False,
                 disabled_reason="failing", next_try_at=None)
    owner = accounts.by_id(db, endpoint["account_id"])
    if owner is not None:
        notices.webhook_disabled(owner, host=endpoint.get("host", ""))
