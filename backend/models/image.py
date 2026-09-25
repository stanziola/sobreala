"""Las imágenes de las plantillas de un cliente.

Viven en la base y no en un almacén aparte a propósito: un almacén de pago pide
dejar una tarjeta y no tiene tope duro de gasto, y estas imágenes son pocas y
pequeñas —van achicadas a 600 píxeles, unos 120 KB— porque `services/imaging.py`
las prepara antes de llegar aquí.

**El nombre es aleatorio y es la dirección.** No se usa el `_id`, que lleva la
hora dentro y va casi en orden: con él, quien tuviera una dirección podría
recorrer las de los demás. Y lleva su extensión pegada, porque la caché de
Cloudflare mira la extensión para decidir si guarda una respuesta, y sin eso
cada apertura de cada correo llegaría hasta aquí.

**Hay un tope por cuenta.** Es lo que impide que esto crezca sin control, y lo
que acota lo que puede quedar huérfano: una imagen subida y nunca guardada en
ninguna pieza no la borra nadie.

**Una imagen que salió en un envío no se borra con su pieza.** Los correos que
ya llegaron la siguen pidiendo cada vez que alguien los abre. Se queda retirada
hasta doce meses después del último envío que la llevó, como el detalle de los
eventos, y la borra Mongo sola con el índice de `expires_at`.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from bson.binary import Binary

# Cuántas puede tener guardadas una cuenta. Veinte por unos 150 KB son tres
# megas por cliente en el peor caso.
LIMIT = 20


def now() -> datetime:
    return datetime.now(timezone.utc)


# Cuánto se queda una imagen que salió en un envío después de que ninguna pieza
# la nombre, contado desde el último envío que la llevó.
KEEP_SENT = timedelta(days=365)

# Lo que es de una pieza: lo retirado solo sigue ahí para los correos enviados.
LIVE = {"expires_at": {"$exists": False}}


# Un fondo que el lienzo fundió al guardar. Lo hace el sistema y no el
# cliente, así que no cuenta contra su tope: si contara, cada vez que guarda
# una plantilla de tres diapositivas perdería tres de sus veinte.
BACKGROUND = "background"


def save(db, account_id, *, data: bytes, ext: str, mime: str,
         kind: str | None = None) -> str:
    """Guardar una imagen ya achicada. Devuelve su nombre, que es su dirección."""
    name = f"{secrets.token_urlsafe(16)}.{ext}"
    doc = {
        "account_id": account_id,
        "name": name,
        "mime": mime,
        "bytes": len(data),
        "data": Binary(data),
        "created_at": now(),
    }
    if kind:
        doc["kind"] = kind
    db.images.insert_one(doc)
    return name


def by_name(db, name: str) -> dict[str, Any] | None:
    """La que se pide desde un correo. Sin cuenta: quien abre el correo no
    tiene sesión, y el nombre es lo único que hace falta saber."""
    return db.images.find_one({"name": name})


def owns(db, account_id, name: str) -> bool:
    """Si esa imagen es de esta cuenta.

    Es lo que se pregunta antes de guardar una pieza: el nombre viaja en un
    campo escondido del formulario, y un campo escondido lo puede escribir
    cualquiera.
    """
    return db.images.count_documents(
        {"name": name, "account_id": account_id, **LIVE}, limit=1) == 1


def count(db, account_id) -> int:
    """Las que cuentan contra el tope: las que subió el cliente y siguen en
    alguna pieza. Una retirada ya no gasta ninguna de las veinte."""
    return db.images.count_documents({"account_id": account_id,
                                      "kind": {"$ne": BACKGROUND}, **LIVE})


def data_of(db, account_id, name: str) -> bytes | None:
    """Los bytes de una imagen de esta cuenta, para fundirla en un fondo."""
    found = db.images.find_one({"name": name, "account_id": account_id},
                               {"data": 1})
    return bytes(found["data"]) if found else None


def mark_sent(db, account_id, names) -> None:
    """Anotar que estas imágenes salieron en un envío, y cuándo.

    Desde ahí, que su pieza se borre o se vuelva a guardar ya no las borra: se
    quedan hasta doce meses después de este envío (ver `remove`).
    """
    wanted = [one for one in names if one]
    if wanted:
        db.images.update_many({"account_id": account_id, "name": {"$in": wanted}},
                              {"$set": {"sent_at": now()}})


def keep(db, account_id, names) -> None:
    """Volver a dejar fijas las retiradas que una pieza vuelve a nombrar, como
    un HTML cargado que las trae escritas. Sin esto, esa pieza perdería la
    imagen el día que venciera."""
    wanted = [one for one in names if one]
    if wanted:
        db.images.update_many({"account_id": account_id, "name": {"$in": wanted},
                               "expires_at": {"$exists": True}},
                              {"$unset": {"expires_at": ""}})


def remove(db, account_id, names) -> int:
    """Quitar las de una pieza que se borró o que cambió. La cuenta va en la
    consulta. Devuelve cuántas se borraron.

    Las que nunca salieron en un envío se borran. Las que salieron se retiran:
    vencen doce meses después del último envío que las llevó, porque los
    correos que ya llegaron las siguen pidiendo.
    """
    wanted = [one for one in names if one]
    if not wanted:
        return 0
    scope = {"account_id": account_id, "name": {"$in": wanted}}
    keep_ms = int(KEEP_SENT.total_seconds() * 1000)
    db.images.update_many({**scope, "sent_at": {"$exists": True}},
                          [{"$set": {"expires_at": {"$add": ["$sent_at", keep_ms]}}}])
    return db.images.delete_many({**scope, "sent_at": {"$exists": False}}).deleted_count
