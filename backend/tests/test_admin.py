"""El panel de administración: quién entra, qué decide y qué no puede ver.

Tres cosas se fijan aquí. Que la puerta no se abra ni se anuncie a quien no
tiene el rol. Que toda decisión sobre la cuenta de otro quede escrita con su
motivo, porque meses después esa frase es la única respuesta honesta a «por qué
me suspendieron». Y que la ficha de un cliente enseñe cifras, no la lista de
direcciones de sus contactos.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone

import pyotp
from conftest import login, register

from models import account as accounts
from models import admin_event as decisions
from models import contact as contacts

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def csrf(client, url="/dashboard"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def turn_on_two_step(browser):
    # Dos pasos: primero la contraseña, después el QR.
    browser.get("/account/two-factor")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    browser.post("/account/two-factor", data={"csrf_token": token, "password": PASSWORD})
    browser.get("/account/two-factor/enable")
    with browser.session_transaction() as sess:
        secret, token = sess["two_factor_setup"], sess["_csrf"]
    browser.post("/account/two-factor/enable", data={
        "csrf_token": token, "code": list(pyotp.TOTP(secret).now())})


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


def make_client_account(client, database, email="socia@ejemplo.com", *,
                        abierta=True):
    register(other(client), email=email, abierta=abierta)
    browser = other(client)
    login(browser, email=email)
    return browser, accounts.by_email(database, email)


def update(admin, database, cliente, *, plan="", ciclo="monthly",
           suspendida=None, motivo="por algo"):
    """Actualizar una cuenta como lo hace la pantalla: un solo formulario.

    Los campos viajan siempre, cambien o no, porque el formulario los dibuja
    todos. Lo que no se pasa aquí se toma de como está la cuenta. Ya no hay
    casilla para aprobar ni para activar: estar activa es el efecto de un pago.
    """
    ahora = accounts.by_id(database, cliente["_id"])
    if suspendida is None:
        suspendida = accounts.is_suspended(ahora)
    data = {"csrf_token": csrf(admin, "/admin/"), "cycle": ciclo,
            "plan": (ahora.get("plan", "") or "") if plan == "" else (plan or ""),
            "reason": motivo}
    if suspendida:
        data["suspendida"] = "1"
    return admin.post(f"/admin/accounts/{cliente['_id']}/update", data=data)


def upload_piece(database, cliente, nombre="Boletín"):
    """Una pieza HTML de las que subían los clientes. Ya no se suben, pero las
    que existen siguen en la lista del administrador."""
    from models import design as designs

    return designs.save(database, cliente["_id"], name=nombre,
                        html="<html><body><h1>Hola</h1></body></html>",
                        uploaded_by=cliente["_id"])


def open_account(admin, cliente, motivo="hicimos la demo, el RUC existe"):
    """Abrir la cuenta después de la demostración, que es la única aprobación
    que queda."""
    return admin.post(f"/admin/accounts/{cliente['_id']}/open", data={
        "csrf_token": csrf(admin, "/admin/"), "reason": motivo})


RUTAS = ("/admin/", "/admin/accounts")


# ----------------------------------------------------------------- la puerta

def test_sin_rol_la_administracion_no_existe(client, database, outbox):
    """404 y no 403: un 403 le confirma a un curioso que la dirección existe."""
    browser, _ = make_client_account(client, database, "sola@ejemplo.com")

    for ruta in RUTAS:
        assert browser.get(ruta).status_code == 404


def test_sin_rol_el_menu_no_ensena_la_fila(client, database, outbox):
    browser, _ = make_client_account(client, database, "sola@ejemplo.com")
    assert "Administración" not in browser.get("/dashboard").get_data(as_text=True)


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
    assert "two-factor" in respuesta.headers["Location"]


def test_con_rol_y_doble_factor_entra(client, database, outbox):
    browser, _ = make_admin(client, database)

    pantalla = browser.get("/admin/")
    assert pantalla.status_code == 200
    assert "Estadísticas" in pantalla.get_data(as_text=True)


# ------------------------------------------------------------ las decisiones

def test_suspender_deja_escrito_el_motivo_y_quien_fue(client, database, outbox):
    admin, jefe = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    update(admin, database, cliente, suspendida=True,
           motivo="rebotes por encima del 3%")

    despues = accounts.by_id(database, cliente["_id"])
    assert despues["status"] == accounts.SUSPENDED

    escrito = decisions.for_account(database, cliente["_id"])
    assert len(escrito) == 1
    assert escrito[0]["before"] == accounts.REGISTERED
    assert escrito[0]["after"] == accounts.SUSPENDED
    assert escrito[0]["admin_id"] == jefe["_id"]
    assert "rebotes" in escrito[0]["reason"]


def test_sin_motivo_no_se_cambia_nada(client, database, outbox):
    """El motivo no es papeleo: es lo que se lee cuando alguien reclame."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    respuesta = update(admin, database, cliente, suspendida=True, motivo="   ")

    assert accounts.by_id(database, cliente["_id"])["status"] == accounts.REGISTERED
    assert decisions.for_account(database, cliente["_id"]) == []
    assert "missing=reason" in respuesta.headers["Location"]


