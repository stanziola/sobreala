"""Hablar con el servidor de un cliente sin que sirva para entrar a la red
interna (octubre de 2026). Lo usan los avisos a su sistema (webhooks).

Una dirección la escribe el cliente, y «https://169.254.169.254/» o un nombre
que resuelve a 10.0.0.5 harían que nuestro servidor le hable a algo que solo se
ve desde dentro. Por eso:

  * **La dirección**: `https`, puerto 443, un nombre (no una IP), sin usuario ni
    contraseña, hasta 500 caracteres.
  * **Cada dirección a la que resuelve tiene que ser pública.** Antes de mirarla
    se desenvuelve la IPv4 que lleva dentro una IPv6 (mapeada, 6to4, NAT64 y
    Teredo), y el multicast se mira aparte: `ipaddress` dice que `ff0e::1` y
    `64:ff9b::7f00:1` son «globales».
  * **Se conecta a la IP ya comprobada**, validando el certificado con el nombre:
    un DNS que cambia entre mirar y conectar no la cuela.
  * **Cinco segundos en total**: un reloj cierra la conexión, así un servidor
    que contesta un byte cada rato no traba a nadie. Sin seguir redirecciones y
    leyendo como mucho 1 KB de la respuesta.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

URL_MAX = 500
TIMEOUT = 5.0
READ_MAX = 1024

NAT64 = ipaddress.ip_network("64:ff9b::/96")
SIX_TO_FOUR = ipaddress.ip_network("2002::/16")
TEREDO = ipaddress.ip_network("2001::/32")


class Refused(ValueError):
    """La dirección no se puede usar; el texto es una clave corta."""


def check_url(url: str) -> tuple[str, str]:
    """La dirección, revisada: devuelve (nombre, ruta con su consulta)."""
    # Solo ASCII y sin espacios ni controles: lo que va en la línea de la
    # petición no puede romperla (un nombre con acentos va en punycode).
    if (not isinstance(url, str) or len(url) > URL_MAX or not url.isascii()
            or any(c <= " " for c in url)):
        raise Refused("url")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise Refused("url") from exc
    host = (parts.hostname or "").rstrip(".").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise Refused("url")
    if port not in (None, 443):
        raise Refused("port")
    if parts.fragment:
        raise Refused("url")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise Refused("ip")
    if "." not in host or host.endswith((".local", ".internal", ".localhost")) \
            or host == "localhost":
        raise Refused("host")
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return host, path


def unwrap(ip):
    """La IPv4 que va dentro de una IPv6, si va."""
    if ip.version != 6:
        return ip
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip in NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip in SIX_TO_FOUR:
        return ip.sixtofour
    if ip in TEREDO:
        return ip.teredo[1]
    return ip


def public(raw: str) -> bool:
    """Si una dirección IP es de internet: ni privada, ni de la propia máquina,
    ni de los metadatos de la nube, ni multicast, ni reservada."""
    try:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
    except ValueError:
        return False
    inner = unwrap(ip)
    for one in {ip, inner}:
        if one.is_multicast or not one.is_global or one.is_reserved:
            return False
    return True


def resolve(host: str) -> str:
    """Una IP pública de ese nombre. Si **alguna** de las suyas no lo es, nada:
    un nombre que mezcla una pública con una privada es una trampa."""
    try:
        found = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise Refused("dns") from exc
    ips = list(dict.fromkeys(one[4][0] for one in found))
    if not ips or not all(public(one) for one in ips):
        raise Refused("private")
    return ips[0]


@dataclass
class Answer:
    ok: bool
    status: int | None
    error: str
    ms: int


def post(url: str, body: bytes, headers: dict[str, str], *,
         resolver=resolve, timeout: float = TIMEOUT) -> Answer:
    """Mandar un POST y decir qué pasó. Nunca lanza: lo que falla es la
    respuesta (`ok` en False y por qué en `error`)."""
    started = time.monotonic()

    def done(ok: bool, status: int | None, error: str) -> Answer:
        return Answer(ok, status, error[:200], int((time.monotonic() - started) * 1000))

    try:
        host, path = check_url(url)
        ip = resolver(host)
    except Refused as exc:
        return done(False, None, f"refused:{exc}")
    raw = None
    watchdog = None
    try:
        raw = socket.create_connection((ip, 443), timeout=timeout)
        # Un reloj para la petición entera, no por operación.
        watchdog = threading.Timer(timeout, raw.close)
        watchdog.daemon = True
        watchdog.start()
        context = ssl.create_default_context()
        conn = context.wrap_socket(raw, server_hostname=host)
        lines = [f"POST {path} HTTP/1.1", f"Host: {host}", "Connection: close",
                 f"Content-Length: {len(body)}", "User-Agent: Sobreala-Webhooks/1"]
        lines += [f"{name}: {value}" for name, value in headers.items()]
        conn.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
        got = b""
        while len(got) < READ_MAX and b"\r\n" not in got:
            chunk = conn.recv(READ_MAX - len(got))
            if not chunk:
                break
            got += chunk
        first = got.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        pieces = first.split(" ")
        if len(pieces) < 2 or not pieces[0].startswith("HTTP/") or not pieces[1].isdigit():
            return done(False, None, "bad_response")
        status = int(pieces[1])
        return done(200 <= status < 300, status, "" if 200 <= status < 300 else f"http_{status}")
    except ssl.SSLCertVerificationError:
        return done(False, None, "certificate")
    except (OSError, ssl.SSLError) as exc:
        return done(False, None, "timeout" if time.monotonic() - started >= timeout
                    else f"connection:{type(exc).__name__}")
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if raw is not None:
            try:
                raw.close()
            except OSError:
                pass
