"""Cobrar con Visa y Mastercard por Paguélofácil.

Lo que se fija aquí: que sin credenciales la tarjeta dice «pronto» y no abre
nada; que con ellas se crea el intento y se manda al enlace de pago; y, sobre
todo, que lo que trae el navegador de vuelta no decide nada: se consulta la
operación, y solo una aprobada, capturada, por el monto del plan y de ese mismo
intento activa el plan, una sola vez aunque lleguen la vuelta y el aviso.
"""

from __future__ import annotations

from config import Config
from models import account as accounts
from models import payment as payments
from services import paguelofacil, plans
from test_payments import confirm, csrf, fake_paypal, inside

SECRETO = "secreto-de-prueba"


def fake_card(monkeypatch, *, status=1, operation="AUTH_CAPTURE", amount=None,
              description=None, last4="4242"):
    """Paguélofácil de mentira. Guarda lo que se le pidió y qué se consultó."""
    asked: dict = {"found": []}

    def create_link(**kwargs):
        asked.update(kwargs)
        return "LK-PRUEBA", "https://checkout.paguelofacil.com?code=LK-PRUEBA"

    def find(oper):
        asked["found"].append(oper)
        return {"oper": oper, "status": status, "operation": operation,
                "amount": asked.get("amount", "") if amount is None else amount,
                "description": (f"Panamails · {asked.get('reference', '')}"
                                if description is None else description),
                "last4": last4, "email": "ana@banco.com"}

    monkeypatch.setattr(paguelofacil, "configured", lambda: True)
    monkeypatch.setattr(paguelofacil, "create_link", create_link)
    monkeypatch.setattr(paguelofacil, "find", find)
    return asked


def pay_card(browser, plan="basico", cycle="monthly"):
    return browser.post("/configuracion/pagos/contratar", data={
        "csrf_token": csrf(browser), "plan": plan, "cycle": cycle, "metodo": "card"})


def back_from_card(browser, attempt, oper="OPER-1", **extra):
    query = {"PARM_1": str(attempt), "Oper": oper, "Estado": "Aprobada", **extra}
    return browser.get("/configuracion/pagos/tarjeta/volver", query_string=query)


def ready_to_pay(client, database):
    browser = inside(client)
    confirm(database)
    return browser, accounts.by_email(database, "ana@ejemplo.com")


# ------------------------------------------------------------ sin credenciales

def test_sin_credenciales_la_tarjeta_dice_pronto(client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser, _ = ready_to_pay(client, database)
    pantalla = browser.get("/contratar/basico").get_data(as_text=True)
    assert 'value="card"' not in pantalla
    assert "Pronto" in pantalla

    # Escrito a mano, se lee como PayPal: la tarjeta no abre nada.
    respuesta = pay_card(browser)
    assert respuesta.headers["Location"].startswith("https://sandbox.paypal.com/")
    assert database.payments.find_one({})["method"] == payments.PAYPAL


# ------------------------------------------------------------ con credenciales

def test_con_tarjeta_va_al_enlace_de_pago(client, database, outbox, monkeypatch):
    pedido = fake_card(monkeypatch)
    browser, _ = ready_to_pay(client, database)
    assert 'value="card"' in browser.get("/contratar/basico").get_data(as_text=True)

    respuesta = pay_card(browser)

    assert respuesta.headers["Location"] == "https://checkout.paguelofacil.com?code=LK-PRUEBA"
    intento = database.payments.find_one({})
    assert intento["method"] == payments.CARD
    assert intento["provider"] == "paguelofacil"
    assert intento["link_code"] == "LK-PRUEBA"
    assert pedido["amount"] == plans.amount("basico", "monthly")
    assert pedido["reference"] == str(intento["_id"])
    assert pedido["return_url"].endswith("/configuracion/pagos/tarjeta/volver")


def test_solo_con_tarjeta_y_sin_paypal_se_puede_pagar(client, database, outbox,
                                                      monkeypatch):
    fake_card(monkeypatch)
    monkeypatch.setattr("services.paypal.configured", lambda: False)
    browser, _ = ready_to_pay(client, database)
    pantalla = browser.get("/contratar/basico").get_data(as_text=True)
    assert "El pago en línea todavía no está disponible" not in pantalla
    # PayPal escrito a mano cae en lo que hay: no se abre nada de PayPal.
    respuesta = browser.post("/configuracion/pagos/contratar", data={
        "csrf_token": csrf(browser), "plan": "basico", "cycle": "monthly",
        "metodo": "paypal"})
    assert "error=paypal" in respuesta.headers["Location"]


def test_aprobada_y_consultada_activa_el_plan(client, database, outbox, monkeypatch):
    pedido = fake_card(monkeypatch)
    browser, cuenta = ready_to_pay(client, database)
    pay_card(browser)
    intento = database.payments.find_one({})

    respuesta = back_from_card(browser, intento["_id"])

    assert "hecho=1" in respuesta.headers["Location"]
    assert pedido["found"] == ["OPER-1"]
    pagado = database.payments.find_one({})
    assert pagado["status"] == payments.COMPLETED
    assert pagado["card_last4"] == "4242" and pagado["order_id"] == "OPER-1"
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) == "basico"
    lista = browser.get("/configuracion/pagos").get_data(as_text=True)
    assert "terminada en 4242" in lista


