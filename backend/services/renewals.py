"""La renovación automática con una suscripción de PayPal (octubre de 2026).

El cliente aprueba una suscripción una vez y **PayPal cobra cada periodo por su
cuenta**: no hace falta ningún proceso en segundo plano, que es lo que el
proyecto todavía no tiene. Este archivo es todo lo que Sobreala hace con ella:
crearla, enterarse de lo que PayPal cobró, y cancelarla.

La regla de siempre sigue en pie: **lo decide la respuesta de PayPal al
servidor**. Nada de lo que traiga el navegador o el aviso prueba un cobro; sirven
para saber *de qué suscripción preguntar*. `sync()` le pide a PayPal los cobros
de esa suscripción y solo ellos activan el plan, comparando antes el monto y la
moneda contra lo que ese plan cuesta.

Cada cobro se anota con su id de PayPal en un índice único
(`payments.record_charge()`), así que el mismo cobro no da dos periodos aunque lo
traigan a la vez la vuelta del navegador, el aviso y Facturación.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from models import account as accounts
from models import payment as payments
from services import notices, paypal, plans


def iso(moment: datetime) -> str:
    """La fecha como la quiere PayPal: ISO, en UTC y con la Z."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(value: str) -> datetime | None:
    """La fecha que dice PayPal («2026-11-12T10:00:00Z»), o None si no se entiende."""
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def plan_id_for(db, plan: str, cycle: str) -> str:
    """El plan de cobro de PayPal para ese plan nuestro y ese ciclo.

    Se crea la primera vez que hace falta y se guarda (`paypal_plans`). La clave
    lleva el monto: si el precio cambia en `docs/pricing.md`, sale otro plan de
    PayPal con el monto nuevo, y las suscripciones ya aprobadas siguen cobrando
    lo que aprobaron.
    """
    amount = plans.amount(plan, cycle)
    key = f"{plan}:{cycle}:{amount}"
    found = db.paypal_plans.find_one({"key": key})
    if found:
        return found["paypal_id"]

    product = db.paypal_plans.find_one({"key": "product"})
    if product is None:
        product_id = paypal.create_product()
        try:
            db.paypal_plans.insert_one({"key": "product", "paypal_id": product_id})
        except DuplicateKeyError:
            product_id = db.paypal_plans.find_one({"key": "product"})["paypal_id"]
    else:
        product_id = product["paypal_id"]

    name = f"Sobreala {plans.PLANS[plan]['name']} ({cycle})"
    plan_id = paypal.create_plan(
        product_id=product_id, name=name, cycle=cycle, amount=amount,
        currency=plans.CURRENCY, reference=f"plan-{key}")
    try:
        db.paypal_plans.insert_one({"key": key, "paypal_id": plan_id})
    except DuplicateKeyError:
        plan_id = db.paypal_plans.find_one({"key": key})["paypal_id"]
    return plan_id


def start(db, account: dict[str, Any], plan: str, cycle: str, *, return_url: str,
          cancel_url: str, first_charge: datetime | None = None) -> str:
    """Crear la suscripción y devolver la dirección donde el cliente la aprueba.

    `first_charge` es cuándo cobra el primer periodo: sin ella, al aprobarla (un
    pago nuevo); con ella, ese día (quien ya pagó suelto y activa la renovación
    para cuando venza lo que pagó). PayPal no acepta una fecha ya pasada ni de
    este mismo minuto, así que se pide con unos minutos de margen.
    """
    start_time = ""
    if first_charge is not None:
        start_time = iso(max(first_charge, accounts.now() + timedelta(minutes=10)))
    sub_id, approve = paypal.create_subscription(
        plan_id=plan_id_for(db, plan, cycle),
        reference=f"{account['_id']}:{plan}:{cycle}",
        return_url=return_url, cancel_url=cancel_url, start_time=start_time)
    accounts.start_subscription(db, account["_id"], sub_id=sub_id, plan=plan, cycle=cycle)
    return approve


def confirm(db, account: dict[str, Any], sub_id: str) -> bool:
    """La vuelta de PayPal: preguntarle si el cliente la aprobó.

    La suscripción tiene que ser **la que esta cuenta tiene anotada**, y PayPal
    tiene que decir que es de ella (`custom_id`) y que está aprobada. Lo que traiga
    la dirección del navegador no vale por sí solo."""
    mine = accounts.subscription_of(account)
    if not mine or mine.get("id") != sub_id:
        return False
    try:
        found = paypal.get_subscription(sub_id)
    except paypal.PayPalError:
        return False
    if not found["custom_id"].startswith(f"{account['_id']}:"):
        return False
    if found["status"] not in ("ACTIVE", "APPROVED"):
        return False
    accounts.set_subscription(db, account["_id"], status=accounts.SUB_ACTIVE,
                              next=parse(found["next"]), payer=found["payer"])
    return True


