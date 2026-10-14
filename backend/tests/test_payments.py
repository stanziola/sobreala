"""Pagar un plan con PayPal.

Lo que fijan estas pruebas es la parte que, si sale mal, sale mal con el dinero
de alguien: que nadie active un plan sin haber pagado, que lo que decide sea la
respuesta de PayPal y no lo que traiga el navegador, y que recargar la página de
vuelta no regale otro periodo.

El cliente de PayPal se sustituye, que es lo único que no se puede llamar de
verdad desde una prueba. Todo lo demás —quién puede comprar, qué monto se pide,
qué se activa— es nuestro y se ejerce tal cual.
"""

from __future__ import annotations

import re

from conftest import login, register

from config import Config
from models import account as accounts
from models import payment as payments
from services import paypal, plans


def fuera_de_la_bandeja(html: str) -> str:
    """La página sin la bandeja de agregar un método de pago: va escondida en
    un `<dialog>` y solo se ve al pedirla (octubre de 2026)."""
    return re.sub(r"<dialog.*?</dialog>", "", html, flags=re.S)

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def csrf(client, url="/settings/billing"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def confirm(database, email="ana@ejemplo.com"):
    """Confirmar el correo, que es lo único que hace falta para contratar.

    Antes hacía falta además que un administrador aprobara la cuenta a mano.
    Se quitó: esperar a que alguien te apruebe para poder pagar no protegía
    nada, y la revisión que sí importa se hace antes del primer envío.
    """
    cuenta = accounts.by_email(database, email)
    database.accounts.update_one(
        {"_id": cuenta["_id"]},
        {"$set": {"email_confirmed_at": cuenta["created_at"]}})
    return accounts.by_id(database, cuenta["_id"])


def fake_paypal(monkeypatch, *, status="COMPLETED", amount=None, currency="USD"):
    """PayPal de mentira. Guarda lo que se le pidió cobrar."""
    asked: dict = {}

    def create(**kwargs):
        asked.update(kwargs)
        return "ORDEN-1", "https://sandbox.paypal.com/checkoutnow?token=ORDEN-1"

    def capture(order_id):
        asked["captured"] = order_id
        return {"status": status,
                "amount": asked["amount"] if amount is None else amount,
                "currency": currency}

    monkeypatch.setattr(paypal, "configured", lambda: True)
    monkeypatch.setattr(paypal, "create", create)
    monkeypatch.setattr(paypal, "capture", capture)
    return asked


def buy(client, plan="basico", cycle="monthly"):
    return client.post("/settings/billing/checkout", data={
        "csrf_token": csrf(client), "plan": plan, "cycle": cycle})


def come_back(client, order="ORDEN-1"):
    return client.get(f"/settings/billing/return?token={order}")


# ------------------------------------------------------------- quién puede

def test_una_cuenta_registrada_no_puede_contratar(client, database, outbox,
                                                  monkeypatch):
    """Registrada explora, aprobada compra. Lo comprueba la ruta, no la
    pantalla: un formulario se escribe a mano."""
    fake_paypal(monkeypatch)
    browser = inside(client)

    respuesta = buy(browser)

    assert "error=status" in respuesta.headers["Location"]
    assert database.payments.count_documents({}) == 0
    assert accounts.by_email(database, "ana@ejemplo.com")["status"] == accounts.REGISTERED


def test_una_cuenta_aprobada_llega_a_paypal(client, database, outbox, monkeypatch):
    pedido = fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    respuesta = buy(browser)

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    assert database.payments.count_documents({"status": payments.CREATED}) == 1
    assert pedido["amount"] == plans.amount("basico", "monthly")


def test_un_plan_que_ya_no_existe_no_se_compra(client, database, outbox, monkeypatch):
    """Corporativo se quitó de docs/pricing.md: quien tenga el enlace viejo no
    puede comprarlo."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    respuesta = buy(browser, plan="corporativo")

    assert "error=plan" in respuesta.headers["Location"]
    assert database.payments.count_documents({}) == 0


def test_un_plan_inventado_no_crea_nada(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    assert "error=plan" in buy(browser, plan="infinito").headers["Location"]
    assert "error=plan" in buy(browser, cycle="semanal").headers["Location"]
    assert database.payments.count_documents({}) == 0


# ------------------------------------------------------------- el monto

def test_el_monto_es_el_que_dice_el_documento(client, database, outbox, monkeypatch):
    """Los precios no se copian al backend: salen de docs/pricing.md."""
    for plan, cycle in (("basico", "monthly"), ("basico", "yearly"),
                        ("negocio", "monthly"), ("empresa", "yearly")):
        pedido = fake_paypal(monkeypatch)
        browser = inside(client, email=f"{plan}{cycle}@ejemplo.com")
        confirm(database, f"{plan}{cycle}@ejemplo.com")

        buy(browser, plan=plan, cycle=cycle)
        assert pedido["amount"] == plans.amount(plan, cycle)
        assert pedido["currency"] == plans.CURRENCY


# --------------------------------------------------- lo que decide es PayPal

def test_si_paypal_no_confirma_no_se_activa_nada(client, database, outbox,
                                                 monkeypatch):
    fake_paypal(monkeypatch, status="PAYER_ACTION_REQUIRED")
    browser = inside(client)
    confirm(database)
    buy(browser)

    respuesta = come_back(browser)

    assert "error=capture" in respuesta.headers["Location"]
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta["status"] == accounts.REGISTERED
    assert cuenta.get("plan") is None
    assert database.payments.count_documents({"status": payments.FAILED}) == 1


def test_si_el_monto_no_cuadra_no_se_activa_nada(client, database, outbox,
                                                 monkeypatch):
    """Cobró algo distinto de lo que vale el plan. Queda escrito y no se
    activa: es lo que hace falta para poder reclamarlo."""
    fake_paypal(monkeypatch, amount="1.00")
    browser = inside(client)
    confirm(database)
    buy(browser)

    respuesta = come_back(browser)

    assert "error=amount" in respuesta.headers["Location"]
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta.get("plan") is None
    anotado = database.payments.find_one({"status": payments.FAILED})
    assert "1.00" in anotado["error"]


def test_una_orden_de_otra_cuenta_no_encuentra_nada(client, database, outbox,
                                                    monkeypatch):
    fake_paypal(monkeypatch)
    una = inside(client)
    confirm(database)
    buy(una)

    ajena = inside(other(client), email="otra@ejemplo.com")
    respuesta = come_back(ajena)

    assert "error=order" in respuesta.headers["Location"]
    assert accounts.by_email(database, "otra@ejemplo.com").get("plan") is None


# ------------------------------------------------------------- el pago bueno

def test_pagar_deja_la_cuenta_activa_con_su_plan(client, database, outbox,
                                                 monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser)

    respuesta = come_back(browser)
    assert "/settings/billing/receipt/" in respuesta.headers["Location"]

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta["status"] == accounts.ACTIVE
    assert cuenta["plan"] == "basico"
    assert cuenta["plan_until"] is not None
    # Y el tope de contactos es el de su plan.
    assert accounts.contact_limit(cuenta) == 1000
    assert "de 1000 contactos" in browser.get("/contacts").get_data(as_text=True)


def test_volver_dos_veces_no_alarga_el_periodo(client, database, outbox,
                                               monkeypatch):
    """Recargar la página de vuelta entra otra vez por aquí."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser)
    come_back(browser)

    vencia = accounts.by_email(database, "ana@ejemplo.com")["plan_until"]
    respuesta = come_back(browser)

    assert "/settings/billing/receipt/" in respuesta.headers["Location"]
    assert accounts.by_email(database, "ana@ejemplo.com")["plan_until"] == vencia
    assert database.payments.count_documents({"status": payments.COMPLETED}) == 1


def test_el_mismo_plan_se_vuelve_a_comprar_cuando_vence(client, database, outbox,
                                                        monkeypatch):
    """Vigente no se paga otra vez; vencido sí, y cuenta desde hoy."""
    from datetime import timedelta

    fake_paypal(monkeypatch)
    browser = inside(client)
    cuenta = confirm(database)
    buy(browser)
    come_back(browser)

    # Vigente: el mismo mes no se paga otra vez (la pantalla ofrece pasarlo a
    # anual, que sí es mejorar) y la ruta no crea otro pago.
    pantalla = browser.get("/checkout/basico").get_data(as_text=True)
    assert 'name="cycle" value="monthly"' not in pantalla
    assert 'name="cycle" value="yearly"' in pantalla
    assert buy(browser).headers["Location"].endswith("/checkout/basico")
    assert database.payments.count_documents({"account_id": cuenta["_id"]}) == 1

    # Vencido: se compra como la primera vez.
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {
        "plan_until": accounts.now() - timedelta(days=1)}})
    monkeypatch.setattr(paypal, "create",
                        lambda **k: ("ORDEN-2", "https://sandbox.paypal.com/x"))
    assert buy(browser).headers["Location"].startswith("https://sandbox.paypal.com/")
    come_back(browser, order="ORDEN-2")
    nuevo = accounts.by_email(database, "ana@ejemplo.com")["plan_until"]
    assert nuevo > accounts.now() + timedelta(days=25)


