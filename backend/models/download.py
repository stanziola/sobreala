"""El archivo del correo individual, guardado para bajarlo (octubre de 2026).

Hasta ese mes el archivo iba adjunto dentro del correo y no se guardaba. Se
cambió para poder saber **si la persona lo bajó**: un adjunto se abre en el
buzón de quien lo recibe y nadie se entera; un enlace de descarga, sí.

Un documento por archivo, con el contenido dentro (hasta 5 MB, lejos del tope
de 16 MB de un documento de Mongo). **Vence a los `KEEP_DAYS` días**: el índice
TTL `expires_at` hace que Atlas lo borre solo, y después el enlace dice que ya
no está.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import Binary

KEEP_DAYS = 30
# Lo que una cuenta puede tener guardado a la vez (octubre de 2026): diez
# archivos del tamaño más grande. Sin tope, mandar el mismo archivo de 5 MB a
# cien personas eran 500 MB dentro de la base.
ACCOUNT_BYTES = 50 * 1024 * 1024


def now() -> datetime:
    return datetime.now(timezone.utc)


def save(db, account_id, campaign_id, *, name: str, content_type: str,
         data: bytes) -> Any:
    """Guardar el archivo de ese correo. Devuelve su id."""
    return db.downloads.insert_one({
        "account_id": account_id,
        "campaign_id": campaign_id,
        "name": name,
        "content_type": content_type,
        "size": len(data),
        "data": Binary(data),
        "created_at": now(),
        "expires_at": now() + timedelta(days=KEEP_DAYS),
    }).inserted_id


def stored_bytes(db, account_id) -> int:
    """Cuánto ocupan los archivos que esa cuenta tiene guardados y vigentes."""
    found = list(db.downloads.aggregate([
        {"$match": {"account_id": account_id, "expires_at": {"$gt": now()}}},
        {"$group": {"_id": None, "bytes": {"$sum": "$size"}}}]))
    return int(found[0]["bytes"]) if found else 0


def has_room(db, account_id, size: int) -> bool:
    return stored_bytes(db, account_id) + size <= ACCOUNT_BYTES


def by_id(db, download_id, *, with_data: bool = False) -> dict[str, Any] | None:
    """El archivo, o None si no existe o ya venció. Sin el contenido, salvo que
    se pida: la página que lo enseña solo necesita su nombre y su tamaño."""
    found = db.downloads.find_one({"_id": download_id},
                                  None if with_data else {"data": 0})
    if found is None:
        return None
    expires = found.get("expires_at")
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    # El TTL de Atlas pasa cada minuto o así: lo vencido y todavía no borrado
    # tampoco se entrega.
    if expires is not None and expires <= now():
        return None
    return found
