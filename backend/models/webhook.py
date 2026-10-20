"""Los avisos a su sistema (webhooks) y sus entregas (octubre de 2026).

`webhook_endpoints`: a dónde manda la cuenta sus avisos, hasta `LIMIT`, cada
uno con los eventos que quiere y su `salt`, que junto con `SECRET_KEY` da su
secreto (el secreto no se guarda: `services/webhooks.secret_of`).

`webhook_deliveries`: un aviso por destino y evento, **una sola vez** (índice
único `(endpoint_id, event_key)`: SNS puede repetir un aviso y el índice de
`events` no es único). Los entregados se borran a los 3 días y los demás a los
30.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

LIMIT = 5
DESCRIPTION_MAX = 120

EMAIL_DELIVERED = "email.delivered"
EMAIL_BOUNCED = "email.bounced"
EMAIL_COMPLAINED = "email.complained"
EMAIL_REJECTED = "email.rejected"
EMAIL_OPENED = "email.opened"
EMAIL_CLICKED = "email.clicked"
EMAIL_DOWNLOADED = "email.downloaded"
CONTACT_UNSUBSCRIBED = "contact.unsubscribed"
CAMPAIGN_FINISHED = "campaign.finished"
TEST = "test"
EVENTS = (EMAIL_DELIVERED, EMAIL_BOUNCED, EMAIL_COMPLAINED, EMAIL_REJECTED,
          EMAIL_OPENED, EMAIL_CLICKED, EMAIL_DOWNLOADED, CONTACT_UNSUBSCRIBED,
          CAMPAIGN_FINISHED)

PENDING = "pending"
DELIVERED = "delivered"
FAILED = "failed"

# Reintentos, en segundos desde el fallo anterior.
BACKOFF = (60, 300, 1800, 7200, 21600, 43200, 86400)
# Fallando más de esto seguido, el aviso se apaga y se le dice al dueño.
GIVE_UP = timedelta(hours=72)
# Cada cuánto se vuelve a mirar uno de un destino apagado: si lo encienden, sale.
BACKOFF_PAUSE = timedelta(hours=1)
KEEP_DELIVERED = timedelta(days=3)
KEEP_OTHERS = timedelta(days=30)


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(when: datetime | None) -> datetime | None:
    if when is not None and when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when


# ------------------------------------------------------------ los destinos

def for_account(db, account_id) -> list[dict[str, Any]]:
    return list(db.webhook_endpoints.find({"account_id": account_id}).sort("created_at", 1))


def by_id(db, account_id, endpoint_id) -> dict[str, Any] | None:
    return db.webhook_endpoints.find_one({"_id": endpoint_id, "account_id": account_id})


def listening(db, account_id, kind: str) -> list[dict[str, Any]]:
    """Los encendidos de esa cuenta que quieren ese evento."""
    return list(db.webhook_endpoints.find({"account_id": account_id, "enabled": True,
                                           "events": kind}))


def create(db, account_id, *, url: str, host: str, events: list[str],
           description: str) -> Any:
    return db.webhook_endpoints.insert_one({
        "account_id": account_id, "url": url, "host": host, "events": list(events),
        "description": description[:DESCRIPTION_MAX], "enabled": True,
        "salt": secrets.token_hex(16), "created_at": now(), "updated_at": now(),
        "failing_since": None, "next_try_at": None}).inserted_id


def update(db, account_id, endpoint_id, **changes: Any) -> bool:
    return db.webhook_endpoints.update_one(
        {"_id": endpoint_id, "account_id": account_id},
        {"$set": {**changes, "updated_at": now()}}).matched_count == 1


def rotate(db, account_id, endpoint_id) -> bool:
    """Otro secreto: el de antes deja de servir en ese momento."""
    return update(db, account_id, endpoint_id, salt=secrets.token_hex(16))


def remove(db, account_id, endpoint_id) -> bool:
    gone = db.webhook_endpoints.delete_one({"_id": endpoint_id, "account_id": account_id})
    db.webhook_deliveries.delete_many({"endpoint_id": endpoint_id, "account_id": account_id})
    return gone.deleted_count == 1


# ------------------------------------------------------------ las entregas

def queue(db, endpoint: dict[str, Any], *, event_key: str, kind: str,
          payload: dict[str, Any]) -> bool:
    """Anotar uno para entregar. False si ese evento ya estaba para ese destino."""
    moment = now()
    try:
        db.webhook_deliveries.insert_one({
            "account_id": endpoint["account_id"], "endpoint_id": endpoint["_id"],
            "event_key": event_key, "kind": kind, "payload": payload,
            "status": PENDING, "attempts": 0, "next_at": moment, "created_at": moment,
            "expires_at": moment + KEEP_OTHERS})
    except DuplicateKeyError:
        return False
    return True


def due(db, *, limit: int = 50) -> list[dict[str, Any]]:
    """Los que toca intentar ahora, los más viejos primero."""
    return list(db.webhook_deliveries.find({"status": PENDING, "next_at": {"$lte": now()}})
                .sort("next_at", 1).limit(limit))


def claim(db, delivery_id, *, seconds: int = 60) -> dict[str, Any] | None:
    """Tomarlo para intentarlo: corre su hora un poco, así otro proceso no lo
    intenta a la vez."""
    moment = now()
    return db.webhook_deliveries.find_one_and_update(
        {"_id": delivery_id, "status": PENDING, "next_at": {"$lte": moment}},
        {"$set": {"next_at": moment + timedelta(seconds=seconds)}},
        return_document=ReturnDocument.AFTER)


def delivered(db, delivery_id, *, status: int | None, ms: int) -> None:
    moment = now()
    db.webhook_deliveries.update_one({"_id": delivery_id}, {
        "$set": {"status": DELIVERED, "last_status": status, "last_error": "",
                 "ms": ms, "delivered_at": moment, "expires_at": moment + KEEP_DELIVERED},
        "$inc": {"attempts": 1}})


def retry(db, delivery: dict[str, Any], *, status: int | None, error: str, ms: int,
          give_up: bool) -> datetime | None:
    """Anotar un intento fallido. Devuelve cuándo va el siguiente, o None si
    ya no hay más."""
    attempts = int(delivery.get("attempts", 0)) + 1
    over = give_up or attempts > len(BACKOFF)
    when = None if over else now() + timedelta(seconds=BACKOFF[attempts - 1])
    db.webhook_deliveries.update_one({"_id": delivery["_id"]}, {"$set": {
        "status": FAILED if over else PENDING, "attempts": attempts,
        "last_status": status, "last_error": error, "ms": ms,
        **({"next_at": when} if when else {})}})
    return when


def recent(db, account_id, endpoint_id, *, limit: int = 50) -> list[dict[str, Any]]:
    return list(db.webhook_deliveries.find({"account_id": account_id,
                                            "endpoint_id": endpoint_id},
                                           {"payload": 0})
                .sort("created_at", -1).limit(limit))
