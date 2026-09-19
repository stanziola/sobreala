"""Hablar con Paguélofácil: pedir un enlace de pago y consultar una transacción.

Es la tarjeta Visa y Mastercard sin PayPal: no todo el que tiene tarjeta tiene
cuenta de PayPal. Con `urllib` y nada más, como `paypal.py`: son dos llamadas
HTTP y no justifican una dependencia.

Dos cosas que este archivo no hace, a propósito:

  * **No toca la tarjeta.** El cliente la escribe en la página de
    Paguélofácil, en su dominio. Aquí viajan un monto, una descripción y un
    número de operación. Es la regla 9 de CLAUDE.md.
  * **No decide si alguien pagó.** Lo que trae el navegador al volver
    («Estado=Aprobada», el monto) lo escribe cualquiera en la dirección. Lo que
    cuenta es lo que responde `find()` cuando el servidor pregunta por esa
    operación, y lo compara quien llama contra lo que el plan cuesta.

Documentación: developers.paguelofacil.com, «Enlace de pago» y «Transacciones».
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import Config

# Cuánto vale un enlace: una hora, de sobra para pagar y corto para que uno
# viejo no quede abierto.
EXPIRES_IN = 3600
DESCRIPTION_MAX = 150
# Las operaciones que son dinero cobrado. Las demás (autorizar sin capturar,
# reversar) no activan nada.
PAID = ("CAPTURE", "AUTH_CAPTURE", "RECURRENT")


class PagueloFacilError(RuntimeError):
    """Algo salió mal hablando con Paguélofácil. El detalle va al registro, no
    a la pantalla: al cliente no le sirve el cuerpo de una respuesta HTTP."""


def configured() -> bool:
    """Si se puede cobrar con tarjeta: hace falta crear enlaces y consultar."""
    return bool(Config.PAGUELOFACIL_CCLW and Config.PAGUELOFACIL_TOKEN)


def _open(request: urllib.request.Request, what: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            raw = answer.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        print(f"  [paguelofacil] {what} devolvio {exc.code}: {detail}", flush=True)
        raise PagueloFacilError(f"paguelofacil {exc.code}") from exc
    except OSError as exc:
        print(f"  [paguelofacil] no se pudo {what}: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)
        raise PagueloFacilError("paguelofacil unreachable") from exc
    try:
        return json.loads(raw) if raw else {}
    except ValueError as exc:
        raise PagueloFacilError("paguelofacil respondio algo que no es JSON") from exc


def create_link(*, amount: str, description: str, reference: str,
                return_url: str) -> tuple[str, str]:
    """Pedir el enlace de pago. Devuelve (su código, la dirección a la que
    mandar al cliente).

    `reference` es el id de nuestro intento. Va en `PARM_1`, que vuelve tal
    cual, y **dentro de la descripción**, que es lo que se lee al consultar la
    operación: así una operación pagada para otro intento no sirve para este.
    La dirección de vuelta va en hexadecimal, que es como la pide Paguélofácil.
    """
    if not configured():
        raise PagueloFacilError("faltan las credenciales de Paguélofácil")
    body = urllib.parse.urlencode({
        "CCLW": Config.PAGUELOFACIL_CCLW,
        "CMTN": amount,
        "CDSC": f"{description} · {reference}"[:DESCRIPTION_MAX],
        "RETURN_URL": return_url.encode("utf-8").hex(),
        "PARM_1": reference,
        "EXPIRES_IN": str(EXPIRES_IN),
        # Solo tarjeta: el efectivo no se confirma al momento.
        "CARD_TYPE": "CARD",
    }).encode("ascii")
    request = urllib.request.Request(Config.paguelofacil_link(), data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "*/*")
    answer = _open(request, "pedir el enlace")
    data = answer.get("data") or {}
    if not answer.get("success") or not data.get("url"):
        print(f"  [paguelofacil] el enlace no vino: {str(answer)[:300]}", flush=True)
        raise PagueloFacilError("el enlace no trajo dirección")
    url = str(data["url"])
    # Solo a una página de pago que conocemos: es la que la cabecera deja
    # abrir, y mandar a otra sería mandar a pagar a donde diga una respuesta.
    parsed = urllib.parse.urlparse(url)
    if f"{parsed.scheme}://{parsed.netloc}" not in Config.paguelofacil_checkout():
        print(f"  [paguelofacil] el enlace apunta a {parsed.netloc}, que no está "
              f"en PAGUELOFACIL_CHECKOUT", flush=True)
        raise PagueloFacilError("el enlace apunta a un sitio desconocido")
    return str(data.get("code") or ""), url


def find(oper: str) -> dict[str, Any] | None:
    """Lo que Paguélofácil dice de esa operación, o None si no la encuentra.

    Esto es lo único que prueba que alguien pagó. Devuelve el estado (1 es
    aprobada), el tipo de operación, el monto, la descripción que se mandó al
    crear el enlace y los últimos números de la tarjeta, que es lo que la lista
    de pagos enseña. Nada más de la tarjeta viene ni se guarda.
    """
    if not configured():
        raise PagueloFacilError("faltan las credenciales de Paguélofácil")
    query = urllib.parse.urlencode({"filter": f"codOper::{oper}", "limit": "1"})
    url = (f"{Config.paguelofacil_admin()}/PFManagementServices/api/v1/"
           f"MerchantTransactions?{query}")
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", Config.PAGUELOFACIL_TOKEN)
    request.add_header("Accept", "application/json")
    answer = _open(request, "consultar la operacion")
    rows = answer.get("data")
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("transactions") or [rows]
    for row in rows or []:
        if str(row.get("codOper", "")) == oper:
            return {
                "oper": oper,
                "status": int(row.get("status") or 0),
                "operation": str(row.get("operationType") or ""),
                "amount": _money(row.get("totalPay")),
                "description": str(row.get("description") or ""),
                "last4": str(row.get("displayNum") or "")[-4:],
                "email": str(row.get("email") or "")[:200],
            }
    return None


def _money(raw: Any) -> str:
    """Un monto con dos decimales, en texto, como lo guarda `payments`."""
    try:
        return f"{float(raw):.2f}"
    except (TypeError, ValueError):
        return ""


def paid(found: dict[str, Any] | None) -> bool:
    """Si esa operación es dinero cobrado: aprobada y capturada."""
    return bool(found and found["status"] == 1 and found["operation"] in PAID)
