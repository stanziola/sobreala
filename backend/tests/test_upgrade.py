"""Mejorar de plan: qué se puede comprar, el descuento por los correos sin usar
y el recibo al volver de pagar.

Lo que se fija aquí es lo que no se puede aflojar: con un plan vigente solo se
mejora (así el crédito nunca sobra), el descuento lo calcula el servidor y es
lo que se compara al cobrar, y el mes empieza de nuevo con el plan nuevo.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from models import account as accounts
from services import upgrade
from test_payments import buy, come_back, confirm, fake_paypal, inside

ROOT = Path(__file__).resolve().parent.parent.parent


def cuenta(plan, cycle, *, days=20, sent=0):
    return {"plan": plan, "plan_cycle": cycle,
            "plan_until": accounts.now() + timedelta(days=days),
            "sent_counts": {accounts.quota_month(): sent}}


# ------------------------------------------------------------ qué se deja

def test_con_un_plan_vigente_solo_se_mejora():
    nada = {}
    assert upgrade.refused(nada, "basico", "monthly") == ""

    mensual = cuenta("negocio", "monthly")
    assert upgrade.refused(mensual, "empresa", "monthly") == ""
    assert upgrade.refused(mensual, "empresa", "yearly") == ""
    assert upgrade.refused(mensual, "negocio", "yearly") == ""
    assert upgrade.refused(mensual, "negocio", "monthly") == upgrade.SAME
    assert upgrade.refused(mensual, "basico", "yearly") == upgrade.DOWNGRADE

    anual = cuenta("negocio", "yearly", days=200)
    assert upgrade.refused(anual, "empresa", "yearly") == ""
    assert upgrade.refused(anual, "empresa", "monthly") == upgrade.YEARLY_ONLY
    assert upgrade.refused(anual, "negocio", "yearly") == upgrade.SAME
    assert upgrade.refused(anual, "basico", "yearly") == upgrade.DOWNGRADE

    # Vencido es como no tener nada.
    vencido = cuenta("negocio", "yearly", days=-1)
    assert upgrade.refused(vencido, "basico", "monthly") == ""


# ------------------------------------------------------------ el descuento

def test_el_mensual_descuenta_los_correos_sin_usar():
    # Negocio sin usar nada: se descuenta el mes entero.
    entero = upgrade.quote(cuenta("negocio", "monthly"), "empresa", "monthly")
    assert entero["credit"]["amount"] == Decimal("25.00")
    assert entero["total"] == Decimal("30.00")
    # Con 5,000 de 15,000 enviados, quedan dos tercios.
    usado = upgrade.quote(cuenta("negocio", "monthly", sent=5000), "empresa", "monthly")
    assert usado["credit"]["amount"] == Decimal("16.67")
    assert usado["credit"]["unused"] == 10000 and usado["credit"]["emails"] == 15000
    assert usado["total"] == Decimal("38.33")


def test_el_anual_descuenta_los_meses_que_faltan_y_lo_de_este_mes():
    # Básico anual ($144, $12 al mes) con 8 meses enteros después de este y
    # 1,000 de 5,000 usados: 8 × 12 + 0.8 × 12.
    anual = cuenta("basico", "yearly", days=9 * 30 + 15, sent=1000)
    precio = upgrade.quote(anual, "negocio", "yearly")
    assert precio["credit"]["months"] == 8
    assert precio["credit"]["amount"] == Decimal("105.60")
    assert precio["total"] == Decimal("134.40")
    # Recién comprado no puede pasar de lo que se pagó.
    nuevo = upgrade.credit(cuenta("basico", "yearly", days=365))
    assert nuevo["amount"] <= Decimal("144.00")


def test_sin_plan_no_hay_descuento():
    precio = upgrade.quote({}, "negocio", "monthly")
    assert precio["credit"]["amount"] == Decimal("0.00")
    assert precio["total"] == Decimal("25.00")


# ------------------------------------------------------------ de punta a punta

def con_negocio(database, *, sent=5000):
    ana = accounts.by_email(database, "ana@ejemplo.com")
    accounts.activate_plan(database, ana["_id"], "negocio",
                           accounts.now() + timedelta(days=20), cycle="monthly")
    accounts.add_sent(database, ana["_id"], sent)
    return ana


def test_mejorar_cobra_con_descuento_empieza_hoy_y_deja_recibo(client, database, outbox,
                                                                monkeypatch):
    pedido = fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    ana = con_negocio(database)

    resumen = browser.get("/contratar/empresa").get_data(as_text=True)
    assert "Descuento por los correos sin usar" in resumen
    assert "10,000 de 15,000" in resumen and "Pagar $38.33" in resumen
    # Sin ITBMS el plan y el descuento, el ITBMS aparte, y suman el total.
    assert "$51.40" in resumen and "−$15.58" in resumen and "$2.51" in resumen

    buy(browser, plan="empresa")
    # Lo que se le pide a PayPal ya lleva el descuento, y queda en el intento.
    assert pedido["amount"] == "38.33"
    intento = database.payments.find_one({"account_id": ana["_id"]})
    assert intento["price"] == "55.00" and intento["credit"] == "16.67"

    respuesta = come_back(browser)
    recibo_url = respuesta.headers["Location"]
    assert "/configuracion/pagos/recibo/" in recibo_url
    ahora = accounts.by_id(database, ana["_id"])
    assert ahora["plan"] == "empresa" and ahora["plan_cycle"] == "monthly"
    # Empieza hoy, y el mes de nuevo: lo enviado antes no cuenta.
    assert ahora["plan_until"] < accounts.now() + timedelta(days=31)
    assert accounts.quota_left(ahora) == 50000

    recibo = browser.get(recibo_url).get_data(as_text=True)
    assert "Tu pago se completó" in recibo
    # De cifras, solo el total.
    assert "$38.33" in recibo and "Descuento" not in recibo and "ITBMS" not in recibo
    assert "receipt__tick" in recibo and "Empresa" in recibo
    # De otra cuenta no se abre.
    otra = inside(client, email="beto@ejemplo.com")
    assert otra.get(recibo_url).status_code == 404


def test_un_cobro_sin_el_descuento_no_activa_nada(client, database, outbox, monkeypatch):
    """Si quien cobra dice otra cifra que la del intento, no se activa: se
    compara contra el monto guardado, no contra el precio de lista."""
    fake_paypal(monkeypatch, amount="55.00")
    browser = inside(client)
    confirm(database)
    ana = con_negocio(database)
    buy(browser, plan="empresa")

    assert "error=monto" in come_back(browser).headers["Location"]
    assert accounts.by_id(database, ana["_id"])["plan"] == "negocio"


def test_con_un_anual_solo_se_mejora_en_anual(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    ana = accounts.by_email(database, "ana@ejemplo.com")
    accounts.activate_plan(database, ana["_id"], "basico",
                           accounts.now() + timedelta(days=200), cycle="yearly")

    # Pulsó el mensual: el resumen enseña el anual, que es el que se puede.
    resumen = browser.get("/contratar/negocio").get_data(as_text=True)
    assert 'name="cycle" value="yearly"' in resumen
    assert 'name="cycle" value="monthly"' not in resumen
    assert "Prefiero pagar un mes" not in resumen
    # Y a mano tampoco.
    assert buy(browser, plan="negocio").headers["Location"].endswith("/contratar/negocio")
    assert database.payments.count_documents({}) == 0


def test_planes_dice_obtener_y_la_nota_del_prorrateo():
    html = (ROOT / "landing" / "planes" / "index.html").read_text(encoding="utf-8")
    assert "Obtener Plan Negocio" in html and "Empezar con" not in html
    assert "los correos que no usaste se descuentan" in html
    assert 'data-label-to-yearly="Pasar a anual"' in html
    assert 'data-label-yearly-only="Solo en anual"' in html


# ------------------------------------------------ el desglose y los logos

def test_el_pago_trae_el_itbms_los_logos_y_la_frase(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    pantalla = browser.get("/contratar/negocio").get_data(as_text=True)
    # El plan sin ITBMS, el ITBMS encima del total, y el total al final:
    # $23.36 + $1.64 = $25.00.
    plan = pantalla.index("$23.36")
    itbms = pantalla.index("ITBMS (7%)")
    total = pantalla.index("Total a pagar ahora")
    assert plan < itbms < total and "$1.64" in pantalla and "$25.00" in pantalla
    # Cada método son sus logos, con su nombre en el texto alternativo, sin
    # título ni descripción.
    assert 'alt="PayPal"' in pantalla and 'alt="Visa"' in pantalla
    assert "Tarjeta de crédito o débito" not in pantalla.split("Usar este")[0]
    assert "Se paga en la página de PayPal" not in pantalla
    assert "Panamails nunca guarda tus datos de pago." in pantalla
    assert "el pago se hace en la página del proveedor" not in pantalla


def test_el_recibo_solo_trae_el_total(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser, plan="negocio")
    recibo = browser.get(come_back(browser).headers["Location"]).get_data(as_text=True)
    assert "Total pagado" in recibo and "$25.00" in recibo
    assert "ITBMS" not in recibo and "$1.64" not in recibo


def test_el_pie_trae_los_cuatro_logos_a_color():
    html = (ROOT / "landing" / "index.html").read_text(encoding="utf-8")
    for nombre, archivo in (("Yappy", "yappy.svg"), ("PayPal", "paypal.png"),
                            ("Visa", "visa.svg"), ("Mastercard", "mastercard.svg")):
        assert f'src="/assets/img/payments/{archivo}" alt="{nombre}"' in html
    # Las copias de Visa y Mastercard van recortadas a su dibujo, en el sitio y
    # en el panel, con el viewBox de brand/payments/viewbox.json.
    import json

    recortes = json.loads((ROOT / "brand" / "payments" / "viewbox.json").read_text(encoding="utf-8"))
    for marca in ("visa", "mastercard"):
        for copia in (ROOT / "landing" / "assets" / "img" / "payments" / f"{marca}.svg",
                      ROOT / "backend" / "static" / "img" / "payments" / f"{marca}.svg"):
            assert f'viewBox="{recortes[marca]}"' in copia.read_text(encoding="utf-8")
