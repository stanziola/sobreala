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


def pedir(browser, *, business=NEGOCIO, purpose=PARA_QUE, contacts="500_2k",
          source="customers", website="", token_from="/welcome", source_other=""):
    """Pedir la demostración como lo hace la bienvenida."""
    return browser.post("/welcome/demo", data={
        "csrf_token": csrf(browser, token_from), "business": business,
        "purpose": purpose, "contacts": contacts, "source": source,
        "source_other": source_other, "website": website})


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
        "csrf_token": csrf(browser, "/settings"), "source": "members", "attest": "1", "note": "",
        "archivo": (io.BytesIO(b"correo\nana@coop.com\n"), "lista.csv")},
        content_type="multipart/form-data")

    assert respuesta.headers["Location"].endswith("/welcome?para=contacts")
    assert database.contacts.count_documents({"account_id": cuenta["_id"]}) == 0


def test_el_menu_ensena_las_cuatro_filas_y_cada_una_lleva_a_la_demo(
        client, database, outbox, monkeypatch):
    """Cerrada, el menú es el de siempre: la fila del Dashboard (hasta octubre
    de 2026, las cuatro filas de cliente), y cada pantalla de su árbol aterriza
    en la bienvenida, que ya no dice a cuál quería entrar (se
    quitó en octubre de 2026: la bienvenida ofrece las dos formas de abrirla).
    La migaja es la de cualquiera sin plan, así que el menú del sitio también
    las enseña."""
    monkeypatch.setattr(Config, "PUBLIC_SITE_URL", "http://localhost")
    browser, _ = cerrada(client, database)

    pantalla = browser.get("/welcome").get_data(as_text=True)

    assert ">Dashboard</span>" in pantalla
    assert ">Tu demostración<" not in pantalla
    assert browser.get_cookie("sa_in").value == "1:::closed"

    for url, seccion in (("/dashboard", "Estadísticas"),
                         ("/campaigns", "Enviar correos"),
                         ("/contacts", "Contactos"), ("/templates", "Plantillas")):
        destino = browser.get(url).headers["Location"]
        bienvenida = browser.get(destino).get_data(as_text=True)
        assert f"Para entrar a {seccion}" not in bienvenida, url
        assert "Pedir la demostración" in bienvenida, url

    for url in ("/welcome", "/welcome?para=otra"):
        assert "Para entrar a" not in browser.get(url).get_data(as_text=True)


def test_configuracion_avisa_en_amarillo_mientras_falte_enviar_documentos(
        client, database, outbox):
    """Mientras falte enviar un documento, Cuenta lo dice y lleva al formulario.
    Abrir la cuenta no lo quita: lo quita enviarlos (octubre de 2026; antes se
    verificaban en la demostración)."""
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)

    cerrada_ = browser.get("/settings").get_data(as_text=True)
    assert "notice--pending" in cerrada_
    assert "Pendiente de verificación:" in cerrada_
    assert 'href="/verification"' in cerrada_
    assert "se verifican en la demostración" not in cerrada_

    open_account(admin, cuenta)
    assert "notice--pending" in browser.get("/settings").get_data(as_text=True)

    for kind in accounts.VERIFY_KINDS:
        accounts.set_verification(database, cuenta["_id"], kind, accounts.REVIEW)
    enviados = browser.get("/settings").get_data(as_text=True)
    assert "notice--pending" not in enviados
    assert "Pendiente de verificación:" not in enviados


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
    assert "Identificación personal" not in pantalla
    # El texto de las dos formas de empezar y la lista de la demo se quitaron.
    assert "Hay dos formas de empezar" not in pantalla
    assert "En la demostración abrimos tu cuenta" not in pantalla
    assert "Desde ahí tienes lo del plan Básico" not in pantalla

    corta = pedir(browser, business="Tienda")
    assert "Cuéntanos un poco más" in corta.get_data(as_text=True)
    assert avisos(database, mail_log.ADMIN_DEMO) == []
    assert "demo_requested_at" not in accounts.by_id(database, cuenta["_id"])

    respuesta = pedir(browser, website="minegocio.com")
    assert respuesta.headers["Location"].endswith("/welcome")

    despues = accounts.by_id(database, cuenta["_id"])
    assert despues["demo_requested_at"]
    assert despues["demo_business"] == NEGOCIO
    assert despues["demo_purpose"] == PARA_QUE
    assert despues["demo_contacts"] == "500_2k"
    assert despues["demo_source"] == "customers"
    assert despues["demo_website"] == "https://minegocio.com"
    # Pedirla no la abre: eso lo decide una persona.
    assert not accounts.is_open(despues)

    aviso, = avisos(database, mail_log.ADMIN_DEMO)
    assert aviso["to"] == "jefe@ejemplo.com"
    assert "+50760000000" in aviso["text"]
    assert "Identificación" not in aviso["text"]
    assert NEGOCIO in aviso["text"] and PARA_QUE in aviso["text"]
    assert "De 500 a 2,000" in aviso["text"]
    assert "Son mis clientes o socios" in aviso["text"]
    assert "https://minegocio.com" in aviso["text"]

    pantalla = browser.get("/welcome").get_data(as_text=True)
    assert "Tu solicitud ha sido recibida" in pantalla
    # Y qué pasa ahora (octubre de 2026): se revisa pronto, y la confirmación
    # llega al correo de la cuenta. El teléfono no.
    assert "La revisamos pronto" in pantalla and cuenta["email"] in pantalla
    assert "Te escribimos al" not in pantalla


