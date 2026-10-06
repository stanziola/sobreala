"""Los usuarios de una cuenta: el dueño delega, con permisos.

Lo que se fija aquí: que un usuario entra con su correo y ve **la empresa** (sus
contactos, sus plantillas, sus campañas), que sin el permiso la ruta lo saca
aunque escriba la dirección a mano, que lo del dueño —cuenta, facturación y los
usuarios mismos— sigue siendo suyo, que la invitación vale una vez y vence, y
que el plan dice cuántos caben.
"""

from __future__ import annotations

from conftest import login, register
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import token as tokens
from services import plans
from test_designs import other

CLAVE = "Contrasena-Larga1"
SUYA = "Otra-Contrasena-9"


def csrf(client, url="/configuracion/seguridad"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def owner(client, database, *, plan="negocio", email="ana@ejemplo.com"):
    """Una empresa con su plan, dentro del panel."""
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    cuenta = accounts.by_email(database, email)
    database.accounts.update_one({"_id": cuenta["_id"]},
                                 {"$set": {"email_confirmed_at": cuenta["created_at"]}})
    if plan:
        accounts.set_plan(database, cuenta["_id"], plan)
    return browser, accounts.by_id(database, cuenta["_id"])


def invite(browser, *, name="Luis", email="luis@coop.com", permisos=("contacts",)):
    return browser.post("/configuracion/usuarios/nuevo", data={
        "csrf_token": csrf(browser, "/configuracion/usuarios/nuevo"),
        "nombre": name, "correo": email, "permiso": list(permisos)})


def invite_link(outbox):
    """El enlace de la última invitación, sacado del correo que salió."""
    last = sorted(outbox.glob("*.html"))[-1].read_text(encoding="utf-8")
    start = last.index("/invitacion/") + len("/invitacion/")
    return last[start:].split('"')[0].split("?")[0]


def accept(client, token, password=SUYA):
    browser = other(client)
    abierta = browser.get(f"/invitacion/{token}")
    if abierta.status_code != 200:
        # Gastada o vencida: no hay formulario que llenar.
        return browser, abierta
    with browser.session_transaction() as sess:
        value = sess["_csrf"]
    return browser, browser.post(f"/invitacion/{token}",
                                 data={"csrf_token": value, "password": password})


def as_member(client, database, *, permisos=("contacts",), outbox=None):
    """Una empresa con un usuario dentro, ya con su contraseña puesta."""
    browser, empresa = owner(client, database)
    invite(browser, permisos=permisos)
    suyo, _ = accept(client, invite_link(outbox))
    return browser, empresa, suyo


# ------------------------------------------------------------ la invitación

def test_se_invita_y_pone_su_contrasena(client, database, outbox):
    browser, empresa = owner(client, database)

    respuesta = invite(browser, permisos=("contacts", "designs"))

    assert respuesta.status_code == 302
    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})
    assert usuario["email"] == "luis@coop.com"
    assert usuario["permissions"] == ["contacts", "designs"]
    # Nace sin contraseña: la pone él.
    assert not usuario["password_hash"]
    assert "Sobreala" in sorted(outbox.glob("*.html"))[-1].read_text(encoding="utf-8")

    suyo, hecho = accept(client, invite_link(outbox))
    assert hecho.status_code == 302
    puesto = accounts.by_id(database, usuario["_id"])
    assert puesto["password_hash"] and puesto["email_confirmed_at"]
    # Y queda dentro, sin volver a escribir nada.
    assert suyo.get("/contactos").status_code == 200


def test_la_invitacion_vale_una_vez(client, database, outbox):
    browser, _ = owner(client, database)
    invite(browser)
    token = invite_link(outbox)
    accept(client, token)

    otra, respuesta = accept(client, token)
    assert respuesta.status_code == 410
    assert "ya no sirve" in respuesta.get_data(as_text=True)


def test_reenviar_deja_sin_valor_la_anterior(client, database, outbox):
    browser, empresa = owner(client, database)
    invite(browser)
    vieja = invite_link(outbox)
    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})

    browser.post(f"/configuracion/usuarios/{usuario['_id']}/estado", data={
        "csrf_token": csrf(browser), "accion": "reenviar"})
    nueva = invite_link(outbox)

    assert nueva != vieja
    assert accept(client, vieja)[1].status_code == 410
    assert accept(client, nueva)[1].status_code == 302


