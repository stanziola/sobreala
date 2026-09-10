"""Los diseños de correo que sube un cliente.

Se llaman «diseños» y no «templates» por una razón práctica: en este proyecto
`templates/` ya son las plantillas Jinja del panel, y dos cosas distintas con el
mismo nombre se confunden en cada archivo que las toque. Para el cliente la
pantalla dice **Plantillas**, que es la palabra que él usa.

Los prediseñados del producto no viven aquí: son archivos que viajan con el
repositorio, iguales para todos. Esta colección guarda lo que sube cada cliente,
que es lo único que hay que revisar y aprobar.

**Solo la primera subida de cada cliente se aprueba a mano.** Después queda
habilitado, porque lo que se revisa la primera vez no es el archivo: es si esa
organización sabe lo que está mandando. Todo queda guardado y visible desde
administración, aprobado o no.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Qué se puede hacer con un diseño subido.
PENDING = "pending"      # esperando la primera aprobación del administrador
APPROVED = "approved"    # se puede usar en una campaña
REJECTED = "rejected"    # no se puede usar; el motivo queda escrito

NAME_MAX = 80


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_name(raw: str) -> str:
    return " ".join((raw or "").split())[:NAME_MAX]


def save(db, account_id, *, name: str, html: str, status: str,
         uploaded_by=None) -> Any:
    """Guardar una pieza subida. Devuelve su id.

    El HTML se guarda entero y tal como llegó. Es lo que hay que poder volver a
    mirar cuando alguien pregunte qué se envió, y no se puede reconstruir.
    """
    return db.designs.insert_one({
        "account_id": account_id,
        "name": clean_name(name),
        "html": html,
        "bytes": len(html.encode("utf-8")),
        "status": status,
        "reason": "",
        "uploaded_by": uploaded_by,
        "created_at": now(),
        "reviewed_at": None,
    }).inserted_id


def for_account(db, account_id, *, limit: int = 50) -> list[dict[str, Any]]:
    return list(db.designs.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))


def by_id(db, account_id, design_id) -> dict[str, Any] | None:
    """Uno de esta cuenta. El id de otra cuenta no encuentra nada, porque la
    cuenta es parte de la consulta y no algo que se compruebe después."""
    return db.designs.find_one({"_id": design_id, "account_id": account_id})


def count(db, account_id) -> int:
    return db.designs.count_documents({"account_id": account_id})


def approved_before(db, account_id) -> bool:
    """Si esta cuenta ya pasó la primera revisión.

    Es lo que decide si la siguiente subida entra aprobada o se queda esperando.
    """
    return db.designs.count_documents(
        {"account_id": account_id, "status": APPROVED}, limit=1) == 1


def waiting(db, *, limit: int = 50) -> list[dict[str, Any]]:
    """Lo que espera revisión, de todas las cuentas. Lo lee el administrador."""
    return list(db.designs.find({"status": PENDING})
                .sort("created_at", 1).limit(limit))


def review(db, design_id, *, status: str, reason: str = "") -> bool:
    """Aprobar o rechazar. Solo mueve lo que todavía estaba esperando."""
    if status not in (APPROVED, REJECTED):
        return False
    result = db.designs.update_one(
        {"_id": design_id, "status": PENDING},
        {"$set": {"status": status, "reason": reason.strip()[:300],
                  "reviewed_at": now()}})
    return result.modified_count == 1


def remove(db, account_id, design_id) -> bool:
    """El cliente borra la suya. La cuenta va en la consulta, siempre."""
    return db.designs.delete_one(
        {"_id": design_id, "account_id": account_id}).deleted_count == 1
