"""La renovación automática con una suscripción de PayPal.

PayPal tiene el reloj: el cliente aprueba una vez y PayPal cobra cada periodo.
Lo que fijan estas pruebas es lo que, si sale mal, sale mal con el dinero de
alguien: que **lo decida la respuesta de PayPal al servidor** y no el navegador ni
el cuerpo del aviso, que el **mismo cobro no dé dos periodos** venga por donde
venga, que un monto distinto no active nada, y que el aviso sin firma no haga
nada.

PayPal se sustituye entero (`fake_subscriptions`): es lo único que no se puede
llamar desde una prueba. Todo lo demás es nuestro y se ejerce tal cual.
"""

from __future__ import annotations

from datetime import timedelta

from test_payments import confirm, csrf, inside, other

from config import Config
from models import account as accounts
from models import mail_log
from models import payment as payments
from services import paypal, plans

EMAIL = "ana@ejemplo.com"


def fake_subscriptions(monkeypatch, *, webhook=True):
    """PayPal de mentira con suscripciones. Guarda lo que se le pidió."""
    state: dict = {"created": [], "charges": [], "status": "ACTIVE",
                   "cancelled": [], "valid": True, "reference": "", "next": ""}

    def create_subscription(**kwargs):
        state["created"].append(kwargs)
        state["reference"] = kwargs["reference"]
        return "I-SUB1", "https://sandbox.paypal.com/webapps/billing/subscriptions?ba_token=BA-1"

    def get_subscription(sub_id):
        return {"status": state["status"], "custom_id": state["reference"],
                "plan_id": "PLAN", "next": state["next"], "payer": "ana@paypal.com"}

    monkeypatch.setattr(paypal, "configured", lambda: True)
    monkeypatch.setattr(Config, "PAYPAL_WEBHOOK_ID", "WH-1" if webhook else "")
    monkeypatch.setattr(paypal, "create_product", lambda: "PROD-1")
    monkeypatch.setattr(paypal, "create_plan",
                        lambda **kw: f"PLAN-{kw['cycle']}-{kw['amount']}")
    monkeypatch.setattr(paypal, "create_subscription", create_subscription)
    monkeypatch.setattr(paypal, "get_subscription", get_subscription)
    monkeypatch.setattr(paypal, "transactions",
                        lambda sub_id, *, start, end: list(state["charges"]))
    monkeypatch.setattr(paypal, "cancel_subscription",
                        lambda sub_id, reason: state["cancelled"].append(sub_id))
    monkeypatch.setattr(paypal, "verify_webhook", lambda headers, event: state["valid"])
    return state


def cobro(id_, amount="25.00", currency="USD", status="COMPLETED"):
    return {"id": id_, "status": status, "amount": amount, "currency": currency,
            "time": "2026-10-11T10:00:00Z", "payer": "ana@paypal.com"}


def pagar_con_renovacion(browser, plan="negocio", cycle="monthly"):
    return browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, f"/checkout/{plan}"), "plan": plan,
        "cycle": cycle, "renovar": "1"})


def volver(browser, sub="I-SUB1"):
    return browser.get(f"/settings/billing/renewal/return?subscription_id={sub}")


def aviso(browser, tipo="PAYMENT.SALE.COMPLETED", sub="I-SUB1"):
    return browser.post("/webhooks/paypal", json={
        "event_type": tipo, "resource": {"billing_agreement_id": sub, "id": sub}})


def correos(database, purpose):
    return list(database.mail_log.find({"purpose": purpose}))


def cuenta_pagada(client, database, monkeypatch, plan="negocio"):
    """Una cuenta con su plan pagado suelto, vigente por unos días."""
    state = fake_subscriptions(monkeypatch)
    browser = inside(client)
    confirm(database, EMAIL)
    cuenta = accounts.by_email(database, EMAIL)
    accounts.activate_plan(database, cuenta["_id"], plan,
                           accounts.now() + timedelta(days=10), cycle="monthly")
    return browser, accounts.by_id(database, cuenta["_id"]), state


# ------------------------------------------------------------- el pago

