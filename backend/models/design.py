"""Los diseños de correo que sube un cliente.

Se llaman «diseños» y no «templates» por una razón práctica: en este proyecto
`templates/` ya son las plantillas Jinja del panel, y dos cosas distintas con el
mismo nombre se confunden en cada archivo que las toque. Para el cliente la
pantalla dice **Plantillas**, que es la palabra que él usa.

Los prediseñados del producto no viven aquí: son archivos que viajan con el
repositorio, iguales para todos. Esta colección guarda lo que sube cada cliente,
que es lo único que hay que revisar y aprobar.

**Nadie aprueba una pieza a mano.** Lo que puede hacer daño lo rechaza el
validador al subirla —`services/html_check.py`— y eso es mecánico, no un
juicio. La única puerta con una persona detrás está una vez por cuenta, antes de
su primera campaña, y es sobre la cuenta y su lista, no sobre el archivo. Tener
las dos serían dos revisiones manuales para la misma decisión.

Todo queda guardado y visible desde administración, que es lo que permite abrir
una pieza cuando haga falta.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

NAME_MAX = 80


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_name(raw: str) -> str:
    return " ".join((raw or "").split())[:NAME_MAX]


def save(db, account_id, *, name: str, html: str, uploaded_by=None) -> Any:
    """Guardar una pieza subida. Devuelve su id.

    El HTML se guarda entero y tal como llegó. Es lo que hay que poder volver a
    mirar cuando alguien pregunte qué se envió, y no se puede reconstruir.
    """
    return db.designs.insert_one({
        "account_id": account_id,
        "name": clean_name(name),
        "html": html,
        "bytes": len(html.encode("utf-8")),
        "uploaded_by": uploaded_by,
        "created_at": now(),
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


def latest(db, *, limit: int = 100) -> list[dict[str, Any]]:
    """Lo último que ha subido cualquier cliente. Lo lee el administrador."""
    return list(db.designs.find().sort("created_at", -1).limit(limit))


def remove(db, account_id, design_id) -> bool:
    """El cliente borra la suya. La cuenta va en la consulta, siempre."""
    return db.designs.delete_one(
        {"_id": design_id, "account_id": account_id}).deleted_count == 1
