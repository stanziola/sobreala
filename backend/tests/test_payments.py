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

from conftest import login, register

from models import account as accounts
from models import payment as payments
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


def approve(database, email="ana@ejemplo.com"):
    """Aprobar la cuenta, que es lo que la deja contratar."""
    cuenta = accounts.by_email(database, email)
    accounts.set_status(database, cuenta["_id"], accounts.APPROVED)
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
    return client.post("/configuracion/pagos/contratar", data={
        "csrf_token": csrf(client), "plan": plan, "cycle": cycle})


def come_back(client, order="ORDEN-1"):
    return client.get(f"/configuracion/pagos/volver?token={order}")


# ------------------------------------------------------------- quién puede

def test_una_cuenta_registrada_no_puede_contratar(client, database, outbox,
                                                  monkeypatch):
    """Registrada explora, aprobada compra. Lo comprueba la ruta, no la
    pantalla: un formulario se escribe a mano."""
    fake_paypal(monkeypatch)
    browser = inside(client)

    respuesta = buy(browser)

    assert "error=estado" in respuesta.headers["Location"]
    assert database.payments.count_documents({}) == 0
    assert accounts.by_email(database, "ana@ejemplo.com")["status"] == accounts.REGISTERED


def test_una_cuenta_aprobada_llega_a_paypal(client, database, outbox, monkeypatch):
    pedido = fake_paypal(monkeypatch)
    browser = inside(client)
    approve(database)

    respuesta = buy(browser)

    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    assert database.payments.count_documents({"status": payments.CREATED}) == 1
    assert pedido["amount"] == plans.amount("basico", "monthly")


def test_corporativo_no_se_compra_por_la_web(client, database, outbox, monkeypatch):
    """docs/pricing.md dice que va sin precio público: comprarlo aquí pondría
    un precio donde el documento dice que no hay ninguno."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    approve(database)

    respuesta = buy(browser, plan="corporativo")

    assert "error=plan" in respuesta.headers["Location"]
    assert database.payments.count_documents({}) == 0


def test_un_plan_inventado_no_crea_nada(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    approve(database)

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
        approve(database, f"{plan}{cycle}@ejemplo.com")

        buy(browser, plan=plan, cycle=cycle)
        assert pedido["amount"] == plans.amount(plan, cycle)
        assert pedido["currency"] == plans.CURRENCY


# --------------------------------------------------- lo que decide es PayPal

def test_si_paypal_no_confirma_no_se_activa_nada(client, database, outbox,
                                                 monkeypatch):
    fake_paypal(monkeypatch, status="PAYER_ACTION_REQUIRED")
    browser = inside(client)
    approve(database)
    buy(browser)

    respuesta = come_back(browser)

    assert "error=cobro" in respuesta.headers["Location"]
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta["status"] == accounts.APPROVED
    assert cuenta.get("plan") is None
    assert database.payments.count_documents({"status": payments.FAILED}) == 1


def test_si_el_monto_no_cuadra_no_se_activa_nada(client, database, outbox,
                                                 monkeypatch):
    """Cobró algo distinto de lo que vale el plan. Queda escrito y no se
    activa: es lo que hace falta para poder reclamarlo."""
    fake_paypal(monkeypatch, amount="1.00")
    browser = inside(client)
    approve(database)
    buy(browser)

    respuesta = come_back(browser)

    assert "error=monto" in respuesta.headers["Location"]
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta.get("plan") is None
    anotado = database.payments.find_one({"status": payments.FAILED})
    assert "1.00" in anotado["error"]


def test_una_orden_de_otra_cuenta_no_encuentra_nada(client, database, outbox,
                                                    monkeypatch):
    fake_paypal(monkeypatch)
    una = inside(client)
    approve(database)
    buy(una)

    ajena = inside(other(client), email="otra@ejemplo.com")
    respuesta = come_back(ajena)

    assert "error=orden" in respuesta.headers["Location"]
    assert accounts.by_email(database, "otra@ejemplo.com").get("plan") is None


# ------------------------------------------------------------- el pago bueno

def test_pagar_deja_la_cuenta_activa_con_su_plan(client, database, outbox,
                                                 monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    approve(database)
    buy(browser)

    respuesta = come_back(browser)
    assert "hecho=1" in respuesta.headers["Location"]

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta["status"] == accounts.ACTIVE
    assert cuenta["plan"] == "basico"
    assert cuenta["plan_until"] is not None
    # Y con eso, el tope de contactos deja de ser el de una cuenta sin plan.
    assert accounts.contact_limit(cuenta) == 1000
    assert "de 1000 contactos" in browser.get("/contactos").get_data(as_text=True)


def test_volver_dos_veces_no_alarga_el_periodo(client, database, outbox,
                                               monkeypatch):
    """Recargar la página de vuelta entra otra vez por aquí."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    approve(database)
    buy(browser)
    come_back(browser)

    vencia = accounts.by_email(database, "ana@ejemplo.com")["plan_until"]
    respuesta = come_back(browser)

    assert "hecho=1" in respuesta.headers["Location"]
    assert accounts.by_email(database, "ana@ejemplo.com")["plan_until"] == vencia
    assert database.payments.count_documents({"status": payments.COMPLETED}) == 1


def test_renovar_el_mismo_plan_suma_al_final(client, database, outbox,
                                             monkeypatch):
    """Pagar antes de tiempo no tira los días que quedaban."""
    fake_paypal(monkeypatch)
    browser = inside(client)
    approve(database)
    buy(browser)
    come_back(browser)
    primero = accounts.by_email(database, "ana@ejemplo.com")["plan_until"]

    # Una segunda compra, con su propia orden.
    monkeypatch.setattr(paypal, "create",
                        lambda **k: ("ORDEN-2", "https://sandbox.paypal.com/x"))
    buy(browser)
    come_back(browser, order="ORDEN-2")

    segundo = accounts.by_email(database, "ana@ejemplo.com")["plan_until"]
    assert segundo > primero


# ------------------------------------------------------------- la pantalla

def test_sin_credenciales_la_pantalla_se_dibuja_y_no_deja_contratar(
        client, database, outbox, monkeypatch):
    monkeypatch.setattr(paypal, "configured", lambda: False)
    browser = inside(client)
    approve(database)

    pantalla = browser.get("/configuracion/pagos").get_data(as_text=True)
    assert "Básico" in pantalla
    assert "todavía no está disponible" in pantalla

    assert "error=paypal" in buy(browser).headers["Location"]
    assert database.payments.count_documents({}) == 0


def test_una_cuenta_registrada_ve_por_que_no_puede(client, database, outbox,
                                                   monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)

    pantalla = browser.get("/configuracion/pagos").get_data(as_text=True)
    assert "Básico" in pantalla
    assert "Todavía no puedes contratar" in pantalla
    assert "/configuracion/pagos/contratar" not in pantalla
