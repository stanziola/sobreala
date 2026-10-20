"""Candados cortos en la base: una cosa a la vez (octubre de 2026).

Lo usa la carga de contactos: dos cargas a la vez (dos peticiones de la API, o
una de la API y una importación del panel) calcularían el sitio del plan sobre
la misma cifra y lo pasarían entre las dos. El candado se toma con una sola
escritura condicional y vence solo: si quien lo tenía se murió, a los
`seconds` lo puede tomar otro.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError


def now() -> datetime:
    return datetime.now(timezone.utc)


def acquire(db, name: str, seconds: int) -> str | None:
    """Tomarlo. Devuelve con qué soltarlo, o None si otro lo tiene."""
    token = secrets.token_hex(8)
    moment = now()
    try:
        db.locks.find_one_and_update(
            {"_id": name, "until": {"$lt": moment}},
            {"$set": {"until": moment + timedelta(seconds=seconds), "token": token}},
            upsert=True)
    except DuplicateKeyError:
        return None
    return token


def release(db, name: str, token: str | None) -> None:
    if token:
        db.locks.delete_one({"_id": name, "token": token})


def held(db, name: str) -> bool:
    return db.locks.count_documents({"_id": name, "until": {"$gte": now()}}, limit=1) == 1
