"""Configuración: the four sections, what can be switched off and what cannot.

The line these pin down is the one that matters: a notice that warns somebody
another person is inside their account has no switch, and a request that tries
to invent one changes nothing. The rest —which section draws what, a plan that
is not contracted yet— is there so the screen cannot quietly lose a row.
"""

from __future__ import annotations

import pyotp
from conftest import login, register

from models import account as accounts
from models import mail_log

PASSWORD = "Contrasena-Larga1"
PHONE = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"


def other(client):
    return client.application.test_client()


def csrf(client, url="/configuracion"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def save(client, **wanted):
    """Post the notification form the way the screen does.

    An unchecked switch sends nothing at all, which is what a browser does, so
    the test has to leave those keys out rather than send them as false.
    """
    token = csrf(client, "/configuracion/notificaciones")
    data = {"csrf_token": token}
    data.update({name: "on" for name, on in wanted.items() if on})
    return client.post("/configuracion/notificaciones", data=data)


def turn_on_two_step(client):
    # Dos pasos: primero la contraseña, después el QR.
    client.get("/cuenta/dos-pasos")
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    client.post("/cuenta/dos-pasos", data={"csrf_token": token, "password": PASSWORD})
    client.get("/cuenta/dos-pasos/activar")
    with client.session_transaction() as sess:
        secret, token = sess["two_factor_setup"], sess["_csrf"]
    client.post("/cuenta/dos-pasos/activar", data={
        "csrf_token": token, "code": list(pyotp.TOTP(secret).now())})
    return secret


def bodies(outbox, needle):
    return [p.read_text(encoding="utf-8") for p in sorted(outbox.glob("*.txt"))
            if needle in p.read_text(encoding="utf-8")]


# ------------------------------------------------------- the two-step notice

def test_turning_two_step_on_and_off_is_announced(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    turn_on_two_step(inside)
    assert bodies(outbox, "ya pide un segundo paso")
    assert database.mail_log.count_documents({"purpose": mail_log.TWO_FACTOR}) == 1

    inside.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf(inside, "/cuenta/dos-pasos"),
        "action": "disable", "password": PASSWORD})
    assert bodies(outbox, "dejó de pedir el segundo paso")
    assert database.mail_log.count_documents({"purpose": mail_log.TWO_FACTOR}) == 2


def test_a_failed_notice_does_not_undo_the_change(client, database, outbox,
                                                  monkeypatch):
    """The mail is a warning, not a gate: the change already happened."""
    register(client)
    inside = other(client)
    login(inside)

    from services import mailer
    original = mailer.send

    def only_that_one_explodes(*args, **kwargs):
        if kwargs.get("purpose") == mail_log.TWO_FACTOR:
            raise RuntimeError("el proveedor rechazo el mensaje")
        return original(*args, **kwargs)

    monkeypatch.setattr(mailer, "send", only_that_one_explodes)
    turn_on_two_step(inside)

    assert accounts.two_factor_on(accounts.by_email(database, "ana@ejemplo.com"))


def test_the_two_step_notice_has_no_switch(client, database, outbox):
    """Not even a form that names it can turn it off: the account never stores
    a preference for it, so wants() is never consulted about it."""
    register(client)
    inside = other(client)
    login(inside)
    save(inside, two_factor=False, password_changed=False)

    stored = accounts.by_email(database, "ana@ejemplo.com")["notifications"]
    assert "two_factor" not in stored
    assert "password_changed" not in stored
    assert set(stored) == set(accounts.NOTICES)

    turn_on_two_step(inside)
    assert bodies(outbox, "ya pide un segundo paso")


# ------------------------------------------------ the notice that does switch

def test_the_new_device_notice_goes_out_when_nothing_was_chosen(client, database,
                                                                outbox):
    register(client)
    phone = other(client)
    phone.get("/entrar", headers={"User-Agent": PHONE})
    with phone.session_transaction() as sess:
        token = sess["_csrf"]
    phone.post("/entrar", headers={"User-Agent": PHONE}, data={
        "csrf_token": token, "email": "ana@ejemplo.com", "password": PASSWORD})

    assert bodies(outbox, "dispositivo nuevo")


