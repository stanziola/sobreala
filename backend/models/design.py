"""Los diseños de correo que sube un cliente.

Se llaman «diseños» y no «templates» por una razón práctica: en este proyecto
`templates/` ya son las plantillas Jinja del panel, y dos cosas distintas con el
mismo nombre se confunden en cada archivo que las toque. Para el cliente la
pantalla dice **Plantillas**, que es la palabra que él usa.

Aquí caben dos cosas, y el campo `source` dice cuál es cada una:

  * **`upload`**, el HTML que sube el cliente. Se guarda entero y tal como
    llegó: es lo que hay que poder volver a mirar cuando alguien pregunte qué
    se envió, y no se puede reconstruir.
  * **`builtin`**, una prediseñada del producto que el cliente llenó. De esta se
    guarda **de qué plantilla salió y qué escribió en cada casilla**, no el HTML
    armado. Guardar el resultado dejaría la pieza imposible de volver a editar,
    y además el archivo de la plantilla puede mejorar: al reabrirla se arma otra
    vez con lo que ella diga hoy.

Los archivos de las prediseñadas no viven en la base de datos: viajan con el
repositorio, en `email_templates/`, iguales para todos y sin nada que aprobar.

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

# De dónde salió cada pieza. Va escrito en todos los documentos y no solo en los
# nuevos: un campo que a veces está es fácil de equivocar en una consulta.
UPLOAD = "upload"
BUILT_IN = "builtin"


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
        "source": UPLOAD,
        "name": clean_name(name),
        "html": html,
        "bytes": len(html.encode("utf-8")),
        "uploaded_by": uploaded_by,
        "created_at": now(),
    }).inserted_id


def save_filled(db, account_id, *, name: str, template: str,
                filled: dict[str, str]) -> Any:
    """Guardar una prediseñada llena. Devuelve su id.

    Se guarda lo que escribió y no el correo armado, para que reabrirla
    devuelva las casillas como estaban.
    """
    return db.designs.insert_one({
        "account_id": account_id,
        "source": BUILT_IN,
        "template": template,
        "fields": dict(filled),
        "name": clean_name(name),
        "created_at": now(),
        "updated_at": now(),
    }).inserted_id


def update_filled(db, account_id, design_id, *, name: str,
                  filled: dict[str, str]) -> bool:
    """Volver a guardar una prediseñada que se editó.

    La cuenta va en la consulta, así que el id de otra cuenta no encuentra
    nada. `template` no se toca: cambiar de plantilla es empezar otra pieza,
    no editar esta.
    """
    return db.designs.update_one(
        {"_id": design_id, "account_id": account_id, "source": BUILT_IN},
        {"$set": {"name": clean_name(name), "fields": dict(filled),
                  "updated_at": now()}}).matched_count == 1


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
    """El HTML que ha subido cualquier cliente. Lo lee el administrador.

    Las prediseñadas llenas no salen: son nuestras plantillas con el texto de
    alguien dentro, y no hay ningún archivo ajeno que mirar.
    """
    return list(db.designs.find({"source": UPLOAD})
                .sort("created_at", -1).limit(limit))


def remove(db, account_id, design_id) -> dict[str, Any] | None:
    """El cliente borra la suya, y devuelve lo que borró.

    Devuelve el documento y no un sí o un no porque quien llama tiene que poder
    borrar también las imágenes que colgaban de él. La cuenta va en la consulta,
    siempre.
    """
    return db.designs.find_one_and_delete(
        {"_id": design_id, "account_id": account_id})