def test_sin_el_correo_confirmado_no_se_pide(client, database, outbox):
    browser, cuenta = cerrada(client, database, confirmada=False)

    respuesta = pedir(browser)

    assert "confirma primero tu correo" in respuesta.get_data(as_text=True)
    assert "demo_requested_at" not in accounts.by_id(database, cuenta["_id"])


def test_la_demo_se_pide_una_sola_vez(client, database, outbox):
    """Con la solicitud hecha el formulario ya no sale: queda el aviso verde, y
    un segundo envío no guarda nada ni vuelve a avisar a quien administra."""
    make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    assert 'name="business"' in browser.get("/welcome").get_data(as_text=True)
    assert "notice--done" not in browser.get("/welcome").get_data(as_text=True)

    assert pedir(browser).status_code == 302
    pantalla = browser.get("/welcome").get_data(as_text=True)
    assert "notice--done" in pantalla
    assert "Tu solicitud ha sido recibida" in pantalla
    assert "Espera la aprobación" not in pantalla
    assert "Para entrar a" not in pantalla
    assert 'name="business"' not in pantalla
    assert "Avisar de nuevo" not in pantalla

    otra = pedir(browser, business="Otra cosa distinta del negocio.",
                 token_from="/settings")
    assert otra.status_code == 302
    assert otra.headers["Location"].endswith("/welcome")
    assert accounts.by_id(database, cuenta["_id"])["demo_business"] == NEGOCIO
    assert len(avisos(database, mail_log.ADMIN_DEMO)) == 1


def test_los_datos_nuevos_de_la_demo_se_piden_y_se_revisan(client, database, outbox):
    make_admin(client, database)
    browser, cuenta = cerrada(client, database)

    pantalla = browser.get("/welcome").get_data(as_text=True)
    assert "¿Cuántos contactos tienes?" in pantalla
    assert "¿Cómo conseguiste esos contactos?" in pantalla
    assert "Sitio web (opcional)" in pantalla

    sin_contactos = pedir(browser, contacts="")
    assert "Elige una opción" in sin_contactos.get_data(as_text=True)
    sin_origen = pedir(browser, source="inventado")
    assert "Elige una opción" in sin_origen.get_data(as_text=True)
    mal_sitio = pedir(browser, website="no es un sitio")
    assert "dirección válida" in mal_sitio.get_data(as_text=True)
    assert "demo_requested_at" not in accounts.by_id(database, cuenta["_id"])
    assert avisos(database, mail_log.ADMIN_DEMO) == []

    # El sitio es opcional: vacío no se guarda.
    assert pedir(browser).status_code == 302
    assert "demo_website" not in accounts.by_id(database, cuenta["_id"])


def test_que_acepta_como_sitio_web():
    assert accounts.clean_website("") == ""
    assert accounts.clean_website("  ") == ""
    assert accounts.clean_website("minegocio.com") == "https://minegocio.com"
    assert accounts.clean_website("http://x.org/a") == "http://x.org/a"
    assert accounts.clean_website("nada") is None
    assert accounts.clean_website("ftp://x.com") is None
    assert accounts.clean_website("a b.com") is None
    assert accounts.clean_website("x" * 200 + ".com") is None


def test_que_acepta_como_telefono():
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
        ["+50760000001", "+50760000002"], "")
    assert accounts.clean_phones(["abc"], ["PA"]) == ([], "error_phone")
    # De Panamá sin código, o de fuera con el suyo.
    assert accounts.whatsapp_url("60000000") == "https://wa.me/50760000000"
    assert accounts.whatsapp_url("+13055550101") == "https://wa.me/13055550101"


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
    assert browser.get_cookie("sa_in").value == "1:::demo"


