"""La colección payments: un documento por intento de pago.

Se escribe **antes** de mandar a nadie a PayPal o a Paguélofácil, no después de
volver. Así, si alguien paga y el navegador se cierra en el camino de vuelta, el
intento existe y se puede reconciliar; si solo se guardara al volver, ese pago
no habría ocurrido para nosotros.

De la tarjeta no hay nada aquí salvo sus últimos cuatro números, y no puede
haber más: el pago entero pasa en la página de quien cobra. Es la regla 9.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

CREATED = "created"        # se creó la orden, nadie ha pagado todavía
COMPLETED = "completed"    # PayPal confirmó el cobro y la cuenta se activó
FAILED = "failed"          # volvió de PayPal sin cobrar, o con otro monto

# Cuánto dura lo pagado. El anual son doce meses, no trescientos sesenta y
# cinco días: quien paga el 31 de enero espera que le valga hasta el 31 de
# enero, y aquí se aproxima con días porque no hace falta más precisión.
DAYS = {"monthly": 30, "yearly": 365}


def now() -> datetime:
    return datetime.now(timezone.utc)


# Con qué se paga. **`METHODS` son los que tienen cobro hecho**: PayPal y la
# tarjeta, que va por Paguélofácil. Cuál se ofrece de verdad depende además de
# que haya credenciales (`ready()` en la ruta); Yappy está anunciado y no llega
# hasta aquí, así que un formulario escrito a mano con `metodo=yappy` acaba
# pagando por PayPal y no abriendo una puerta que no existe.
PAYPAL = "paypal"
CARD = "card"
YAPPY = "yappy"
METHODS = (PAYPAL, CARD)
ALL = (PAYPAL, CARD, YAPPY)
# Quién cobra cada método.
PROVIDERS = {PAYPAL: "paypal", CARD: "paguelofacil"}


def start(db, account_id, *, plan: str, cycle: str, amount: str,
          currency: str, method: str = PAYPAL) -> Any:
    """Anotar el intento. Devuelve su id, que viaja a quien cobra como
    referencia."""
    method = method if method in METHODS else PAYPAL
    return db.payments.insert_one({
        "account_id": account_id,
        "provider": PROVIDERS[method],
        # Con qué eligió pagar. Lo de antes no lo tiene y se lee como PayPal,
        # que es lo único que había.
        "method": method,
        "plan": plan,
        "cycle": cycle,
        # El monto que se pidió cobrar, para poder compararlo con el que se
        # cobró de verdad cuando vuelva.
        "amount": amount,
        "currency": currency,
        "order_id": "",
        "status": CREATED,
        "error": "",
        "created_at": now(),
        "completed_at": None,
    }).inserted_id


def attach_order(db, payment_id, order_id: str) -> None:
    db.payments.update_one({"_id": payment_id},
                           {"$set": {"order_id": order_id}})


def attach_link(db, payment_id, code: str) -> None:
    """El código del enlace de pago de Paguélofácil. La operación, que es otra
    cosa, no se sabe hasta que se paga (`complete()`)."""
    db.payments.update_one({"_id": payment_id},
                           {"$set": {"link_code": code}})


def by_order(db, account_id, order_id: str) -> dict[str, Any] | None:
    """El intento que corresponde a esa orden, dentro de esta cuenta.

    El account_id va en la consulta: una orden de otra cuenta no encuentra
    nada, aunque alguien traiga su identificador en la dirección.
    """
    return db.payments.find_one({"account_id": account_id,
                                 "order_id": order_id})


def by_id(db, payment_id, account_id=None) -> dict[str, Any] | None:
    """Un intento por su id. Con `account_id`, solo si es de esa cuenta: la
    vuelta del navegador lo pide así. Sin ella lo pide el aviso automático de
    Paguélofácil, que no trae sesión y se comprueba consultando la operación."""
    wanted: dict[str, Any] = {"_id": payment_id}
    if account_id is not None:
        wanted["account_id"] = account_id
    return db.payments.find_one(wanted)


def complete(db, payment_id, *, payer_email: str = "", last4: str = "",
             order_id: str = "") -> bool:
    """Marcar el pago como cobrado. **False si ya lo estaba.**

    Es la única escritura que decide si se alarga un plan, y por eso es
    condicional: recargar la página de vuelta entra aquí una segunda vez y se
    va con las manos vacías, en vez de regalar otro periodo. Y con tarjeta, la
    vuelta del navegador y el aviso automático llegan los dos: el segundo
    tampoco da nada.

    `last4` son los últimos cuatro números de la tarjeta, lo único de ella que
    se guarda, para que la lista de pagos diga con cuál. `order_id` es la
    operación de Paguélofácil, que no se conoce hasta que se paga.
    """
    changes: dict[str, Any] = {"status": COMPLETED, "completed_at": now(),
                               "payer_email": payer_email}
    if last4:
        changes["card_last4"] = last4[-4:]
    if order_id:
        changes["order_id"] = order_id
    result = db.payments.update_one({"_id": payment_id, "status": CREATED},
                                    {"$set": changes})
    return result.modified_count == 1


def fail(db, payment_id, reason: str) -> None:
    db.payments.update_one({"_id": payment_id, "status": CREATED},
                           {"$set": {"status": FAILED, "error": reason[:200],
                                     "completed_at": now()}})


def used_methods(paid: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Con qué se ha pagado, sacado de los pagos cobrados: el método y las
    cuentas que pagaron por él. Nada de esto es un dato de tarjeta."""
    used: dict[str, list[str]] = {}
    for one in paid:
        method = one.get("method") or PAYPAL
        who = used.setdefault(method, [])
        if one.get("payer_email") and one["payer_email"] not in who:
            who.append(one["payer_email"])
    return used


def until(cycle: str, *, since: datetime | None = None) -> datetime:
    """Hasta cuándo vale lo que se acaba de pagar."""
    return (since or now()) + timedelta(days=DAYS.get(cycle, DAYS["monthly"]))


def for_account(db, account_id, *, limit: int = 20,
                only_paid: bool = False) -> list[dict[str, Any]]:
    """Los intentos de esa cuenta, lo más reciente primero.

    `only_paid` es para la pantalla del cliente: ahí un intento sin cobrar se
    quedaría para siempre al lado del pago bueno, pareciendo que se debe algo
    cuando no se debe nada. **No se deja de escribir ninguno**: son lo que
    permite reconciliar a quien pagó y se le cerró el navegador en el camino de
    vuelta, y la ficha del administrador los sigue pidiendo todos.
    """
    wanted: dict[str, Any] = {"account_id": account_id}
    if only_paid:
        wanted["status"] = COMPLETED
    return list(db.payments.find(wanted)
                .sort("created_at", -1).limit(limit))
