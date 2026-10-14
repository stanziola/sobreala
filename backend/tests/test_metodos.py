"""Facturación enseña lo guardado, PayPal se guarda entrando una vez, y se puede
guardar más de una cuenta.

PayPal se sustituye entero (`fake_vault`): es lo único que no se puede llamar
desde una prueba. Lo que fijan estas pruebas es lo que sale mal con el dinero de
alguien: que la vuelta solo valga con **la petición que se le hizo a esa cuenta**,
que quitar no borre aquí lo que PayPal no quitó, que solo se quite y se cobre
**una cuenta guardada de esa cuenta**, y que pagar con lo guardado **compare el
monto** como cualquier otro cobro.
"""

from __future__ import annotations

from test_payments import confirm, csrf, inside

from models import account as accounts
from services import paypal, plans

EMAIL = "ana@ejemplo.com"


def fake_vault(monkeypatch, *, charged=None, fail_delete=False):
    """PayPal de mentira con cuentas guardadas. Guarda lo que se le pidió, y la
    cuenta que guarda la próxima vuelta se cambia con `state["next"]`."""
    state: dict = {"setups": [], "deleted": [], "paid": [], "orders": [],
                   "charged": charged,
                   "next": {"id": "VAULT-1", "payer": "ana@paypal.com"}}

    def create_setup_token(**kwargs):
        state["setups"].append(kwargs)
        return "SETUP-1", "https://sandbox.paypal.com/agreements/approve?ba_token=SETUP-1"

    def pay_saved(**kwargs):
        state["paid"].append(kwargs)
        found = state["charged"] or {"amount": kwargs["amount"], "currency": "USD"}
        return "ORDEN-1", {"status": "COMPLETED", "amount": found["amount"],
                           "currency": found["currency"], "payer": "ana@paypal.com"}

    def create(**kwargs):
        state["orders"].append(kwargs)
        return "ORDEN-2", "https://sandbox.paypal.com/checkoutnow?token=ORDEN-2"

    def delete_payment_token(token_id):
        if fail_delete:
            raise paypal.PayPalError("paypal 500")
        state["deleted"].append(token_id)

    monkeypatch.setattr(paypal, "configured", lambda: True)
    monkeypatch.setattr(paypal, "create_setup_token", create_setup_token)
    monkeypatch.setattr(paypal, "save_payment_token",
                        lambda setup_id: dict(state["next"]))
    monkeypatch.setattr(paypal, "delete_payment_token", delete_payment_token)
    monkeypatch.setattr(paypal, "pay_saved", pay_saved)
    monkeypatch.setattr(paypal, "create", create)
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


def guardadas(database, cuenta):
    return accounts.paypal_vaults_of(accounts.by_id(database, cuenta["_id"]))


def quitar(browser, token):
    return browser.post("/settings/billing/paypal/remove",
                        data={"csrf_token": csrf(browser), "token": token})


def pagar(browser, metodo, plan="negocio"):
    return browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, f"/checkout/{plan}"), "plan": plan,
        "cycle": "monthly", "metodo": metodo})


# ------------------------------------------------------------- Facturación

def test_sin_nada_guardado_dice_que_no_hay_y_ofrece_agregar(client, database,
                                                            monkeypatch):
    browser, _, _ = abierta(client, database, monkeypatch)

    pantalla = browser.get("/settings/billing").get_data(as_text=True)

    assert "No tienes métodos de pago guardados" in pantalla
    assert "Agregar método de pago" in pantalla
    # Solo lo guardado: la lista para agregar no sale hasta que se pide.
    for sobra in ("Yappy", "Próximamente", "Disponible", "No disponible"):
        assert sobra not in pantalla


def test_agregar_abre_la_lista_con_tarjeta_y_yappy_no_disponibles(
        client, database, monkeypatch):
    browser, _, _ = abierta(client, database, monkeypatch)

    pantalla = browser.get("/settings/billing?agregar=1").get_data(as_text=True)
    lista = pantalla.split('class="method-picker"')[1]

    assert 'alt="PayPal"' in lista and 'action="/settings/billing/paypal"' in lista
    assert 'alt="Visa"' in lista and 'alt="Mastercard"' in lista
    assert 'alt="Yappy"' in lista
    # La tarjeta y Yappy no se pueden guardar todavía.
    assert lista.count("No disponible") == 2
    assert "Cancelar" in lista


def test_agregar_manda_a_paypal_y_la_vuelta_la_guarda(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)

    respuesta = agregar(browser)

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    assert state["setups"][0]["reference"] == str(cuenta["_id"])
    # Sin plan y sin cobro: solo anotó la petición.
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.paypal_vaults_of(despues) == []
    assert despues["paypal_setup"]["id"] == "SETUP-1"
    assert database.payments.count_documents({}) == 0

    vuelta = volver(browser)

    assert "paypal=saved" in vuelta.headers["Location"]
    guardada, = guardadas(database, cuenta)
    assert guardada["id"] == "VAULT-1" and guardada["payer"] == "ana@paypal.com"
    pantalla = browser.get("/settings/billing?paypal=saved").get_data(as_text=True)
    assert "Listo, guardamos tu cuenta de PayPal" in pantalla
    # El logo a la izquierda y la cuenta al lado, en la misma fila que Eliminar.
    fila = pantalla.split('class="setting__text saved-method"')[1].split("</form>")[0]
    assert 'alt="PayPal"' in fila and "ana@paypal.com" in fila and "Eliminar" in fila
    assert fila.index('alt="PayPal"') < fila.index("ana@paypal.com")
    # Con una guardada se puede agregar otra, y ya no dice que no hay.
    assert "Agregar método de pago" in pantalla
    assert "No tienes métodos de pago guardados" not in pantalla
    # De PayPal no se guarda nada más que el identificador y el correo.
    assert "paypal_setup" not in accounts.by_id(database, cuenta["_id"])