def test_abierta_por_la_demo_tiene_lo_del_basico_y_envia_solo_a_prueba(client, database,
                                                                       outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    open_account(admin, cuenta)

    cuenta = accounts.by_id(database, cuenta["_id"])
    assert accounts.contact_limit(cuenta) == 1000
    assert "de 1000 contactos" in browser.get("/contacts").get_data(as_text=True)
    # Envía, pero solo a sus direcciones de prueba (octubre de 2026): sin una
    # confirmada no sale nada, y no se le pide un plan.
    assert accounts.in_demo(cuenta)
    assert sender.blocked(cuenta)[:1] == ["demo_addresses"]
    assert "plan" not in sender.blocked(cuenta)


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


def test_la_ficha_ensena_su_telefono_y_sus_respuestas(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    pedir(browser)

    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "https://wa.me/50760000000" in ficha
    # Una cuenta nueva no escribe su identificación: la ficha no la enseña.
    assert "Identificación personal</h3>" not in ficha.split("Verificaciones")[0]
    assert NEGOCIO in ficha and PARA_QUE in ficha
    assert "Abrir la cuenta" in ficha

    open_account(admin, cuenta)
    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Abrir la cuenta" not in ficha
    assert "Abierta hace" in ficha


# ---------------------------------------------------------- o pagar

def test_pagar_ya_no_pide_la_identificacion_y_abre_la_cuenta_con_todo(
        client, database, outbox, monkeypatch):
    fake_paypal(monkeypatch)
    browser, cuenta = cerrada(client, database)

    # Desde octubre de 2026 la identificación es solo el documento: el pago ya
    # no la pide, y pagar sin escribir nada funciona.
    assert 'name="tax_id"' not in browser.get("/checkout/basico").get_data(as_text=True)
    pago = browser.post("/settings/billing/checkout", data={
        "csrf_token": csrf(browser, "/checkout/basico"), "plan": "basico",
        "cycle": "monthly"})
    assert pago.headers["Location"].startswith("https://sandbox.paypal.com/")
    come_back(browser)

    pagada = accounts.by_id(database, cuenta["_id"])
    assert "tax_id" not in pagada
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


def test_la_migaja_dice_en_que_punto_esta_la_empresa(client, database, outbox,
                                                     monkeypatch):
    """Octubre de 2026: la portada cambia sus botones según esto. Cerrada,
    «Solicitar demo»; pedida, «Ver mi solicitud»; abierta por la demostración,
    solo «Ver planes»; con plan, «Ir al Dashboard». Un usuario de la empresa
    lleva el estado de su empresa."""
    from test_users import as_member

    monkeypatch.setattr(Config, "PUBLIC_SITE_URL", "http://localhost")
    browser, cuenta = cerrada(client, database)
    browser.get("/welcome")
    assert browser.get_cookie("sa_in").value == "1:::closed"

    pedir(browser)
    browser.get("/welcome")
    assert browser.get_cookie("sa_in").value == "1:::requested"

    jefe, _ = make_admin(client, database)
    open_account(jefe, cuenta)
    browser.get("/dashboard")
    assert browser.get_cookie("sa_in").value == "1:::demo"

    accounts.set_plan(database, cuenta["_id"], "negocio")
    browser.get("/dashboard")
    assert browser.get_cookie("sa_in").value == "1:negocio:monthly:paid"

    _, empresa, suyo = as_member(client, database, outbox=outbox)
    accounts.set_plan(database, empresa["_id"], "empresa")
    suyo.get("/contacts")
    assert suyo.get_cookie("sa_in").value == "1:empresa:monthly:paid"


def test_la_portada_trae_los_botones_de_cada_estado():
    """El sitio construido lleva lo que nav.js pone según la migaja: «Ver mi
    solicitud» y «Ir al Dashboard»; la demostración abierta no tiene principal
    y «Ver planes» hace de respaldo."""
    from pathlib import Path

    sitio = (Path(__file__).resolve().parents[2] / "landing" / "index.html").read_text(
        encoding="utf-8")
    portada = sitio.split('class="hero__actions"')[1].split("</div>")[0]
    assert 'data-label-requested="Ver mi solicitud"' in portada
    assert 'data-label-paid="Ir al Dashboard"' in portada
    assert 'data-href-paid="https://app.sobreala.com/dashboard"' in portada
    assert "data-label-demo" not in portada and "data-cta-backup" in portada
    # El del bloque del lienzo (octubre de 2026; antes, el del final de los
    # tutoriales): con la demostración ya se puede usar el lienzo.
    assert 'data-label-demo="Ir al lienzo"' in sitio


def test_otra_forma_dice_cual(client, database, outbox):
    """«Otra forma» abre su casilla (octubre de 2026): sin decir cuál no se pide,
    y lo que dice llega a la ficha y al correo de quien administra."""
    make_admin(client, database)
    browser, cuenta = cerrada(client, database)
    pantalla = browser.get("/welcome").get_data(as_text=True)
    assert 'name="source_other"' in pantalla and 'data-shown-value="other"' in pantalla

    sin_decir = pedir(browser, source="other", source_other="")
    assert "Cuéntanos cómo los conseguiste" in sin_decir.get_data(as_text=True)
    assert "demo_requested_at" not in accounts.by_id(database, cuenta["_id"])

    assert pedir(browser, source="other",
                 source_other="Los anotamos en la feria del libro").status_code == 302
    guardada = accounts.by_id(database, cuenta["_id"])
    assert guardada["demo_source_other"] == "Los anotamos en la feria del libro"
    aviso, = avisos(database, mail_log.ADMIN_DEMO)
    assert "Otra forma: Los anotamos en la feria del libro" in aviso["text"]


def test_con_otra_opcion_no_se_guarda_el_texto(client, database, outbox):
    browser, cuenta = cerrada(client, database)
    pedir(browser, source="customers", source_other="esto no va")
    assert "demo_source_other" not in accounts.by_id(database, cuenta["_id"])