def test_un_plan_inventado_no_se_aplica(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    update(admin, database, cliente, plan="infinito", motivo="a ver si cuela")

    despues = accounts.by_id(database, cliente["_id"])
    assert despues.get("plan") is None
    assert decisions.for_account(database, cliente["_id"]) == []


# ------------------------------------------------------------- la suspensión

def test_una_cuenta_suspendida_no_puede_entrar(client, database, outbox):
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    update(admin, database, cliente, suspendida=True,
           motivo="rebotes por encima del 3%")

    # La sesión que ya tenía abierta se cierra con ella.
    assert navegador.get("/dashboard").status_code == 302

    de_nuevo = other(client)
    respuesta = login(de_nuevo, email="socia@ejemplo.com")
    assert respuesta.status_code == 200
    assert "suspendida" in respuesta.get_data(as_text=True)
    assert de_nuevo.get("/dashboard").status_code == 302


def test_al_levantar_la_suspension_vuelve_a_entrar(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    for suspendida, motivo in ((True, "impago"), (False, "pagó, resuelto")):
        update(admin, database, cliente, suspendida=suspendida, motivo=motivo)

    navegador = other(client)
    assert login(navegador, email="socia@ejemplo.com").status_code == 302
    assert navegador.get("/dashboard").status_code == 200
    assert len(decisions.for_account(database, cliente["_id"])) == 2


# ------------------------------------------------------------------ el plan

def test_cambiar_el_plan_cambia_el_limite_de_contactos(client, database, outbox):
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    # Sin plan, el del Básico: así que el que cambia el número es el Negocio.
    assert accounts.contact_limit(cliente) == 1000

    update(admin, database, cliente, plan="negocio", ciclo="yearly",
           motivo="pagó el Negocio anual por transferencia")

    despues = accounts.by_id(database, cliente["_id"])
    assert despues["plan"] == "negocio"
    assert accounts.contact_limit(despues) == 3000
    # Ponerlo a mano hace lo mismo que un pago: activa y con vencimiento, no un
    # plan suelto que no vence nunca.
    assert despues["status"] == accounts.ACTIVE
    assert accounts.plan_until(despues) is not None
    # Y la pantalla del cliente lo dice sin que nadie la toque.
    assert "de 3000 contactos" in navegador.get("/contacts").get_data(as_text=True)


# ------------------------------------------------------------------ la ficha

def test_la_ficha_ensena_cifras_y_no_direcciones(client, database, outbox):
    """La lista de contactos es del cliente y de quien está en ella."""
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    # La etiqueta se crea antes de poder elegirla.
    navegador.get("/contacts/tags")
    with navegador.session_transaction() as sess:
        token = sess["_csrf"]
    navegador.post("/contacts/tags/new",
                   data={"csrf_token": token, "tag": "socios"})

    navegador.get("/contacts/import")
    with navegador.session_transaction() as sess:
        token = sess["_csrf"]
    navegador.post("/contacts/import", data={
        "csrf_token": token, "source": contacts.MEMBERS, "tags": ["socios"],
        "note": "", "archivo": (io.BytesIO(b"correo\nana@coop.com\nbea@coop.com\n"),
                                "socios.csv"),
    }, content_type="multipart/form-data")

    ficha = admin.get(f"/admin/accounts/{cliente['_id']}").get_data(as_text=True)

    # La cifra sí, el origen que declaró también, las direcciones no.
    assert "2 / 1000" in ficha
    assert "socios.csv" in ficha
    assert "socios de la organización" in ficha or "socios" in ficha
    assert "ana@coop.com" not in ficha
    assert "bea@coop.com" not in ficha


def test_una_cuenta_que_no_existe_da_404(client, database, outbox):
    admin, _ = make_admin(client, database)
    assert admin.get("/admin/accounts/000000000000000000000000").status_code == 404
    assert admin.get("/admin/accounts/no-es-un-id").status_code == 404


# ------------------------------------------------------------------ el rol

def test_toda_cuenta_nace_con_su_rol(client, database, outbox):
    """Un campo que a veces está y a veces no es fácil de equivocar."""
    register(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")

    assert cuenta["role"] == accounts.CLIENT
    assert not accounts.is_admin(cuenta)


def test_quitar_el_rol_deja_client_y_no_un_hueco(client, database, outbox):
    _, jefe = make_admin(client, database)
    accounts.set_role(database, jefe["_id"], None)

    despues = accounts.by_id(database, jefe["_id"])
    assert despues["role"] == accounts.CLIENT
    assert not accounts.is_admin(despues)


def test_un_rol_mal_escrito_no_es_administrador(client, database, outbox):
    """Lo que decide es la comparación exacta, no que el campo tenga algo."""
    browser, cuenta = make_client_account(client, database, "casi@ejemplo.com")
    database.accounts.update_one({"_id": cuenta["_id"]},
                                 {"$set": {"role": "Admin"}})

    assert not accounts.is_admin(accounts.by_id(database, cuenta["_id"]))
    assert browser.get("/admin/").status_code == 404


def test_la_tabla_filtra_por_estado(client, database, outbox):
    admin, _ = make_admin(client, database)
    make_client_account(client, database, "una@ejemplo.com")
    _, dos = make_client_account(client, database, "dos@ejemplo.com")
    accounts.set_status(database, dos["_id"], accounts.ACTIVE)

    activas = admin.get("/admin/accounts?status=active").get_data(as_text=True)
    assert "dos@ejemplo.com" in activas
    assert "una@ejemplo.com" not in activas


# ------------------------------------------------- un solo botón de actualizar

def test_cambiar_plan_y_suspension_a_la_vez_deja_dos_lineas_con_el_mismo_motivo(
        client, database, outbox):
    """admin_events guarda una por cosa cambiada: así se sigue leyendo."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    update(admin, database, cliente, plan="negocio", suspendida=True,
           motivo="pagó el Negocio y a la vez se le fue en rebotes")

    despues = accounts.by_id(database, cliente["_id"])
    # La suspensión va después del plan, así que le gana: poner un plan deja la
    # cuenta activa y esto tiene que poder apagarla en el mismo envío.
    assert despues["status"] == accounts.SUSPENDED
    assert despues["plan"] == "negocio"

    escrito = decisions.for_account(database, cliente["_id"])
    assert len(escrito) == 2
    assert {row["kind"] for row in escrito} == {decisions.STATUS, decisions.PLAN}
    assert all("rebotes" in row["reason"] for row in escrito)


def test_actualizar_sin_cambiar_nada_no_escribe_una_decision(client, database,
                                                             outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    update(admin, database, cliente, motivo="por mirar")

    assert decisions.for_account(database, cliente["_id"]) == []


# ------------------------------------------------------------- la actividad

def test_la_actividad_trae_entradas_importaciones_pagos_y_decisiones(
        client, database, outbox):
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database, abierta=False)
    open_account(admin, cliente, motivo="hablé con la junta")

    navegador.get("/contacts/import")
    with navegador.session_transaction() as sess:
        token = sess["_csrf"]
    navegador.post("/contacts/import", data={
        "csrf_token": token, "source": "members", "note": "",
        "archivo": (io.BytesIO(b"correo\nana@coop.com\n"), "socios.csv")},
        content_type="multipart/form-data")

    ficha = admin.get(f"/admin/accounts/{cliente['_id']}").get_data(as_text=True)
    assert "Actividad" in ficha
    assert "Entró a la cuenta" in ficha          # de auth_events
    assert "socios.csv" in ficha                 # de imports
    assert "hablé con la junta" in ficha         # de admin_events
    # Y lo que no cambia: las direcciones de sus contactos no se enseñan.
    assert "ana@coop.com" not in ficha


def enviada(database, cliente, subject="Asamblea de marzo", cuantas=1):
    """Una campaña guardada y sus envíos, con una dirección dentro para
    comprobar que no se dibuja."""
    momento = datetime.now(timezone.utc)
    campana = database.campaigns.insert_one({
        "account_id": cliente["_id"], "subject": subject, "tag": "",
        "status": "sent", "position": 3, "total": 3,
        "sent": 2, "skipped": 1, "failed": 0, "errors": [],
        "created_at": momento, "updated_at": momento,
        "scheduled_at": momento, "started_at": momento,
        "finished_at": momento}).inserted_id
    for _ in range(cuantas):
        database.campaign_runs.insert_one({
            "account_id": cliente["_id"], "campaign_id": campana,
            "subject": subject, "tag": "", "total": 3,
            "sent": 2, "skipped": 1, "failed": 0,
            "errors": [{"email": "ana@coop.com", "error": "no salió"}],
            "started_at": momento, "finished_at": momento})


def cobrado(database, cliente, plan="negocio"):
    momento = datetime.now(timezone.utc)
    database.payments.insert_one({
        "account_id": cliente["_id"], "plan": plan, "cycle": "monthly",
        "amount": "60.00", "currency": "USD", "order_id": "ORDEN-1",
        "status": "completed", "created_at": momento, "updated_at": momento})


def test_la_actividad_ensena_las_campanas_y_no_a_quien_salieron(
        client, database, outbox):
    """Mandar una campaña es actividad de la cuenta como entrar o pagar, y de
    ella se dicen cifras: cuántos salieron, nunca a quiénes."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)
    enviada(database, cliente)

    ficha = admin.get(f"/admin/accounts/{cliente['_id']}").get_data(as_text=True)
    assert "Asamblea de marzo" in ficha
    assert "2 salieron" in ficha
    assert "ana@coop.com" not in ficha


def test_una_campana_mandada_dos_veces_son_dos_lineas(client, database, outbox):
    """La que sale cada mes no es una cosa que pasó una vez."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)
    enviada(database, cliente, subject="Boletín", cuantas=2)

    ficha = admin.get(
        f"/admin/accounts/{cliente['_id']}?activity=emails").get_data(as_text=True)
    assert ficha.count("Envió «Boletín»") == 2


def test_el_filtro_de_actividad_deja_solo_lo_que_se_pide(
        client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)
    cobrado(database, cliente)
    enviada(database, cliente)

    entera = admin.get(f"/admin/accounts/{cliente['_id']}").get_data(as_text=True)
    assert "Entró a la cuenta" in entera
    assert "Pagó el plan Negocio" in entera
    assert "Asamblea de marzo" in entera

    pagos = admin.get(
        f"/admin/accounts/{cliente['_id']}?activity=payments").get_data(as_text=True)
    assert "Pagó el plan Negocio" in pagos
    assert "Entró a la cuenta" not in pagos
    assert "Asamblea de marzo" not in pagos

    correos = admin.get(
        f"/admin/accounts/{cliente['_id']}?activity=emails").get_data(as_text=True)
    assert "Asamblea de marzo" in correos
    assert "Pagó el plan Negocio" not in correos


def test_un_tipo_de_actividad_inventado_se_mira_como_todo(
        client, database, outbox):
    """La dirección la escribe cualquiera, y una página vacía por una letra de
    más parecería que la cuenta no ha hecho nada."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)
    cobrado(database, cliente)

    ficha = admin.get(
        f"/admin/accounts/{cliente['_id']}?activity=inventado").get_data(as_text=True)
    assert "Entró a la cuenta" in ficha
    assert "Pagó el plan Negocio" in ficha


def test_la_actividad_no_ensena_las_direcciones_de_sus_contactos(
        client, database, outbox):
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)
    navegador.get("/contacts/import")
    with navegador.session_transaction() as sess:
        token = sess["_csrf"]
    navegador.post("/contacts/import", data={
        "csrf_token": token, "source": "members", "note": "",
        "archivo": (io.BytesIO(b"correo\nbea@coop.com\ncarlos@coop.com\n"),
                    "lista.csv")},
        content_type="multipart/form-data")

    ficha = admin.get(f"/admin/accounts/{cliente['_id']}").get_data(as_text=True)
    assert "bea@coop.com" not in ficha
    assert "carlos@coop.com" not in ficha


def test_lo_decidido_se_lee_en_la_ficha_de_la_cuenta(client, database, outbox):
    """Ya no hay portada con «últimas decisiones»: cada ficha tiene la suya."""
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database, abierta=False)
    open_account(admin, cliente, motivo="revisé su lista")

    ficha = admin.get(f"/admin/accounts/{cliente['_id']}").get_data(as_text=True)
    assert "Actividad" in ficha
    assert "Se abrió la cuenta" in ficha
    assert "revisé su lista" in ficha


# ----------------------------------------------------------- dónde se aterriza

def test_todos_aterrizan_en_el_sitio(client, database, outbox):
    """Una sola regla: entrar lleva al sitio, administre o no.

    A administracion se llega con el menu, que para esa cuenta la tiene de
    primera fila. Antes eran dos reglas para el mismo momento y se notaba al
    saltar entre cuentas: una te dejaba en un sitio y la otra en otro.
    """
    from config import Config

    admin, _ = make_admin(client, database)
    assert admin.get("/login").headers["Location"] == Config.PUBLIC_SITE_URL

    navegador, _ = make_client_account(client, database)
    assert navegador.get("/login").headers["Location"] == Config.PUBLIC_SITE_URL


def test_aterrizar_en_el_sitio_no_le_abre_las_pantallas_de_cliente(
        client, database, outbox):
    """Aterrizar es una cosa y la puerta es otra: su cuenta sigue sin panel."""
    admin, _ = make_admin(client, database)

    respuesta = admin.get("/dashboard")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/admin/")


# ----------------------------------------------------- la cola de plantillas

def test_la_lista_ensena_de_quien_es_cada_pieza(client, database, outbox):
    """Ya no es una cola: nadie aprueba una pieza a mano."""
    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)
    upload_piece(database, cliente)

    lista = admin.get("/admin/templates").get_data(as_text=True)
    assert accounts.by_id(database, cliente["_id"])["company_name"] in lista
    assert "Boletín" in lista
    # Y no hay nada que pulsar para aprobarla o rechazarla.
    assert "Aprobar" not in lista
    assert "Rechazar" not in lista