def test_turning_the_new_device_notice_off_stops_it(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    save(inside, new_login=False, billing=True)

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert accounts.wants(account, accounts.NEW_LOGIN) is False
    assert accounts.wants(account, accounts.BILLING) is True

    # Signing in to change the setting was itself a new device and warned; what
    # is counted is whether the next one adds another.
    before = len(bodies(outbox, "dispositivo nuevo"))

    phone = other(client)
    phone.get("/entrar", headers={"User-Agent": PHONE})
    with phone.session_transaction() as sess:
        token = sess["_csrf"]
    phone.post("/entrar", headers={"User-Agent": PHONE}, data={
        "csrf_token": token, "email": "ana@ejemplo.com", "password": PASSWORD})

    assert len(bodies(outbox, "dispositivo nuevo")) == before
    assert phone.get("/panel").status_code == 200      # it still got in


def test_a_stale_form_saves_nothing(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    inside.post("/configuracion/notificaciones",
                data={"csrf_token": "de-ayer", "billing": "on"})

    assert "notifications" not in accounts.by_email(database, "ana@ejemplo.com")


# ------------------------------------------------------------- the screen

def test_settings_need_a_session(client, database):
    assert client.get("/configuracion").status_code == 302
    assert client.get("/configuracion/seguridad").status_code == 302


def test_an_invented_section_lands_on_the_first_one(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    answer = inside.get("/configuracion/inventada")

    assert answer.status_code == 302
    # A la primera suya, nombrada: para un cliente es Cuenta y para un
    # administrador Seguridad, así que la dirección lo dice en vez de depender
    # de cuál sea el valor por omisión de la vista.
    assert answer.headers["Location"].endswith("/configuracion/cuenta")


def test_each_section_draws_its_own(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    account = inside.get("/configuracion").get_data(as_text=True)
    assert "Cooperativa Ejemplo" in account
    assert "ana@ejemplo.com" in account

    security = inside.get("/configuracion/seguridad").get_data(as_text=True)
    assert "/cambiar-contrasena" in security
    assert "/cuenta/dos-pasos" in security
    assert "Tus dispositivos" in security

    notices = inside.get("/configuracion/notificaciones").get_data(as_text=True)
    assert "Siempre activo" in notices
    assert 'name="new_login"' in notices
    # The fixed ones are listed, and none of them is a field that could be sent.
    assert 'name="password_changed"' not in notices

    payments = inside.get("/configuracion/pagos").get_data(as_text=True)
    assert "PayPal" in payments and "Yappy" in payments
    assert "Próximamente" in payments


def test_an_account_with_no_plan_says_so(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    assert "Sin plan contratado" in inside.get("/configuracion").get_data(as_text=True)


def test_the_panel_no_longer_holds_the_settings(client, database, outbox):
    """They live in one place now, so nobody has to look in two."""
    register(client)
    inside = other(client)
    login(inside)
    panel = inside.get("/panel").get_data(as_text=True)

    assert "Tus dispositivos" not in panel
    assert "/configuracion" in panel


# --------------------------------------------------------------- signing out

def test_the_sign_out_link_signs_out(client, database, outbox):
    """El botón del sitio público es un enlace, y un enlace es un GET.

    Salir cuesta un clic desde los dos sitios: el enlace del sitio y el
    formulario del panel hacen lo mismo. El enlace no lleva testigo porque viene
    de otro dominio y no puede llevarlo.
    """
    register(client)
    inside = other(client)
    login(inside)

    salida = inside.get("/salir")
    assert salida.status_code == 302
    assert salida.headers["Location"].endswith("/entrar")
    assert inside.get("/panel").status_code == 302


def test_a_prefetched_sign_out_closes_nothing(client, database, outbox):
    """Lo único que no obedece: una petición que el navegador dice estar
    adelantando por su cuenta. Sin esto, un navegador que precarga enlaces
    sacaría a alguien de su cuenta sin que hubiera pulsado nada."""
    for cabecera in ("Sec-Purpose", "Purpose", "X-Moz"):
        register(client, email=f"{cabecera.lower()}@ejemplo.com")
        inside = other(client)
        login(inside, email=f"{cabecera.lower()}@ejemplo.com")

        adelantada = inside.get("/salir", headers={cabecera: "prefetch"})
        assert adelantada.status_code == 200, cabecera
        assert inside.get("/panel").status_code == 200, cabecera


def test_signing_out_kills_the_session_document(client, database, outbox):
    """No basta con olvidar la galleta: quien copió su valor no puede seguir
    entrando con ella."""
    from models import session as sessions

    register(client)
    inside = other(client)
    login(inside)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert len(sessions.for_account(database, cuenta["_id"])) == 1

    inside.get("/salir")
    assert sessions.for_account(database, cuenta["_id"]) == []


def test_the_sign_out_form_still_needs_its_token(client, database, outbox):
    """El del panel sí lleva testigo, y sin uno bueno no cierra nada."""
    register(client)
    inside = other(client)
    login(inside)

    inside.post("/salir", data={"csrf_token": "no-es"})
    assert inside.get("/panel").status_code == 200


def test_the_sign_out_page_needs_a_session(client, database):
    assert client.get("/salir").status_code == 302


# --------------------------------------- varias cuentas abiertas a la vez

def quien(browser, database):
    """La cuenta que este navegador está usando ahora mismo."""
    from models import session as sessions

    with browser.session_transaction() as sess:
        doc = sessions.find(database, sess.get("sid"))
    return doc["account_id"] if doc else None


def abiertas(browser, database):
    """Las cuentas que este navegador tiene abiertas, vivas de verdad."""
    from models import session as sessions

    with browser.session_transaction() as sess:
        raws = list(sess.get("sids") or [])
    vivas = [sessions.find(database, raw) for raw in raws]
    return [doc["account_id"] for doc in vivas if doc]


def add_account(browser, email, password=PASSWORD):
    """Agregar una cuenta desde la pantalla de entrar, como lo hace la pantalla."""
    browser.get("/entrar?agregar=1")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    return browser.post("/entrar?agregar=1", data={
        "csrf_token": token, "email": email, "password": password,
        "remember": "1"})


def switch_to(browser, account_id, accion=""):
    data = {"csrf_token": csrf(browser, "/cambiar-cuenta"),
            "cuenta": str(account_id)}
    if accion:
        data["accion"] = accion
    return browser.post("/cambiar-cuenta", data=data)


def two_accounts(client, database):
    """Un navegador con dos cuentas abiertas. Devuelve (navegador, una, dos)."""
    register(client, email="una@ejemplo.com")
    register(client, email="dos@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")
    add_account(browser, "dos@ejemplo.com")
    return (browser,
            accounts.by_email(database, "una@ejemplo.com")["_id"],
            accounts.by_email(database, "dos@ejemplo.com")["_id"])


def test_dos_cuentas_abiertas_y_se_salta_sin_contrasena(client, database, outbox):
    """Es lo que pidió: dos sesiones de verdad y cambiar rápido entre ellas."""
    browser, una, dos = two_accounts(client, database)

    # La recién agregada queda en uso, y la primera sigue abierta.
    assert quien(browser, database) == dos
    assert set(abiertas(browser, database)) == {una, dos}

    # Saltar no pide nada y no cierra nada.
    salto = switch_to(browser, una)
    assert salto.status_code == 302
    assert quien(browser, database) == una
    assert set(abiertas(browser, database)) == {una, dos}
    assert browser.get("/panel").status_code == 200


def test_las_dos_son_sesiones_de_verdad(client, database, outbox):
    """Cada una tiene su documento, así que aparece en Seguridad y se puede
    cerrar desde otro dispositivo como cualquier otra."""
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)

    assert len(sessions.for_account(database, una)) == 1
    assert len(sessions.for_account(database, dos)) == 1


def test_la_pantalla_lista_las_dos_y_dice_en_cual_estas(client, database, outbox):
    browser, una, dos = two_accounts(client, database)

    pantalla = browser.get("/cambiar-cuenta").get_data(as_text=True)
    assert "una@ejemplo.com" in pantalla
    assert "dos@ejemplo.com" in pantalla
    assert "Estás aquí" in pantalla


def test_la_pantalla_no_dibuja_ningun_testigo(client, database, outbox):
    """Un testigo en el HTML sería la sesión escrita en la página."""
    browser, _, _ = two_accounts(client, database)

    pantalla = browser.get("/cambiar-cuenta").get_data(as_text=True)
    with browser.session_transaction() as sess:
        testigos = list(sess.get("sids") or [])
    assert testigos
    for raw in testigos:
        assert raw not in pantalla


def test_cerrar_una_deja_la_otra(client, database, outbox):
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)

    switch_to(browser, una, accion="quitar")

    assert abiertas(browser, database) == [dos]
    assert sessions.for_account(database, una) == []
    assert len(sessions.for_account(database, dos)) == 1


def test_cerrar_sesion_las_cierra_todas(client, database, outbox):
    """En una computadora prestada, salir tiene que significar que no queda
    ninguna cuenta abierta."""
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)

    browser.post("/salir", data={"csrf_token": csrf(browser)})

    assert sessions.for_account(database, una) == []
    assert sessions.for_account(database, dos) == []
    assert browser.get("/panel").status_code == 302


def test_entrar_de_cero_cierra_lo_que_el_navegador_tuviera(client, database, outbox):
    """Entrar sin «agregar» sigue dejando una sola cuenta, como siempre hizo.

    Se llega aquí cuando la activa se muere —la cerraron desde otro dispositivo—
    y quedan otras en el navegador: la que quedaba viva se cierra de verdad, y
    no solo se olvida, porque una sesión viva cuyo testigo ya nadie tiene es una
    puerta suelta que además saldría en la pantalla de dispositivos de su
    dueño.
    """
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)
    sessions.revoke_others(database, dos)
    assert browser.get("/panel").status_code == 302

    login(browser, email="una@ejemplo.com")

    assert abiertas(browser, database) == [una]
    assert len(sessions.for_account(database, una)) == 1


def test_una_cerrada_desde_otro_dispositivo_desaparece(client, database, outbox):
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)
    sessions.revoke_others(database, una)  # como «cerrar las otras» en Seguridad

    pantalla = browser.get("/cambiar-cuenta").get_data(as_text=True)
    assert "una@ejemplo.com" not in pantalla
    assert abiertas(browser, database) == [dos]