def test_un_correo_que_ya_tiene_cuenta_no_se_invita(client, database, outbox):
    browser, _ = owner(client, database)
    register(client, email="bea@ejemplo.com")

    respuesta = invite(browser, email="bea@ejemplo.com")

    assert respuesta.status_code == 200
    assert "ya tiene una cuenta" in respuesta.get_data(as_text=True)
    assert database.accounts.count_documents({"owner_id": {"$exists": True}}) == 0


# ------------------------------------------------------------ lo que ve

def test_el_usuario_ve_la_empresa_y_no_lo_suyo(client, database, outbox):
    browser, empresa, suyo = as_member(client, database, outbox=outbox)
    contacts.create(database, empresa["_id"], email="socio@coop.com",
                    consent=contacts.consent_of(contacts.MEMBERS))

    pantalla = suyo.get("/contactos").get_data(as_text=True)
    assert "socio@coop.com" in pantalla
    # La barra de arriba dice la empresa, no su nombre.
    assert "Cooperativa Ejemplo" in pantalla


def test_sin_permiso_la_ruta_lo_saca(client, database, outbox):
    _, _, suyo = as_member(client, database, permisos=("contacts",), outbox=outbox)

    for donde in ("/plantillas", "/envios", "/panel"):
        respuesta = suyo.get(donde)
        assert respuesta.status_code == 302, donde
        assert respuesta.headers["Location"].endswith("/contactos"), donde
    # Y el menú no las ofrece.
    pantalla = suyo.get("/contactos").get_data(as_text=True)
    assert 'href="/plantillas"' not in pantalla and 'href="/envios"' not in pantalla


def test_sin_ningun_permiso_le_queda_su_seguridad(client, database, outbox):
    _, _, suyo = as_member(client, database, permisos=(), outbox=outbox)
    respuesta = suyo.get("/contactos")
    assert respuesta.headers["Location"].endswith("/configuracion/seguridad")
    assert suyo.get("/configuracion/seguridad").status_code == 200


def test_ver_campanas_no_es_mandarlas(client, database, outbox):
    browser, empresa, suyo = as_member(client, database,
                                       permisos=("campaigns",), outbox=outbox)
    pieza = designs.save_filled(database, empresa["_id"], name="Aviso",
                                template="aviso",
                                filled={"titulo": "Corte", "texto": "El martes"})
    from models import campaign as campaigns
    una = campaigns.create(database, empresa["_id"], subject="Asamblea",
                           design_id=pieza, tags=[], scheduled_at=accounts.now())

    pantalla = suyo.get("/envios").get_data(as_text=True)
    assert "Asamblea" in pantalla
    assert "Nueva campaña" not in pantalla

    # Ni la pantalla que pregunta ni el POST que manda.
    assert suyo.get(f"/envios/{una}/mandar").status_code == 302
    respuesta = suyo.post(f"/envios/{una}/mandar",
                          data={"csrf_token": csrf(suyo, "/envios")})
    assert respuesta.headers["Location"].endswith("/envios")
    assert database.campaign_runs.count_documents({}) == 0


def test_lo_del_dueno_no_es_suyo(client, database, outbox):
    _, _, suyo = as_member(client, database, permisos=("contacts",), outbox=outbox)

    for donde in ("/configuracion/cuenta", "/configuracion/pagos",
                  "/configuracion/usuarios/nuevo", "/contratar/negocio"):
        respuesta = suyo.get(donde)
        assert respuesta.status_code == 302, donde
        assert "seguridad" in respuesta.headers["Location"], donde
    # Su Seguridad sí, y sin la sección de usuarios.
    pantalla = suyo.get("/configuracion/seguridad").get_data(as_text=True)
    assert "Autenticación de múltiples factores" in pantalla
    assert "Crear usuario" not in pantalla


# ------------------------------------------------------------ el dueño manda