def test_la_casilla_sale_solo_con_el_aviso_montado_y_sin_plan_vigente(
        client, database, outbox, monkeypatch):
    fake_subscriptions(monkeypatch, webhook=False)
    browser = inside(client)
    confirm(database, EMAIL)
    assert 'name="renovar"' not in browser.get("/checkout/negocio").get_data(as_text=True)

    fake_subscriptions(monkeypatch)
    pantalla = browser.get("/checkout/negocio").get_data(as_text=True)
    assert 'name="renovar"' in pantalla and "Renovar solo cada mes con PayPal" in pantalla
    anual = browser.get("/checkout/negocio?cycle=yearly").get_data(as_text=True)
    assert "Renovar solo cada año con PayPal" in anual

    # Quien ya tiene un plan vigente solo mejora, y eso se paga suelto.
    cuenta = accounts.by_email(database, EMAIL)
    accounts.activate_plan(database, cuenta["_id"], "basico",
                           accounts.now() + timedelta(days=10), cycle="monthly")
    assert 'name="renovar"' not in browser.get("/checkout/empresa").get_data(as_text=True)


def test_pagar_con_la_casilla_crea_la_suscripcion_y_el_cobro_activa_el_plan(
        client, database, outbox, monkeypatch):
    state = fake_subscriptions(monkeypatch)
    browser = inside(client)
    confirm(database, EMAIL)

    respuesta = pagar_con_renovacion(browser)

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    pedida = state["created"][0]
    assert pedida["plan_id"] == f"PLAN-monthly-{plans.amount('negocio', 'monthly')}"
    # Cobra el primer periodo al aprobarla, sin fecha de arranque.
    assert pedida["start_time"] == ""
    cuenta = accounts.by_email(database, EMAIL)
    assert accounts.subscription_of(cuenta)["status"] == accounts.SUB_PENDING
    # Todavía nada pagado: el navegador no prueba nada.
    assert accounts.plan_of(cuenta) is None
    assert database.payments.count_documents({}) == 0

    state["charges"] = [cobro("TXN-1", plans.amount("negocio", "monthly"))]
    vuelta = volver(browser)

    assert "/settings/billing/receipt/" in vuelta.headers["Location"]
    cuenta = accounts.by_email(database, EMAIL)
    assert accounts.plan_of(cuenta) == "negocio" and accounts.is_open(cuenta)
    assert accounts.renewal_on(cuenta)
    vence = cuenta["plan_until"]
    assert correos(database, mail_log.RENEWAL)

    # Recargar la vuelta, o que llegue el aviso, no da otro periodo.
    volver(browser)
    aviso(browser)
    assert accounts.by_email(database, EMAIL)["plan_until"] == vence
    assert database.payments.count_documents({"transaction_id": "TXN-1"}) == 1


def test_la_vuelta_pregunta_a_paypal_y_no_se_fia_de_la_direccion(
        client, database, outbox, monkeypatch):
    state = fake_subscriptions(monkeypatch)
    browser = inside(client)
    confirm(database, EMAIL)
    pagar_con_renovacion(browser)

    # Una suscripción que no es la de esta cuenta no cuenta.
    state["charges"] = [cobro("TXN-1", plans.amount("negocio", "monthly"))]
    ajena = volver(browser, sub="I-OTRA")
    assert "error=cancelled" in ajena.headers["Location"]
    assert accounts.plan_of(accounts.by_email(database, EMAIL)) is None

    # Ni una que PayPal dice que sigue sin aprobar.
    state["status"] = "APPROVAL_PENDING"
    sin = volver(browser)
    assert "error=cancelled" in sin.headers["Location"]
    assert accounts.plan_of(accounts.by_email(database, EMAIL)) is None
    assert database.payments.count_documents({}) == 0


def test_un_monto_o_una_moneda_distintos_no_activan_nada(client, database, outbox,
                                                         monkeypatch):
    state = fake_subscriptions(monkeypatch)
    browser = inside(client)
    confirm(database, EMAIL)
    pagar_con_renovacion(browser)

    state["charges"] = [cobro("TXN-1", "1.00"), cobro("TXN-2", currency="EUR")]
    volver(browser)

    cuenta = accounts.by_email(database, EMAIL)
    assert accounts.plan_of(cuenta) is None
    malos = list(database.payments.find({}))
    assert len(malos) == 2 and all(one["status"] == payments.FAILED for one in malos)
    # Y el mismo cobro malo no se vuelve a mirar.
    aviso(browser)
    assert database.payments.count_documents({}) == 2


# --------------------------------------------------------- desde Facturación

