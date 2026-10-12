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
    return _paid(answer)


def _paid(answer: dict[str, Any]) -> dict[str, str]:
    """Lo que de verdad se cobró, según la respuesta de PayPal a una orden."""
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


# --------------------------------------------------------------- PayPal guardado
#
# Guardar la cuenta de PayPal (octubre de 2026): el cliente entra a PayPal una
# vez, sin plan y sin cobro, y queda guardada (PayPal Vault, «payment method
# tokens»). Lo que se guarda aquí es un identificador y el correo de esa cuenta:
# ninguna tarjeta, ninguna clave (regla 9). Sirve para pagar sin volver a iniciar
# sesión; quien decide que se cobró sigue siendo la respuesta de PayPal.

def vault_ready() -> bool:
    return configured()


def create_setup_token(*, reference: str, return_url: str,
                       cancel_url: str) -> tuple[str, str]:
    """Pedir guardar una cuenta de PayPal. Devuelve (el id de la petición, la
    dirección donde el cliente entra a PayPal y lo aprueba). `reference` es nuestro
    identificador de la cuenta."""
    answer = _call("/v3/vault/setup-tokens", body={
        "customer": {"merchant_customer_id": reference[:64]},
        "payment_source": {"paypal": {
            "usage_type": "MERCHANT", "customer_type": "CONSUMER",
            "experience_context": {
                "brand_name": "Sobreala", "locale": "es-ES",
                "shipping_preference": "NO_SHIPPING",
                "return_url": return_url, "cancel_url": cancel_url},
        }},
    }, headers={**_auth(), "PayPal-Request-Id": f"vault-{reference}-{int(time.time())}"})
    for link in answer.get("links", []):
        if link.get("rel") in ("approve", "payer-action"):
            return answer["id"], link["href"]
    raise PayPalError("la petición no trajo dirección de aprobación")


def save_payment_token(setup_id: str) -> dict[str, str]:
    """Con la petición ya aprobada, guardar la cuenta. Devuelve su identificador y
    el correo de la cuenta de PayPal, para que el cliente reconozca cuál es."""
    answer = _call("/v3/vault/payment-tokens", body={
        "payment_source": {"token": {"id": setup_id, "type": "SETUP_TOKEN"}},
    }, headers={**_auth(), "PayPal-Request-Id": f"save-{setup_id}"})
    wallet = (answer.get("payment_source") or {}).get("paypal") or {}
    if not answer.get("id"):
        raise PayPalError("no se pudo guardar la cuenta")
    return {"id": answer["id"], "payer": (wallet.get("email_address") or "")[:200]}


def delete_payment_token(token_id: str) -> None:
    """Quitar la cuenta guardada. Si PayPal ya no la tiene (404), da igual."""
    try:
        _call(f"/v3/vault/payment-tokens/{token_id}", method="DELETE",
              headers=_auth())
    except PayPalError as exc:
        if str(exc) != "paypal 404":
            raise


def pay_saved(*, vault_id: str, amount: str, currency: str, description: str,
              reference: str) -> tuple[str, dict[str, str]]:
    """Cobrar con la cuenta guardada, sin que el cliente vuelva a iniciar sesión.
    Devuelve (el id de la orden, lo que se cobró). Igual que `capture()`: es la
    respuesta de PayPal lo que prueba que se pagó, y quien llama compara el monto."""
    answer = _call("/v2/checkout/orders", body={
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": currency, "value": amount},
            "description": description[:127],
            "custom_id": reference,
        }],
        "payment_source": {"paypal": {"vault_id": vault_id}},
    }, headers={**_auth(), "PayPal-Request-Id": reference})
    # Con una cuenta guardada la orden suele salir ya cobrada; si no, se cobra.
    if answer.get("status") == "COMPLETED":
        return answer["id"], _paid(answer)
    return answer["id"], capture(answer["id"])


# ---------------------------------------------------------------- suscripciones
#
# La renovación automática (octubre de 2026). PayPal tiene el reloj: el cliente
# aprueba una suscripción una vez y PayPal cobra cada periodo por su cuenta, así
# que no hace falta ningún proceso en segundo plano. Aquí solo se habla con él;
# quién decide que algo se cobró sigue siendo quien llama, preguntando a PayPal
# (`transactions()`) y comparando el monto, nunca lo que traiga el navegador.

# Los periodos de PayPal para cada ciclo nuestro.
UNITS = {"monthly": "MONTH", "yearly": "YEAR"}


def renewals_ready() -> bool:
    """La renovación automática necesita las credenciales y el webhook: sin él no
    nos enteraríamos de las renovaciones hasta que el cliente entrara a mirar."""
    return configured() and bool(Config.PAYPAL_WEBHOOK_ID)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {token()}"}