# PayPal dice su estado en mayúsculas; esto es lo nuestro.
STATES = {"ACTIVE": accounts.SUB_ACTIVE, "SUSPENDED": accounts.SUB_SUSPENDED,
          "CANCELLED": accounts.SUB_CANCELLED, "EXPIRED": accounts.SUB_CANCELLED}


def settle_charge(db, account: dict[str, Any], sub: dict[str, Any],
                  charge: dict[str, str]) -> Any:
    """Un cobro de PayPal: compararlo, anotarlo una sola vez y alargar el plan.

    Devuelve el id del pago anotado, o None si ya estaba escrito o no cuadraba.
    Un monto o una moneda distintos no activan nada, pero se anotan fallidos: así
    queda la diferencia a la vista y el mismo cobro no se vuelve a mirar."""
    plan, cycle = sub["plan"], sub["cycle"]
    wanted = plans.amount(plan, cycle)
    common = dict(transaction_id=charge["id"], sub_id=sub["id"], plan=plan,
                  cycle=cycle, amount=wanted, currency=plans.CURRENCY,
                  payer_email=charge.get("payer") or sub.get("payer", ""))
    if charge["amount"] != wanted or charge["currency"] != plans.CURRENCY:
        payments.record_charge(
            db, account["_id"], status=payments.FAILED,
            error=f"amount: {charge['amount']} {charge['currency']}", **common)
        return None
    paid_id = payments.record_charge(db, account["_id"], **common)
    if paid_id is None:
        return None

    running = accounts.plan_until(account)
    renewed = (accounts.plan_of(account) == plan and running is not None
               and running > accounts.now())
    until = payments.until(cycle, since=accounts.renews_from(account, plan))
    accounts.activate_plan(db, account["_id"], plan, until, cycle=cycle)
    notices.paid(account, plan=plan, until=until, renewed=renewed, charged=wanted)
    if not renewed:
        notices.payment_to_admins(db, account, plan=plan)
    return paid_id


def sync(db, account: dict[str, Any]) -> list[Any]:
    """Preguntarle a PayPal por los cobros de la suscripción y liquidar los que
    no estén escritos. Devuelve los pagos nuevos.

    La llaman la vuelta del navegador, el aviso de PayPal y Facturación al
    abrirse (por si el aviso no llegó): los tres hacen lo mismo y ninguno puede
    dar un periodo de más, por el índice único de cada cobro. No deja escapar un
    error de PayPal: quien llama ya hizo lo suyo, y esto se reintenta."""
    sub = accounts.subscription_of(account)
    if not sub or not sub.get("id") or sub.get("status") == accounts.SUB_PENDING:
        return []
    created = sub.get("created_at") or accounts.now()
    try:
        charges = paypal.transactions(
            sub["id"], start=iso(created - timedelta(days=1)),
            end=iso(accounts.now() + timedelta(days=1)))
        found = paypal.get_subscription(sub["id"])
    except paypal.PayPalError:
        return []

    new = []
    for charge in sorted(charges, key=lambda one: one["time"]):
        if charge["status"] != "COMPLETED":
            continue
        fresh = accounts.by_id(db, account["_id"])
        got = settle_charge(db, fresh, sub, charge)
        if got is not None:
            new.append(got)
    state = STATES.get(found["status"])
    if state and state != sub.get("status"):
        accounts.set_subscription(db, account["_id"], status=state)
    upcoming = parse(found["next"])
    if upcoming and upcoming != sub.get("next"):
        accounts.set_subscription(db, account["_id"], next=upcoming)
    return new


def cancel(db, account: dict[str, Any], reason: str = "Cancelada por el cliente") -> bool:
    """Cancelar en PayPal. El plan sigue hasta su fecha: lo ya pagado es del
    cliente. False si PayPal no la canceló."""
    sub = accounts.subscription_of(account)
    if not sub or not sub.get("id"):
        return False
    try:
        paypal.cancel_subscription(sub["id"], reason)
    except paypal.PayPalError:
        return False
    accounts.set_subscription(db, account["_id"], status=accounts.SUB_CANCELLED)
    notices.renewal_off(account)
    return True


def event(db, event_type: str, resource: dict[str, Any]) -> bool:
    """Un aviso de PayPal ya verificado. De él solo se usa **de qué suscripción es**
    (`billing_agreement_id` en un cobro, `id` en un cambio de estado): lo demás se
    le pregunta a PayPal. True si era de una cuenta nuestra."""
    sub_id = resource.get("billing_agreement_id") or resource.get("id") or ""
    account = accounts.by_subscription(db, sub_id)
    if account is None:
        return False
    sync(db, account)
    fresh = accounts.by_id(db, account["_id"])
    if event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
        notices.renewal_failed(fresh)
    return True