def test_con_una_guardada_se_agrega_otra(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)

    state["next"] = {"id": "VAULT-2", "payer": "luis@paypal.com"}
    assert agregar(browser).headers["Location"].startswith("https://sandbox.paypal.com/")
    assert "paypal=saved" in volver(browser).headers["Location"]

    assert [one["id"] for one in guardadas(database, cuenta)] == ["VAULT-1", "VAULT-2"]
    pantalla = browser.get("/settings/billing").get_data(as_text=True)
    assert "ana@paypal.com" in pantalla and "luis@paypal.com" in pantalla
    assert pantalla.count('class="setting__text saved-method"') == 2


def test_la_misma_cuenta_guardada_dos_veces_no_se_repite(client, database,
                                                         monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)

    state["next"] = {"id": "VAULT-1B", "payer": "Ana@PayPal.com"}
    guardar(browser)

    guardada, = guardadas(database, cuenta)
    assert guardada["id"] == "VAULT-1B"
    # La anterior se borra en PayPal.
    assert state["deleted"] == ["VAULT-1"]


def test_la_vuelta_solo_vale_con_la_peticion_de_esa_cuenta(client, database,
                                                           monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch)

    # Sin haber pedido nada, o con otra petición: no se guarda.
    assert "error=cancelled" in volver(browser).headers["Location"]
    agregar(browser)
    assert "error=cancelled" in volver(browser, "OTRA").headers["Location"]
    assert "error=cancelled" in volver(browser, "").headers["Location"]
    assert guardadas(database, cuenta) == []


def test_si_paypal_falla_al_guardar_no_queda_nada(client, database, monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch)
    agregar(browser)

    def roto(setup_id):
        raise paypal.PayPalError("paypal 500")

    monkeypatch.setattr(paypal, "save_payment_token", roto)
    assert "error=paypal" in volver(browser).headers["Location"]
    assert guardadas(database, cuenta) == []


def test_eliminar_una_la_quita_en_paypal_y_deja_la_otra(client, database,
                                                        monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)
    state["next"] = {"id": "VAULT-2", "payer": "luis@paypal.com"}
    guardar(browser)

    respuesta = quitar(browser, "VAULT-1")

    assert "paypal=removed" in respuesta.headers["Location"]
    assert state["deleted"] == ["VAULT-1"]
    assert [one["id"] for one in guardadas(database, cuenta)] == ["VAULT-2"]
    pantalla = browser.get("/settings/billing").get_data(as_text=True)
    assert "ana@paypal.com" not in pantalla and "luis@paypal.com" in pantalla


def test_no_se_quita_una_que_no_es_de_esta_cuenta(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)

    quitar(browser, "AJENA")
    quitar(browser, "")

    assert state["deleted"] == []
    assert len(guardadas(database, cuenta)) == 1


def test_si_paypal_no_la_quita_aqui_tampoco(client, database, monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch, fail_delete=True)
    guardar(browser)

    respuesta = quitar(browser, "VAULT-1")

    assert "error=paypal" in respuesta.headers["Location"]
    assert len(guardadas(database, cuenta)) == 1


def test_sin_testigo_no_se_agrega_ni_se_quita(client, database, monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)

    browser.post("/settings/billing/paypal", data={})
    assert state["setups"] == []

    guardar(browser)
    browser.post("/settings/billing/paypal/remove", data={"token": "VAULT-1"})
    assert state["deleted"] == []
    assert len(guardadas(database, cuenta)) == 1


def test_la_guardada_en_el_campo_de_antes_se_ve_y_se_quita(client, database,
                                                           monkeypatch):
    """Hubo una sola cuenta guardada, en `paypal_vault`. La que quedó escrita ahí
    se sigue viendo, se paga con ella y se quita."""
    browser, cuenta, state = abierta(client, database, monkeypatch)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"paypal_vault": {
        "id": "VIEJA", "payer": "vieja@paypal.com", "created_at": accounts.now()}}})

    assert "vieja@paypal.com" in browser.get("/settings/billing").get_data(as_text=True)
    assert 'value="saved:VIEJA"' in browser.get("/checkout/negocio").get_data(as_text=True)

    quitar(browser, "VIEJA")

    assert state["deleted"] == ["VIEJA"]
    despues = accounts.by_id(database, cuenta["_id"])
    assert "paypal_vault" not in despues and accounts.paypal_vaults_of(despues) == []


