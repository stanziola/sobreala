"""Cambiar el correo de una cuenta que ya está confirmada.

Corregirlo antes de confirmar es otra pantalla y otra prueba. Esta fija lo de
después, que es lo que puede costar una cuenta: que haga falta la contraseña,
que haga falta un código en la dirección **nueva** —un error de dedo dejaría la
cuenta apuntando al buzón de nadie, y aquí eso significa perderla— y que la
dirección **vieja** se entere, porque ese aviso es lo único que le queda al
dueño si quien lo hizo no era él.
"""

from __future__ import annotations

from conftest import code_from_outbox, login, register

from models import account as accounts
from models import mail_log
from models import token as tokens

PASSWORD = "Contrasena-Larga1"
NUEVA = "nueva@ejemplo.com"


def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def csrf(client, url="/cuenta/correo"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def ask(browser, email=NUEVA, password=PASSWORD):
    """Pedir el cambio: la dirección nueva y la contraseña."""
    return browser.post("/cuenta/correo", data={
        "csrf_token": csrf(browser), "email": email, "password": password})


def type_code(browser, code):
    token = csrf(browser, "/cuenta/correo/codigo")
    digits = list(str(code)) if len(str(code)) == 6 else [str(code)]
    return browser.post("/cuenta/correo/codigo", data={
        "csrf_token": token, "code": digits})


def sent(database, purpose):
    return list(database.mail_log.find({"purpose": purpose}))


# ------------------------------------------------------------- el camino

def test_el_correo_cambia_con_la_contrasena_y_el_codigo(client, database, outbox):
    browser = inside(client)

    ask(browser)
    # Todavía no cambió nada: la cuenta sigue entrando por la de siempre.
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta is not None
    assert accounts.pending_email(cuenta) == NUEVA

    type_code(browser, code_from_outbox(outbox))

    assert accounts.by_email(database, "ana@ejemplo.com") is None
    movida = accounts.by_email(database, NUEVA)
    assert movida is not None
    assert accounts.pending_email(movida) == ""
    # Y queda confirmada: el código acaba de probar que esa dirección es suya,
    # que es exactamente lo que prueba confirmar.
    assert movida["email_confirmed_at"]


def test_una_cuenta_sin_confirmar_queda_confirmada(client, database, outbox):
    """Pedir dos veces la misma prueba no protege de nada."""
    browser = inside(client)
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"] is None

    ask(browser)
    type_code(browser, code_from_outbox(outbox))

    assert accounts.by_email(database, NUEVA)["email_confirmed_at"]


def test_el_codigo_va_a_la_nueva_y_el_aviso_a_la_vieja(client, database, outbox):
    browser = inside(client)

    ask(browser)
    codigo = sent(database, mail_log.EMAIL_CHANGE_CODE)
    assert len(codigo) == 1
    assert codigo[0]["to"] == NUEVA

    type_code(browser, code_from_outbox(outbox))

    aviso = sent(database, mail_log.EMAIL_CHANGED)
    assert len(aviso) == 1
    assert aviso[0]["to"] == "ana@ejemplo.com"
    assert NUEVA in aviso[0]["text"]
    # La alarma no lleva ninguna puerta dentro: quien la recibe ya no controla
    # esa cuenta.
    assert "/entrar" not in aviso[0]["html"]


def test_despues_se_entra_con_la_nueva_y_no_con_la_vieja(client, database, outbox):
    browser = inside(client)
    ask(browser)
    type_code(browser, code_from_outbox(outbox))

    con_la_nueva = other(client)
    assert login(con_la_nueva, email=NUEVA).headers["Location"].endswith("/panel")

    con_la_vieja = other(client)
    respuesta = login(con_la_vieja, email="ana@ejemplo.com")
    assert respuesta.status_code == 200
    assert "no coinciden" in respuesta.get_data(as_text=True) or \
        "no es correcta" in respuesta.get_data(as_text=True) or \
        "error" in respuesta.get_data(as_text=True).lower()


# --------------------------------------------------------- lo que no pasa

def test_sin_la_contrasena_no_se_pide_nada(client, database, outbox):
    browser = inside(client)

    respuesta = ask(browser, password="otra-cosa")

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert accounts.pending_email(cuenta) == ""
    assert sent(database, mail_log.EMAIL_CHANGE_CODE) == []
    assert "contraseña" in respuesta.get_data(as_text=True)


def test_sin_el_codigo_no_cambia_nada(client, database, outbox):
    browser = inside(client)
    ask(browser)

    type_code(browser, "000000")

    assert accounts.by_email(database, "ana@ejemplo.com") is not None
    assert accounts.by_email(database, NUEVA) is None


def test_una_direccion_de_otra_cuenta_se_rechaza(client, database, outbox):
    register(client, email="bea@ejemplo.com")
    browser = inside(client)

    respuesta = ask(browser, email="bea@ejemplo.com")

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert accounts.pending_email(cuenta) == ""
    assert "Ya existe una cuenta" in respuesta.get_data(as_text=True)


def test_la_misma_direccion_de_siempre_se_rechaza(client, database, outbox):
    browser = inside(client)

    respuesta = ask(browser, email="ana@ejemplo.com")

    assert "ya es la dirección de tu cuenta" in respuesta.get_data(as_text=True)
    assert sent(database, mail_log.EMAIL_CHANGE_CODE) == []


def test_el_codigo_no_sirve_dos_veces(client, database, outbox):
    browser = inside(client)
    ask(browser)
    codigo = code_from_outbox(outbox)
    type_code(browser, codigo)

    # La cuenta ya se movió; volver a escribirlo no puede mover nada.
    otra_vez = type_code(browser, codigo)

    assert otra_vez.status_code == 302
    assert otra_vez.headers["Location"].endswith("/cuenta/correo")


def test_cinco_intentos_y_se_acabo(client, database, outbox):
    browser = inside(client)
    ask(browser)

    for _ in range(tokens.MAX_ATTEMPTS):
        type_code(browser, "000000")
    ultima = type_code(browser, code_from_outbox(outbox))

    assert accounts.by_email(database, NUEVA) is None
    assert "demasiadas veces" in ultima.get_data(as_text=True) or \
        "intentos" in ultima.get_data(as_text=True)


# ------------------------------------------------------------ las puertas

def test_sin_sesion_manda_a_entrar(client, database):
    assert client.get("/cuenta/correo").status_code == 302
    assert client.get("/cuenta/correo/codigo").status_code == 302


def test_la_pantalla_del_codigo_sin_nada_pendiente_vuelve(client, database, outbox):
    browser = inside(client)

    respuesta = browser.get("/cuenta/correo/codigo")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/cuenta/correo")


def test_la_pantalla_de_cuenta_ofrece_cambiarlo(client, database, outbox):
    browser = inside(client)

    pantalla = browser.get("/configuracion").get_data(as_text=True)

    assert "/cuenta/correo" in pantalla
    assert "le avisamos a la dirección anterior" in pantalla.lower()
