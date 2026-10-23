"""El enlace de descarga del archivo de un correo individual.

Firmado con la llave del servidor, como el de la baja (`services/unsubscribe.py`):
lleva el id del archivo y una firma que se vuelve a calcular para comprobarla,
así que no hay nada que guardar por enlace. La firma va con su propio prefijo,
para que un testigo de baja no sirva de enlace de descarga ni al revés.

**Abrir el enlace no baja el archivo.** Abre una página que lo baja sola, con
su botón por si no: los antivirus y los escáneres de correo abren los enlaces
de lo que revisan, y no hace falta mandarles el archivo a ellos.
"""

from __future__ import annotations

import secrets

from bson import ObjectId
from bson.errors import InvalidId

from config import Config
from services.security import hash_keyed

SIGNATURE = 32
PREFIX = "download:"


def sign(download_id) -> str:
    raw = str(download_id)
    return f"{raw}.{hash_keyed(PREFIX + raw)[:SIGNATURE]}"


def id_of(token: str | None):
    """De qué archivo es ese testigo, o None si la firma no cuadra."""
    if not token or "." not in token:
        return None
    raw, _, signature = token.partition(".")
    if not secrets.compare_digest(hash_keyed(PREFIX + raw)[:SIGNATURE], signature):
        return None
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def link(download_id) -> str:
    """La dirección entera, que es la que va dentro del correo."""
    return f"{Config.APP_BASE_URL}/d/{sign(download_id)}"


def size_label(size: int) -> str:
    """«2.3 MB» o «180 KB», para la página y el botón del correo."""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{max(1, round(size / 1024))} KB"
