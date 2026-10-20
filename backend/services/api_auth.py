"""Quién llama a la API y desde dónde (octubre de 2026).

**La IP de quien llama** es lo que cuentan los límites de llaves malas y lo que
mira la lista de IP permitidas de una llave, así que no puede salir de una
cabecera que escribe cualquiera. En producción el camino es Cloudflare →
Railway → aquí: `ProxyFix(x_for=1)` deja en `request.remote_addr` la dirección
que se conectó con Railway, y si esa es de Cloudflare, la de verdad viene en
`CF-Connecting-IP`. Si no es de Cloudflare (alguien que le habla directo a
Railway), esa cabecera no vale nada y se usa la conexión.

Los rangos son los que publica Cloudflare en cloudflare.com/ips-v4 y ips-v6,
copiados el 17 de octubre de 2026. Cambian muy de vez en cuando; si cambian, se
copian otra vez aquí.

(`client_ip()` del panel todavía cree `CF-Connecting-IP` de cualquiera: está
dicho y espera.)
"""

from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_address, ip_network

from flask import request

CLOUDFLARE_IPV4 = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
)
CLOUDFLARE_IPV6 = (
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)
CLOUDFLARE = tuple(ip_network(one) for one in CLOUDFLARE_IPV4 + CLOUDFLARE_IPV6)


def from_cloudflare(address: str) -> bool:
    try:
        ip = ip_address(address)
    except ValueError:
        return False
    return any(ip.version == net.version and ip in net for net in CLOUDFLARE)


def caller_ip() -> str:
    """La IP de quien llama, sin creerle a una cabecera que no viene de
    Cloudflare."""
    remote = request.remote_addr or ""
    if from_cloudflare(remote):
        claimed = request.headers.get("CF-Connecting-IP", "")[:64].strip()
        try:
            return str(ip_address(claimed))
        except ValueError:
            pass
    try:
        return str(ip_address(remote))
    except ValueError:
        return "unknown"


def bucket(address: str) -> str:
    """De quién son los intentos fallidos: la IP, o su bloque /64 en IPv6, que
    es lo que le toca a cada conexión y lo que un atacante tiene de sobra."""
    try:
        ip = ip_address(address)
    except ValueError:
        return address
    if ip.version == 6:
        return str(ip_network(f"{ip}/64", strict=False))
    return str(ip)


@lru_cache(maxsize=1024)
def _network(raw: str):
    return ip_network(raw, strict=False)


def clean_ips(lines) -> tuple[list[str], list[str]]:
    """Las IP o rangos escritos, normalizados, y los que no se entendieron.
    Un rango de todo internet (`/0`) no es una lista: se rechaza."""
    good: list[str] = []
    bad: list[str] = []
    for raw in lines:
        one = (raw or "").strip()
        if not one:
            continue
        try:
            net = ip_network(one, strict=False)
        except ValueError:
            bad.append(one[:60])
            continue
        if net.prefixlen == 0:
            bad.append(one[:60])
            continue
        text = str(net.network_address) if net.num_addresses == 1 else str(net)
        if text not in good:
            good.append(text)
    return good, bad


def ip_allowed(address: str, allowed: list[str]) -> bool:
    """Si esa IP está en la lista. Una lista vacía deja entrar desde donde sea."""
    if not allowed:
        return True
    try:
        ip = ip_address(address)
    except ValueError:
        return False
    for raw in allowed:
        try:
            net = _network(raw)
        except ValueError:
            continue
        if ip.version == net.version and ip in net:
            return True
    return False


def bearer() -> str:
    """La llave que llega en `Authorization: Bearer …`, o vacío."""
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return value.strip()[:200]