def test_una_suspendida_desaparece(client, database, outbox):
    browser, una, dos = two_accounts(client, database)
    accounts.set_status(database, una, accounts.SUSPENDED)

    pantalla = browser.get("/cambiar-cuenta").get_data(as_text=True)
    assert "una@ejemplo.com" not in pantalla
    # Y la lista queda limpia, no solo sin dibujar.
    assert abiertas(browser, database) == [dos]
    assert switch_to(browser, una).status_code == 302
    assert quien(browser, database) == dos


def test_hay_un_tope_de_cuentas_a_la_vez(client, database, outbox):
    """El tope existe porque esto viaja en una galleta."""
    from blueprints.auth.routes import MAX_ACCOUNTS
    from models import session as sessions

    correos = [f"c{n}@ejemplo.com" for n in range(MAX_ACCOUNTS + 1)]
    for correo in correos:
        register(client, email=correo)

    browser = other(client)
    login(browser, email=correos[0])
    for correo in correos[1:]:
        add_account(browser, correo)

    assert len(abiertas(browser, database)) == MAX_ACCOUNTS
    # La más vieja se fue, y se cerró de verdad.
    primera = accounts.by_email(database, correos[0])["_id"]
    assert primera not in abiertas(browser, database)
    assert sessions.for_account(database, primera) == []


