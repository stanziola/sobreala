"""La cuenta nueva nace cerrada y se abre con la demostración o con el pago.

Lo que se fija aquí es la puerta. Que una cuenta que nadie revisó no guarde
nada, porque cualquiera puede registrarse y las imágenes viven en la base. Que la
demostración se pida contando a qué se dedica el negocio y para qué usará
Sobreala (el teléfono y la identificación ya vienen del registro). Y que pagar
abra la cuenta con todo y sin esperar a nadie, porque la habilitación antes del
primer envío se quitó.
"""

from __future__ import annotations

import io

from conftest import login, register
from test_admin import make_admin, open_account
from test_payments import come_back, confirm, fake_paypal

from config import Config
from models import account as accounts
from models import admin_event as decisions
from models import mail_log
from services import sender

CLIENTA = "socia@ejemplo.com"
# Las cuatro pantallas de cliente, el remitente y la descarga de Estadísticas.
AREAS = ("/dashboard", "/contacts", "/templates", "/campaigns",
         "/campaigns/sender", "/dashboard/export.csv")


def other(client):
    return client.application.test_client()


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def cerrada(client, database, email=CLIENTA, *, confirmada=True):
    """Una cuenta recién creada, con sesión abierta, sin demostración ni pago."""
    register(other(client), email=email, abierta=False)
    browser = other(client)
    login(browser, email=email)
    if confirmada:
        confirm(database, email)
    return browser, accounts.by_email(database, email)


NEGOCIO = "Una cooperativa de ahorro y crédito en Santiago."
PARA_QUE = "Avisos de asambleas y estados de cuenta a los socios."


def pedir(browser, *, business=NEGOCIO, purpose=PARA_QUE):
    """Pedir la demostración como lo hace la bienvenida."""
    return browser.post("/welcome/demo", data={
        "csrf_token": csrf(browser, "/welcome"), "business": business,
        "purpose": purpose})


def avisos(database, purpose):
    return list(database.mail_log.find({"purpose": purpose}))


# ------------------------------------------------------------------ cerrada

def test_cerrada_no_entra_a_ninguna_pantalla_de_cliente(client, database, outbox):
    browser, _ = cerrada(client, database)

    for url in AREAS:
        respuesta = browser.get(url)
        assert respuesta.status_code == 302, url
        assert "/welcome?para=" in respuesta.headers["Location"], url

    # Lo que sí: su bienvenida, su Configuración y contratar.
    assert "Pedir la demostración" in browser.get("/welcome").get_data(as_text=True)
    assert browser.get("/settings").status_code == 200
    assert browser.get("/checkout/basico").status_code == 200


def test_cerrada_no_guarda_nada_aunque_escriba_el_formulario(client, database,
                                                             outbox):
    """La puerta está en la ruta: la fila del menú no es un permiso."""
    browser, cuenta = cerrada(client, database)

    respuesta = browser.post("/contacts/import", data={
        "csrf_token": csrf(browser, "/settings"), "source": "members", "note": "",
        "archivo": (io.BytesIO(b"correo\nana@coop.com\n"), "lista.csv")},
        content_type="multipart/form-data")

    assert respuesta.headers["Location"].endswith("/welcome?para=contacts")
    assert database.contacts.count_documents({"account_id": cuenta["_id"]}) == 0