def test_el_archivo_no_se_sirve_como_html(client, database, outbox):
    """Bajarlo, no dibujarlo: es el documento de otro y esta sesión es la que
    puede abrir y suspender las cuentas de todo el mundo."""
    from models import design as designs

    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)
    upload_piece(database, cliente)
    subida = designs.for_account(database, cliente["_id"])[0]

    respuesta = admin.get(f"/admin/templates/{subida['_id']}/file")
    assert respuesta.mimetype == "text/plain"
    assert "attachment" in respuesta.headers["Content-Disposition"]


def test_la_cola_no_existe_para_quien_no_es_administrador(client, database,
                                                          outbox):
    navegador, _ = make_client_account(client, database)
    assert navegador.get("/admin/templates").status_code == 404


# ------------------------------------ el administrador solo administra

def test_las_pantallas_de_cliente_lo_devuelven_a_administracion(client,
                                                                database,
                                                                outbox):
    """Una cuenta de administrador no tiene contactos ni plantillas."""
    admin, _ = make_admin(client, database)

    for url in ("/dashboard", "/contacts", "/contacts/import",
                "/contacts/tags", "/templates"):
        respuesta = admin.get(url)
        assert respuesta.status_code == 302, url
        assert respuesta.headers["Location"].endswith("/admin/"), url


