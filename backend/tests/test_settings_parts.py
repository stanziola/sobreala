"""Configuración en subsecciones (octubre de 2026).

Cada sección se despliega en el menú en sus subsecciones, y cada una tiene su
dirección y enseña solo lo suyo. Lo que fijan estas pruebas: que cada dirección
abra lo suyo y la de siempre abra la primera, que las direcciones viejas sigan
cayendo donde está lo que avisan, que un formulario vuelva a su subsección
(también si algo falla), que guardar los avisos de una subsección **no apague
los de la otra**, que un usuario de la empresa no vea Usuarios, que Google solo
salga conectado, y que agregar un método de pago venga en una bandeja.
"""

from __future__ import annotations

from conftest import login, register
from test_users import as_member

from models import account as accounts



def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def test_cada_subseccion_tiene_su_direccion(client, database, outbox):
    browser = inside(client)
    for url, title in (("/settings/account/profile", "Perfil"),
                       ("/settings/account/contact", "Dirección y teléfonos"),
                       ("/settings/account/verification", "Verificación"),
                       ("/settings/account/plan", "Tu plan"),
                       ("/settings/security/two-step", "Autenticación de múltiples factores"),
                       ("/settings/security/password", "Contraseña"),
                       ("/settings/security/users", "Usuarios"),
                       ("/settings/security/sessions", "Sesiones"),
                       ("/settings/notifications/plan", "Plan y facturación"),
                       ("/settings/notifications/security", "Seguridad"),
                       ("/settings/billing/plan", "Tu plan"),
                       ("/settings/billing/methods", "Métodos de pago"),
                       ("/settings/billing/auto-renewal", "Renovación automática"),
                       ("/settings/billing/history", "Historial de compras")):
        pantalla = browser.get(url)
        assert pantalla.status_code == 200, url
        assert f'class="settings__title">{title}<' in pantalla.get_data(as_text=True), url

    # La de siempre abre la primera; una que no existe vuelve a su sección.
    assert ">Autenticación de múltiples factores<" in browser.get(
        "/settings/security").get_data(as_text=True)
    assert browser.get("/settings/security/inventada").headers["Location"].endswith(
        "/settings/security")


def test_el_menu_despliega_las_subsecciones(client, database, outbox):
    browser = inside(client)
    pantalla = browser.get("/settings/security/sessions").get_data(as_text=True)
    assert pantalla.count("data-settings-toggle") >= 4
    assert 'href="/settings/billing/history"' in pantalla
    assert 'class="settings-nav__item is-current"' in pantalla
    assert 'aria-current="page">Sesiones<' in pantalla


def test_las_direcciones_viejas_caen_donde_esta_lo_que_avisan(client, database, outbox):
    browser = inside(client)
    assert ">Usuarios<" in browser.get("/settings/security?user=invited").get_data(as_text=True)
    assert ">Contraseña<" in browser.get("/settings/security?updated=1").get_data(as_text=True)
    assert 'class="settings__title">Métodos de pago<' in browser.get(
        "/settings/billing?paypal=saved").get_data(as_text=True)
    assert 'class="settings__title">Dirección y teléfonos<' in browser.get(
        "/settings?editar=address").get_data(as_text=True)


def test_un_formulario_vuelve_a_su_subseccion(client, database, outbox):
    browser = inside(client)
    bien = browser.post("/settings/account/contact", data={
        "csrf_token": csrf(browser, "/settings/account/contact"),
        "address": "Apartado 0816-00001, Santiago, Veraguas"})
    assert "/settings/account/contact?address=1" in bien.headers["Location"]
    # Con un error, se vuelve a dibujar ahí mismo, con el campo abierto.
    mal = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings/account"), "address": "corta"})
    pantalla = mal.get_data(as_text=True)
    assert 'class="settings__title">Dirección y teléfonos<' in pantalla
    assert 'name="address"' in pantalla


def test_guardar_una_subseccion_de_avisos_no_apaga_la_otra(client, database, outbox):
    browser = inside(client)
    browser.post("/settings/notifications/security", data={
        "csrf_token": csrf(browser, "/settings/notifications/security")})  # sin new_login
    browser.post("/settings/notifications/plan", data={
        "csrf_token": csrf(browser, "/settings/notifications/plan"),
        "billing": "on", "plan_state": "on"})

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert accounts.wants(cuenta, accounts.NEW_LOGIN) is False
    assert accounts.wants(cuenta, accounts.BILLING) is True


def test_un_usuario_de_la_empresa_no_ve_usuarios(client, database, outbox):
    _, _, suyo = as_member(client, database, outbox=outbox)

    pantalla = suyo.get("/settings/security").get_data(as_text=True)
    assert 'href="/settings/security/users"' not in pantalla
    assert suyo.get("/settings/security/users").status_code == 302


def test_google_solo_sale_conectado(client, database, outbox):
    browser = inside(client)
    sin = browser.get("/settings/security/password").get_data(as_text=True)
    assert "Google" not in sin
    database.accounts.update_one({"email_normalized": "ana@ejemplo.com"},
                                 {"$set": {"google_sub": "G-ANA"}})
    con = browser.get("/settings/security/password").get_data(as_text=True)
    assert "Google" in con and "Desconectar" in con


def test_agregar_un_metodo_viene_en_una_bandeja(client, database, outbox):
    browser = inside(client)
    pantalla = browser.get("/settings/billing/methods").get_data(as_text=True)
    assert 'data-open-dialog="agregar-metodo"' in pantalla
    assert '<dialog class="drawer drawer--slide" id="agregar-metodo"' in pantalla
    # Sin JavaScript, el enlace de siempre abre la lista en la misma pantalla.
    sin_js = browser.get("/settings/billing/methods?agregar=1").get_data(as_text=True)
    assert 'class="method-picker"' in sin_js
