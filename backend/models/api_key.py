"""Las llaves de la API pública (octubre de 2026).

Una llave es lo que un sistema de fuera (la tienda de un cliente, el programa de
una cooperativa) pone en `Authorization: Bearer …` para hablar con su cuenta
sin sesión. **Se guarda solo su hash** (regla 6), igual que las sesiones: una
copia de la base no abre ninguna cuenta. La llave entera se enseña una sola vez,
en la respuesta que la crea; después solo se reconoce por su prefijo y sus
cuatro últimos.

Son de la empresa, no de la persona: las crea y las revoca el dueño, y hablan
con los datos de la empresa igual que el panel.

Dos clases:

  * **de verdad** (`sa_live_…`): hace lo que digan sus permisos;
  * **de prueba** (`sa_test_…`): solo lee, y los envíos se simulan. Es la que se
    le da a un programador para ensayar, y por eso no puede escribir nada: si se
    filtra desde un servidor de pruebas, no borra ni manda nada.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from services.security import hash_token

LIVE = "live"
TEST = "test"
MODES = (LIVE, TEST)
PREFIXES = {LIVE: "sa_live_", TEST: "sa_test_"}

# Los permisos, en el orden en que los ofrece la pantalla.
CONTACTS_READ = "contacts:read"
CONTACTS_WRITE = "contacts:write"
TEMPLATES_READ = "templates:read"
TEMPLATES_WRITE = "templates:write"
EMAILS_SEND = "emails:send"
CAMPAIGNS_READ = "campaigns:read"
CAMPAIGNS_WRITE = "campaigns:write"
CAMPAIGNS_SEND = "campaigns:send"
STATS_READ = "stats:read"
SCOPES = (CONTACTS_READ, CONTACTS_WRITE, TEMPLATES_READ, TEMPLATES_WRITE,
          EMAILS_SEND, CAMPAIGNS_READ, CAMPAIGNS_WRITE, CAMPAIGNS_SEND, STATS_READ)
# Lo que una llave de prueba puede tener: leer, y los dos envíos, que con ella
# se simulan.
TEST_SCOPES = (CONTACTS_READ, TEMPLATES_READ, EMAILS_SEND, CAMPAIGNS_READ,
               CAMPAIGNS_SEND, STATS_READ)
READ_SCOPES = (CONTACTS_READ, TEMPLATES_READ, CAMPAIGNS_READ, STATS_READ)

# Los atajos de la pantalla de crear.
PRESETS = {
    "send": (EMAILS_SEND,),
    "read": READ_SCOPES,
    "all": SCOPES,
}

KEY_LIMIT = 10
NAME_MAX = 60
IPS_MAX = 10
# Cuántos días vive: nunca (0), un mes, tres o un año.
EXPIRY_DAYS = (0, 30, 90, 365)
# El último uso se escribe como mucho una vez por minuto: una escritura por
# petición convertiría leer la API en escribir en la base.
TOUCH_EVERY = timedelta(minutes=1)
# Lo que se enseña para reconocerla: el prefijo y cuatro letras, y los cuatro
# últimos.
SHOWN = 4


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_name(raw: str) -> str:
    return " ".join((raw or "").split())[:NAME_MAX]


def clean_scopes(wanted, mode: str) -> list[str]:
    """Los permisos que existen y que esa clase de llave puede tener, en orden."""
    allowed = TEST_SCOPES if mode == TEST else SCOPES
    chosen = {one for one in (wanted or []) if one in allowed}
    return [one for one in SCOPES if one in chosen]


def looks_like(raw: str | None) -> bool:
    """Si tiene la forma de una llave nuestra. Se mira antes de ir a la base."""
    raw = raw or ""
    return (any(raw.startswith(prefix) for prefix in PREFIXES.values())
            and 20 <= len(raw) <= 120)


def create(db, account_id, *, name: str, mode: str, scopes: list[str],
           ips: list[str], days: int, ip: str = "") -> tuple[str, dict[str, Any]]:
    """Crear una llave. Devuelve el valor entero, que no se guarda, y el
    documento. Quien llama ya comprobó todo lo demás."""
    raw = PREFIXES[mode] + secrets.token_urlsafe(32)
    moment = now()
    doc = {
        "account_id": account_id,
        "token_hash": hash_token(raw),
        "prefix": raw[:len(PREFIXES[mode]) + SHOWN],
        "last4": raw[-SHOWN:],
        "name": clean_name(name),
        "mode": mode,
        "scopes": clean_scopes(scopes, mode),
        "ips": list(ips)[:IPS_MAX],
        "expires_at": moment + timedelta(days=days) if days else None,
        "created_at": moment,
        "created_ip": ip,
        "last_used_at": None,
        "last_used_ip": "",
        "revoked_at": None,
        "revoked_by": None,
        "revoke_reason": "",
    }
    doc["_id"] = db.api_keys.insert_one(doc).inserted_id
    return raw, doc


def is_live(doc: dict[str, Any] | None) -> bool:
    """Si todavía abre: ni revocada ni vencida."""
    if not doc or doc.get("revoked_at"):
        return False
    expires = doc.get("expires_at")
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires is None or expires > now()


def find(db, raw: str | None) -> dict[str, Any] | None:
    """La llave que abre ese valor, o None. Revocada, vencida o inventada
    responden lo mismo."""
    if not looks_like(raw):
        return None
    doc = db.api_keys.find_one({"token_hash": hash_token(raw)})
    return doc if is_live(doc) else None


def for_account(db, account_id) -> list[dict[str, Any]]:
    """Las de la cuenta, las activas primero y las más nuevas arriba."""
    found = list(db.api_keys.find({"account_id": account_id}, {"token_hash": 0})
                 .sort("created_at", -1))
    return sorted(found, key=lambda one: not is_live(one))


def active_count(db, account_id) -> int:
    return sum(1 for one in for_account(db, account_id) if is_live(one))


def by_id(db, account_id, key_id) -> dict[str, Any] | None:
    """Una de esa cuenta. La cuenta va en la consulta."""
    if key_id is None:
        return None
    return db.api_keys.find_one({"_id": key_id, "account_id": account_id},
                                {"token_hash": 0})


def revoke(db, account_id, key_id, *, by=None, reason: str = "") -> bool:
    """Revocarla. False si no era de esa cuenta o ya estaba revocada."""
    return db.api_keys.update_one(
        {"_id": key_id, "account_id": account_id, "revoked_at": None},
        {"$set": {"revoked_at": now(), "revoked_by": by,
                  "revoke_reason": reason.strip()[:300]}}).modified_count == 1


def touch(db, doc: dict[str, Any], ip: str) -> None:
    """Anotar que se usó, como mucho una vez por minuto."""
    last = doc.get("last_used_at")
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last is not None and now() - last < TOUCH_EVERY:
        return
    db.api_keys.update_one({"_id": doc["_id"]},
                           {"$set": {"last_used_at": now(), "last_used_ip": ip}})