def test_su_menu_no_trae_las_filas_de_cliente(client, database, outbox):
    admin, _ = make_admin(client, database)

    menu = admin.get("/admin/").get_data(as_text=True)
    assert "Administración" in menu
    assert "Configuración" in menu
    assert ">Contactos<" not in menu
    assert ">Plantillas<" not in menu


def test_estadisticas_no_lleva_menu_de_secciones(client, database, outbox):
    """Es la misma pantalla que ve el cliente, así que se ve igual: suelta.

    Tuvo una pestaña dentro de administración y se quitó cuando ganó su propia
    fila en el menú de la cuenta; llegar dos veces al mismo sitio sobra, y el
    menú de secciones al lado la hacía distinta de la del cliente.
    """
    admin, _ = make_admin(client, database)
    make_client_account(client, database)

    suelta = admin.get("/admin/").get_data(as_text=True)
    assert "settings__tab" not in suelta

    con_pestanas = admin.get("/admin/accounts").get_data(as_text=True)
    pestanas = re.findall(r'class="settings__tab[^"]*"[^>]*>\s*([^<]+)',
                          con_pestanas)
    assert [p.strip() for p in pestanas] == [
        "Cuentas", "Clientes", "Plantillas subidas", "Correos del sistema"]


def test_su_menu_lleva_estadisticas_encima_de_administracion(client, database,
                                                             outbox):
    """Dos filas y dos destinos: si llevaran al mismo, una sobraría."""
    admin, _ = make_admin(client, database)
    menu = admin.get("/admin/").get_data(as_text=True)
    panel = menu[menu.index('class="menu__panel"'):]

    filas = re.findall(r'<a class="menu__item" href="([^"]+)">.*?<span>([^<]+)</span>',
                       panel, re.S)
    hasta_configuracion = [texto for _, texto in filas][:2]
    assert hasta_configuracion == ["Estadísticas", "Administración"]

    destinos = dict((texto, href) for href, texto in filas)
    assert destinos["Estadísticas"].endswith("/admin/")
    assert destinos["Administración"].endswith("/admin/accounts")