def test_el_menu_ensena_las_cuatro_filas_y_cada_una_lleva_a_la_demo(
        client, database, outbox, monkeypatch):
    """Cerrada, el menú es el de siempre: las cuatro filas de cliente, y cada
    una aterriza en la bienvenida diciendo a cuál quería entrar. La migaja es
    la de cualquiera sin plan, así que el menú del sitio también las enseña."""
    monkeypatch.setattr(Config, "PUBLIC_SITE_URL", "http://localhost")
    browser, _ = cerrada(client, database)

    pantalla = browser.get("/welcome").get_data(as_text=True)

    for fila in (">Estadísticas<", ">Enviar correos<", ">Contactos<",
                 ">Plantillas<"):
        assert fila in pantalla, fila
    assert ">Tu demostración<" not in pantalla
    assert browser.get_cookie("sa_in").value == "1"

    for url, seccion in (("/dashboard", "Estadísticas"),
                         ("/campaigns", "Enviar correos"),
                         ("/contacts", "Contactos"), ("/templates", "Plantillas")):
        destino = browser.get(url).headers["Location"]
        bienvenida = browser.get(destino).get_data(as_text=True)
        assert (f"Para entrar a {seccion}, contrata un plan o pide la "
                "demostración.") in bienvenida, url
        assert "Pedir la demostración" in bienvenida, url

    # Sin `para`, o con uno que no existe, no dice nada de más.
    for url in ("/welcome", "/welcome?para=otra"):
        assert "Para entrar a" not in browser.get(url).get_data(as_text=True)


def test_configuracion_avisa_en_amarillo_mientras_falte_verificar(client, database,
                                                                   outbox):
    """Mientras falte verificar la identificación o la dirección, Cuenta lo dice
    y lleva a sus documentos. Abrir la cuenta no lo quita: lo quita verificar
    las dos (octubre de 2026; antes se verificaban en la demostración)."""
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)

    cerrada_ = browser.get("/settings").get_data(as_text=True)
    assert "notice--pending" in cerrada_
    assert "Pendiente de verificación:" in cerrada_
    assert 'href="#verificaciones"' in cerrada_
    assert "se verifican en la demostración" not in cerrada_

    open_account(admin, cuenta)
    assert "notice--pending" in browser.get("/settings").get_data(as_text=True)

    for kind in accounts.VERIFY_KINDS:
        accounts.set_verification(database, cuenta["_id"], kind, accounts.VERIFIED)
    verificada = browser.get("/settings").get_data(as_text=True)
    assert "notice--pending" not in verificada
    assert "Pendiente de verificación:" not in verificada


# ---------------------------------------------------------- pedir la demo

def test_pedir_la_demo_pregunta_a_que_se_dedica_y_para_que(client, database,
                                                          outbox):
    """Ya no pide el WhatsApp ni la identificación: vienen del registro."""
    make_admin(client, database)
    browser, cuenta = cerrada(client, database)

    pantalla = browser.get("/welcome").get_data(as_text=True)
    assert "¿A qué se dedica tu negocio?" in pantalla
    assert "¿Para qué usarás Sobreala?" in pantalla
    assert 'name="phone"' not in pantalla and 'name="tax_id"' not in pantalla
    # El texto de las dos formas de empezar y la lista de la demo se quitaron.
    assert "Hay dos formas de empezar" not in pantalla
    assert "En la demostración abrimos tu cuenta" not in pantalla
    assert "Desde ahí tienes lo del plan Básico" not in pantalla

    corta = pedir(browser, business="Tienda")
    assert "Cuéntanos un poco más" in corta.get_data(as_text=True)
    assert avisos(database, mail_log.ADMIN_DEMO) == []
    assert "demo_requested_at" not in accounts.by_id(database, cuenta["_id"])

    respuesta = pedir(browser)
    assert respuesta.headers["Location"].endswith("/welcome?demo=sent")

    despues = accounts.by_id(database, cuenta["_id"])
    assert despues["demo_requested_at"]
    assert despues["demo_business"] == NEGOCIO
    assert despues["demo_purpose"] == PARA_QUE
    # Pedirla no la abre: eso lo decide una persona.
    assert not accounts.is_open(despues)

    aviso, = avisos(database, mail_log.ADMIN_DEMO)
    assert aviso["to"] == "jefe@ejemplo.com"
    assert "+50760000000" in aviso["text"]
    assert "8-123-456" in aviso["text"]
    assert NEGOCIO in aviso["text"] and PARA_QUE in aviso["text"]

    pantalla = browser.get("/welcome?demo=sent").get_data(as_text=True)
    assert "Te escribimos al +50760000000" in pantalla


