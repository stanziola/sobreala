"""La colección payments: un documento por intento de pago.

Se escribe **antes** de mandar a nadie a PayPal, no después de volver. Así, si
alguien paga y el navegador se cierra en el camino de vuelta, el intento existe
y se puede reconciliar; si solo se guardara al volver, ese pago no habría
ocurrido para nosotros.

De la tarjeta no hay nada aquí, y no puede haberlo: el pago entero pasa en el
checkout de PayPal. Es la regla 9.
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


# Con qué se paga. **`METHODS` es lo que cobra hoy**, y es lo único que esta
# ruta acepta; los otros dos están anunciados en la pantalla y no llegan hasta
# aquí, así que un formulario escrito a mano con `metodo=yappy` acaba pagando
# por PayPal y no abriendo una puerta que no existe.
#
# La tarjeta va a ser una pasarela con afiliación de comercio en Panamá, no el
# checkout de PayPal, y esa decisión está pendiente. Cuando exista, entra aquí
# y lo demás —la pantalla, el documento del intento— ya está puesto.
PAYPAL = "paypal"
CARD = "card"
YAPPY = "yappy"
METHODS = (PAYPAL,)
SOON = (CARD, YAPPY)


def start(db, account_id, *, plan: str, cycle: str, amount: str,
          currency: str, method: str = PAYPAL) -> Any:
    """Anotar el intento. Devuelve su id, que viaja a PayPal como referencia."""
    return db.payments.insert_one({
        "account_id": account_id,
        "provider": "paypal",
        # Con qué eligió pagar. Lo de antes no lo tiene y se lee como PayPal,
        # que es lo único que había.
        "method": method if method in METHODS else PAYPAL,
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


def by_order(db, account_id, order_id: str) -> dict[str, Any] | None:
    """El intento que corresponde a esa orden, dentro de esta cuenta.

    El account_id va en la consulta: una orden de otra cuenta no encuentra
    nada, aunque alguien traiga su identificador en la dirección.
    """
    return db.payments.find_one({"account_id": account_id,
                                 "order_id": order_id})


def complete(db, payment_id) -> bool:
    """Marcar el pago como cobrado. **False si ya lo estaba.**

    Es la única escritura que decide si se alarga un plan, y por eso es
    condicional: recargar la página de vuelta entra aquí una segunda vez y se
    va con las manos vacías, en vez de regalar otro periodo.
    """
    result = db.payments.update_one(
        {"_id": payment_id, "status": CREATED},
        {"$set": {"status": COMPLETED, "completed_at": now()}})
    return result.modified_count == 1


def fail(db, payment_id, reason: str) -> None:
    db.payments.update_one({"_id": payment_id, "status": CREATED},
                           {"$set": {"status": FAILED, "error": reason[:200],
                                     "completed_at": now()}})


def until(cycle: str, *, since: datetime | None = None) -> datetime:
    """Hasta cuándo vale lo que se acaba de pagar."""
    return (since or now()) + timedelta(days=DAYS.get(cycle, DAYS["monthly"]))


def for_account(db, account_id, *, limit: int = 20) -> list[dict[str, Any]]:
    return list(db.payments.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))
