"""Que repetir una petición de la API no haga dos veces lo mismo (octubre de 2026).

Un sistema de fuera reintenta cuando no le llega la respuesta: la red se cortó,
el servidor tardó. Si la primera sí había mandado el correo, el reintento lo
mandaría otra vez. Con la cabecera `Idempotency-Key`, la segunda petición con la
misma llave recibe la respuesta de la primera en vez de repetirla.

Cada registro es de una cuenta, una llave de la API, un método y una ruta: la
misma `Idempotency-Key` en otra ruta, o desde otra llave, es otra cosa. Se mira
**después** de comprobar la llave y su permiso, así que nadie lee respuestas
ajenas adivinando una.

Mientras la primera sigue en curso, la segunda espera (409). Ese «en curso»
vence a los `PENDING_SECONDS`: si la primera murió a la mitad, la llave no
queda trabada un día entero. Lo que se guarda vence a las 24 horas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

KEEP_HOURS = 24
PENDING_SECONDS = 120
KEY_MAX = 100
# Lo que cabe de la respuesta. Más grande, se guarda lo esencial (`compact`).
BODY_MAX = 16 * 1024

NEW = "new"
REPLAY = "replay"
MISMATCH = "mismatch"
BUSY = "busy"


def now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(when):
    if when is not None and when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when


def begin(db, *, account_id, key_id, method: str, path: str, key: str,
          body_hash: str) -> tuple[str, dict[str, Any] | None]:
    """Empezar una petición con esa llave. Devuelve qué hacer y el registro."""
    moment = now()
    who = {"account_id": account_id, "key_id": key_id, "method": method,
           "path": path, "key": key}
    try:
        db.api_idempotency.insert_one({
            **who, "body_hash": body_hash, "status": None, "body": None,
            "pending_until": moment + timedelta(seconds=PENDING_SECONDS),
            "created_at": moment,
            "expires_at": moment + timedelta(hours=KEEP_HOURS)})
        return NEW, db.api_idempotency.find_one(who)
    except DuplicateKeyError:
        pass
    found = db.api_idempotency.find_one(who)
    if found is None:
        return BUSY, None
    if found.get("body_hash") != body_hash:
        return MISMATCH, found
    if found.get("status") is not None:
        return REPLAY, found
    if _aware(found.get("pending_until")) and _aware(found["pending_until"]) > moment:
        return BUSY, found
    # La primera murió sin terminar: esta la retoma, si nadie se adelantó.
    taken = db.api_idempotency.find_one_and_update(
        {"_id": found["_id"], "status": None, "pending_until": found["pending_until"]},
        {"$set": {"pending_until": moment + timedelta(seconds=PENDING_SECONDS)}},
        return_document=ReturnDocument.AFTER)
    return (NEW, taken) if taken else (BUSY, found)


def finish(db, record_id, *, status: int, body: Any) -> None:
    """Guardar la respuesta para devolverla al repetir."""
    db.api_idempotency.update_one({"_id": record_id},
                                  {"$set": {"status": int(status), "body": body,
                                            "pending_until": None}})


def drop(db, record_id) -> None:
    """Olvidarla: lo que falló por nuestra culpa (5xx) o por el límite (429)
    se puede volver a intentar con la misma llave."""
    db.api_idempotency.delete_one({"_id": record_id})