def test_activarla_desde_facturacion_empieza_el_dia_que_vence(client, database,
                                                              outbox, monkeypatch):
    browser, cuenta, state = cuenta_pagada(client, database, monkeypatch)
    pantalla = browser.get("/settings/billing/auto-renewal").get_data(as_text=True)
    assert "Activar con PayPal" in pantalla

    respuesta = browser.post("/settings/billing/renewal", data={
        "csrf_token": csrf(browser)})

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    # Cobra cuando vence lo que pagó, no antes: la fecha viaja a PayPal.
    pedida = state["created"][0]
    assert pedida["start_time"].startswith(cuenta["plan_until"].strftime("%Y-%m-%d"))
    assert accounts.subscription_of(accounts.by_id(database, cuenta["_id"]))["plan"] == "negocio"

    state["next"] = "2026-11-12T10:00:00Z"
    vuelta = volver(browser)

    assert "renewal=on" in vuelta.headers["Location"]
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.renewal_on(despues)
    # No cobró nada todavía: el plan sigue siendo el mismo hasta su fecha.
    assert despues["plan_until"] == cuenta["plan_until"]
    assert database.payments.count_documents({}) == 0
    pantalla = browser.get("/settings/billing/auto-renewal").get_data(as_text=True)
    assert "Cancelar renovación" in pantalla and "Próximo cobro" in pantalla


def test_sin_el_aviso_montado_no_sale_la_fila_ni_el_boton(client, database, outbox,
                                                          monkeypatch):
    browser, cuenta, _ = cuenta_pagada(client, database, monkeypatch)
    monkeypatch.setattr(Config, "PAYPAL_WEBHOOK_ID", "")

    # La subsección existe (octubre de 2026), pero sin botón: dice por qué.
    pantalla = browser.get("/settings/billing/auto-renewal").get_data(as_text=True)
    assert "Activar con PayPal" not in pantalla and "Próximamente" not in pantalla
    assert "todavía no está disponible" in pantalla
    sin = browser.post("/settings/billing/renewal", data={"csrf_token": csrf(browser)})
    assert "/settings/billing" in sin.headers["Location"]
    assert accounts.subscription_of(accounts.by_id(database, cuenta["_id"])) is None


# ----------------------------------------------------------- las renovaciones

def activa(client, database, monkeypatch):
    browser, cuenta, state = cuenta_pagada(client, database, monkeypatch)
    browser.post("/settings/billing/renewal", data={"csrf_token": csrf(browser)})
    volver(browser)
    return browser, accounts.by_id(database, cuenta["_id"]), state


def test_la_renovacion_llega_por_el_aviso_y_alarga_desde_el_vencimiento(
        client, database, outbox, monkeypatch):
    browser, cuenta, state = activa(client, database, monkeypatch)
    vencia = cuenta["plan_until"]

    state["charges"] = [cobro("TXN-R1", plans.amount("negocio", "monthly"))]
    respuesta = aviso(other(client))

    assert respuesta.status_code == 200
    nuevo = accounts.by_id(database, cuenta["_id"])["plan_until"]
    assert nuevo == vencia + timedelta(days=payments.DAYS["monthly"])
    # El mismo aviso otra vez (PayPal reintenta) no da otro mes.
    aviso(other(client))
    aviso(other(client), tipo="BILLING.SUBSCRIPTION.ACTIVATED")
    assert accounts.by_id(database, cuenta["_id"])["plan_until"] == nuevo
    assert database.payments.count_documents({"transaction_id": "TXN-R1"}) == 1


def test_facturacion_al_abrirse_recoge_lo_que_el_aviso_no_trajo(client, database,
                                                                outbox, monkeypatch):
    browser, cuenta, state = activa(client, database, monkeypatch)
    state["charges"] = [cobro("TXN-R1", plans.amount("negocio", "monthly"))]

    browser.get("/settings/billing")

    assert accounts.by_id(database, cuenta["_id"])["plan_until"] == \
        cuenta["plan_until"] + timedelta(days=payments.DAYS["monthly"])
    browser.get("/settings/billing")
    assert database.payments.count_documents({"transaction_id": "TXN-R1"}) == 1