# ------------------------------------------------------------- la pantalla

def test_sin_credenciales_la_pantalla_se_dibuja_y_no_deja_contratar(
        client, database, outbox, monkeypatch):
    monkeypatch.setattr(paypal, "configured", lambda: False)
    browser = inside(client)
    confirm(database)

    pantalla = browser.get("/checkout/basico").get_data(as_text=True)
    assert "Básico" in pantalla
    assert "todavía no está disponible" in pantalla

    assert "error=paypal" in buy(browser).headers["Location"]
    assert database.payments.count_documents({}) == 0


def test_sin_el_correo_confirmado_no_se_contrata(client, database, outbox,
                                                 monkeypatch):
    """La única puerta que queda, y se dice cuál es para poder abrirla."""
    fake_paypal(monkeypatch)
    browser = inside(client)

    pantalla = browser.get("/checkout/basico").get_data(as_text=True)
    assert "Básico" in pantalla
    assert "confirma primero tu correo" in pantalla
    assert "/settings/billing/checkout" not in pantalla

    assert "error=status" in buy(browser).headers["Location"]
    assert database.payments.count_documents({}) == 0


def test_recien_confirmada_ya_puede_contratar(client, database, outbox,
                                              monkeypatch):
    """Nadie la aprueba: confirma su correo y llega hasta PayPal."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    cuenta = confirm(database)
    assert cuenta["status"] == accounts.REGISTERED

    respuesta = buy(browser)
    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")


def test_una_cuenta_suspendida_no_contrata(client, database, outbox,
                                           monkeypatch):
    """Suspender cierra su sesión, así que el testigo se toma antes."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    cuenta = confirm(database)
    token = csrf(browser)
    accounts.set_status(database, cuenta["_id"], accounts.SUSPENDED)

    browser.post("/settings/billing/checkout", data={
        "csrf_token": token, "plan": "basico", "cycle": "monthly"})

    assert database.payments.count_documents({}) == 0
    assert accounts.can_buy(accounts.by_id(database, cuenta["_id"])) is False


