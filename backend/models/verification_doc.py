"""Los documentos que el cliente sube para verificar su identificación y su
dirección.

Uno por cuenta y por clase (`identity`, `address`): subir otro lo reemplaza.
Viven en la base, como las facturas, y **se borran en cuanto el administrador
decide**, lo verifique o lo rechace: de la cédula de alguien o de su recibo de
luz no hace falta guardar más que el resultado (`accounts.verifications`).

Solo PDF, JPG o PNG de hasta 5 MB, reconocidos por cómo empiezan y no por cómo
se llaman. Los baja solo un administrador, siempre como archivo y nunca dentro
de una página del panel: es el documento de otro, y la sesión abierta es la de
administración.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson.binary import Binary

MAX_BYTES = 5 * 1024 * 1024

# Cómo empieza cada formato aceptado, y lo que se dice al bajarlo.
KINDS_OF_FILE = (
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def file_type(raw: bytes) -> tuple[str, str] | None:
    """El tipo y la extensión del archivo, o None si no es uno de los tres."""
    for magic, mime, ext in KINDS_OF_FILE:
        if raw.startswith(magic):
            return mime, ext
    return None


def save(db, account_id, kind: str, *, data: bytes, mime: str, ext: str) -> None:
    db.verification_docs.update_one(
        {"account_id": account_id, "kind": kind},
        {"$set": {"data": Binary(data), "bytes": len(data), "mime": mime,
                  "ext": ext, "uploaded_at": now()}},
        upsert=True)


def of(db, account_id, kind: str) -> dict[str, Any] | None:
    """El documento de esa clase, si es de esa cuenta. La cuenta va en la
    consulta."""
    return db.verification_docs.find_one({"account_id": account_id, "kind": kind})


def present(db, account_id) -> dict[str, dict[str, Any]]:
    """Qué documentos tiene la cuenta, sin traer los archivos."""
    return {one["kind"]: one for one in db.verification_docs.find(
        {"account_id": account_id}, {"data": 0})}


def remove(db, account_id, kind: str) -> None:
    db.verification_docs.delete_one({"account_id": account_id, "kind": kind})
