"""Entrar, registrarse y conectar con Apple (octubre de 2026).

Lo que Apple hace distinto y que no puede fallar: que la clave secreta sea un
JWT ES256 que Apple acepte; que el `id_token` solo valga si es de Apple, para
nosotros, vigente y con **el `nonce` que se mandó al salir**; que su vuelta por
POST se reenvíe desde nuestra página **sin tocar la sesión** (si la tocara, el
navegador cambiaría la galleta de quien entra); y que el resto pase como con
Google: entra solo por su id, nunca por el correo.
"""

from __future__ import annotations

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import SIGNUP_EXTRA, login, register
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from config import Config
from models import account as accounts
from services import apple_auth

EMAIL = "ana@ejemplo.com"
PASSWORD = "Contrasena-Larga1"
RELAY = "x7k2m9q4ab@privaterelay.appleid.com"
CLAVE = ec.generate_private_key(ec.SECP256R1())


@pytest.fixture()
def apple(monkeypatch):
    """Apple configurado con una clave de prueba, y su servidor de mentira: el
    token que devolvería, armado con el `nonce` que se le mande."""
    pem = CLAVE.private_bytes(serialization.Encoding.PEM,
                              serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption()).decode("ascii")
    monkeypatch.setattr(Config, "APPLE_CLIENT_ID", "com.sobreala.web")
    monkeypatch.setattr(Config, "APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setattr(Config, "APPLE_KEY_ID", "KEY1234567")
    # Como se pega en Railway: con «\n» escritos.
    monkeypatch.setattr(Config, "APPLE_PRIVATE_KEY", pem.replace("\n", "\\n"))
    state = {"claims": {"sub": "001234.abcd.0001", "email": EMAIL,
                        "email_verified": "true"}, "secrets": [], "codes": []}

    def token(code, redirect_uri):
        state["codes"].append(code)
        state["secrets"].append(apple_auth.client_secret())
        claims = {"iss": apple_auth.ISSUER, "aud": "com.sobreala.web",
                  "exp": int(time.time()) + 600, "nonce": state.get("nonce", ""),
                  **state["claims"]}
        body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        return {"id_token": f"e30.{body}.firma"}

    monkeypatch.setattr(apple_auth, "_token", token)
    return state


def other(client):
    return client.application.test_client()


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def salir(browser, apple, path="/login/apple"):
    """Pulsar el botón: el `state` viaja a Apple, y el `nonce` también."""
    salida = browser.get(path) if isinstance(path, str) else path
    destino = urlparse(salida.headers["Location"])
    assert destino.netloc == "appleid.apple.com"
    pedido = parse_qs(destino.query)
    assert pedido["response_mode"] == ["form_post"] and pedido["scope"] == ["name email"]
    apple["nonce"] = pedido["nonce"][0]
    return pedido["state"][0]


def volver(client, browser, state, *, user="", code="CODIGO"):
    """Apple vuelve con un POST desde su dominio, **sin la galleta**; nuestra
    página lo reenvía, y ese sí la lleva."""
    datos = {"state": state, "code": code}
    if user:
        datos["user"] = user
    primero = other(client).post("/login/apple/return", data=datos)
    assert primero.status_code == 200
    assert "Set-Cookie" not in primero.headers
    pagina = primero.get_data(as_text=True)
    assert 'name="relay"' in pagina and f'value="{state}"' in pagina
    return browser.post("/login/apple/return", data={**datos, "relay": "1"})


# ------------------------------------------------------------------ la clave

def test_la_clave_secreta_es_un_jwt_es256_que_apple_acepta(apple):
    jwt = apple_auth.client_secret(now=1_800_000_000)
    cabeza, cuerpo, firma = jwt.split(".")

    def leer(parte):
        return json.loads(base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4)))

    assert leer(cabeza) == {"alg": "ES256", "kid": "KEY1234567"}
    assert leer(cuerpo) == {"iss": "TEAM123456", "iat": 1_800_000_000,
                            "exp": 1_800_000_300, "aud": "https://appleid.apple.com",
                            "sub": "com.sobreala.web"}
    crudo = base64.urlsafe_b64decode(firma + "=" * (-len(firma) % 4))
    assert len(crudo) == 64
    der = encode_dss_signature(int.from_bytes(crudo[:32], "big"),
                               int.from_bytes(crudo[32:], "big"))
    CLAVE.public_key().verify(der, f"{cabeza}.{cuerpo}".encode(), ec.ECDSA(hashes.SHA256()))
    with pytest.raises(InvalidSignature):
        CLAVE.public_key().verify(der, b"otra cosa", ec.ECDSA(hashes.SHA256()))


