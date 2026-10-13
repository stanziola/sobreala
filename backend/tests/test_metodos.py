"""Facturación solo enseña lo guardado, y PayPal se guarda entrando una vez.

PayPal se sustituye entero (`fake_vault`): es lo único que no se puede llamar
desde una prueba. Lo que fijan estas pruebas es lo que sale mal con el dinero de
alguien: que la vuelta solo valga con **la petición que se le hizo a esa cuenta**,
que quitar no borre aquí lo que PayPal no quitó, que pagar con la cuenta guardada
**compare el monto** como cualquier otro cobro.
"""

from __future__ import annotations

from test_payments import confirm, csrf, inside

from models import account as accounts
from services import paypal, plans

EMAIL = "ana@ejemplo.com"


def fake_vault(monkeypatch, *, charged=None, fail_delete=False):
    """PayPal de mentira con cuentas guardadas. Guarda lo que se le pidió."""
    state: dict = {"setups": [], "deleted": [], "paid": [], "charged": charged}

    def create_setup_token(**kwargs):
        state["setups"].append(kwargs)
        return "SETUP-1", "https://sandbox.paypal.com/agreements/approve?ba_token=SETUP-1"

    def pay_saved(**kwargs):
        state["paid"].append(kwargs)
        found = state["charged"] or {"amount": kwargs["amount"], "currency": "USD"}
        return "ORDEN-1", {"status": "COMPLETED", "amount": found["amount"],
                           "currency": found["currency"], "payer": "ana@paypal.com"}

    def delete_payment_token(token_id):
        if fail_delete:
            raise paypal.PayPalError("paypal 500")
        state["deleted"].append(token_id)

    monkeypatch.setattr(paypal, "configured", lambda: True)
    monkeypatch.setattr(paypal, "create_setup_token", create_setup_token)
    monkeypatch.setattr(paypal, "save_payment_token",
                        lambda setup_id: {"id": "VAULT-1", "payer": "ana@paypal.com"})
    monkeypatch.setattr(paypal, "delete_payment_token", delete_payment_token)
    monkeypatch.setattr(paypal, "pay_saved", pay_saved)
    return state


def abierta(client, database, monkeypatch, **kwargs):
    state = fake_vault(monkeypatch, **kwargs)
    browser = inside(client)
    confirm(database, EMAIL)
    return browser, accounts.by_email(database, EMAIL), state


def agregar(browser):
    return browser.post("/settings/billing/paypal", data={"csrf_token": csrf(browser)})


def volver(browser, setup="SETUP-1"):
    return browser.get(f"/settings/billing/paypal/return?approval_token_id={setup}")


def guardar(browser):
    agregar(browser)
    return volver(browser)


def test_sin_nada_guardado_dice_que_no_hay_y_ofrece_agregar(client, database,
                                                            monkeypatch):
    browser, _, _ = abierta(client, database, monkeypatch)

    pantalla = browser.get("/settings/billing").get_data(as_text=True)

    assert "Agregar PayPal" in pantalla
    # Solo lo guardado: lo disponible y lo que viene no se enseñan.
    for sobra in ("Yappy", "Próximamente", "Disponible", "Tarjeta de crédito"):
        assert sobra not in pantalla


def test_agregar_manda_a_paypal_y_la_vuelta_la_guarda(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)

    respuesta = agregar(browser)

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    assert state["setups"][0]["reference"] == str(cuenta["_id"])
    # Sin plan y sin cobro: solo anotó la petición.
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.paypal_vault_of(despues) is None
    assert despues["paypal_setup"]["id"] == "SETUP-1"
    assert database.payments.count_documents({}) == 0

    vuelta = volver(browser)

    assert "paypal=saved" in vuelta.headers["Location"]
    guardada = accounts.paypal_vault_of(accounts.by_id(database, cuenta["_id"]))
    assert guardada["id"] == "VAULT-1" and guardada["payer"] == "ana@paypal.com"
    pantalla = browser.get("/settings/billing?paypal=saved").get_data(as_text=True)
    assert "ana@paypal.com" in pantalla and "Eliminar" in pantalla
    # Lo guardado se reconoce por su logo.
    guardado = pantalla.split('alt="PayPal"')[1]
    assert "ana@paypal.com" in guardado.split("Eliminar")[0]
    assert "Agregar PayPal" not in pantalla
    assert "Listo, guardamos tu cuenta de PayPal" in pantalla
    # De PayPal no se guarda nada más que el identificador y el correo.
    assert "paypal_setup" not in accounts.by_id(database, cuenta["_id"])