# ------------------------------- la cabecera que dejaba el botón sin hacer nada

def test_la_cabecera_permite_ir_a_pagar(client, database, outbox):
    """`form-action` gobierna también la redirección que sigue al envío.

    Con solo 'self', el navegador se negaba a seguir hasta PayPal: el servidor
    creaba la orden, respondía 302, y desde fuera parecía que el botón no hacía
    nada. Es el fallo que se reprodujo en Chrome antes de arreglarlo.
    """
    from config import Config

    cabecera = client.get("/login").headers["Content-Security-Policy"]
    regla = next(p.strip() for p in cabecera.split(";")
                 if p.strip().startswith("form-action"))

    assert Config.paypal_checkout() in regla
    assert "'self'" in regla
    # Y sigue sin permitir cualquier otro destino.
    assert "*" not in regla
    assert "https://ejemplo.com" not in regla


def test_el_destino_de_pago_sale_del_entorno(monkeypatch):
    """En producción no se permite el de pruebas, ni al revés."""
    from config import Config

    monkeypatch.setattr(Config, "PAYPAL_ENV", "live")
    assert Config.paypal_checkout() == "https://www.paypal.com"
    monkeypatch.setattr(Config, "PAYPAL_ENV", "sandbox")
    assert Config.paypal_checkout() == "https://www.sandbox.paypal.com"


def test_en_produccion_sandbox_solo_si_esta_escrito(monkeypatch, capsys):
    """Con llaves puestas fuera de desarrollo: live arranca, sandbox escrito a
    propósito arranca y lo dice en el registro, y sin la variable no arranca,
    para que el lanzamiento no se quede en sandbox por olvido."""
    import pytest

    for name, value in (("ENV", "production"), ("SECRET_KEY", "una-clave"),
                        ("APP_BASE_URL", "https://app.sobreala.com"),
                        ("MAIL_BACKEND", "file"), ("PAGUELOFACIL_CCLW", ""),
                        ("PAYPAL_CLIENT_ID", "llave-de-prueba")):
        monkeypatch.setattr(Config, name, value)

    monkeypatch.setattr(Config, "PAYPAL_ENV", "live")
    monkeypatch.setattr(Config, "PAYPAL_ENV_SET", True)
    Config.check()
    assert "en sandbox" not in capsys.readouterr().out

    monkeypatch.setattr(Config, "PAYPAL_ENV", "sandbox")
    Config.check()
    assert "en sandbox: los cobros son de prueba" in capsys.readouterr().out

    monkeypatch.setattr(Config, "PAYPAL_ENV_SET", False)
    with pytest.raises(RuntimeError, match="PAYPAL_ENV no esta escrito"):
        Config.check()


