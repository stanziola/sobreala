"""Configuración, una página por sección (octubre de 2026).

Cada sección se lee entera y sus partes son anclas: primero Cuenta y
Facturación, y después Seguridad, Notificaciones y las direcciones de prueba,
que se desplegaban en el menú. Lo que fijan estas pruebas: que cada sección
traiga todas sus partes, que las direcciones de antes caigan en su ancla, que un
formulario vuelva a su parte (también si algo falla), que Notificaciones guarde
todo con un botón sin apagar nada que no se dibujó, que un usuario de la empresa
no vea Usuarios, que Google solo salga conectado, y que agregar un método de
pago venga en una bandeja.
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


def test_seguridad_y_notificaciones_se_leen_enteras(client, database, outbox):
    """Octubre de 2026: sin desplegables, cada parte es un subtítulo con su
    ancla, y una dirección de antes lleva a la sección y baja a su parte."""
    browser = inside(client)
    seguridad = browser.get("/settings/security").get_data(as_text=True)
    assert 'class="settings__title">Seguridad<' in seguridad
    for parte, nombre in (("two-step", "Autenticación de múltiples factores"),
                          ("password", "Contraseña"), ("users", "Usuarios"),
                          ("sessions", "Sesiones")):
        assert f'id="{parte}">{nombre}<' in seguridad, parte
    avisos = browser.get("/settings/notifications").get_data(as_text=True)
    for parte, nombre in (("plan", "Plan y facturación"), ("security", "Seguridad")):
        assert f'id="{parte}">{nombre}<' in avisos, parte
    # Un solo «Guardar».
    assert avisos.count('class="btn" type="submit"') == 1

    for vieja, ancla in (("/settings/security/sessions", "/settings/security#sessions"),
                         ("/settings/security/two-step", "/settings/security#two-step"),
                         ("/settings/notifications/plan", "/settings/notifications#plan")):
        respuesta = browser.get(vieja)
        assert respuesta.status_code == 302, vieja
        assert respuesta.headers["Location"].endswith(ancla), vieja
    assert browser.get("/settings/security/inventada").headers["Location"].endswith(
        "/settings/security")


def test_cuenta_y_facturacion_se_leen_enteras(client, database, outbox):
    """Octubre de 2026: sin subsecciones, cada parte es un subtítulo con su ancla."""
    browser = inside(client)
    cuenta = browser.get("/settings/account").get_data(as_text=True)
    assert 'class="settings__title">Cuenta<' in cuenta
    for parte, nombre in (("profile", "Perfil"), ("contact", "Dirección y teléfonos"),
                          ("verification", "Verificación"), ("plan", "Tu plan")):
        assert f'id="{parte}">{nombre}<' in cuenta
    pagos = browser.get("/settings/billing").get_data(as_text=True)
    for parte, nombre in (("plan", "Tu plan"), ("methods", "Métodos de pago"),
                          ("auto-renewal", "Renovación automática"),
                          ("history", "Historial de compras")):
        assert f'id="{parte}">{nombre}<' in pagos
    # Una dirección de antes lleva a la sección y baja a su parte.
    vieja = browser.get("/settings/billing/methods?agregar=1")
    assert vieja.status_code == 302
    assert vieja.headers["Location"].endswith("/settings/billing?agregar=1#methods")
    assert browser.get("/settings/account/inventada").headers["Location"].endswith(
        "/settings/account")


def test_el_menu_no_se_despliega(client, database, outbox):
    """Una lista con íconos: sin flechas ni subsecciones, y la sección en la
    que se está marcada sin raya azul."""
    browser = inside(client)
    pantalla = browser.get("/settings/security").get_data(as_text=True)
    assert "data-settings-toggle" not in pantalla
    assert "settings-subnav" not in pantalla and "settings-nav__item" not in pantalla
    assert 'href="/settings/billing"' in pantalla
    assert 'is-current"\n       href="/settings/security" aria-current="page"' in pantalla


def test_los_avisos_de_siempre_salen_en_la_pagina_entera(client, database, outbox):
    """Las redirecciones de siempre traen su aviso, y la página entera lo
    enseña: antes elegían la subsección donde estaba."""
    browser = inside(client)
    assert "Listo, le mandamos la invitación a su correo." in browser.get(
        "/settings/security?user=invited").get_data(as_text=True)
    assert "notice notice--ok" in browser.get(
        "/settings/security?updated=1").get_data(as_text=True)


def test_un_formulario_vuelve_a_su_parte(client, database, outbox):
    browser = inside(client)
    bien = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings/account"),
        "address": "Apartado 0816-00001, Santiago, Veraguas"})
    assert bien.headers["Location"].endswith("/settings/account?address=1#address")
    # Con un error, se vuelve a dibujar con el campo abierto.
    mal = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings/account"), "address": "corta"})
    pantalla = mal.get_data(as_text=True)
    assert 'id="contact">Dirección y teléfonos<' in pantalla
    assert 'name="address"' in pantalla


def test_un_solo_guardar_para_todos_los_avisos(client, database, outbox):
    """Un formulario para toda la página: lo que no va marcado se apaga, lo
    marcado se enciende, y los de seguridad no se tocan."""
    browser = inside(client)
    browser.post("/settings/notifications", data={
        "csrf_token": csrf(browser, "/settings/notifications"),
        "billing": "on", "plan_state": "on"})  # sin new_login

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert accounts.wants(cuenta, accounts.NEW_LOGIN) is False
    assert accounts.wants(cuenta, accounts.BILLING) is True


def test_un_usuario_de_la_empresa_no_ve_usuarios(client, database, outbox):
    _, _, suyo = as_member(client, database, outbox=outbox)

    pantalla = suyo.get("/settings/security").get_data(as_text=True)
    assert 'id="users"' not in pantalla
    # La dirección de antes lo deja en Seguridad, sin bajar a Usuarios.
    assert suyo.get("/settings/security/users").headers["Location"].endswith(
        "/settings/security")


def test_google_solo_sale_conectado(client, database, outbox):
    browser = inside(client)
    sin = browser.get("/settings/security").get_data(as_text=True)
    assert "Google" not in sin
    database.accounts.update_one({"email_normalized": "ana@ejemplo.com"},
                                 {"$set": {"google_sub": "G-ANA"}})
    con = browser.get("/settings/security").get_data(as_text=True)
    assert "Google" in con and "Desconectar" in con


def test_agregar_un_metodo_viene_en_una_bandeja(client, database, outbox):
    browser = inside(client)
    pantalla = browser.get("/settings/billing").get_data(as_text=True)
    assert 'data-open-dialog="agregar-metodo"' in pantalla
    assert '<dialog class="drawer drawer--slide" id="agregar-metodo"' in pantalla
    # Sin JavaScript, el enlace de siempre abre la lista en la misma pantalla.
    sin_js = browser.get("/settings/billing?agregar=1").get_data(as_text=True)
    assert 'class="method-picker"' in sin_js
