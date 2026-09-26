"""Qué se puede comprar teniendo un plan, y cuánto se descuenta al mejorar.

Con un plan vigente solo se mejora, así que el crédito nunca sobra:

  * **Mensual**: uno mayor, mensual o anual, o el mismo en anual.
  * **Anual**: solo uno mayor, y en anual.
  * Bajar de plan, o repetir el mismo ciclo del que se tiene, no se deja.

**El crédito son los correos que no se usaron**, al precio al que se pagaron:
en un mensual, el mes × lo que queda de su cuota; en un anual, los meses enteros
que faltan más lo que queda de la cuota de este mes, al precio del año entre
doce. El plan nuevo empieza hoy, con su cuota entera. Lo calcula siempre el
servidor al crear el intento de pago, y ese monto es el que se compara al cobrar.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from models import account as accounts
from services import plans

# Lo que se dice cuando no se deja comprar. Las claves las traduce la pantalla.
DOWNGRADE = "downgrade"
SAME = "same"
YEARLY_ONLY = "yearly_only"

# Cuántos días tiene un mes al contar los que le faltan a un anual: los mismos
# con los que se venden (`payments.DAYS`).
MONTH_DAYS = 30

CENT = Decimal("0.01")


def holding(account: dict[str, Any] | None) -> tuple[str | None, str]:
    """El plan vigente y su ciclo. Sin plan vigente, (None, mensual)."""
    return accounts.current_plan(account), accounts.plan_cycle(account)


def refused(account: dict[str, Any] | None, plan: str, cycle: str) -> str:
    """Por qué no se puede comprar ese plan en ese ciclo, o vacío si se puede."""
    have, have_cycle = holding(account)
    if not have:
        return ""
    mine, wanted = plans.rank(have), plans.rank(plan)
    if wanted < mine:
        return DOWNGRADE
    if have_cycle == plans.YEARLY:
        if wanted == mine:
            return SAME
        return "" if cycle == plans.YEARLY else YEARLY_ONLY
    if wanted == mine and cycle != plans.YEARLY:
        return SAME
    return ""


def credit(account: dict[str, Any] | None, when: datetime | None = None) -> dict[str, Any]:
    """Cuánto vale lo que queda del plan vigente, y de dónde sale.

    `amount` en dólares; `unused` y `emails`, los correos de este mes sin usar y
    los que traía el mes; `months`, los meses enteros que le faltan a un anual.
    """
    have, have_cycle = holding(account)
    nothing = {"amount": Decimal("0.00"), "unused": 0, "emails": 0, "months": 0}
    emails = plans.emails_a_month(have) if have else None
    paid = plans.price(have, have_cycle) if have else None
    if not have or not emails or paid is None:
        return nothing

    unused = max(0, emails - accounts.used_this_month(account, when))
    share = Decimal(unused) / Decimal(emails)
    months = 0
    if have_cycle == plans.YEARLY:
        per_month = paid / 12
        until = accounts.plan_until(account)
        moment = when or accounts.now()
        if until is not None:
            # Los meses enteros que quedan después de este, que es el que se
            # cuenta por sus correos.
            months = max(0, (until - moment).days // MONTH_DAYS - 1)
        value = per_month * (Decimal(months) + share)
    else:
        value = paid * share
    value = min(value, paid).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"amount": value, "unused": unused, "emails": emails, "months": months}


def quote(account: dict[str, Any] | None, plan: str, cycle: str,
          when: datetime | None = None) -> dict[str, Any] | None:
    """Lo que se paga por ese plan en ese ciclo: el precio, el descuento y el
    total. None si ese plan no se vende así."""
    price = plans.price(plan, cycle)
    if price is None:
        return None
    discount = credit(account, when)
    total = max(Decimal("0.00"), price - discount["amount"]).quantize(CENT)
    # El desglose que se enseña: el plan y el descuento sin ITBMS, y el ITBMS
    # aparte, que se suma y da el total. El ITBMS sale del total (es lo que se
    # cobra), el plan sin él es su precio entre 1.07, y el descuento es lo que
    # falta para que las filas sumen exacto al centavo.
    tax = plans.itbms_in(total)
    if discount["amount"] > 0:
        net_price = plans.without_itbms(price)
        net_credit = net_price - (total - tax)
    else:
        net_price, net_credit = total - tax, Decimal("0.00")
    return {"price": price.quantize(CENT), "credit": discount, "total": total,
            "tax": tax, "net_price": net_price, "net_credit": net_credit}