# ------------------------------------------ la pantalla de contratar un plan

def test_sin_sesion_contratar_manda_a_entrar_con_su_plan(client, database):
    respuesta = client.get("/checkout/basico")

    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]
    assert "plan=basico" in respuesta.headers["Location"]


def test_al_entrar_sigue_hasta_el_plan_que_iba_a_comprar(client, database,
                                                         outbox, monkeypatch):
    fake_paypal(monkeypatch)
    register(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    database.accounts.update_one(
        {"_id": cuenta["_id"]},
        {"$set": {"email_confirmed_at": cuenta["created_at"]}})

    navegador = other(client)
    navegador.get("/login?plan=negocio")      # lo anota al dibujar la pantalla
    respuesta = login(navegador)

    assert respuesta.headers["Location"].endswith("/checkout/negocio")
    # Y se gasta: volver a entrar aterriza donde siempre.
    otra = other(client)
    otra.get("/login")
    assert login(otra).headers["Location"] == Config.PUBLIC_SITE_URL


def test_un_plan_inventado_en_la_direccion_no_se_recuerda(client, database,
                                                          outbox):
    register(client)
    navegador = other(client)
    navegador.get("/login?plan=infinito")

    assert login(navegador).headers["Location"] == Config.PUBLIC_SITE_URL


def test_contratar_ensena_el_plan_y_sus_dos_ciclos(client, database, outbox,
                                                   monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    pantalla = browser.get("/checkout/basico").get_data(as_text=True)
    assert "Obtener Plan Básico" in pantalla
    # El resumen del ciclo que se eligió, con su total y un solo botón de pagar,
    # y el otro ciclo a un enlace.
    assert "Total a pagar ahora" in pantalla
    assert f"Pagar ${plans.amount('basico', 'monthly')}" in pantalla
    assert f"Prefiero pagar un año: ${plans.amount('basico', 'yearly')}" in pantalla
    assert pantalla.count('action="/settings/billing/checkout"') == 1
    assert pantalla.count('name="cycle"') == 1


def test_contratar_ensena_con_que_se_puede_pagar_y_con_que_todavia_no(
        client, database, outbox, monkeypatch):
    """Los que faltan se enseñan igual: esconderlos haría que quien no tiene
    PayPal cerrara la página creyendo que no puede pagar de ninguna forma."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    pantalla = browser.get("/checkout/basico").get_data(as_text=True)

    assert 'value="paypal"' in pantalla
    # Cada método son sus logos: la tarjeta, Visa y Mastercard.
    assert 'alt="Visa"' in pantalla and 'alt="Mastercard"' in pantalla
    assert 'alt="Yappy"' in pantalla
    # Y los que no cobran no son un control que se pueda mandar.
    assert 'value="card"' not in pantalla
    assert 'value="yappy"' not in pantalla
    assert pantalla.count("Pronto") == 2


def test_el_metodo_queda_escrito_en_el_intento(client, database, outbox,
                                               monkeypatch):
    pedido = fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser), "plan": "basico", "cycle": "monthly",
        "metodo": "paypal"})

    intento = database.payments.find_one({})
    assert intento["method"] == "paypal"
    assert pedido


def test_un_metodo_que_todavia_no_cobra_no_abre_ninguna_puerta(
        client, database, outbox, monkeypatch):
    """El formulario se puede escribir a mano. Lo que no cobra hoy se lee como
    PayPal en vez de crear un intento de algo que no existe."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser), "plan": "basico", "cycle": "monthly",
        "metodo": "yappy"})

    intento = database.payments.find_one({})
    assert intento["method"] == "paypal"


