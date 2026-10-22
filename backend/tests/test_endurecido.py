"""Los huecos de seguridad que se vieron y se cerraron (octubre de 2026).

Cada prueba fija uno: la contraseña del segundo factor vale solo para la cuenta
y la sesión que la dieron; la IP de una cabecera solo se cree si la conexión es
de Cloudflare; un código de eliminar la cuenta vale una vez aunque lleguen dos
peticiones juntas; un salto de línea en un nombre no entra a una cabecera; un
número infinito en el lienzo no da error 500; las plantillas y los archivos de
Redactar tienen tope; y HSTS va en todo lo que sale por HTTPS, también en el
sitio público.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from conftest import login, register
from test_campaigns import catch, make, ready, send_it
from test_settings import two_accounts, switch_to
from test_single import PDF, escribir
from test_two_factor import prove

from blueprints.auth import routes as auth_routes
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import download as downloads
from models import token as tokens
from services import canvas

ROOT = Path(__file__).resolve().parents[2]


def other(client):
    return client.application.test_client()


# ------------------------------------------------------- el segundo factor

def test_la_contrasena_de_una_cuenta_no_abre_el_qr_de_otra(client, database, outbox):
    browser, una, dos = two_accounts(client, database)
    prove(browser)                       # la de «dos», que es la que está en uso
    assert browser.get("/account/two-factor/enable").status_code == 200
    switch_to(browser, una)
    assert browser.get("/account/two-factor/enable").status_code == 302
    # Y el secreto que se estaba preparando tampoco se pasa de una a otra.
    with browser.session_transaction() as sess:
        assert sess["two_factor_setup"]["account"] == str(dos)


# ------------------------------------------------------------------- la IP

def test_la_ip_de_una_cabecera_solo_vale_si_viene_de_cloudflare(client, database):
    def intento(**extra):
        client.get("/login")
        with client.session_transaction() as sess:
            token = sess["_csrf"]
        client.post("/login", headers={"CF-Connecting-IP": "203.0.113.9"},
                    data={"csrf_token": token, "email": "x@ejemplo.com",
                          "password": "loquesea"}, **extra)
        return [d["key"] for d in database.rate_limits.find({})]

    directo = intento()
    assert not any("203.0.113.9" in k for k in directo)
    desde_cloudflare = intento(environ_base={"REMOTE_ADDR": "104.16.0.1"})
    assert any("203.0.113.9" in k for k in desde_cloudflare)


# ----------------------------------------------------- eliminar la cuenta

def test_un_codigo_de_eliminar_vale_una_vez(client, database, outbox, monkeypatch):
    """Si otra petición lo gastó entre mirarlo y usarlo, esta no elimina."""
    register(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    accounts.confirm_email(database, cuenta["_id"])
    browser = other(client)
    login(browser)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"password_hash": ""}})
    code = tokens.issue(database, cuenta["_id"], tokens.ERASE)
    monkeypatch.setattr(auth_routes.tokens, "spend", lambda db, doc: False)
    browser.get("/settings/delete")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    pantalla = browser.post("/settings/delete", data={
        "csrf_token": token, "confirm_name": cuenta["company_name"], "email_code": code})
    assert pantalla.status_code == 200
    assert accounts.by_id(database, cuenta["_id"]) is not None


# ------------------------------------------------------- saltos de línea

def test_un_salto_de_linea_en_un_nombre_no_llega_a_una_cabecera(client, database, outbox,
                                                                monkeypatch):
    salidos = catch(monkeypatch)
    browser, cuenta, pieza = ready(client, database, howmany=0)
    # Escrito a mano: se guarda en una línea.
    contacts.create(database, cuenta["_id"], email="ana@coop.com", name="Ana\nPérez",
                    consent=contacts.consent_of(contacts.MEMBERS))
    assert database.contacts.find_one({"email": "ana@coop.com"})["name"] == "Ana Pérez"
    # Uno que ya estaba guardado con el salto: el asunto sale igual en una línea.
    database.contacts.update_one({"email": "ana@coop.com"},
                                 {"$set": {"name": "Ana\r\nBcc: otro@x.com"}})
    make(browser, pieza, subject="Hola *|NOMBRE|*")
    send_it(browser, database, cuenta["_id"])
    correo, = salidos
    assert correo["Subject"] == "Hola Ana Bcc: otro@x.com"
    assert correo["Bcc"] is None


# ------------------------------------------------------------- el lienzo

def test_un_numero_infinito_en_el_lienzo_no_revienta():
    texto = {"t": "text", "x": 10, "y": 10, "w": 100, "h": 40, "text": "Hola"}
    for raro in ('1e999', '-1e999'):
        crudo = json.dumps({"h": 400, "items": [texto]}).replace('"x": 10', f'"x": {raro}')
        hecho = canvas.parse(crudo)
        assert hecho is not None and hecho["items"][0]["x"] == 0
    for literal in ("NaN", "Infinity", "-Infinity"):
        crudo = json.dumps({"h": 400, "items": [texto]}).replace('"y": 10', f'"y": {literal}')
        assert canvas.parse(crudo) is None
    # Y un interlineado o un recorte que no son números de verdad no se guardan.
    leido = canvas.read({"h": 400, "items": [{**texto, "line": float("nan")},
                                             {"t": "image", "x": 0, "y": 0, "w": 50, "h": 50,
                                              "name": "a.png",
                                              "crop": [0, 0, float("nan"), 1]}]})
    assert leido["items"][0]["line"] == 1.4
    assert "crop" not in leido["items"][1]


def test_el_lienzo_del_panel_con_nan_no_da_500(client, database, outbox):
    browser, cuenta, _ = ready(client, database, howmany=0)
    browser.get("/templates/create")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    respuesta = browser.post("/templates/create", data={
        "csrf_token": token, "nombre": "Prueba",
        "lienzo": '{"h": NaN, "items": [{"t": "text", "x": Infinity}]}'})
    assert respuesta.status_code in (200, 302)


# ---------------------------------------------------- lo que llena la base

def test_las_plantillas_tienen_tope_tambien_en_el_panel(client, database, outbox,
                                                       monkeypatch):
    browser, cuenta, pieza = ready(client, database, howmany=0)
    monkeypatch.setattr(designs, "LIMIT", designs.count(database, cuenta["_id"]))
    browser.get("/templates")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    antes = designs.count(database, cuenta["_id"])
    copia = browser.post("/templates/duplicate", data={"csrf_token": token,
                                                       "id": str(pieza)})
    assert "full=1" in copia.headers["Location"]
    assert designs.count(database, cuenta["_id"]) == antes
    pantalla = browser.get(copia.headers["Location"]).get_data(as_text=True)
    assert "que es lo que cabe" in pantalla


def test_los_archivos_de_redactar_tienen_tope_por_cuenta(client, database, outbox,
                                                        monkeypatch):
    browser, cuenta, _ = ready(client, database)
    salidos = catch(monkeypatch)
    monkeypatch.setattr(downloads, "ACCOUNT_BYTES", len(PDF) + 10)
    escribir(browser, archivo=(io.BytesIO(PDF), "uno.pdf"))
    assert len(salidos) == 1
    pantalla = escribir(browser, archivo=(io.BytesIO(PDF), "dos.pdf"))
    assert "que es lo que cabe" in pantalla.get_data(as_text=True)
    assert len(salidos) == 1
    assert database.downloads.count_documents({"account_id": cuenta["_id"]}) == 1


# --------------------------------------------------------------------- HSTS

def test_hsts_por_https_y_no_por_http(client, database):
    seguro = client.get("/login", base_url="https://app.sobreala.com")
    assert "max-age=63072000" in seguro.headers["Strict-Transport-Security"]
    assert "Strict-Transport-Security" not in client.get("/login").headers
    api = client.get("/api/v1/me", base_url="https://app.sobreala.com")
    assert "Strict-Transport-Security" in api.headers


def test_el_sitio_publico_manda_sus_cabeceras():
    cabeceras = (ROOT / "landing" / "_headers").read_text(encoding="utf-8")
    for una in ("Strict-Transport-Security: max-age=63072000; includeSubDomains",
                "X-Frame-Options: DENY", "X-Content-Type-Options: nosniff",
                "frame-ancestors 'none'"):
        assert una in cabeceras
