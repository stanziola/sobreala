"""La firma de los avisos de Amazon SNS (octubre de 2026).

Antes, lo que autorizaba un aviso de SES era solo el secreto en la dirección
(`/webhooks/ses/<secreto>`) y el filtro del tema. Con los webhooks a los
sistemas de los clientes eso pesaba más: quien tuviera el secreto podía
inventarles rebotes y quejas. Ahora, además, **cada aviso trae la firma de
Amazon y se comprueba**, como pide la guía de SNS:

  * el certificado se baja solo de `https://sns.<región>.amazonaws.com/…pem`,
    nunca de la dirección que el cuerpo quiera, y se guarda en memoria;
  * se arma el texto firmado con los campos de cada tipo, en su orden;
  * y se verifica con RSA, SHA1 (`SignatureVersion` 1) o SHA256 (2).

Un aviso sin firma o con una que no cuadra no se acepta. Si no se pudo bajar el
certificado (la red), `Unavailable`: el aviso se contesta 500 y SNS lo vuelve a
mandar.
"""

from __future__ import annotations

import base64
import re
import threading
import urllib.request
from typing import Any
from urllib.parse import urlparse

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# De dónde puede venir el certificado: el mismo servicio de Amazon que firma.
CERT_HOST = re.compile(r"^sns\.[a-z0-9-]+\.amazonaws\.com$")
CERT_MAX_BYTES = 16 * 1024
CACHE_MAX = 20

# Los campos que entran en la firma, por tipo y en este orden.
SIGNED = {
    "Notification": ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"),
    "SubscriptionConfirmation": ("Message", "MessageId", "SubscribeURL", "Timestamp",
                                 "Token", "TopicArn", "Type"),
    "UnsubscribeConfirmation": ("Message", "MessageId", "SubscribeURL", "Timestamp",
                                "Token", "TopicArn", "Type"),
}
HASHES = {"1": hashes.SHA1, "2": hashes.SHA256}

_cache: dict[str, Any] = {}
_lock = threading.Lock()


class Unavailable(RuntimeError):
    """No se pudo bajar el certificado de Amazon. Se reintenta después."""


def cert_url_ok(url: str) -> bool:
    parsed = urlparse(url or "")
    return (parsed.scheme == "https" and bool(CERT_HOST.match(parsed.hostname or ""))
            and parsed.port in (None, 443) and parsed.path.endswith(".pem"))


def fetch_cert(url: str) -> bytes:
    """El certificado en PEM. Aparte, para poder cambiarlo en las pruebas."""
    try:
        with urllib.request.urlopen(url, timeout=10) as answer:  # noqa: S310
            return answer.read(CERT_MAX_BYTES + 1)
    except OSError as exc:
        raise Unavailable(str(exc)) from exc


def public_key(url: str):
    with _lock:
        found = _cache.get(url)
    if found is not None:
        return found
    raw = fetch_cert(url)
    if len(raw) > CERT_MAX_BYTES:
        return None
    try:
        key = x509.load_pem_x509_certificate(raw).public_key()
    except ValueError:
        return None
    if not isinstance(key, rsa.RSAPublicKey):
        return None
    with _lock:
        if len(_cache) >= CACHE_MAX:
            _cache.clear()
        _cache[url] = key
    return key


def signed_text(envelope: dict[str, Any]) -> str | None:
    """El texto que firmó Amazon: «Campo\\nvalor\\n» por cada campo que está."""
    names = SIGNED.get(envelope.get("Type", ""))
    if names is None:
        return None
    out = []
    for name in names:
        value = envelope.get(name)
        if value is None:
            if name == "Subject":
                continue
            return None
        if not isinstance(value, str):
            return None
        out.append(f"{name}\n{value}\n")
    return "".join(out)


def verify(envelope: dict[str, Any]) -> bool:
    """Si el aviso lo firmó Amazon. `Unavailable` si no se pudo saber."""
    if not isinstance(envelope, dict):
        return False
    algorithm = HASHES.get(str(envelope.get("SignatureVersion", "")))
    url = envelope.get("SigningCertURL") or envelope.get("SigningCertUrl") or ""
    text = signed_text(envelope)
    signature = envelope.get("Signature")
    if algorithm is None or text is None or not isinstance(signature, str) \
            or not isinstance(url, str) or not cert_url_ok(url):
        return False
    try:
        raw = base64.b64decode(signature, validate=True)
    except ValueError:
        return False
    key = public_key(url)
    if key is None:
        return False
    try:
        key.verify(raw, text.encode("utf-8"), padding.PKCS1v15(), algorithm())
    except InvalidSignature:
        return False
    return True