def test_sin_el_correo_confirmado_no_se_pide(client, database, outbox):
    browser, cuenta = cerrada(client, database, confirmada=False)

    respuesta = pedir(browser)

    assert "confirma primero tu correo" in respuesta.get_data(as_text=True)
    assert "demo_requested_at" not in accounts.by_id(database, cuenta["_id"])


def test_un_cuarto_aviso_en_el_dia_se_frena(client, database, outbox):
    """Se puede pedir otra vez, para corregir las respuestas, pero no tanto
    que sirva para llenarle el buzón a quien administra."""
    make_admin(client, database)
    browser, _ = cerrada(client, database)

    for _ in range(3):
        assert pedir(browser).status_code == 302
    cuarto = pedir(browser)

    assert "Ya nos avisaste varias veces hoy" in cuarto.get_data(as_text=True)
    assert len(avisos(database, mail_log.ADMIN_DEMO)) == 3


def test_que_acepta_como_telefono_y_como_identificacion():
    # El país del selector pone el prefijo; un «+» escrito manda.
    assert accounts.clean_phone("6000-0000", "PA") == "+50760000000"
    assert accounts.clean_phone("+507 6000-0000", "US") == "+50760000000"
    assert accounts.clean_phone("(305) 555-0101", "US") == "+13055550101"
    # El 0 de marcar dentro del país no va en el número internacional.
    assert accounts.clean_phone("07911 123456", "GB") == "+447911123456"
    assert accounts.clean_phone("seis mil", "PA") is None
    assert accounts.clean_phone("123", "PA") is None
    assert accounts.clean_phone("60000000", "XX") is None
    # Los de la empresa: los vacíos no cuentan, y uno malo se dice.
    assert accounts.clean_phones(["6000-0001", "", "6000-0002"], ["PA", "PA", "PA"]) == (
        ["+50760000001", "+50760000002"], False)
    assert accounts.clean_phones(["abc"], ["PA"]) == ([], True)
    # De Panamá sin código, o de fuera con el suyo.
    assert accounts.whatsapp_url("60000000") == "https://wa.me/50760000000"
    assert accounts.whatsapp_url("+13055550101") == "https://wa.me/13055550101"
    # Varios formatos, porque hay varios: no se exige ninguno.
    for ruc in ("8-123-456", "155612345-2-2015 DV 12", "PE-12-345", "E-8-12345"):
        assert accounts.clean_tax_id(ruc) == ruc
    assert accounts.clean_tax_id("ninguno") is None
    assert accounts.clean_tax_id("8-1") is None


# ------------------------------------------------------- abrirla tú

def test_abrirla_pide_motivo_y_deja_todo_escrito(client, database, outbox,
                                                 monkeypatch):
    monkeypatch.setattr(Config, "PUBLIC_SITE_URL", "http://localhost")
    admin, jefe = make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    pedir(browser)

    sin_motivo = open_account(admin, cuenta, motivo="   ")
    assert "missing=reason" in sin_motivo.headers["Location"]
    assert not accounts.is_open(accounts.by_id(database, cuenta["_id"]))

    open_account(admin, cuenta, motivo="demo el martes, el RUC existe")
    # Pulsar dos veces no anota dos decisiones ni manda dos correos.
    open_account(admin, cuenta, motivo="otra vez")

    abierta = accounts.by_id(database, cuenta["_id"])
    assert abierta["opened_by"] == jefe["_id"]
    escrito = decisions.for_account(database, cuenta["_id"])
    assert [una["kind"] for una in escrito] == [decisions.OPEN]
    assert "el RUC existe" in escrito[0]["reason"]
    assert len(avisos(database, mail_log.OPENED)) == 1

    # Y entra a todo, con su menú de siempre.
    assert browser.get("/contacts").status_code == 200
    menu = browser.get("/dashboard").get_data(as_text=True)
    assert ">Contactos<" in menu
    assert browser.get_cookie("sa_in").value == "1"