def test_su_configuracion_es_seguridad_y_notificaciones(client, database, outbox):
    """Cuenta y Facturación no significan nada en una cuenta que no
    compra. Seguridad sí, y Notificaciones con su propia lista."""
    admin, _ = make_admin(client, database)

    respuesta = admin.get("/settings")
    assert respuesta.headers["Location"].endswith("/settings/security")

    pantalla = admin.get("/settings/security").get_data(as_text=True)
    assert "Contraseña" in pantalla
    assert "Facturación" not in pantalla

    avisos = admin.get("/settings/notifications").get_data(as_text=True)
    assert 'name="admin_signup"' in avisos
    # Y ninguno de los de un cliente, que no recibiría nunca.
    assert 'name="campaigns"' not in avisos

    # Y la de pagos no se abre escribiéndola a mano.
    assert admin.get("/settings/billing").headers["Location"].endswith(
        "/settings/security")


def test_un_administrador_no_contrata_un_plan(client, database, outbox):
    admin, jefe = make_admin(client, database)

    admin.post("/settings/billing/checkout", data={
        "csrf_token": csrf(admin, "/admin/"), "plan": "basico",
        "cycle": "monthly"})

    assert database.payments.count_documents({}) == 0
    assert accounts.by_id(database, jefe["_id"]).get("plan") is None


