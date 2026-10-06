"""El enlace de baja que lleva cada correo de una campaña.

**Es la regla 3 de CLAUDE.md y no es negociable**: va en todos los planes, se
inyecta al enviar —no dentro de la pieza, para que el cliente no lo pueda
quitar— y es único por destinatario.

Único por destinatario **sin escribir nada al enviar**. El enlace lleva el
identificador del contacto y una firma hecha con la llave del servidor; para
comprobarla se vuelve a calcular. Guardar un documento por destinatario sería
multiplicar la base por el tamaño de cada lista para conseguir exactamente lo
mismo.

Lo que la firma evita es que alguien recorra identificadores y dé de baja a los
contactos de otro. No caduca a propósito: un correo de hace dos años sigue
teniendo que poder darse de baja, que es justo lo que exige un remitente masivo.
"""

from __future__ import annotations

import secrets

from bson import ObjectId
from bson.errors import InvalidId

from config import Config
from services.security import hash_keyed

# La mitad de un SHA-256 con llave. De sobra para que no se adivine, y corto
# para que el enlace quepa en una línea del pie del correo.
SIGNATURE = 32


def sign(contact_id) -> str:
    """El testigo de baja de ese contacto."""
    raw = str(contact_id)
    return f"{raw}.{hash_keyed(raw)[:SIGNATURE]}"


def contact_of(token: str | None):
    """De quién es ese testigo, o None si la firma no cuadra."""
    if not token or "." not in token:
        return None
    raw, _, signature = token.partition(".")
    if not secrets.compare_digest(hash_keyed(raw)[:SIGNATURE], signature):
        return None
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def link(contact_id) -> str:
    """La dirección entera, que es la que va dentro del correo.

    Completa porque la abre el buzón de quien recibió la campaña, desde fuera
    de aquí.
    """
    return f"{Config.APP_BASE_URL}/unsubscribe/{sign(contact_id)}"