def test_la_vuelta_solo_vale_con_la_peticion_de_esa_cuenta(client, database,
                                                           monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch)

    # Sin haber pedido nada, o con otra petición: no se guarda.
    assert "error=cancelled" in volver(browser).headers["Location"]
    agregar(browser)
    assert "error=cancelled" in volver(browser, "OTRA").headers["Location"]
    assert "error=cancelled" in volver(browser, "").headers["Location"]
    assert accounts.paypal_vault_of(accounts.by_id(database, cuenta["_id"])) is None


def test_si_paypal_falla_al_guardar_no_queda_nada(client, database, monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch)
    agregar(browser)

    def roto(setup_id):
        raise paypal.PayPalError("paypal 500")

    monkeypatch.setattr(paypal, "save_payment_token", roto)
    assert "error=paypal" in volver(browser).headers["Location"]
    assert accounts.paypal_vault_of(accounts.by_id(database, cuenta["_id"])) is None


def test_eliminar_la_quita_en_paypal_y_aqui(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)

    respuesta = browser.post("/settings/billing/paypal/remove",
                             data={"csrf_token": csrf(browser)})

    assert "paypal=removed" in respuesta.headers["Location"]
    assert state["deleted"] == ["VAULT-1"]
    assert accounts.paypal_vault_of(accounts.by_id(database, cuenta["_id"])) is None
    pantalla = browser.get("/settings/billing").get_data(as_text=True)
    assert "Agregar PayPal" in pantalla and "ana@paypal.com" not in pantalla


def test_si_paypal_no_la_quita_aqui_tampoco(client, database, monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch, fail_delete=True)
    guardar(browser)

    respuesta = browser.post("/settings/billing/paypal/remove",
                             data={"csrf_token": csrf(browser)})

    assert "error=paypal" in respuesta.headers["Location"]
    assert accounts.paypal_vault_of(accounts.by_id(database, cuenta["_id"]))


def test_sin_testigo_no_se_agrega_ni_se_quita(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)

    browser.post("/settings/billing/paypal", data={})
    assert state["setups"] == []

    guardar(browser)
    browser.post("/settings/billing/paypal/remove", data={})
    assert state["deleted"] == []
    assert accounts.paypal_vault_of(accounts.by_id(database, cuenta["_id"]))


def test_el_checkout_cobra_con_la_cuenta_guardada_y_activa(client, database,
                                                           monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)

    pantalla = browser.get("/checkout/negocio").get_data(as_text=True)
    # La cuenta guardada sale debajo del logo de PayPal, sin frase aparte, y
    # cada método es solo su botón de radio.
    paypal_fila = pantalla.split('alt="PayPal"')[1].split('name="metodo"')[0]
    assert "ana@paypal.com" in paypal_fila
    assert "Se cobra con tu PayPal guardado" not in pantalla
    assert "Usar este" not in pantalla

    respuesta = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/negocio"), "plan": "negocio",
        "cycle": "monthly", "metodo": "paypal"})

    # Sin mandar a PayPal: va directo al recibo.
    assert "/settings/billing/receipt/" in respuesta.headers["Location"]
    pagada = state["paid"][0]
    assert pagada["vault_id"] == "VAULT-1"
    assert pagada["amount"] == plans.amount("negocio", "monthly")
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.plan_of(despues) == "negocio" and accounts.is_open(despues)
    assert database.payments.count_documents({"status": "completed"}) == 1


def test_un_monto_distinto_con_la_cuenta_guardada_no_activa_nada(client, database,
                                                                 monkeypatch):
    browser, cuenta, _ = abierta(
        client, database, monkeypatch,
        charged={"amount": "1.00", "currency": "USD"})
    guardar(browser)

    respuesta = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/negocio"), "plan": "negocio",
        "cycle": "monthly", "metodo": "paypal"})

    assert "error=amount" in respuesta.headers["Location"]
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_si_paypal_rechaza_el_cobro_guardado_no_se_activa(client, database,
                                                          monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch)
    guardar(browser)

    def roto(**kwargs):
        raise paypal.PayPalError("paypal 422")

    monkeypatch.setattr(paypal, "pay_saved", roto)
    respuesta = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/negocio"), "plan": "negocio",
        "cycle": "monthly", "metodo": "paypal"})

    assert "error=paypal" in respuesta.headers["Location"]
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None
    assert database.payments.count_documents({"status": "failed"}) == 1
