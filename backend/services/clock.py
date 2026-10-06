"""La hora de quien mira.

Todo se guarda en UTC, que es lo único que no cambia con el lugar. Lo que se
**escribe** en una pantalla (una fecha, una hora, dónde empieza un día en una
gráfica) sale en la zona del dispositivo de quien la está mirando, y una hora
que alguien **escribe** (programar una campaña) se entiende en esa misma zona.

El navegador dice su zona en la galleta `sa_tz`, que escribe el guion de la
cabecera del panel con `Intl.DateTimeFormat().resolvedOptions().timeZone`. La
primera página de un dispositivo nuevo todavía no la trae y sale en hora de
Panamá, que es el mercado; desde la segunda, en la suya.

Los correos que salen sin nadie delante (un plan que vence) usan la última zona
que se vio en esa cuenta, que se guarda en `time_zone`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

COOKIE = "sa_tz"
DEFAULT = "America/Panama"
# Un nombre de zona es algo como «America/Argentina/Buenos_Aires». Lo que no
# tenga esa forma no se le pregunta a zoneinfo, que buscaría un archivo con él.
MAX_NAME = 64


def zone_named(name: str | None) -> ZoneInfo | None:
    """La zona con ese nombre, o None si no existe."""
    name = (name or "").strip()
    if not name or len(name) > MAX_NAME or ".." in name or name.startswith("/"):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def cookie_zone() -> str:
    """El nombre de la zona que mandó el navegador, si es una de verdad."""
    try:
        from flask import has_request_context, request
    except ImportError:  # pragma: no cover
        return ""
    if not has_request_context():
        return ""
    # El navegador la guarda codificada: «America%2FPanama».
    from urllib.parse import unquote
    raw = unquote(request.cookies.get(COOKIE, ""))
    return raw if zone_named(raw) else ""


def current() -> ZoneInfo:
    """La zona de quien está mirando esta página."""
    return zone_named(cookie_zone()) or ZoneInfo(DEFAULT)


def for_account(account) -> ZoneInfo:
    """La zona de una cuenta, para lo que le llega sin estar mirando."""
    return zone_named((account or {}).get("time_zone")) or ZoneInfo(DEFAULT)


def local(when: datetime, zone: ZoneInfo | None = None) -> datetime:
    """Un momento guardado en UTC, en la hora de esa zona.

    Uno sin zona se toma como UTC, que es como se guarda todo.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(zone or current())


def to_utc(naive: datetime, zone: ZoneInfo | None = None) -> datetime:
    """Una hora escrita por alguien (sin zona), pasada a UTC desde la suya."""
    return naive.replace(tzinfo=zone or current()).astimezone(timezone.utc)