def test_el_aviso_sin_firma_o_sin_webhook_no_hace_nada(client, database, outbox,
                                                       monkeypatch):
    browser, cuenta, state = activa(client, database, monkeypatch)
    state["charges"] = [cobro("TXN-R1", plans.amount("negocio", "monthly"))]

    state["valid"] = False
    malo = aviso(other(client))
    assert malo.status_code == 400
    assert database.payments.count_documents({}) == 0

    state["valid"] = True
    monkeypatch.setattr(Config, "PAYPAL_WEBHOOK_ID", "")
    assert aviso(other(client)).status_code == 404
    assert accounts.by_id(database, cuenta["_id"])["plan_until"] == cuenta["plan_until"]


def test_un_aviso_de_otra_suscripcion_o_raro_se_contesta_200(client, database,
                                                             outbox, monkeypatch):
    activa(client, database, monkeypatch)

    assert aviso(other(client), sub="I-DESCONOCIDA").status_code == 200
    assert other(client).post("/webhooks/paypal", json={}).status_code == 200
    assert other(client).post("/webhooks/paypal", json={
        "event_type": "CUSTOMER.DISPUTE.CREATED", "resource": {}}).status_code == 200


def test_un_cobro_fallido_avisa_y_no_corta_el_plan(client, database, outbox,
                                                   monkeypatch):
    browser, cuenta, state = activa(client, database, monkeypatch)

    state["status"] = "SUSPENDED"
    aviso(other(client), tipo="BILLING.SUBSCRIPTION.PAYMENT.FAILED")

    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.subscription_of(despues)["status"] == accounts.SUB_SUSPENDED
    assert despues["plan_until"] == cuenta["plan_until"] and despues["status"] == accounts.ACTIVE
    assert any("No pudimos cobrar tu renovación" in one["subject"]
               for one in correos(database, mail_log.RENEWAL))
    pantalla = browser.get("/settings/billing/auto-renewal").get_data(as_text=True)
    assert "PayPal no pudo cobrar" in pantalla


def test_cancelar_conserva_lo_pagado_y_avisa(client, database, outbox, monkeypatch):
    browser, cuenta, state = activa(client, database, monkeypatch)

    respuesta = browser.post("/settings/billing/renewal/cancel", data={
        "csrf_token": csrf(browser)})

    assert "renewal=off" in respuesta.headers["Location"]
    assert state["cancelled"] == ["I-SUB1"]
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.subscription_of(despues)["status"] == accounts.SUB_CANCELLED
    assert not accounts.renewal_on(despues)
    assert despues["plan"] == "negocio" and despues["plan_until"] == cuenta["plan_until"]
    assert any("Cancelaste la renovación automática" in one["subject"]
               for one in correos(database, mail_log.RENEWAL))
    # Y se puede volver a activar.
    assert "Activar con PayPal" in browser.get(
        "/settings/billing/auto-renewal").get_data(as_text=True)


def test_solo_el_dueno_toca_la_renovacion(client, database, outbox, monkeypatch):
    from test_users import accept, invite, invite_link

    dueno, cuenta, state = cuenta_pagada(client, database, monkeypatch)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})
    invite(dueno)
    luis, _ = accept(client, invite_link(outbox))

    for ruta in ("/settings/billing/renewal", "/settings/billing/renewal/cancel"):
        respuesta = luis.post(ruta, data={"csrf_token": csrf(luis, "/settings/security")})
        assert "/settings/security" in respuesta.headers["Location"], ruta
    assert state["created"] == [] and state["cancelled"] == []


def test_mejorar_de_plan_cancela_la_renovacion_y_se_paga_suelto(client, database,
                                                                outbox, monkeypatch):
    from test_payments import fake_paypal

    browser, cuenta, state = activa(client, database, monkeypatch)
    fake_paypal(monkeypatch)
    # `fake_paypal` cambia `configured`; las suscripciones siguen siendo las de arriba.
    monkeypatch.setattr(Config, "PAYPAL_WEBHOOK_ID", "WH-1")

    respuesta = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/empresa"), "plan": "empresa",
        "cycle": "monthly", "renovar": "1"})

    # Se pagó suelto (una orden), y la suscripción de antes ya no está.
    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/checkoutnow")
    assert state["cancelled"] == ["I-SUB1"] and state["created"][1:] == []
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.subscription_of(despues)["status"] == accounts.SUB_CANCELLED
    assert database.payments.find_one({"plan": "empresa"})["status"] == payments.CREATED