def test_un_cliente_sigue_llegando_a_todo(client, database, outbox):
    """La que importa: el riesgo del cambio es cortarle algo a quien sí lo usa."""
    navegador, _ = make_client_account(client, database)

    for url in ("/dashboard", "/contacts", "/templates"):
        assert navegador.get(url).status_code == 200, url

    menu = navegador.get("/dashboard").get_data(as_text=True)
    assert ">Contactos<" in menu
    assert ">Plantillas<" in menu
    assert "Administración" not in menu

    pagos = navegador.get("/settings/billing").get_data(as_text=True)
    assert "Facturación" in pagos


def test_la_lista_de_cuentas_no_trae_administradores(client, database, outbox):
    """No son clientes: no compran ni envían, y no hay nada que decidir sobre
    ellas. Salían en la lista y, como un administrador no paga nunca, se
    quedaban en «registrada» para siempre."""
    admin, jefe = make_admin(client, database)
    _, cliente = make_client_account(client, database)

    lista = admin.get("/admin/accounts").get_data(as_text=True)
    assert cliente["email"] in lista
    assert jefe["email"] not in lista


# ----------------------------- un estado que el código ya no conoce

def test_un_estado_viejo_no_rompe_la_pantalla(client, database, outbox):
    """`approved` existió hasta que se quitó la aprobación de cuentas.

    El valor quedó escrito en las cuentas que lo tenían, y la interfaz busca el
    texto de un estado por su nombre: uno que no está en la tabla de
    traducciones reventaba la página entera. Se lee como Registrada.
    """
    admin, _ = make_admin(client, database)
    _, cliente = make_client_account(client, database)
    database.accounts.update_one({"_id": cliente["_id"]},
                                 {"$set": {"status": "approved"}})

    tabla = admin.get("/admin/accounts")
    assert tabla.status_code == 200
    assert "Registrada" in tabla.get_data(as_text=True)

    ficha = admin.get(f"/admin/accounts/{cliente['_id']}")
    assert ficha.status_code == 200
    assert "Registrada" in ficha.get_data(as_text=True)

    # Y la del propio cliente, que ya no enseña su estado en Configuración
    # (octubre de 2026), pero tampoco revienta con el valor viejo.
    navegador = other(client)
    login(navegador, email="socia@ejemplo.com")
    suya = navegador.get("/settings/account")
    assert suya.status_code == 200
    assert "Estado de tu cuenta" not in suya.get_data(as_text=True)