def create_product() -> str:
    """El producto de Sobreala en PayPal, del que cuelgan los planes."""
    answer = _call("/v1/catalogs/products", body={
        "name": "Sobreala", "type": "SERVICE", "category": "SOFTWARE"},
        headers={**_auth(), "PayPal-Request-Id": "sobreala-product"})
    return answer["id"]


def create_plan(*, product_id: str, name: str, cycle: str, amount: str,
                currency: str, reference: str) -> str:
    """Un plan de cobro de PayPal: el mismo monto, cada mes o cada año, hasta que
    se cancele (`total_cycles` en 0). Si el primer cobro falla se cancela todo."""
    answer = _call("/v1/billing/plans", body={
        "product_id": product_id, "name": name[:127], "status": "ACTIVE",
        "billing_cycles": [{
            "frequency": {"interval_unit": UNITS[cycle], "interval_count": 1},
            "tenure_type": "REGULAR", "sequence": 1, "total_cycles": 0,
            "pricing_scheme": {"fixed_price": {"value": amount,
                                               "currency_code": currency}},
        }],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee_failure_action": "CANCEL",
            "payment_failure_threshold": 3,
        },
    }, headers={**_auth(), "PayPal-Request-Id": reference})
    return answer["id"]


def create_subscription(*, plan_id: str, reference: str, return_url: str,
                        cancel_url: str, start_time: str = "") -> tuple[str, str]:
    """Crear la suscripción. Devuelve (su id, la dirección donde el cliente la
    aprueba). `reference` es nuestro identificador y viaja como `custom_id`.
    `start_time` (ISO, en UTC) es cuándo cobra el primer periodo: sin él, al
    aprobarla."""
    body: dict[str, Any] = {
        "plan_id": plan_id, "custom_id": reference,
        "application_context": {
            "brand_name": "Sobreala", "locale": "es-ES",
            "shipping_preference": "NO_SHIPPING", "user_action": "SUBSCRIBE_NOW",
            "return_url": return_url, "cancel_url": cancel_url,
        },
    }
    if start_time:
        body["start_time"] = start_time
    answer = _call("/v1/billing/subscriptions", body=body,
                   headers={**_auth(), "PayPal-Request-Id": reference})
    for link in answer.get("links", []):
        if link.get("rel") == "approve":
            return answer["id"], link["href"]
    raise PayPalError("la suscripción no trajo dirección de aprobación")


def get_subscription(subscription_id: str) -> dict[str, Any]:
    """Cómo está la suscripción según PayPal: su estado, de quién es (`custom_id`)
    y cuándo cobra la próxima."""
    answer = _call(f"/v1/billing/subscriptions/{subscription_id}", method="GET",
                   headers=_auth())
    return {
        "status": answer.get("status", ""),
        "custom_id": answer.get("custom_id", ""),
        "plan_id": answer.get("plan_id", ""),
        "next": (answer.get("billing_info") or {}).get("next_billing_time", ""),
        "payer": ((answer.get("subscriber") or {}).get("email_address") or "")[:200],
    }


def transactions(subscription_id: str, *, start: str, end: str) -> list[dict[str, str]]:
    """Lo que PayPal cobró de esa suscripción entre dos fechas (ISO, UTC): una
    por cobro, con su id, su estado, su monto y su moneda. Es lo que prueba que
    un periodo se pagó."""
    answer = _call(
        f"/v1/billing/subscriptions/{subscription_id}/transactions"
        f"?start_time={start}&end_time={end}", method="GET", headers=_auth())
    found = []
    for one in answer.get("transactions") or []:
        gross = (one.get("amount_with_breakdown") or {}).get("gross_amount") or {}
        found.append({
            "id": one.get("id", ""), "status": one.get("status", ""),
            "amount": gross.get("value", ""), "currency": gross.get("currency_code", ""),
            "time": one.get("time", ""),
            "payer": ((one.get("payer_email") or ""))[:200],
        })
    return found


def cancel_subscription(subscription_id: str, reason: str) -> None:
    _call(f"/v1/billing/subscriptions/{subscription_id}/cancel",
          body={"reason": reason[:128]}, headers=_auth())


def verify_webhook(headers: Any, event: dict[str, Any]) -> bool:
    """Si un aviso lo mandó PayPal de verdad: se le pregunta a PayPal con la
    firma que trae. Sin `PAYPAL_WEBHOOK_ID`, ninguno vale."""
    if not Config.PAYPAL_WEBHOOK_ID:
        return False
    try:
        answer = _call("/v1/notifications/verify-webhook-signature", body={
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
            "cert_url": headers.get("PAYPAL-CERT-URL", ""),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
            "webhook_id": Config.PAYPAL_WEBHOOK_ID,
            "webhook_event": event,
        }, headers=_auth())
    except PayPalError:
        return False
    return answer.get("verification_status") == "SUCCESS"
