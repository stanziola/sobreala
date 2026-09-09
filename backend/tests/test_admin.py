"""El panel de administración: quién entra, qué decide y qué no puede ver.

Tres cosas se fijan aquí. Que la puerta no se abra ni se anuncie a quien no
tiene el rol. Que toda decisión sobre la cuenta de otro quede escrita con su
motivo, porque meses después esa frase es la única respuesta honesta a «por qué
me suspendieron». Y que la ficha de un cliente enseñe cifras, no la lista de
direcciones de sus contactos.
"""

from __future__ import annotations

import io

import pyotp
from conftest import login, register

from models import account as accounts
from models import admin_event as decisions
from models import contact as contacts

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def csrf(client, url="/panel"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def turn_on_two_step(browser):
    browser.get("/cuenta/dos-pasos")
    with browser.session_transaction() as sess:
        secret, token = sess["two_factor_setup"], sess["_csrf"]
    browser.post("/cuenta/dos-pasos", data={
        "csrf_token": token, "action": "enable", "password": PASSWORD,
        "code": list(pyotp.TOTP(secret).now())})


def make_admin(client, database, email="jefe@ejemplo.com"):
    """Un administrador: la cuenta, el rol a mano y el doble factor puesto."""
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    cuenta = accounts.by_email(database, email)
    database.accounts.update_one({"_id": cuenta["_id"]},
                                 {"$set": {"email_confirmed_at": cuenta["created_at"]}})
    accounts.set_role(database, cuenta["_id"], accounts.ADMIN)
    turn_on_two_step(browser)
    return browser, accounts.by_email(database, email)


def make_client_account(client, database, email="socia@ejemplo.com"):
    register(other(client), email=email)
    browser = other(client)
    login(browser, email=email)
    return browser, accounts.by_email(database, email)


RUTAS = ("/admin/", "/admin/cuentas")


# ----------------------------------------------------------------- la puerta

def test_sin_rol_la_administracion_no_existe(client, database, outbox):
    """404 y no 403: un 403 le confirma a un curioso que la dirección existe."""
    browser, _ = make_client_account(client, database, "sola@ejemplo.com")

    for ruta in RUTAS:
        assert browser.get(ruta).status_code == 404


def test_sin_rol_el_menu_no_ensena_la_fila(client, database, outbox):
    browser, _ = make_client_account(client, database, "sola@ejemplo.com")
    assert "Administración" not in browser.get("/panel").get_data(as_text=True)


def test_sin_sesion_lleva_a_entrar(client, database):
    assert client.get("/admin/").status_code == 302


def test_con_rol_pero_sin_doble_factor_pide_activarlo(client, database, outbox):
    register(client, email="jefe@ejemplo.com")
    browser = other(client)
    login(browser, email="jefe@ejemplo.com")
    accounts.set_role(database, accounts.by_email(database, "jefe@ejemplo.com")["_id"],
                      accounts.ADMIN)

    respuesta = browser.get("/admin/")
    assert respuesta.status_code == 302
    assert "dos-pasos" in respuesta.headers["Location"]


def test_con_rol_y_doble_factor_entra(client, database, outbox):
    browser, _ = make_admin(client, database)

    pantalla = browser.get("/admin/")
    assert pantalla.status_code == 200
    assert "Esperando aprobación" in pantalla.get_data(as_text=True)
    assert "Administración" in browser.get("/panel").get_data(as_text=True)


# ------------------------------------------------------------ las decisiones

def test_aprobar_deja_escrito_el_motivo_y_quien_fue(client, database, outbox):
    admin, jefe = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    admin.post(f"/admin/cuentas/{cliente['_id']}/estado", data={
        "csrf_token": csrf(admin, "/admin/"), "estado": accounts.APPROVED,
        "motivo": "hablé con la tesorera, la lista es de sus socios"})

    despues = accounts.by_id(database, cliente["_id"])
    assert despues["status"] == accounts.APPROVED

    escrito = decisions.for_account(database, cliente["_id"])
    assert len(escrito) == 1
    assert escrito[0]["before"] == accounts.REGISTERED
    assert escrito[0]["after"] == accounts.APPROVED
    assert escrito[0]["admin_id"] == jefe["_id"]
    assert "tesorera" in escrito[0]["reason"]


def test_sin_motivo_no_se_cambia_nada(client, database, outbox):
    """El motivo no es papeleo: es lo que se lee cuando alguien reclame."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    respuesta = admin.post(f"/admin/cuentas/{cliente['_id']}/estado", data={
        "csrf_token": csrf(admin, "/admin/"), "estado": accounts.SUSPENDED,
        "motivo": "   "})

    assert accounts.by_id(database, cliente["_id"])["status"] == accounts.REGISTERED
    assert decisions.for_account(database, cliente["_id"]) == []
    assert "falta=motivo" in respuesta.headers["Location"]


def test_un_estado_inventado_no_se_aplica(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    admin.post(f"/admin/cuentas/{cliente['_id']}/estado", data={
        "csrf_token": csrf(admin, "/admin/"), "estado": "jefe",
        "motivo": "a ver si cuela"})

    assert accounts.by_id(database, cliente["_id"])["status"] == accounts.REGISTERED


# ------------------------------------------------------------- la suspensión

def test_una_cuenta_suspendida_no_puede_entrar(client, database, outbox):
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    admin.post(f"/admin/cuentas/{cliente['_id']}/estado", data={
        "csrf_token": csrf(admin, "/admin/"), "estado": accounts.SUSPENDED,
        "motivo": "rebotes por encima del 3%"})

    # La sesión que ya tenía abierta se cierra con ella.
    assert navegador.get("/panel").status_code == 302

    de_nuevo = other(client)
    respuesta = login(de_nuevo, email="socia@ejemplo.com")
    assert respuesta.status_code == 200
    assert "suspendida" in respuesta.get_data(as_text=True)
    assert de_nuevo.get("/panel").status_code == 302


def test_al_levantar_la_suspension_vuelve_a_entrar(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    for estado, motivo in ((accounts.SUSPENDED, "impago"),
                           (accounts.APPROVED, "pagó, resuelto")):
        admin.post(f"/admin/cuentas/{cliente['_id']}/estado", data={
            "csrf_token": csrf(admin, "/admin/"), "estado": estado,
            "motivo": motivo})

    navegador = other(client)
    assert login(navegador, email="socia@ejemplo.com").status_code == 302
    assert navegador.get("/panel").status_code == 200
    assert len(decisions.for_account(database, cliente["_id"])) == 2


# ------------------------------------------------------------------ el plan

def test_cambiar_el_plan_cambia_el_limite_de_contactos(client, database, outbox):
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    assert accounts.contact_limit(cliente) == 500

    admin.post(f"/admin/cuentas/{cliente['_id']}/plan", data={
        "csrf_token": csrf(admin, "/admin/"), "plan": "basico",
        "motivo": "contrató el Básico anual"})

    despues = accounts.by_id(database, cliente["_id"])
    assert despues["plan"] == "basico"
    assert accounts.contact_limit(despues) == 1000
    # Y la pantalla del cliente lo dice sin que nadie la toque.
    assert "de 1000 contactos" in navegador.get("/contactos").get_data(as_text=True)


def test_un_plan_inventado_no_se_aplica(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    admin.post(f"/admin/cuentas/{cliente['_id']}/plan", data={
        "csrf_token": csrf(admin, "/admin/"), "plan": "infinito",
        "motivo": "a ver"})

    assert accounts.by_id(database, cliente["_id"]).get("plan") is None


# ------------------------------------------------------------------ la ficha

def test_la_ficha_ensena_cifras_y_no_direcciones(client, database, outbox):
    """La lista de contactos es del cliente y de quien está en ella."""
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    navegador.get("/contactos/importar")
    with navegador.session_transaction() as sess:
        token = sess["_csrf"]
    navegador.post("/contactos/importar", data={
        "csrf_token": token, "source": contacts.MEMBERS, "tags": "socios",
        "note": "", "archivo": (io.BytesIO(b"correo\nana@coop.com\nbea@coop.com\n"),
                                "socios.csv"),
    }, content_type="multipart/form-data")

    ficha = admin.get(f"/admin/cuentas/{cliente['_id']}").get_data(as_text=True)

    # La cifra sí, el origen que declaró también, las direcciones no.
    assert "2 / 500" in ficha
    assert "socios.csv" in ficha
    assert "socios de la organización" in ficha or "socios" in ficha
    assert "ana@coop.com" not in ficha
    assert "bea@coop.com" not in ficha


def test_una_cuenta_que_no_existe_da_404(client, database, outbox):
    admin, _ = make_admin(client, database)
    assert admin.get("/admin/cuentas/000000000000000000000000").status_code == 404
    assert admin.get("/admin/cuentas/no-es-un-id").status_code == 404


def test_la_tabla_filtra_por_estado(client, database, outbox):
    admin, _ = make_admin(client, database)
    make_client_account(client, database, "una@ejemplo.com")
    _, dos = make_client_account(client, database, "dos@ejemplo.com")
    accounts.set_status(database, dos["_id"], accounts.ACTIVE)

    activas = admin.get("/admin/cuentas?estado=active").get_data(as_text=True)
    assert "dos@ejemplo.com" in activas
    assert "una@ejemplo.com" not in activas
