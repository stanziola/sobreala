"""Entrar y registrarse con GitHub (octubre de 2026).

Va por el mismo camino que Google (`PROVIDERS` en las rutas de la cuenta), así
que estas pruebas fijan lo mismo que `test_google.py` con GitHub, y lo que
GitHub tiene distinto: que de su lista de correos valga **solo el principal y
verificado**, que el código salga con PKCE y que cada llamada lleve su
`User-Agent`. GitHub se sustituye entero (`fake_github`): es lo único que no se
puede llamar desde una prueba.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from conftest import SIGNUP_EXTRA, login, register

from config import Config
from models import account as accounts
from services import github_auth

EMAIL = "ana@ejemplo.com"


def fake_github(monkeypatch, **who):
    """GitHub de mentira: dice que es `who` y guarda los códigos que recibió."""
    state = {"codes": [], "who": {"sub": "4242", "email": EMAIL,
                                  "email_verified": True, "name": "Ana Pérez", **who}}

    def answer(code, *, verifier, redirect_uri):
        state["codes"].append((code, verifier, redirect_uri))
        return dict(state["who"])

    monkeypatch.setattr(Config, "GITHUB_CLIENT_ID", "Iv1.cliente")
    monkeypatch.setattr(Config, "GITHUB_CLIENT_SECRET", "secreto")
    monkeypatch.setattr(github_auth, "who", answer)
    return state


def other(client):
    return client.application.test_client()


def ir_a_github(browser, path="/login/github"):
    """Pulsar el botón: devuelve el `state` que viaja a GitHub."""
    salida = browser.get(path)
    assert salida.status_code == 302
    destino = urlparse(salida.headers["Location"])
    assert destino.netloc == "github.com" and destino.path == "/login/oauth/authorize"
    pedido = parse_qs(destino.query)
    assert pedido["code_challenge_method"] == ["S256"] and pedido["code_challenge"][0]
    assert pedido["scope"] == ["read:user user:email"]
    assert pedido["redirect_uri"][0].endswith("/login/github/return")
    return pedido["state"][0]


def entrar_con_github(browser):
    state = ir_a_github(browser)
    return browser.get(f"/login/github/return?state={state}&code=CODIGO")


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def esta_dentro(browser):
    return browser.get("/settings").status_code == 200


# ------------------------------------------------------------------ el botón

def test_sin_el_cliente_de_github_no_hay_boton_ni_rutas(client, database):
    assert Config.GITHUB_CLIENT_ID == "" or Config.GITHUB_CLIENT_SECRET == ""
    assert "Continuar con GitHub" not in client.get("/login").get_data(as_text=True)
    assert client.get("/login/github").status_code == 404
    assert client.get("/login/github/return?state=a&code=b").status_code == 404
    assert client.get("/signup/github").status_code == 404
    # Un proveedor que no existe no es una ruta.
    assert client.get("/login/twitter").status_code == 404


def test_sale_al_lado_de_google(client, database, monkeypatch):
    fake_github(monkeypatch)
    monkeypatch.setattr(Config, "GOOGLE_CLIENT_ID", "cliente.apps.googleusercontent.com")
    monkeypatch.setattr(Config, "GOOGLE_CLIENT_SECRET", "secreto")
    for url in ("/login", "/signup"):
        pantalla = client.get(url).get_data(as_text=True)
        botones = pantalla.split('<div class="providers">')[1].split("</div>")[0]
        assert botones.index("Continuar con Google") < botones.index("Continuar con GitHub")
        assert 'href="/login/github"' in botones and 'class="github-mark"' in botones


# ------------------------------------------------------------- con cuenta

def test_entra_con_su_cuenta_y_queda_enlazada(client, database, outbox, monkeypatch):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    github = fake_github(monkeypatch)
    browser = other(client)

    respuesta = entrar_con_github(browser)

    assert respuesta.status_code == 302 and esta_dentro(browser)
    assert accounts.by_id(database, cuenta["_id"])["github_id"] == "4242"
    codigo, verificador, vuelta = github["codes"][0]
    assert codigo == "CODIGO" and verificador and vuelta.endswith("/login/github/return")
    # La segunda vez entra por su identificador, aunque cambie su correo.
    github["who"]["email"] = "ana.nueva@ejemplo.com"
    otra = other(client)
    entrar_con_github(otra)
    assert esta_dentro(otra)


def test_el_doble_factor_se_pide_tambien_con_github(client, database, outbox, monkeypatch):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    accounts.enable_two_factor(database, cuenta["_id"], "JBSWY3DPEHPK3PXP", [])
    fake_github(monkeypatch)
    browser = other(client)
    assert entrar_con_github(browser).headers["Location"].endswith("/login/code")
    assert not esta_dentro(browser)


def test_lo_que_no_deja_entrar(client, database, outbox, monkeypatch):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    # Sin el correo principal verificado.
    fake_github(monkeypatch, email_verified=False)
    browser = other(client)
    assert "Tu cuenta de GitHub no tiene el correo verificado" in entrar_con_github(
        browser).get_data(as_text=True)
    assert not esta_dentro(browser) and "github_id" not in accounts.by_email(database, EMAIL)
    # Un correo enlazado a otra cuenta de GitHub.
    accounts.link_github(database, cuenta["_id"], "9999")
    fake_github(monkeypatch)
    assert "conectado a otra cuenta de GitHub" in entrar_con_github(
        other(client)).get_data(as_text=True)
    # Con otro state.
    ir_a_github(browser)
    assert "No se completó la entrada con GitHub" in browser.get(
        "/login/github/return?state=OTRO&code=X").get_data(as_text=True)

    def roto(code, *, verifier, redirect_uri):
        raise github_auth.GitHubError("github 500")

    monkeypatch.setattr(github_auth, "who", roto)
    assert "No pudimos hablar con GitHub" in entrar_con_github(
        other(client)).get_data(as_text=True)


# ------------------------------------------------------------- sin cuenta

def test_sin_cuenta_pide_lo_que_falta_y_la_crea_confirmada(client, database, outbox,
                                                           monkeypatch):
    fake_github(monkeypatch, email="nueva@coop.com", sub="777", name="Luis Gómez")
    browser = other(client)

    assert entrar_con_github(browser).headers["Location"].endswith("/signup/github")
    pantalla = browser.get("/signup/github").get_data(as_text=True)
    assert "Entraste con GitHub como nueva@coop.com" in pantalla
    assert 'value="Luis Gómez"' in pantalla and 'name="password"' not in pantalla

    creada = browser.post("/signup/github", data={
        "csrf_token": csrf(browser, "/signup/github"), "company_name": "Coop Sur",
        "contact_name": "Luis Gómez", "phone_country": "PA", "phone": "60001111",
        **SIGNUP_EXTRA})

    assert creada.headers["Location"].endswith("/welcome")
    cuenta = accounts.by_email(database, "nueva@coop.com")
    assert cuenta["github_id"] == "777" and accounts.is_confirmed(cuenta)
    assert cuenta["password_hash"] == "" and "google_sub" not in cuenta
    assert esta_dentro(browser)


# --------------------------------------------------------------- Seguridad

def test_seguridad_dice_conectado_y_desconectar_pide_contrasena(client, database, outbox,
                                                                 monkeypatch):
    register(client)
    fake_github(monkeypatch)
    browser = other(client)
    entrar_con_github(browser)

    pantalla = browser.get("/settings/security").get_data(as_text=True)
    assert "Entras con tu cuenta de GitHub." in pantalla and "Desconectar" in pantalla
    # Google no está conectado: su fila no sale.
    assert "Entras con tu cuenta de Google." not in pantalla

    salida = browser.post("/settings/github/disconnect",
                          data={"csrf_token": csrf(browser, "/settings/security")})
    assert "github=off" in salida.headers["Location"]
    assert "github_id" not in accounts.by_email(database, EMAIL)
    assert "Listo, desconectaste GitHub." in browser.get(
        salida.headers["Location"]).get_data(as_text=True)


# ------------------------------------------------- cómo se le habla a GitHub

class Respuesta:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def github_que_contesta(monkeypatch, emails, user=None):
    """Las tres llamadas de `who()`, contestadas, y lo que se le pidió a cada una."""
    pedidos = []
    respuestas = {
        github_auth.TOKEN_URL: {"access_token": "gho_token", "token_type": "bearer"},
        github_auth.USER_URL: user or {"id": 4242, "login": "ana", "name": "Ana Pérez"},
        github_auth.EMAILS_URL: emails,
    }

    def urlopen(request, timeout=None):
        pedidos.append(request)
        return Respuesta(respuestas[request.full_url])

    monkeypatch.setattr(Config, "GITHUB_CLIENT_ID", "Iv1.cliente")
    monkeypatch.setattr(Config, "GITHUB_CLIENT_SECRET", "secreto")
    monkeypatch.setattr(github_auth.urllib.request, "urlopen", urlopen)
    return pedidos


def test_who_toma_el_principal_verificado(monkeypatch):
    pedidos = github_que_contesta(monkeypatch, [
        {"email": "otra@ejemplo.com", "primary": False, "verified": True},
        {"email": "ana@ejemplo.com", "primary": True, "verified": True}])
    found = github_auth.who("CODIGO", verifier="V", redirect_uri="https://app/x")
    assert found == {"sub": "4242", "email": "ana@ejemplo.com",
                     "email_verified": True, "name": "Ana Pérez"}
    # El código, con su verificador y el secreto, desde el servidor.
    cuerpo = parse_qs(pedidos[0].data.decode())
    assert cuerpo["code"] == ["CODIGO"] and cuerpo["code_verifier"] == ["V"]
    assert cuerpo["client_secret"] == ["secreto"]
    # Todas con su User-Agent, y las de la API con el token.
    assert all(one.get_header("User-agent") == "Sobreala" for one in pedidos)
    assert pedidos[1].get_header("Authorization") == "Bearer gho_token"


def test_who_sin_principal_verificado_no_esta_verificado(monkeypatch):
    github_que_contesta(monkeypatch, [
        {"email": "otra@ejemplo.com", "primary": False, "verified": True},
        {"email": "ana@ejemplo.com", "primary": True, "verified": False}],
        user={"id": 1, "login": "ana", "name": None})
    found = github_auth.who("CODIGO", verifier="V", redirect_uri="https://app/x")
    assert found["email"] == "ana@ejemplo.com" and found["email_verified"] is False
    # Sin nombre, el de usuario.
    assert found["name"] == "ana"


def test_un_codigo_que_no_vale_es_un_error(monkeypatch):
    github_que_contesta(monkeypatch, [])
    monkeypatch.setattr(github_auth.urllib.request, "urlopen",
                        lambda request, timeout=None: Respuesta(
                            {"error": "bad_verification_code"}))
    try:
        github_auth.who("VIEJO", verifier="V", redirect_uri="https://app/x")
    except github_auth.GitHubError as exc:
        assert "bad_verification_code" in str(exc)
    else:
        raise AssertionError("un código que no vale tiene que ser un error")