# ------------------------------------------------------------------ el pago

def test_el_pago_ofrece_primero_las_guardadas_y_cobra_la_elegida(client, database,
                                                                 monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)
    state["next"] = {"id": "VAULT-2", "payer": "luis@paypal.com"}
    guardar(browser)

    pantalla = browser.get("/checkout/negocio").get_data(as_text=True)
    arriba, desplegable = pantalla.split('<details class="pay-other">')
    # Las guardadas primero, cada una con su correo bajo el logo; la primera
    # marcada.
    assert 'value="saved:VAULT-1"\n                 checked' in arriba or \
        'value="saved:VAULT-1" checked' in " ".join(arriba.split())
    assert 'value="saved:VAULT-2"' in arriba
    assert "ana@paypal.com" in arriba and "luis@paypal.com" in arriba
    # Lo demás, en «Utilizar otra cuenta o método de pago», sin nada marcado.
    assert "Utilizar otra cuenta o método de pago" in desplegable
    otros = desplegable.split("</details>")[0]
    assert 'value="paypal"' in otros and "checked" not in otros
    assert "Usar este" not in pantalla

    respuesta = pagar(browser, "saved:VAULT-2")

    # Sin mandar a PayPal: va directo al recibo, con la cuenta elegida.
    assert "/settings/billing/receipt/" in respuesta.headers["Location"]
    pagada, = state["paid"]
    assert pagada["vault_id"] == "VAULT-2"
    assert pagada["amount"] == plans.amount("negocio", "monthly")
    despues = accounts.by_id(database, cuenta["_id"])
    assert accounts.plan_of(despues) == "negocio" and accounts.is_open(despues)
    assert database.payments.count_documents({"status": "completed"}) == 1


def test_una_guardada_que_no_es_de_esta_cuenta_no_cobra(client, database,
                                                        monkeypatch):
    browser, cuenta, state = abierta(client, database, monkeypatch)
    guardar(browser)

    respuesta = pagar(browser, "saved:AJENA")

    assert respuesta.headers["Location"].endswith("/checkout/negocio?cycle=monthly")
    assert state["paid"] == [] and state["orders"] == []
    assert database.payments.count_documents({}) == 0
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_otra_cuenta_manda_a_paypal_a_iniciar_sesion(client, database, monkeypatch):
    """Con cuentas guardadas, `paypal` es PayPal iniciando sesión, no una de las
    guardadas."""
    browser, _, state = abierta(client, database, monkeypatch)
    guardar(browser)

    respuesta = pagar(browser, "paypal")

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/checkoutnow")
    assert state["paid"] == [] and len(state["orders"]) == 1


def test_sin_guardadas_el_pago_es_el_de_siempre(client, database, monkeypatch):
    browser, _, _ = abierta(client, database, monkeypatch)

    pantalla = browser.get("/checkout/negocio").get_data(as_text=True)

    assert "pay-other" not in pantalla and "saved:" not in pantalla
    assert 'value="paypal"' in pantalla and "checked" in pantalla


def test_un_monto_distinto_con_la_cuenta_guardada_no_activa_nada(client, database,
                                                                 monkeypatch):
    browser, cuenta, _ = abierta(
        client, database, monkeypatch,
        charged={"amount": "1.00", "currency": "USD"})
    guardar(browser)

    respuesta = pagar(browser, "saved:VAULT-1")

    assert "error=amount" in respuesta.headers["Location"]
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_si_paypal_rechaza_el_cobro_guardado_no_se_activa(client, database,
                                                          monkeypatch):
    browser, cuenta, _ = abierta(client, database, monkeypatch)
    guardar(browser)

    def roto(**kwargs):
        raise paypal.PayPalError("paypal 422")

    monkeypatch.setattr(paypal, "pay_saved", roto)
    respuesta = pagar(browser, "saved:VAULT-1")

    assert "error=paypal" in respuesta.headers["Location"]
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None
    assert database.payments.count_documents({"status": "failed"}) == 1


# ------------------------------------------------------------- el historial

def test_el_historial_lleva_encabezados_vence_el_y_usd(client, database,
                                                       monkeypatch):
    browser, _, _ = abierta(client, database, monkeypatch)
    guardar(browser)
    pagar(browser, "saved:VAULT-1")

    pantalla = browser.get("/settings/billing").get_data(as_text=True)

    encabezado = pantalla.split("<thead>")[1].split("</thead>")[0]
    for columna in ("Fecha", "Plan", "Periodo", "Método", "Monto"):
        assert f">{columna}<" in encabezado, columna
    monto = plans.amount("negocio", "monthly")
    assert plans.money(monto) in pantalla
    assert f"USD {monto}" not in pantalla or plans.money(monto) == f"USD {monto}"
    assert "vence el" in pantalla and "hasta el" not in pantalla


def test_como_se_escribe_un_monto():
    assert plans.money("15.00") == "USD 15"
    assert plans.money("38.33") == "USD 38.33"
    assert plans.money("1026.00") == "USD 1,026"
    assert plans.money("0.5") == "USD 0.50"
    assert plans.money("25.00", "EUR") == "EUR 25"
