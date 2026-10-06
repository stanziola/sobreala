"""Hablar con PayPal: crear una orden y cobrarla.

Con `urllib` y nada más. Son dos llamadas HTTP y un token; traerse una librería
entera para eso sería añadir una dependencia que hay que mantener y auditar a
cambio de veinte líneas.

Dos cosas que este archivo no hace, a propósito:

  * **No toca la tarjeta.** El pago entero ocurre en el checkout de PayPal, en
    su dominio. Aquí solo viajan un monto y un identificador de orden. Es la
    regla 9 de CLAUDE.md y es la razón de hacerlo así y no de otra forma.
  * **No decide si alguien pagó.** Eso lo decide quien llama, comparando lo que
    responde `capture()` contra lo que ese plan cuesta. Lo que traiga el
    navegador de vuelta no vale como prueba de nada.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any

from config import Config

# El token vive nueve horas; se pide de nuevo bastante antes por si el reloj o
# la red se portan mal.
_token: dict[str, Any] = {"value": "", "until": 0.0}
TOKEN_MARGIN = 300


class PayPalError(RuntimeError):
    """Algo salió mal hablando con PayPal. El detalle va al registro, no a la
    pantalla: al cliente no le sirve el cuerpo de una respuesta HTTP."""


def configured() -> bool:
    return bool(Config.PAYPAL_CLIENT_ID and Config.PAYPAL_SECRET)


def _call(path: str, *, method: str = "POST", body: dict | None = None,
          headers: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{Config.paypal_api()}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            raw = answer.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        print(f"  [paypal] {method} {path} devolvio {exc.code}: {detail}",
              flush=True)
        raise PayPalError(f"paypal {exc.code}") from exc
    except OSError as exc:
        print(f"  [paypal] no se pudo hablar con {url}: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)
        raise PayPalError("paypal unreachable") from exc
    return json.loads(raw) if raw else {}


def token() -> str:
    """El token de aplicación, reutilizado mientras siga vivo."""
    if _token["value"] and time.time() < _token["until"]:
        return _token["value"]
    if not configured():
        raise PayPalError("faltan las credenciales de PayPal")

    pair = f"{Config.PAYPAL_CLIENT_ID}:{Config.PAYPAL_SECRET}".encode("utf-8")
    url = f"{Config.paypal_api()}/v1/oauth2/token"
    request = urllib.request.Request(
        url, data=b"grant_type=client_credentials", method="POST")
    request.add_header("Authorization",
                       "Basic " + base64.b64encode(pair).decode("ascii"))
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            found = json.loads(answer.read())
    except (urllib.error.HTTPError, OSError) as exc:
        print(f"  [paypal] no se pudo pedir el token: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)
        raise PayPalError("paypal token") from exc

    _token["value"] = found["access_token"]
    _token["until"] = time.time() + max(0, int(found.get("expires_in", 0))
                                        - TOKEN_MARGIN)
    return _token["value"]


def create(*, amount: str, currency: str, description: str, reference: str,
           return_url: str, cancel_url: str) -> tuple[str, str]:
    """Crear la orden. Devuelve (id de la orden, dirección a la que mandar).

    `reference` es el identificador de nuestro documento de pago y viaja como
    la clave de idempotencia: si esta petición se repite por un reintento de
    red, PayPal devuelve la misma orden en vez de crear una segunda.
    """
    answer = _call("/v2/checkout/orders", body={
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": currency, "value": amount},
            "description": description[:127],
            "custom_id": reference,
        }],
        "application_context": {
            "brand_name": "Sobreala",
            "locale": "es-ES",
            "landing_page": "LOGIN",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }, headers={"Authorization": f"Bearer {token()}",
                "PayPal-Request-Id": reference})

    for link in answer.get("links", []):
        if link.get("rel") in ("approve", "payer-action"):
            return answer["id"], link["href"]
    raise PayPalError("la orden no trajo dirección de aprobación")


def capture(order_id: str) -> dict[str, str]:
    """Cobrar la orden. Devuelve el estado y lo que de verdad se cobró.

    Esto es lo único que prueba que alguien pagó. Quien llama compara el monto
    y la moneda contra lo que ese plan cuesta antes de activar nada.
    """
    answer = _call(f"/v2/checkout/orders/{order_id}/capture",
                   headers={"Authorization": f"Bearer {token()}",
                            "PayPal-Request-Id": f"cap-{order_id}"})
    captured: dict[str, Any] = {}
    for unit in answer.get("purchase_units", []):
        for one in (unit.get("payments") or {}).get("captures", []):
            captured = one.get("amount") or {}
            break
    return {
        "status": answer.get("status", ""),
        "amount": captured.get("value", ""),
        "currency": captured.get("currency_code", ""),
        # La cuenta de PayPal que pagó, para que Facturación diga con qué se
        # ha pagado. Es un correo, no un dato de tarjeta.
        "payer": ((answer.get("payer") or {}).get("email_address") or "")[:200],
    }