def test_el_token_solo_vale_si_es_de_apple_para_nosotros_y_con_su_nonce(apple):
    apple["nonce"] = "el-nonce"
    assert apple_auth.who("c", verifier="el-nonce", redirect_uri="r")["sub"]
    for malo in ({"iss": "https://evil.example.com"}, {"aud": "otra.app"},
                 {"exp": int(time.time()) - 3600}):
        apple["claims"] = {"sub": "s", "email": EMAIL, **malo}
        with pytest.raises(apple_auth.AppleError):
            apple_auth.who("c", verifier="el-nonce", redirect_uri="r")
    apple["claims"] = {"sub": "s", "email": EMAIL}
    with pytest.raises(apple_auth.AppleError):
        apple_auth.who("c", verifier="otro-nonce", redirect_uri="r")


def test_el_nombre_de_la_primera_vez_sale_del_post(apple):
    assert apple_auth.name_from('{"name":{"firstName":"Ana","lastName":"Pérez"}}') == "Ana Pérez"
    for raro in ("", "no es json", '{"name": "Ana"}', '[1]', '{"name":{"firstName":3}}'):
        assert apple_auth.name_from(raro) == ""


# ------------------------------------------------------------------ las rutas

def test_sin_configurar_no_hay_boton_ni_rutas(client, database):
    assert "Continuar con Apple" not in client.get("/login").get_data(as_text=True)
    assert client.get("/login/apple").status_code == 404
    assert client.post("/login/apple/return", data={"state": "a"}).status_code == 404


def test_con_apple_sale_el_boton_y_form_action_lo_permite(client, database, apple):
    pantalla = client.get("/login")
    assert "Continuar con Apple" in pantalla.get_data(as_text=True)
    assert "https://appleid.apple.com" in pantalla.headers["Content-Security-Policy"]


def test_sin_cuenta_registra_con_el_nombre_y_el_correo_oculto(client, database, outbox,
                                                             apple):
    apple["claims"] = {"sub": "001234.nueva", "email": RELAY, "email_verified": True}
    browser = other(client)
    state = salir(browser, apple)
    nombre = json.dumps({"name": {"firstName": "Marta", "lastName": "Ríos"}})
    vuelta = volver(client, browser, state, user=nombre)
    assert vuelta.headers["Location"].endswith("/signup/apple")
    registro = browser.get("/signup/apple").get_data(as_text=True)
    assert "Marta Ríos" in registro and RELAY in registro

    browser.post("/signup/apple", data={
        "csrf_token": csrf(browser, "/signup/apple"), "company_name": "Coop Sur",
        "contact_name": "Marta Ríos", "phone_country": "PA", "phone": "60001111",
        **SIGNUP_EXTRA})
    suya = accounts.by_email(database, RELAY)
    assert suya["apple_sub"] == "001234.nueva" and accounts.is_confirmed(suya)
    assert suya["password_hash"] == ""


def test_entra_por_su_id_y_no_por_el_correo(client, database, outbox, apple):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    accounts.confirm_email(database, cuenta["_id"])
    browser = other(client)
    # El mismo correo, sin conectar: no entra, y le dice cómo.
    pantalla = volver(client, browser, salir(browser, apple)).get_data(as_text=True)
    assert "entra con contraseña" in pantalla
    assert browser.get("/settings").status_code != 200

    accounts.link_apple(database, cuenta["_id"], "001234.abcd.0001")
    vuelta = volver(client, browser, salir(browser, apple))
    assert vuelta.status_code == 302
    assert browser.get("/settings").status_code == 200


def test_la_vuelta_solo_vale_con_su_state_y_desde_su_sesion(client, database, outbox,
                                                           apple):
    register(client)
    cuenta = accounts.by_email(database, EMAIL)
    accounts.confirm_email(database, cuenta["_id"])
    accounts.link_apple(database, cuenta["_id"], "001234.abcd.0001")
    browser = other(client)
    salir(browser, apple)
    volver(client, browser, "otro-state")
    assert browser.get("/settings").status_code != 200
    # El reenvío desde otro navegador, sin la sesión que salió, tampoco entra.
    ajeno = other(client)
    state = salir(browser, apple)
    ajeno.post("/login/apple/return", data={"state": state, "code": "C", "relay": "1"})
    assert ajeno.get("/settings").status_code != 200
    assert apple["codes"] == []


def test_conectar_apple_desde_seguridad(client, database, outbox, apple):
    register(client)
    accounts.confirm_email(database, accounts.by_email(database, EMAIL)["_id"])
    browser = other(client)
    login(browser)
    assert 'href="/settings/apple/connect"' in browser.get(
        "/settings/security").get_data(as_text=True)
    apple["claims"] = {"sub": "001234.conectada", "email": RELAY, "email_verified": True}
    salida = browser.post("/settings/apple/connect", data={
        "csrf_token": csrf(browser, "/settings/apple/connect"), "password": PASSWORD})
    vuelta = volver(client, browser, salir(browser, apple, path=salida))
    assert vuelta.headers["Location"].endswith("/settings/security?apple=on#password")
    assert accounts.by_email(database, EMAIL)["apple_sub"] == "001234.conectada"
