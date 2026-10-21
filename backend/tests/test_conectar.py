"""Conectar Google o GitHub desde Seguridad (octubre de 2026).

Antes se conectaban solos, la primera vez que se entraba con el mismo correo, y
así GitHub abría una cuenta de contraseña ajena. Ahora se conecta a propósito:
con la prueba de quién es (la contraseña y el código de la app), y solo si a la
vuelta sigue siendo **la misma cuenta y la misma sesión**. Una cuenta de Google
entra a una sola de Sobreala (índice único), y conectarla avisa al correo.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from conftest import SIGNUP_EXTRA, login, register
from pymongo.errors import DuplicateKeyError
from test_google import fake_google

from models import account as accounts
from models import mail_log

EMAIL = "ana@ejemplo.com"
PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def dentro(client, database):
    register(client)
    accounts.confirm_email(database, accounts.by_email(database, EMAIL)["_id"])
    browser = other(client)
    login(browser)
    return browser


def pedir(browser, password=PASSWORD):
    return browser.post("/settings/google/connect", data={
        "csrf_token": csrf(browser, "/settings/google/connect"), "password": password})


def state_de(salida):
    destino = urlparse(salida.headers["Location"])
    assert destino.netloc == "accounts.google.com"
    return parse_qs(destino.query)["state"][0]


def test_seguridad_ofrece_conectar(client, database, outbox, monkeypatch):
    fake_google(monkeypatch)
    browser = dentro(client, database)

    pantalla = browser.get("/settings/security").get_data(as_text=True)

    assert "Conéctalo para entrar también con tu cuenta de Google." in pantalla
    assert 'href="/settings/google/connect"' in pantalla


def test_conectar_pide_la_contrasena_y_enlaza(client, database, outbox, monkeypatch):
    fake_google(monkeypatch, sub="G-ANA", email="ana.personal@gmail.com")
    browser = dentro(client, database)
    pagina = browser.get("/settings/google/connect").get_data(as_text=True)
    assert "Conectar Google" in pagina and 'name="password"' in pagina

    mala = pedir(browser, password="otra-cosa")
    assert mala.status_code == 200 and "contraseña" in mala.get_data(as_text=True)

    salida = pedir(browser)
    vuelta = browser.get(f"/login/google/return?state={state_de(salida)}&code=C")

    assert vuelta.headers["Location"].endswith("/settings/security?google=on#password")
    # Con otro correo en Google, también: lo que cuenta es su id.
    assert accounts.by_email(database, EMAIL)["google_sub"] == "G-ANA"
    assert database.mail_log.count_documents({"purpose": mail_log.PROVIDER}) == 1
    # Y desde ahora entra con Google.
    nuevo = other(client)
    nuevo.get(f"/login/google/return?state={state_de(nuevo.get('/login/google'))}&code=D")
    assert nuevo.get("/settings").status_code == 200


def test_si_cambia_la_sesion_no_se_conecta(client, database, outbox, monkeypatch):
    fake_google(monkeypatch, sub="G-ANA")
    browser = dentro(client, database)
    salida = pedir(browser)
    # A mitad de camino, la sesión ya es otra (cambiar de cuenta, por ejemplo).
    with browser.session_transaction() as sess:
        sess["google_request"] = {**sess["google_request"], "sid": "otra-sesion"}

    vuelta = browser.get(f"/login/google/return?state={state_de(salida)}&code=C")

    assert "google=lost" in vuelta.headers["Location"]
    assert "google_sub" not in accounts.by_email(database, EMAIL)


def test_una_cuenta_de_google_de_otra_no_se_conecta(client, database, outbox, monkeypatch):
    register(client, email="bea@ejemplo.com")
    bea = accounts.by_email(database, "bea@ejemplo.com")
    accounts.link_google(database, bea["_id"], "G-ANA")
    fake_google(monkeypatch, sub="G-ANA")
    browser = dentro(client, database)

    salida = pedir(browser)
    vuelta = browser.get(f"/login/google/return?state={state_de(salida)}&code=C")

    assert "google=taken" in vuelta.headers["Location"]
    assert "google_sub" not in accounts.by_email(database, EMAIL)


def test_sin_contrasena_el_codigo_va_al_correo(client, database, outbox, monkeypatch):
    fake_google(monkeypatch)
    browser = dentro(client, database)
    database.accounts.update_one({"email_normalized": EMAIL}, {"$set": {"password_hash": ""}})

    pagina = browser.get("/settings/google/connect").get_data(as_text=True)
    assert 'name="email_code"' in pagina and 'value="code"' in pagina
    browser.post("/settings/google/connect", data={
        "csrf_token": csrf(browser, "/settings/google/connect"), "action": "code"})
    assert database.mail_log.count_documents({"purpose": mail_log.PROVIDER}) == 1


def test_una_cuenta_de_google_entra_a_una_sola(client, database):
    register(client, email="una@ejemplo.com")
    register(client, email="dos@ejemplo.com")
    una = accounts.by_email(database, "una@ejemplo.com")
    dos = accounts.by_email(database, "dos@ejemplo.com")
    accounts.link_google(database, una["_id"], "G-UNICA")

    with pytest.raises(DuplicateKeyError):
        accounts.link_google(database, dos["_id"], "G-UNICA")


def test_el_aviso_de_registro_dice_como_entra_la_cuenta(client, database, outbox,
                                                       monkeypatch):
    """Una cuenta creada con Google no tiene contraseña: «entra con tu
    contraseña» la dejaba sin saber qué hacer."""
    fake_google(monkeypatch, email="nueva@coop.com", sub="G-NUEVA")
    browser = other(client)
    browser.get(f"/login/google/return?state={state_de(browser.get('/login/google'))}&code=C")
    browser.post("/signup/google", data={
        "csrf_token": csrf(browser, "/signup/google"), "company_name": "Coop Sur",
        "contact_name": "Luis", "phone_country": "PA", "phone": "60001111", **SIGNUP_EXTRA})

    register(other(client), email="nueva@coop.com")

    aviso = sorted(outbox.glob("*.html"))[-1].read_text(encoding="utf-8")
    assert "entra con Google" in aviso and "entra con tu contraseña" not in aviso
