"""Entrar y registrarse con Google.

Google se sustituye entero (`fake_google`): es lo único que no se puede llamar
desde una prueba. Lo que fijan estas pruebas es lo que, si sale mal, deja entrar
a quien no es: que la vuelta solo valga con **el `state` que se guardó al
salir**, que quién es lo diga **Google al servidor** (un correo sin verificar no
entra, y uno enlazado a otra cuenta de Google tampoco), que **tras Google pase lo
mismo que tras la contraseña** (suspendida no entra, el doble factor se pide), y
que nadie se quede sin forma de entrar al desconectarlo.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from conftest import login, register

from config import Config
from models import account as accounts
from models import mail_log
from services import google_auth

EMAIL = "ana@ejemplo.com"


def fake_google(monkeypatch, **who):
    """Google de mentira: dice que es `who` y guarda los códigos que recibió."""
    state = {"codes": [], "who": {"sub": "G-ANA", "email": EMAIL,
                                  "email_verified": True, "name": "Ana Pérez", **who}}

    def answer(code, *, verifier, redirect_uri):
        state["codes"].append((code, verifier, redirect_uri))
        return dict(state["who"])

    monkeypatch.setattr(Config, "GOOGLE_CLIENT_ID", "cliente.apps.googleusercontent.com")
    monkeypatch.setattr(Config, "GOOGLE_CLIENT_SECRET", "secreto")
    monkeypatch.setattr(google_auth, "who", answer)
    return state


def other(client):
    return client.application.test_client()


def ir_a_google(browser, path="/login/google"):
    """Pulsar el botón: devuelve el `state` que viaja a Google."""
    salida = browser.get(path)
    assert salida.status_code == 302
    destino = urlparse(salida.headers["Location"])
    assert destino.netloc == "accounts.google.com"
    pedido = parse_qs(destino.query)
    assert pedido["code_challenge_method"] == ["S256"] and pedido["code_challenge"][0]
    assert pedido["scope"] == ["openid email profile"]
    return pedido["state"][0]


def volver(browser, state, code="CODIGO"):
    return browser.get(f"/login/google/return?state={state}&code={code}")


def entrar_con_google(browser):
    return volver(browser, ir_a_google(browser))


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def esta_dentro(browser):
    return browser.get("/settings").status_code == 200


# ------------------------------------------------------------------ el botón

def test_sin_el_cliente_de_google_no_hay_boton_ni_rutas(client, database):
    assert Config.GOOGLE_CLIENT_ID == "" or Config.GOOGLE_CLIENT_SECRET == ""
    assert "Continuar con Google" not in client.get("/login").get_data(as_text=True)
    assert "Continuar con Google" not in client.get("/signup").get_data(as_text=True)
    assert client.get("/login/google").status_code == 404
    assert client.get("/login/google/return?state=a&code=b").status_code == 404
    assert client.get("/signup/google").status_code == 404


def test_con_el_cliente_sale_en_entrar_y_en_registrarse(client, database, monkeypatch):
    fake_google(monkeypatch)
    for url in ("/login", "/signup"):
        pantalla = client.get(url).get_data(as_text=True)
        assert "Continuar con Google" in pantalla and 'href="/login/google"' in pantalla


def test_el_boton_sigue_cuando_entrar_dice_que_no(client, database, outbox, monkeypatch):
    # Las dos veces que entrar vuelve a la pantalla por su cuenta (suspendida, y
    # agregar una que ya está abierta) el botón tiene que seguir ahí.
    register(client)
    login(client, EMAIL)
    assert esta_dentro(client)
    fake_google(monkeypatch)
    pantalla = client.post("/login?add=1", data={
        "csrf_token": csrf(client, "/login?add=1"), "email": EMAIL,
        "password": "Contrasena-Larga1"}).get_data(as_text=True)
    assert "Continuar con Google" in pantalla and 'href="/login/google?add=1"' in pantalla

    database.accounts.update_one({"email_normalized": EMAIL},
                                 {"$set": {"status": accounts.SUSPENDED}})
    pantalla = login(other(client), EMAIL).get_data(as_text=True)
    assert "Continuar con Google" in pantalla


# ------------------------------------------------------------- con cuenta

def test_entra_con_su_cuenta_y_queda_enlazada(client, database, outbox, monkeypatch):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    google = fake_google(monkeypatch)
    browser = other(client)

    respuesta = entrar_con_google(browser)

    assert respuesta.status_code == 302
    assert esta_dentro(browser)
    assert accounts.by_id(database, cuenta["_id"])["google_sub"] == "G-ANA"
    # El código viaja con su verificador de PKCE y la vuelta registrada.
    codigo, verificador, vuelta = google["codes"][0]
    assert codigo == "CODIGO" and verificador
    assert vuelta.endswith("/login/google/return")
    # Entrar desde un dispositivo nuevo avisa, como con la contraseña.
    assert database.mail_log.count_documents({"purpose": mail_log.NEW_LOGIN}) >= 1

    # La segunda vez entra por su identificador de Google, aunque cambie el correo
    # que Google dice.
    google["who"]["email"] = "ana.nueva@gmail.com"
    otra = other(client)
    entrar_con_google(otra)
    assert esta_dentro(otra)


def test_un_registro_sin_confirmar_queda_confirmado(client, database, outbox, monkeypatch):
    register(client, abierta=False)
    assert not accounts.is_confirmed(accounts.by_email(database, EMAIL))
    fake_google(monkeypatch)

    entrar_con_google(other(client))

    assert accounts.is_confirmed(accounts.by_email(database, EMAIL))


def test_el_doble_factor_se_pide_tambien_con_google(client, database, outbox, monkeypatch):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    accounts.enable_two_factor(database, cuenta["_id"], "JBSWY3DPEHPK3PXP", [])
    fake_google(monkeypatch)
    browser = other(client)

    respuesta = entrar_con_google(browser)

    assert respuesta.headers["Location"].endswith("/login/code")
    assert not esta_dentro(browser)


def test_una_cuenta_suspendida_no_entra(client, database, outbox, monkeypatch):
    register(client)
    database.accounts.update_one({"email_normalized": EMAIL},
                                 {"$set": {"status": accounts.SUSPENDED}})
    fake_google(monkeypatch)
    browser = other(client)

    respuesta = entrar_con_google(browser)

    assert respuesta.status_code == 200
    assert not esta_dentro(browser)


def test_un_correo_enlazado_a_otra_cuenta_de_google_no_entra(client, database, outbox,
                                                             monkeypatch):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    accounts.link_google(database, cuenta["_id"], "G-OTRA")
    fake_google(monkeypatch)
    browser = other(client)

    pantalla = entrar_con_google(browser).get_data(as_text=True)

    assert "conectado a otra cuenta de Google" in pantalla
    assert not esta_dentro(browser)
    assert accounts.by_id(database, cuenta["_id"])["google_sub"] == "G-OTRA"


# --------------------------------------------------- lo que no deja entrar

def test_un_correo_sin_verificar_no_entra(client, database, outbox, monkeypatch):
    register(client)
    fake_google(monkeypatch, email_verified=False)
    browser = other(client)

    pantalla = entrar_con_google(browser).get_data(as_text=True)

    assert "no tiene el correo verificado" in pantalla
    assert not esta_dentro(browser)
    assert "google_sub" not in accounts.by_email(database, EMAIL)


def test_la_vuelta_solo_vale_con_su_state(client, database, outbox, monkeypatch):
    register(client)
    google = fake_google(monkeypatch)
    browser = other(client)

    # Sin haber salido a Google, con otro state, o sin código: no entra, y a
    # Google no se le pregunta nada.
    assert "No se completó" in volver(browser, "INVENTADO").get_data(as_text=True)
    ir_a_google(browser)
    assert "No se completó" in volver(browser, "OTRO").get_data(as_text=True)
    state = ir_a_google(browser)
    assert "No se completó" in browser.get(
        f"/login/google/return?state={state}").get_data(as_text=True)
    assert google["codes"] == []
    assert not esta_dentro(browser)

    # El state se gasta: la misma vuelta dos veces no vale.
    state = ir_a_google(browser)
    volver(browser, state)
    tercera = other(client)
    with tercera.session_transaction() as sess:
        sess["google_request"] = {"state": "X", "verifier": "Y"}
    assert "No se completó" in volver(tercera, state).get_data(as_text=True)


def test_si_google_no_responde_no_entra(client, database, outbox, monkeypatch):
    register(client)
    fake_google(monkeypatch)

    def roto(code, *, verifier, redirect_uri):
        raise google_auth.GoogleError("google 500")

    monkeypatch.setattr(google_auth, "who", roto)
    browser = other(client)

    assert "No pudimos hablar con Google" in entrar_con_google(browser).get_data(as_text=True)
    assert not esta_dentro(browser)


# ------------------------------------------------------------- sin cuenta

def test_sin_cuenta_pide_lo_que_falta_y_la_crea_confirmada(client, database, outbox,
                                                           monkeypatch):
    fake_google(monkeypatch, email="nueva@coop.com", sub="G-NUEVA", name="Luis Gómez")
    browser = other(client)

    respuesta = entrar_con_google(browser)

    assert respuesta.headers["Location"].endswith("/signup/google")
    assert accounts.by_email(database, "nueva@coop.com") is None
    pantalla = browser.get("/signup/google").get_data(as_text=True)
    assert "nueva@coop.com" in pantalla and 'value="Luis Gómez"' in pantalla
    assert 'name="password"' not in pantalla

    incompleta = browser.post("/signup/google", data={
        "csrf_token": csrf(browser, "/signup/google"), "company_name": "",
        "contact_name": "Luis Gómez", "phone_country": "PA", "phone": "",
        "address": "Calle 1"})
    assert "Completa este campo" in incompleta.get_data(as_text=True)
    assert accounts.by_email(database, "nueva@coop.com") is None

    creada = browser.post("/signup/google", data={
        "csrf_token": csrf(browser, "/signup/google"), "company_name": "Coop Sur",
        "contact_name": "Luis Gómez", "phone_country": "PA", "phone": "60001111",
        "address": "Calle 10, Santiago de Veraguas"})

    assert creada.headers["Location"].endswith("/welcome")
    cuenta = accounts.by_email(database, "nueva@coop.com")
    assert cuenta["google_sub"] == "G-NUEVA"
    assert accounts.is_confirmed(cuenta) and "purge_at" not in cuenta
    assert cuenta["password_hash"] == ""
    assert cuenta["phone"] == "+50760001111" and cuenta["company_name"] == "Coop Sur"
    # Nace cerrada, como cualquier registro, y se avisa a quien administra.
    assert not accounts.is_open(cuenta)
    assert esta_dentro(browser)
    # Sin contraseña no se entra con el formulario.
    tercero = other(client)
    login(tercero, email="nueva@coop.com", password="")
    assert not esta_dentro(tercero)


def test_sin_haber_pasado_por_google_no_hay_registro(client, database, monkeypatch):
    fake_google(monkeypatch)
    assert client.get("/signup/google").headers["Location"].endswith("/login")


# --------------------------------------------------------------- Seguridad

def test_seguridad_dice_conectado_y_desconectar_pide_contrasena(client, database, outbox,
                                                                 monkeypatch):
    register(client)
    fake_google(monkeypatch)
    browser = other(client)
    entrar_con_google(browser)

    pantalla = browser.get("/settings/security").get_data(as_text=True)
    assert "Conectado" in pantalla and "Desconectar" in pantalla

    salida = browser.post("/settings/google/disconnect",
                          data={"csrf_token": csrf(browser, "/settings/security")})
    assert "google=off" in salida.headers["Location"]
    assert "google_sub" not in accounts.by_email(database, EMAIL)


def test_sin_contrasena_no_se_desconecta(client, database, outbox, monkeypatch):
    fake_google(monkeypatch, email="nueva@coop.com", sub="G-NUEVA")
    browser = other(client)
    entrar_con_google(browser)
    browser.post("/signup/google", data={
        "csrf_token": csrf(browser, "/signup/google"), "company_name": "Coop Sur",
        "contact_name": "Luis", "phone_country": "PA", "phone": "60001111",
        "address": "Calle 10, Santiago de Veraguas"})

    pantalla = browser.get("/settings/security").get_data(as_text=True)
    assert "Conectado" in pantalla and "Desconectar" not in pantalla
    salida = browser.post("/settings/google/disconnect",
                          data={"csrf_token": csrf(browser, "/settings/security")})
    assert "google=nopassword" in salida.headers["Location"]
    assert accounts.by_email(database, "nueva@coop.com")["google_sub"] == "G-NUEVA"