def test_agregar_con_dos_pasos_pide_el_codigo(client, database, outbox):
    """Agregar pasa por la pantalla de entrar entera, segundo paso incluido."""
    register(client, email="una@ejemplo.com")
    register(client, email="dos@ejemplo.com")

    suyo = other(client)
    login(suyo, email="dos@ejemplo.com")
    turn_on_two_step(suyo)
    secreto = accounts.by_email(database, "dos@ejemplo.com")["two_factor"]["secret"]

    browser = other(client)
    login(browser, email="una@ejemplo.com")
    respuesta = add_account(browser, "dos@ejemplo.com")
    assert respuesta.headers["Location"].endswith("/entrar/codigo")

    browser.post("/entrar/codigo", data={
        "csrf_token": csrf(browser, "/entrar/codigo"),
        "code": list(pyotp.TOTP(secreto).now())})

    una = accounts.by_email(database, "una@ejemplo.com")["_id"]
    dos = accounts.by_email(database, "dos@ejemplo.com")["_id"]
    assert quien(browser, database) == dos
    assert set(abiertas(browser, database)) == {una, dos}


def test_saltar_necesita_su_testigo(client, database, outbox):
    browser, una, dos = two_accounts(client, database)

    browser.post("/cambiar-cuenta", data={"csrf_token": "no-es",
                                          "cuenta": str(una)})

    assert quien(browser, database) == dos


