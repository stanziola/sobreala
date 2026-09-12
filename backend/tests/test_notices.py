"""Los avisos de la cuenta: el plan, la habilitación de envío y la suspensión.

Lo que se fija aquí es cuándo sale cada correo y cuándo no. Que contratar y
renovar no digan lo mismo. Que un aviso de vencimiento salga **una sola vez** y
vuelva a estar disponible al renovar, sin que nadie tenga que limpiar un campo.
Que el correo de suspensión no lleve dentro el motivo que se escribió para el
registro. Y que apagar un interruptor apague lo que promete y nada más.

Todos son transaccionales: sin enlace de baja y sin marca de agua, que es la
regla 8 de CLAUDE.md.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import code_from_outbox, confirm as type_code, login, register
from test_admin import clear_sending, make_admin, update

from models import account as accounts
from models import mail_log
from services import paypal, plans

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def csrf(client, url="/configuracion/pagos"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def confirm(database, email="ana@ejemplo.com"):
    cuenta = accounts.by_email(database, email)
    database.accounts.update_one(
        {"_id": cuenta["_id"]},
        {"$set": {"email_confirmed_at": cuenta["created_at"]}})
    return accounts.by_id(database, cuenta["_id"])


def fake_paypal(monkeypatch):
    """PayPal de mentira, con una orden distinta cada vez.

    Distinta a propósito: pagar dos veces es lo que hace falta para probar que
    la segunda se lee como una renovación.
    """
    asked: dict = {}

    def create(**kwargs):
        asked.update(kwargs)
        asked["n"] = asked.get("n", 0) + 1
        order = f"ORDEN-{asked['n']}"
        asked["order"] = order
        return order, f"https://sandbox.paypal.com/checkoutnow?token={order}"

    def capture(order_id):
        return {"status": "COMPLETED", "amount": asked["amount"],
                "currency": "USD"}

    monkeypatch.setattr(paypal, "configured", lambda: True)
    monkeypatch.setattr(paypal, "create", create)
    monkeypatch.setattr(paypal, "capture", capture)
    return asked


def pay(client, pedido, plan="basico", cycle="monthly"):
    """Contratar y volver, como vuelve el navegador desde PayPal."""
    client.post("/configuracion/pagos/contratar", data={
        "csrf_token": csrf(client), "plan": plan, "cycle": cycle})
    return client.get(f"/configuracion/pagos/volver?token={pedido['order']}")


def sent(database, purpose) -> list[dict]:
    return list(database.mail_log.find({"purpose": purpose}))


def only(database, purpose) -> dict:
    found = sent(database, purpose)
    assert len(found) == 1, f"{purpose}: {len(found)} correos"
    return found[0]


def an_admin(client, database, email="jefe@ejemplo.com"):
    """Una cuenta con el rol, sin pasar por la pantalla."""
    register(other(client), email=email)
    cuenta = accounts.by_email(database, email)
    accounts.set_role(database, cuenta["_id"], accounts.ADMIN)
    return accounts.by_id(database, cuenta["_id"])


def with_plan(database, email, plan, until):
    cuenta = accounts.by_email(database, email)
    accounts.activate_plan(database, cuenta["_id"], plan, until)
    return accounts.by_id(database, cuenta["_id"])


def switch(database, email, notice, on):
    cuenta = accounts.by_email(database, email)
    accounts.set_notifications(database, cuenta["_id"], {
        name: (on if name == notice else True) for name in accounts.NOTICES})


def admin_switch(database, email, notice, on):
    """Lo mismo en una cuenta de administrador, que tiene su propia lista."""
    cuenta = accounts.by_email(database, email)
    accounts.set_notifications(
        database, cuenta["_id"],
        {name: (on if name == notice else True)
         for name in accounts.ADMIN_NOTICES},
        names=accounts.ADMIN_NOTICES)


# ------------------------------------------------ los avisos de quien manda

def test_confirmar_el_registro_avisa_a_quien_administra(client, database,
                                                        outbox):
    """Al confirmar y no al escribir el formulario: lo que no se confirma se
    borra a las 24 horas, y avisar de cada intento sería avisar de cada
    dirección escrita mal."""
    an_admin(client, database)
    visitante = other(client)
    register(visitante, email="socia@ejemplo.com")

    assert sent(database, mail_log.ADMIN_SIGNUP) == []

    type_code(visitante, code_from_outbox(outbox))

    aviso = only(database, mail_log.ADMIN_SIGNUP)
    assert aviso["to"] == "jefe@ejemplo.com"
    assert "socia@ejemplo.com" in aviso["text"]


def test_apagar_el_aviso_de_registro_lo_apaga(client, database, outbox):
    an_admin(client, database)
    admin_switch(database, "jefe@ejemplo.com", accounts.ADMIN_SIGNUP, False)
    visitante = other(client)
    register(visitante, email="socia@ejemplo.com")

    type_code(visitante, code_from_outbox(outbox))

    assert sent(database, mail_log.ADMIN_SIGNUP) == []


def test_apagar_el_aviso_de_pago_lo_apaga(client, database, outbox, monkeypatch):
    pedido = fake_paypal(monkeypatch)
    an_admin(client, database)
    admin_switch(database, "jefe@ejemplo.com", accounts.ADMIN_PAYMENT, False)
    browser = inside(client)
    confirm(database)

    pay(browser, pedido)

    # El comprobante del cliente sigue saliendo: apagar el suyo no apaga el de
    # nadie más.
    assert len(sent(database, mail_log.PLAN_PAID)) == 1
    assert sent(database, mail_log.ADMIN_PAYMENT) == []


def test_un_plan_vencido_tambien_se_le_avisa_a_quien_administra(
        client, database, outbox):
    an_admin(client, database)
    browser = inside(client)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() - timedelta(days=2))

    browser.get("/panel")
    browser.get("/panel")

    aviso = only(database, mail_log.ADMIN_PLAN_END)
    assert aviso["to"] == "jefe@ejemplo.com"
    assert "se quedó sin plan" in aviso["text"]
    # Y al cliente le llegó el suyo, una sola vez.
    only(database, mail_log.PLAN_EXPIRED)


def test_apagar_el_aviso_de_vencimiento_no_apaga_el_del_cliente(
        client, database, outbox):
    an_admin(client, database)
    admin_switch(database, "jefe@ejemplo.com", accounts.ADMIN_PLAN_END, False)
    browser = inside(client)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() - timedelta(days=2))

    browser.get("/panel")

    assert sent(database, mail_log.ADMIN_PLAN_END) == []
    only(database, mail_log.PLAN_EXPIRED)


# --------------------------------------------------------------- el plan

def test_contratar_manda_el_comprobante_y_avisa_a_quien_administra(
        client, database, outbox, monkeypatch):
    pedido = fake_paypal(monkeypatch)
    an_admin(client, database)
    browser = inside(client)
    confirm(database)

    pay(browser, pedido)

    comprobante = only(database, mail_log.PLAN_PAID)
    assert comprobante["to"] == "ana@ejemplo.com"
    assert "Ya tienes el plan" in comprobante["text"]
    # Y quien administra se entera sin tener que entrar a mirar.
    aviso = only(database, mail_log.ADMIN_PAYMENT)
    assert aviso["to"] == "jefe@ejemplo.com"
    assert "falta habilitarle" in aviso["text"]


def test_renovar_no_dice_lo_mismo_que_contratar(client, database, outbox,
                                                monkeypatch):
    pedido = fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    pay(browser, pedido)
    pay(browser, pedido)

    dichos = [one["text"] for one in sent(database, mail_log.PLAN_PAID)]
    assert len(dichos) == 2
    assert "Ya tienes el plan" in dichos[0]
    assert "sigue corriendo" in dichos[1]
    assert "no se pierden" in dichos[1]


def test_apagar_pagos_y_plan_apaga_el_comprobante(client, database, outbox,
                                                  monkeypatch):
    pedido = fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    switch(database, "ana@ejemplo.com", accounts.BILLING, False)

    pay(browser, pedido)

    assert sent(database, mail_log.PLAN_PAID) == []
    # Pero el plan se activó igual: el correo avisa, no decide.
    assert accounts.by_email(database, "ana@ejemplo.com")["plan"] == "basico"


# ----------------------------------------------- lo que se vence, al entrar

def test_al_entrar_al_panel_avisa_de_lo_que_esta_por_vencerse(
        client, database, outbox):
    browser = inside(client)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() + timedelta(days=3))

    browser.get("/panel")
    aviso = only(database, mail_log.PLAN_EXPIRING)
    assert "vence" in aviso["subject"]

    # Y recargar no manda un segundo correo.
    browser.get("/panel")
    assert len(sent(database, mail_log.PLAN_EXPIRING)) == 1


def test_renovar_devuelve_el_aviso_para_el_ciclo_siguiente(client, database,
                                                           outbox):
    """La marca guarda la fecha avisada, así que renovar la deja de coincidir."""
    browser = inside(client)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() + timedelta(days=3))
    browser.get("/panel")

    # Renovó: la fecha se corre un año y ya no hay nada que avisar.
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() + timedelta(days=365))
    browser.get("/panel")
    assert len(sent(database, mail_log.PLAN_EXPIRING)) == 1

    # Un año después, el aviso vuelve a salir sin haber limpiado nada.
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() + timedelta(days=2))
    browser.get("/panel")
    assert len(sent(database, mail_log.PLAN_EXPIRING)) == 2


def test_un_plan_vencido_avisa_una_sola_vez(client, database, outbox):
    browser = inside(client)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() - timedelta(days=2))

    browser.get("/panel")
    browser.get("/panel")

    aviso = only(database, mail_log.PLAN_EXPIRED)
    assert "venció" in aviso["subject"]
    # Y dice lo que más preocupa: que no se borró nada.
    assert "No se borró nada" in aviso["text"]


def test_un_plan_vencido_hace_meses_no_avisa_de_nada(client, database, outbox):
    """Al subir esto, las cuentas viejas de prueba no reciben correos de algo
    de hace medio año."""
    browser = inside(client)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() - timedelta(days=200))

    browser.get("/panel")

    assert sent(database, mail_log.PLAN_EXPIRED) == []


def test_apagar_el_estado_del_plan_apaga_solo_eso(client, database, outbox):
    browser = inside(client)
    switch(database, "ana@ejemplo.com", accounts.PLAN_STATE, False)
    with_plan(database, "ana@ejemplo.com", "negocio",
              accounts.now() - timedelta(days=2))

    browser.get("/panel")

    assert sent(database, mail_log.PLAN_EXPIRED) == []


# ------------------------------------------- lo que decide un administrador

def test_habilitar_el_envio_se_avisa(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser = inside(client, "socia@ejemplo.com")
    cliente = accounts.by_email(database, "socia@ejemplo.com")

    clear_sending(admin, cliente)

    aviso = only(database, mail_log.SENDING_CLEARED)
    assert aviso["to"] == "socia@ejemplo.com"
    assert "habilitada" in aviso["text"]


def test_suspender_avisa_sin_decir_el_motivo(client, database, outbox):
    """El motivo se escribe para el registro y puede ser corto y duro."""
    admin, _ = make_admin(client, database)
    inside(client, "socia@ejemplo.com")
    cliente = accounts.by_email(database, "socia@ejemplo.com")

    update(admin, database, cliente, suspendida=True,
           motivo="lista comprada, rebotes al 40%")

    aviso = only(database, mail_log.SUSPENDED)
    assert aviso["to"] == "socia@ejemplo.com"
    assert "lista comprada" not in aviso["text"]
    assert "lista comprada" not in aviso["html"]
    assert "escríbenos" in aviso["text"]


def test_levantar_la_suspension_tambien_se_avisa(client, database, outbox):
    admin, _ = make_admin(client, database)
    inside(client, "socia@ejemplo.com")
    cliente = accounts.by_email(database, "socia@ejemplo.com")

    update(admin, database, cliente, suspendida=True, motivo="revisando algo")
    update(admin, database, cliente, suspendida=False, motivo="ya está claro")

    assert len(sent(database, mail_log.SUSPENDED)) == 1
    aviso = only(database, mail_log.REINSTATED)
    assert "seguir donde estabas" in aviso["text"]


def test_el_plan_puesto_a_mano_avisa_igual(client, database, outbox):
    """Quien pagó por Yappy recibe lo mismo que quien pagó por PayPal."""
    admin, _ = make_admin(client, database)
    inside(client, "socia@ejemplo.com")
    cliente = accounts.by_email(database, "socia@ejemplo.com")

    update(admin, database, cliente, plan="negocio", motivo="pagó por Yappy")

    aviso = only(database, mail_log.PLAN_PAID)
    assert "Negocio" in aviso["subject"]
    assert plans.PLANS["negocio"]["name"] == "Negocio"


# ------------------------------------------------------------- la regla 8

def test_ninguno_lleva_baja_ni_marca_de_agua(client, database, outbox,
                                             monkeypatch):
    """Son transaccionales: la baja y la marca son para campañas de clientes."""
    pedido = fake_paypal(monkeypatch)
    an_admin(client, database)
    browser = inside(client)
    confirm(database)
    pay(browser, pedido)
    with_plan(database, "ana@ejemplo.com", "basico",
              accounts.now() - timedelta(days=1))
    browser.get("/panel")

    mirados = 0
    for purpose in (mail_log.PLAN_PAID, mail_log.PLAN_EXPIRED,
                    mail_log.ADMIN_PAYMENT):
        for one in sent(database, purpose):
            mirados += 1
            assert "Anular la suscripción" not in one["html"]
            assert "Enviado con" not in one["html"]
    assert mirados >= 3
