"""Los correos que manda la API, uno por documento (octubre de 2026).

No van en Enviados: una tienda con quinientas confirmaciones al día taparía las
campañas. Se ven en API → Correos, y lo que pasó con cada uno (entregado,
abierto, rebotado) vive en `events`, atado a su id: SES devuelve ese id en las
etiquetas de cada aviso (`campaign` y `run`, como un envío de una persona).

**Nunca se guardan los datos ni el HTML**: un código de acceso o un enlace para
cambiar la contraseña no se quedan en la base. El asunto se guarda como se
escribió, con sus marcas sin llenar. Se borran solos a los 30 días.

El estado pasa de `pending` (apartado y a punto de salir) a `sent` o `failed`.
Uno que se quedó en `pending` es uno cuyo proceso murió entre llamar a SES y
anotarlo: no se sabe si salió, y repetir con la misma `Idempotency-Key` lo
devuelve tal cual en vez de mandarlo otra vez.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

PENDING = "pending"
SENT = "sent"
FAILED = "failed"
STATUSES = (PENDING, SENT, FAILED)

TRANSACTIONAL = "transactional"
PROMOTIONAL = "promotional"
TYPES = (TRANSACTIONAL, PROMOTIONAL)

KEEP_DAYS = 30


def now() -> datetime:
    return datetime.now(timezone.utc)


def start(db, *, account_id, key_id, kind: str, to: str, contact_id, subject: str,
          template_id, sent_from: str, reply_to: str, request_key: str | None):
    """Anotar uno que está por salir. Devuelve su id, o None si esa
    `Idempotency-Key` ya tiene uno (lo dice el índice único)."""
    moment = now()
    doc = {"account_id": account_id, "key_id": key_id, "kind": kind, "to": to,
           "to_normalized": to.strip().lower(), "contact_id": contact_id,
           "subject": subject, "template_id": template_id, "from": sent_from,
           "reply_to": reply_to, "status": PENDING, "created_at": moment,
           "expires_at": moment + timedelta(days=KEEP_DAYS)}
    if request_key:
        doc["request_key"] = request_key
    try:
        return db.messages.insert_one(doc).inserted_id
    except DuplicateKeyError:
        return None


def sent(db, message_id, *, ses_id: str) -> None:
    db.messages.update_one({"_id": message_id, "status": PENDING},
                           {"$set": {"status": SENT, "ses_id": ses_id[:200],
                                     "sent_at": now()}})


def failed(db, message_id, *, error: str) -> None:
    db.messages.update_one({"_id": message_id, "status": PENDING},
                           {"$set": {"status": FAILED, "error": error[:300]}})


def by_request(db, account_id, key_id, request_key: str) -> dict[str, Any] | None:
    return db.messages.find_one({"account_id": account_id, "key_id": key_id,
                                 "request_key": request_key})


def forget(db, message_id) -> None:
    """Quitar uno que falló, para que repetir con la misma clave lo intente de
    nuevo."""
    db.messages.delete_one({"_id": message_id, "status": FAILED})


def by_id(db, account_id, message_id) -> dict[str, Any] | None:
    return db.messages.find_one({"_id": message_id, "account_id": account_id})


def by_ids(db, ids) -> dict[Any, dict[str, Any]]:
    """Varios por id, para escribir su asunto donde se listan eventos."""
    wanted = [one for one in set(ids) if one is not None]
    if not wanted:
        return {}
    return {one["_id"]: one for one in db.messages.find(
        {"_id": {"$in": wanted}}, {"subject": 1, "kind": 1, "account_id": 1})}


def count_this_month(db, account_id) -> dict[str, int]:
    """Cuántos de cada clase salieron este mes (lo que ve el administrador)."""
    start_of_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    counted = {kind: 0 for kind in TYPES}
    for row in db.messages.aggregate([
            {"$match": {"account_id": account_id, "status": SENT,
                        "created_at": {"$gte": start_of_month}}},
            {"$group": {"_id": "$kind", "n": {"$sum": 1}}}]):
        counted[row["_id"]] = row["n"]
    return counted