def test_no_se_puede_saltar_a_una_cuenta_que_no_esta_abierta(client, database, outbox):
    """El identificador viaja en un formulario, así que nunca se cree solo."""
    browser, una, dos = two_accounts(client, database)
    register(client, email="ajena@ejemplo.com")
    ajena = accounts.by_email(database, "ajena@ejemplo.com")["_id"]

    switch_to(browser, ajena)

    assert quien(browser, database) == dos


def test_sin_ninguna_abierta_lleva_a_entrar(client, database):
    assert client.get("/cambiar-cuenta").status_code == 302


def test_both_menus_offer_the_switch(client, database, outbox):
    """La regla de CLAUDE.md: lo que está en los dos sitios se cambia en los
    dos. El panel lo dibuja y el sitio público lo publica ya construido."""
    from pathlib import Path

    register(client)
    inside = other(client)
    login(inside)

    panel = inside.get("/panel").get_data(as_text=True)
    assert "Cambiar de cuenta" in panel
    assert "/cambiar-cuenta" in panel

    raiz = Path(__file__).resolve().parent.parent.parent
    sitio = (raiz / "landing" / "index.html").read_text(encoding="utf-8")
    assert "Cambiar de cuenta" in sitio
    assert "/cambiar-cuenta" in sitio


# ------------------------------------ crear otra cuenta sin cerrar la abierta

def register_another(browser, email, company="Otra Cooperativa"):
    """Registrar desde dentro de otra cuenta, como lo hace la pantalla."""
    browser.get("/registro?agregar=1")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    return browser.post("/registro?agregar=1", data={
        "csrf_token": token, "company_name": company, "contact_name": "Bea",
        "email": email, "phone": "60000000", "password": PASSWORD})


def test_la_pantalla_de_agregar_ofrece_crear_una(client, database, outbox):
    """El pie decía «todavía no tienes cuenta», que estando dentro es mentira,
    y encima el enlace rebotaba a la portada."""
    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    pantalla = browser.get("/entrar?agregar=1").get_data(as_text=True)

    assert "no existe esa cuenta" in pantalla
    assert "no tienes cuenta" not in pantalla
    assert "/registro?agregar=1" in pantalla


def test_se_crea_otra_cuenta_y_la_primera_sigue_abierta(client, database, outbox):
    from conftest import code_from_outbox, confirm

    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    # El formulario se dibuja en vez de devolver a la portada.
    formulario = browser.get("/registro?agregar=1")
    assert formulario.status_code == 200
    assert "Vas a crear otra cuenta" in formulario.get_data(as_text=True)

    register_another(browser, "dos@ejemplo.com")
    confirm(browser, code_from_outbox(outbox))

    una = accounts.by_email(database, "una@ejemplo.com")["_id"]
    dos = accounts.by_email(database, "dos@ejemplo.com")["_id"]
    assert quien(browser, database) == dos
    assert set(abiertas(browser, database)) == {una, dos}


def test_el_registro_sin_la_marca_sigue_devolviendo(client, database, outbox):
    """Quien ya está dentro y abre /registro sin más no tiene nada que hacer ahí."""
    from config import Config

    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    respuesta = browser.get("/registro")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == Config.PUBLIC_SITE_URL