def test_abierta_por_la_demo_tiene_lo_del_basico_y_no_envia(client, database,
                                                            outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    open_account(admin, cuenta)

    cuenta = accounts.by_id(database, cuenta["_id"])
    assert accounts.contact_limit(cuenta) == 1000
    assert "de 1000 contactos" in browser.get("/contacts").get_data(as_text=True)
    # Lo único que le falta es enviar, y eso pide un plan.
    assert "plan" in sender.blocked(cuenta)


def test_el_filtro_trae_a_quien_pidio_la_demo_y_sigue_cerrada(client, database,
                                                              outbox):
    """La cola es un filtro más de Cuentas, no una pantalla aparte."""
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    cola = "/admin/accounts?status=demo"

    assert CLIENTA not in admin.get(cola).get_data(as_text=True)
    pedir(browser)
    assert CLIENTA in admin.get(cola).get_data(as_text=True)
    open_account(admin, cuenta)
    assert CLIENTA not in admin.get(cola).get_data(as_text=True)


def test_la_ficha_ensena_su_telefono_su_identificacion_y_sus_respuestas(
        client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    pedir(browser)

    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "https://wa.me/50760000000" in ficha
    assert "8-123-456" in ficha
    assert NEGOCIO in ficha and PARA_QUE in ficha
    assert "Abrir la cuenta" in ficha

    open_account(admin, cuenta)
    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Abrir la cuenta" not in ficha
    assert "Abierta hace" in ficha


# ---------------------------------------------------------- o pagar

def test_pagar_pide_la_identificacion_si_falta_y_abre_la_cuenta_con_todo(
        client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser, cuenta = cerrada(client, database)

    # Desde octubre de 2026 viene del registro, así que al pagar ya sale escrita.
    assert 'value="8-123-456"' in browser.get("/checkout/basico").get_data(as_text=True)
    # Una cuenta de antes, que no la dejó, la escribe al pagar.
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$unset": {"tax_id": ""}})
    assert 'name="tax_id"' in browser.get("/checkout/basico").get_data(as_text=True)

    sin_ruc = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/basico"), "plan": "basico",
        "cycle": "monthly"})
    assert "error=tax_id" in sin_ruc.headers["Location"]
    assert database.payments.count_documents({}) == 0

    con_ruc = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/basico"), "plan": "basico",
        "cycle": "monthly", "tax_id": "8-123-456"})
    assert con_ruc.headers["Location"].startswith("https://sandbox.paypal.com/")
    come_back(browser)

    pagada = accounts.by_id(database, cuenta["_id"])
    assert pagada["tax_id"] == "8-123-456"
    assert accounts.is_open(pagada)
    # La abrió el pago, no una persona.
    assert pagada["opened_at"] and "opened_by" not in pagada
    assert browser.get("/contacts").status_code == 200
    # Y envía sin esperar a nadie: con su dirección y su remitente, sale.
    accounts.set_postal(database, cuenta["_id"], "Apartado 0816-00001, Santiago")
    accounts.set_handle(database, cuenta["_id"], "c" + str(cuenta["_id"])[-8:])
    assert sender.blocked(accounts.by_id(database, cuenta["_id"])) == []


def test_las_cuentas_de_antes_siguen_abiertas(client, database, outbox):
    """Las que ya habían pagado o se habían habilitado no tienen `opened_at`, y
    no hubo que migrarlas."""
    _, pagada = cerrada(client, database, "pagada@ejemplo.com")
    _, habilitada = cerrada(client, database, "habilitada@ejemplo.com")
    database.accounts.update_one({"_id": pagada["_id"]},
                                 {"$set": {"plan": "negocio"}})
    database.accounts.update_one({"_id": habilitada["_id"]},
                                 {"$set": {"sending_cleared_at": accounts.now()}})

    assert accounts.is_open(accounts.by_id(database, pagada["_id"]))
    assert accounts.is_open(accounts.by_id(database, habilitada["_id"]))