def test_un_plan_que_no_existe_no_tiene_pantalla_de_contratar(client, database, outbox,
                                                               monkeypatch):
    """Ni uno que se quitó ni uno inventado."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    for plan in ("corporativo", "inventado"):
        respuesta = browser.get(f"/checkout/{plan}")
        assert respuesta.status_code == 302
        assert "error=plan" in respuesta.headers["Location"]
    assert database.payments.count_documents({}) == 0


def test_opciones_de_pago_ya_no_vende(client, database, outbox, monkeypatch):
    """Los planes se eligen en el sitio; esta pantalla dice cómo te cobramos."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser)
    come_back(browser)

    # Los métodos (sin la bandeja de agregar) y lo cobrado, que desde octubre de
    # 2026 son dos subsecciones de Facturación.
    pantalla = fuera_de_la_bandeja(
        browser.get("/settings/billing/methods").get_data(as_text=True)
        + browser.get("/settings/billing/history").get_data(as_text=True))
    assert "/settings/billing/checkout" not in pantalla
    # Y sí sigue diciendo qué tienes y qué se te ha cobrado.
    assert "PayPal" in pantalla
    # Los métodos son solo los guardados: Yappy no se guarda, no sale.
    assert "Yappy" not in pantalla and "Próximamente" not in pantalla
    assert "Facturación" in pantalla


def test_tus_pagos_solo_ensena_lo_que_se_cobro(client, database, outbox,
                                               monkeypatch):
    from models import invoice as invoices

    # Las facturas están escondidas por ahora; esto prueba cómo se ven el día
    # que se enciendan.
    monkeypatch.setattr(invoices, "SHOWN", True)
    """Un intento a medias se quedaría ahí para siempre al lado del pago bueno,
    pareciendo que se debe algo cuando no se debe nada. Escrito sigue, que es
    lo que permite reconciliarlo."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser)
    come_back(browser)
    # Y otro que se queda a medias: se crea la orden y nadie vuelve de PayPal.
    buy(browser, plan="negocio")

    pantalla = browser.get("/settings/billing/history").get_data(as_text=True)

    # Una fila por pago cobrado, esperando su factura; el intento a medias no.
    assert pantalla.count("Factura en camino") == 1
    assert "Sin terminar" not in pantalla
    # Los dos intentos siguen escritos, que es de lo que vive la reconciliación.
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert len(payments.for_account(database, cuenta["_id"])) == 2


# ------------------------------------------- bajar de plan no se hace por la web

def test_con_un_plan_no_se_baja_a_uno_menor(client, database, outbox,
                                            monkeypatch):
    """Lo que ya se pagó no se devuelve, así que quitarle sitio a una cuenta a
    cambio de nada tiene que pasar por una conversación."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    cuenta = confirm(database)
    accounts.set_plan(database, cuenta["_id"], "empresa")

    pantalla = browser.get("/checkout/basico").get_data(as_text=True)
    assert "Ya tienes un plan mayor" in pantalla
    assert 'action="/settings/billing/checkout"' not in pantalla

    # Y el servidor lo comprueba, no solo la pantalla.
    respuesta = buy(browser, plan="basico")
    assert respuesta.headers["Location"].endswith("/checkout/basico")
    assert database.payments.count_documents({}) == 0


def test_el_plan_vigente_no_se_renueva_antes_de_tiempo(client, database, outbox,
                                                        monkeypatch):
    """Comprar el que ya se tiene no se deja: se vuelve a comprar al vencer."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    cuenta = confirm(database)
    accounts.set_plan(database, cuenta["_id"], "negocio")

    pantalla = browser.get("/checkout/negocio").get_data(as_text=True)
    assert 'name="cycle" value="monthly"' not in pantalla
    assert buy(browser, plan="negocio").headers["Location"].endswith("/checkout/negocio")

    # Con un anual, ni siquiera el paso a anual: ya lo tiene.
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan_cycle": "yearly"}})
    pantalla = browser.get("/checkout/negocio?cycle=anual").get_data(as_text=True)
    assert "Cuando venza lo vuelves a contratar" in pantalla
    assert 'action="/settings/billing/checkout"' not in pantalla


def test_subir_de_plan_sigue_pudiendo(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    cuenta = confirm(database)
    accounts.set_plan(database, cuenta["_id"], "basico")

    assert buy(browser, plan="empresa").headers["Location"].startswith(
        "https://sandbox.paypal.com/")


def test_la_escalera_sale_del_documento_de_precios():
    """Sin copiar aquí una lista de nombres que un día lo contradiga."""
    from services import plans

    assert [plans.rank(k) for k in plans.PLANS] == [0, 1, 2]
    assert plans.rank(None) == -1 and plans.rank("inventado") == -1
    assert plans.is_downgrade("negocio", "basico") is True
    assert plans.is_downgrade("negocio", "negocio") is False
    assert plans.is_downgrade("negocio", "empresa") is False
    # Sin plan no se baja de ningún sitio.
    assert plans.is_downgrade(None, "basico") is False