def test_lo_que_dice_el_navegador_no_decide(client, database, outbox, monkeypatch):
    """Vuelve con «Estado=Aprobada», pero Paguélofácil dice que se denegó."""
    fake_card(monkeypatch, status=0)
    browser, cuenta = ready_to_pay(client, database)
    pay_card(browser)
    intento = database.payments.find_one({})

    respuesta = back_from_card(browser, intento["_id"], TotalPagado="15.00")

    assert "error=cobro" in respuesta.headers["Location"]
    assert database.payments.find_one({})["status"] == payments.FAILED
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_una_autorizacion_sin_capturar_no_es_un_pago(client, database, outbox,
                                                     monkeypatch):
    fake_card(monkeypatch, operation="AUTH")
    browser, cuenta = ready_to_pay(client, database)
    pay_card(browser)
    back_from_card(browser, database.payments.find_one({})["_id"])
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_el_monto_que_no_cuadra_no_activa(client, database, outbox, monkeypatch):
    fake_card(monkeypatch, amount="1.00")
    browser, cuenta = ready_to_pay(client, database)
    pay_card(browser)
    respuesta = back_from_card(browser, database.payments.find_one({})["_id"])
    assert "error=monto" in respuesta.headers["Location"]
    fallido = database.payments.find_one({})
    assert fallido["status"] == payments.FAILED and "monto" in fallido["error"]
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_una_operacion_de_otro_intento_no_sirve(client, database, outbox, monkeypatch):
    fake_card(monkeypatch, description="Panamails · 0123456789abcdef01234567")
    browser, cuenta = ready_to_pay(client, database)
    pay_card(browser)
    respuesta = back_from_card(browser, database.payments.find_one({})["_id"])
    assert "error=orden" in respuesta.headers["Location"]
    assert accounts.plan_of(accounts.by_id(database, cuenta["_id"])) is None


def test_el_intento_de_otra_cuenta_no_se_toca(client, database, outbox, monkeypatch):
    fake_card(monkeypatch)
    ana, _ = ready_to_pay(client, database)
    pay_card(ana)
    suyo = database.payments.find_one({})

    bea = inside(client, "bea@ejemplo.com")
    respuesta = back_from_card(bea, suyo["_id"])
    assert "error=orden" in respuesta.headers["Location"]
    assert database.payments.find_one({})["status"] == payments.CREATED


# ------------------------------------------------------------ el aviso

def test_la_vuelta_y_el_aviso_dan_un_solo_periodo(client, database, outbox,
                                                  monkeypatch):
    fake_card(monkeypatch)
    monkeypatch.setattr(Config, "PAGUELOFACIL_WEBHOOK_SECRET", SECRETO)
    browser, cuenta = ready_to_pay(client, database)
    pay_card(browser)
    intento = database.payments.find_one({})

    # Paga y cierra el navegador: llega primero el aviso.
    aviso = client.post(f"/webhooks/paguelofacil/{SECRETO}", json={
        "codOper": "OPER-1", "status": 1, "operationType": "AUTH_CAPTURE",
        "totalPay": "15.00", "description": f"Panamails Básico · {intento['_id']}"})
    assert aviso.status_code == 200
    hasta = accounts.plan_until(accounts.by_id(database, cuenta["_id"]))
    assert hasta is not None

    # Y después vuelve: no se alarga nada.
    respuesta = back_from_card(browser, intento["_id"])
    assert "hecho=1" in respuesta.headers["Location"]
    assert accounts.plan_until(accounts.by_id(database, cuenta["_id"])) == hasta
    assert database.payments.count_documents({"status": payments.COMPLETED}) == 1


def test_el_aviso_con_otro_secreto_no_existe(client, database, outbox, monkeypatch):
    monkeypatch.setattr(Config, "PAGUELOFACIL_WEBHOOK_SECRET", SECRETO)
    assert client.post("/webhooks/paguelofacil/otro", json={}).status_code == 404
    monkeypatch.setattr(Config, "PAGUELOFACIL_WEBHOOK_SECRET", "")
    assert client.post(f"/webhooks/paguelofacil/{SECRETO}", json={}).status_code == 404


def test_un_aviso_que_no_se_entiende_se_contesta_200(client, database, outbox,
                                                     monkeypatch):
    fake_card(monkeypatch)
    monkeypatch.setattr(Config, "PAGUELOFACIL_WEBHOOK_SECRET", SECRETO)
    assert client.post(f"/webhooks/paguelofacil/{SECRETO}",
                       data="no es nada").status_code == 200


# ------------------------------------------------------------ los precios

def test_los_precios_nuevos():
    assert plans.amount("basico", "monthly") == "15.00"
    assert plans.amount("negocio", "monthly") == "25.00"
    assert plans.amount("empresa", "monthly") == "55.00"
    assert plans.amount("empresa", "yearly") == "528.00"


def test_la_cabecera_deja_ir_a_pagar_con_tarjeta(client, database, outbox):
    browser = inside(client)
    regla = next(p for p in browser.get("/configuracion/pagos")
                 .headers["Content-Security-Policy"].split(";")
                 if p.strip().startswith("form-action"))
    for sitio in Config.paguelofacil_checkout():
        assert sitio in regla
    # Sin comodines: cada sitio por su nombre.
    assert "*" not in regla


def test_el_enlace_a_un_sitio_desconocido_no_se_sigue(monkeypatch):
    """Si la respuesta mandara a otra página, no se manda a nadie a pagar ahí."""
    import io
    import json as _json

    monkeypatch.setattr(Config, "PAGUELOFACIL_CCLW", "CCLW")
    monkeypatch.setattr(Config, "PAGUELOFACIL_TOKEN", "TOKEN")

    def respuesta(request, timeout=0):
        cuerpo = _json.dumps({"success": True, "data": {
            "url": "https://otro-sitio.com/pagar", "code": "LK-X"}}).encode()
        return io.BytesIO(cuerpo)

    monkeypatch.setattr("urllib.request.urlopen", respuesta)
    try:
        paguelofacil.create_link(amount="15.00", description="Panamails",
                                 reference="abc", return_url="https://panel/volver")
    except paguelofacil.PagueloFacilError:
        pass
    else:
        raise AssertionError("mandó a un sitio que no conoce")