# ------------------------- el administrador tampoco contrata desde /pricing

def test_un_administrador_que_abre_contratar_vuelve_a_administracion(
        client, database, outbox):
    admin, _ = make_admin(client, database)

    respuesta = admin.get("/checkout/basico")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/admin/")
    assert database.payments.count_documents({}) == 0


def test_un_administrador_no_ve_la_bienvenida(client, database, outbox):
    """Es una pantalla de cliente, y su cuenta no tiene plan que elegir."""
    admin, _ = make_admin(client, database)

    respuesta = admin.get("/welcome")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/admin/")


def test_la_migaja_del_sitio_publico_dice_el_rol(client, database, outbox,
                                                 monkeypatch):
    """El sitio es estático y en otro dominio: lo único que sabe es esa migaja.

    Sin el rol le ofrecía a un administrador el panel de envíos y los
    contactos, que su cuenta no tiene.

    La migaja se pone en el dominio padre de los dos despliegues; aquí se apunta
    a localhost para que el navegador de prueba, que vive ahí, la acepte.
    """
    from config import Config
    monkeypatch.setattr(Config, "PUBLIC_SITE_URL", "http://localhost")

    admin, _ = make_admin(client, database)
    navegador, cliente = make_client_account(client, database)

    admin.get("/admin/")
    assert admin.get_cookie("sa_in").value == "admin"

    navegador.get("/dashboard")
    assert navegador.get_cookie("sa_in").value == "1"

    # Con plan lleva también cuál, para que /pricing pueda apagar los menores.
    accounts.set_plan(database, cliente["_id"], "negocio")
    navegador.get("/dashboard")
    assert navegador.get_cookie("sa_in").value == "1:negocio:monthly"

    # Vencido ya no va: es cuando se vuelve a comprar desde /pricing.
    from datetime import timedelta
    database.accounts.update_one({"_id": cliente["_id"]}, {"$set": {
        "plan_until": accounts.now() - timedelta(days=1)}})
    navegador.get("/dashboard")
    assert navegador.get_cookie("sa_in").value == "1"