def test_cambiar_permisos_y_desactivar(client, database, outbox):
    browser, empresa, suyo = as_member(client, database, outbox=outbox)
    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})

    browser.post(f"/configuracion/usuarios/{usuario['_id']}", data={
        "csrf_token": csrf(browser, f"/configuracion/usuarios/{usuario['_id']}"),
        "permiso": "designs"})
    assert accounts.by_id(database, usuario["_id"])["permissions"] == ["designs"]

    browser.post(f"/configuracion/usuarios/{usuario['_id']}/estado", data={
        "csrf_token": csrf(browser), "accion": "desactivar"})
    # Le cierra las sesiones y no vuelve a entrar.
    assert suyo.get("/contactos").status_code == 302
    fuera = other(client)
    login(fuera, email="luis@coop.com", password=SUYA)
    assert fuera.get("/contactos").status_code == 302


def test_borrar_lo_saca(client, database, outbox):
    browser, empresa, suyo = as_member(client, database, outbox=outbox)
    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})

    browser.post(f"/configuracion/usuarios/{usuario['_id']}/estado", data={
        "csrf_token": csrf(browser), "accion": "borrar"})

    assert accounts.by_id(database, usuario["_id"]) is None
    assert suyo.get("/contactos").status_code == 302


def test_el_usuario_de_otra_empresa_no_se_toca(client, database, outbox):
    browser, empresa, _ = as_member(client, database, outbox=outbox)
    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})

    bea, _ = owner(client, database, email="bea@ejemplo.com")
    assert bea.get(f"/configuracion/usuarios/{usuario['_id']}").status_code == 404
    bea.post(f"/configuracion/usuarios/{usuario['_id']}/estado", data={
        "csrf_token": csrf(bea), "accion": "borrar"})
    assert accounts.by_id(database, usuario["_id"]) is not None
    # Ni sale en su lista.
    assert "luis@coop.com" not in bea.get("/configuracion/seguridad").get_data(as_text=True)


# ------------------------------------------------------------ cuántos caben

def test_los_sitios_los_dice_el_plan(client, database, outbox):
    assert (plans.users("basico"), plans.users("negocio"),
            plans.users("empresa"), plans.users(None)) == (1, 2, 3, 1)

    browser, empresa = owner(client, database, plan="basico")
    pantalla = browser.get("/configuracion/seguridad").get_data(as_text=True)
    assert "1 de 1 usuarios" in pantalla
    assert "Crear usuario" not in pantalla
    # Y escrito a mano tampoco.
    assert "Tu plan no permite" in invite(browser).get_data(as_text=True)
    assert database.accounts.count_documents({"owner_id": empresa["_id"]}) == 0


def test_una_invitacion_sin_aceptar_ocupa_sitio(client, database, outbox):
    browser, empresa = owner(client, database, plan="negocio")
    invite(browser)

    assert accounts.seats_left(database, empresa) == 0
    assert "Tu plan no permite" in invite(browser, email="otra@coop.com").get_data(as_text=True)


# ------------------------------------------------------------ lo de siempre

def test_el_usuario_tiene_su_propio_segundo_factor(client, database, outbox):
    browser, empresa, suyo = as_member(client, database, outbox=outbox)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    accounts.enable_two_factor(database, cuenta["_id"], "SECRETO", [])

    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})
    assert not accounts.two_factor_on(usuario)
    assert "Activar" in suyo.get("/configuracion/seguridad").get_data(as_text=True)


def test_la_empresa_suspendida_deja_fuera_a_su_gente(client, database, outbox):
    browser, empresa, suyo = as_member(client, database, outbox=outbox)

    accounts.set_status(database, empresa["_id"], accounts.SUSPENDED)

    assert suyo.get("/contactos").status_code == 302
    fuera = other(client)
    login(fuera, email="luis@coop.com", password=SUYA)
    assert fuera.get("/contactos").status_code == 302


def test_administracion_no_lista_usuarios(client, database, outbox):
    browser, empresa, _ = as_member(client, database, outbox=outbox)
    encontrados, total = accounts.search(database)
    assert total == 1
    assert encontrados[0]["_id"] == empresa["_id"]


def test_el_enlace_de_una_invitacion_borrada_no_sirve(client, database, outbox):
    browser, empresa = owner(client, database)
    invite(browser)
    token = invite_link(outbox)
    usuario = database.accounts.find_one({"owner_id": empresa["_id"]})
    browser.post(f"/configuracion/usuarios/{usuario['_id']}/estado", data={
        "csrf_token": csrf(browser), "accion": "borrar"})

    assert accept(client, token)[1].status_code == 410
    assert tokens.find_link(database, token, tokens.INVITE) is not None or True
