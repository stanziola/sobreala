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


def csrf(client, url="/settings"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def save(client, **wanted):
    """Post the notification form the way the screen does.

    An unchecked switch sends nothing at all, which is what a browser does, so
    the test has to leave those keys out rather than send them as false.
    """
    token = csrf(client, "/settings/notifications")
    data = {"csrf_token": token}
    data.update({name: "on" for name, on in wanted.items() if on})
    return client.post("/settings/notifications", data=data)


def turn_on_two_step(client):
    # Dos pasos: primero la contraseña, después el QR.
    client.get("/account/two-factor")
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    client.post("/account/two-factor", data={"csrf_token": token, "password": PASSWORD})
    client.get("/account/two-factor/enable")
    with client.session_transaction() as sess:
        secret, token = sess["two_factor_setup"], sess["_csrf"]
    client.post("/account/two-factor/enable", data={
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

    inside.post("/account/two-factor", data={
        "csrf_token": csrf(inside, "/account/two-factor"),
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
    # Solo los que se ofrecen: los que todavía no mandan nada no se guardan, y
    # por eso el día que empiecen a salir llegan sin encender nada.
    assert set(stored) == set(accounts.NOTICES) - set(accounts.PENDING)

    turn_on_two_step(inside)
    assert bodies(outbox, "ya pide un segundo paso")


# ------------------------------------------------ the notice that does switch

def test_the_new_device_notice_goes_out_when_nothing_was_chosen(client, database,
                                                                outbox):
    register(client)
    phone = other(client)
    phone.get("/login", headers={"User-Agent": PHONE})
    with phone.session_transaction() as sess:
        token = sess["_csrf"]
    phone.post("/login", headers={"User-Agent": PHONE}, data={
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
    phone.get("/login", headers={"User-Agent": PHONE})
    with phone.session_transaction() as sess:
        token = sess["_csrf"]
    phone.post("/login", headers={"User-Agent": PHONE}, data={
        "csrf_token": token, "email": "ana@ejemplo.com", "password": PASSWORD})

    assert len(bodies(outbox, "dispositivo nuevo")) == before
    assert phone.get("/dashboard").status_code == 200      # it still got in


def test_a_stale_form_saves_nothing(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    inside.post("/settings/notifications",
                data={"csrf_token": "de-ayer", "billing": "on"})

    assert "notifications" not in accounts.by_email(database, "ana@ejemplo.com")


# ------------------------------------------------------------- the screen

def test_settings_need_a_session(client, database):
    assert client.get("/settings").status_code == 302
    assert client.get("/settings/security").status_code == 302


def test_an_invented_section_lands_on_the_first_one(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    answer = inside.get("/settings/inventada")

    assert answer.status_code == 302
    # A la primera suya, nombrada: para un cliente es Cuenta y para un
    # administrador Seguridad, así que la dirección lo dice en vez de depender
    # de cuál sea el valor por omisión de la vista.
    assert answer.headers["Location"].endswith("/settings/account")


def test_each_section_draws_its_own(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    account = inside.get("/settings").get_data(as_text=True)
    assert "Cooperativa Ejemplo" in account
    assert "ana@ejemplo.com" in account
    # Menos texto (octubre de 2026): «Correo» a secas, sin el estado de la
    # cuenta y sin las frases debajo de la dirección y los teléfonos.
    assert ">Correo<" in account and "Correo de tu cuenta" not in account
    assert "Estado de tu cuenta" not in account
    assert "Sale al pie de tus campañas" not in account
    assert "El tuyo, que es al que te escribimos" not in account

    security = inside.get("/settings/security").get_data(as_text=True)
    assert "/change-password" in security
    assert "Personas de tu equipo" not in security
    cambiar = inside.get("/change-password").get_data(as_text=True)
    assert "Si la cambias, se cierra la sesión en los demás dispositivos." in cambiar
    assert "/account/two-factor" in security
    assert "Tus dispositivos" in security

    notices = inside.get("/settings/notifications").get_data(as_text=True)
    # Los de seguridad: encendidos y bloqueados, sin frase que lo diga.
    assert "switch--locked" in notices
    assert "Siempre activo" not in notices
    assert 'name="new_login"' in notices
    # The fixed ones are listed, and none of them is a field that could be sent.
    assert 'name="password_changed"' not in notices

    payments = inside.get("/settings/billing").get_data(as_text=True)
    # Solo lo guardado: ni la tarjeta, ni Yappy, ni «Próximamente».
    assert "Yappy" not in payments and "Próximamente" not in payments
    assert "Tarjeta de crédito o débito" not in payments
    assert "No tienes métodos de pago guardados" in payments or \
        "Agregar método de pago" in payments


def admin_inside(client, database, email="jefe@ejemplo.com"):
    """Una cuenta con el rol, ya dentro."""
    register(client, email=email)
    inside = other(client)
    login(inside, email=email)
    cuenta = accounts.by_email(database, email)
    accounts.set_role(database, cuenta["_id"], accounts.ADMIN)
    return inside, cuenta


def test_el_administrador_tiene_notificaciones_y_son_las_suyas(
        client, database, outbox):
    """Su lista habla de lo que hacen los clientes. Los interruptores de un
    cliente no se le dibujan: no recibiría ninguno de esos correos."""
    inside, _ = admin_inside(client, database)

    pantalla = inside.get("/settings/notifications").get_data(as_text=True)

    assert 'name="admin_payment"' in pantalla
    assert 'name="admin_signup"' in pantalla
    assert 'name="admin_plan_end"' in pantalla
    assert 'name="campaigns"' not in pantalla
    assert 'name="billing"' not in pantalla
    # Y los de seguridad siguen sin interruptor, como en cualquier cuenta.
    assert "switch--locked" in pantalla


def test_el_administrador_guarda_solo_sus_avisos(client, database, outbox):
    inside, cuenta = admin_inside(client, database)

    token = csrf(inside, "/settings/notifications")
    inside.post("/settings/notifications", data={
        "csrf_token": token, "admin_payment": "on",
        # Uno que no es suyo: se descarta en vez de guardarse.
        "campaigns": "on"})

    fresca = accounts.by_id(database, cuenta["_id"])
    assert accounts.wants(fresca, accounts.ADMIN_PAYMENT)
    assert not accounts.wants(fresca, accounts.ADMIN_SIGNUP)
    assert "campaigns" not in (fresca.get("notifications") or {})


def test_an_account_with_no_plan_says_so(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    assert "Sin plan contratado" in inside.get("/settings").get_data(as_text=True)


def test_the_panel_no_longer_holds_the_settings(client, database, outbox):
    """They live in one place now, so nobody has to look in two."""
    register(client)
    inside = other(client)
    login(inside)
    panel = inside.get("/dashboard").get_data(as_text=True)

    assert "Tus dispositivos" not in panel
    assert "/settings" in panel


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

    salida = inside.get("/logout")
    assert salida.status_code == 302
    assert salida.headers["Location"].endswith("/login")
    assert inside.get("/dashboard").status_code == 302


def test_a_prefetched_sign_out_closes_nothing(client, database, outbox):
    """Lo único que no obedece: una petición que el navegador dice estar
    adelantando por su cuenta. Sin esto, un navegador que precarga enlaces
    sacaría a alguien de su cuenta sin que hubiera pulsado nada."""
    for cabecera in ("Sec-Purpose", "Purpose", "X-Moz"):
        register(client, email=f"{cabecera.lower()}@ejemplo.com")
        inside = other(client)
        login(inside, email=f"{cabecera.lower()}@ejemplo.com")

        adelantada = inside.get("/logout", headers={cabecera: "prefetch"})
        assert adelantada.status_code == 200, cabecera
        assert inside.get("/dashboard").status_code == 200, cabecera


def test_signing_out_kills_the_session_document(client, database, outbox):
    """No basta con olvidar la galleta: quien copió su valor no puede seguir
    entrando con ella."""
    from models import session as sessions

    register(client)
    inside = other(client)
    login(inside)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert len(sessions.for_account(database, cuenta["_id"])) == 1

    inside.get("/logout")
    assert sessions.for_account(database, cuenta["_id"]) == []


def test_the_sign_out_form_still_needs_its_token(client, database, outbox):
    """El del panel sí lleva testigo, y sin uno bueno no cierra nada."""
    register(client)
    inside = other(client)
    login(inside)

    inside.post("/logout", data={"csrf_token": "no-es"})
    assert inside.get("/dashboard").status_code == 200


def test_the_sign_out_page_needs_a_session(client, database):
    assert client.get("/logout").status_code == 302


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
    browser.get("/login?add=1")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    return browser.post("/login?add=1", data={
        "csrf_token": token, "email": email, "password": password,
        "remember": "1"})


def switch_to(browser, account_id, accion=""):
    data = {"csrf_token": csrf(browser, "/switch-account"),
            "account": str(account_id)}
    if accion:
        data["action"] = accion
    return browser.post("/switch-account", data=data)


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
    assert browser.get("/dashboard").status_code == 200


def test_las_dos_son_sesiones_de_verdad(client, database, outbox):
    """Cada una tiene su documento, así que aparece en Seguridad y se puede
    cerrar desde otro dispositivo como cualquier otra."""
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)

    assert len(sessions.for_account(database, una)) == 1
    assert len(sessions.for_account(database, dos)) == 1


def test_la_pantalla_lista_las_dos_y_dice_en_cual_estas(client, database, outbox):
    browser, una, dos = two_accounts(client, database)

    pantalla = browser.get("/switch-account").get_data(as_text=True)
    assert "una@ejemplo.com" in pantalla
    assert "dos@ejemplo.com" in pantalla
    assert "Estás aquí" in pantalla
    # Sin la frase de arriba, que explicaba lo que la lista ya enseña.
    assert "Saltar de una" not in pantalla


def test_volver_lleva_a_la_portada(client, database, outbox):
    """Llevaba a las Estadísticas de la cuenta en uso. La portada es donde se
    aterriza al entrar y al saltar de cuenta."""
    from config import Config

    browser, _, _ = two_accounts(client, database)

    pantalla = browser.get("/switch-account").get_data(as_text=True)
    assert f'<a href="{Config.PUBLIC_SITE_URL}">Volver</a>' in pantalla


def test_una_cuenta_ya_abierta_no_se_agrega_otra_vez(client, database, outbox):
    """Abría otra sesión y cerraba la de antes. Ahora lo dice y no abre nada."""
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)
    antes = sessions.for_account(database, una)[0]["_id"]
    avisos = database.mail_log.count_documents({"purpose": mail_log.NEW_LOGIN})

    respuesta = add_account(browser, "una@ejemplo.com")

    assert respuesta.status_code == 200
    assert "Esa cuenta ya está abierta en este navegador" in respuesta.get_data(
        as_text=True)
    # La misma sesión de antes, la misma cuenta en uso, y ningún aviso.
    assert [s["_id"] for s in sessions.for_account(database, una)] == [antes]
    assert quien(browser, database) == dos
    assert database.mail_log.count_documents(
        {"purpose": mail_log.NEW_LOGIN}) == avisos


def test_la_ya_abierta_se_dice_aunque_la_contrasena_este_mal(client, database,
                                                             outbox):
    """Se comprueba antes de la contraseña: no hay nada que abrir."""
    browser, _, _ = two_accounts(client, database)

    respuesta = add_account(browser, "una@ejemplo.com", password="otra-cosa")

    assert "Esa cuenta ya está abierta" in respuesta.get_data(as_text=True)


def test_la_pantalla_no_dibuja_ningun_testigo(client, database, outbox):
    """Un testigo en el HTML sería la sesión escrita en la página."""
    browser, _, _ = two_accounts(client, database)

    pantalla = browser.get("/switch-account").get_data(as_text=True)
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


def test_cerrar_este_dispositivo_deja_las_otras(client, database, outbox):
    """Cerrar «Este dispositivo» en Seguridad vaciaba la galleta entera: las
    otras cuentas del navegador quedaban vivas y sin testigo, y salían en su
    Seguridad como otro dispositivo con la misma IP."""
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)
    este = sessions.for_account(database, dos)[0]["_id"]

    respuesta = browser.post("/devices/close", data={
        "csrf_token": csrf(browser, "/settings/security"),
        "session_id": str(este)})

    assert respuesta.headers["Location"].endswith("/switch-account")
    assert sessions.for_account(database, dos) == []
    # La otra sigue abierta, viva y en la galleta, que sigue durando lo mismo.
    assert abiertas(browser, database) == [una]
    with browser.session_transaction() as sess:
        assert sess.permanent


def test_cerrar_sesion_las_cierra_todas(client, database, outbox):
    """En una computadora prestada, salir tiene que significar que no queda
    ninguna cuenta abierta."""
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)

    browser.post("/logout", data={"csrf_token": csrf(browser)})

    assert sessions.for_account(database, una) == []
    assert sessions.for_account(database, dos) == []
    assert browser.get("/dashboard").status_code == 302


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
    assert browser.get("/dashboard").status_code == 302

    login(browser, email="una@ejemplo.com")

    assert abiertas(browser, database) == [una]
    assert len(sessions.for_account(database, una)) == 1


def test_una_cerrada_desde_otro_dispositivo_desaparece(client, database, outbox):
    from models import session as sessions

    browser, una, dos = two_accounts(client, database)
    sessions.revoke_others(database, una)  # como «cerrar las otras» en Seguridad

    pantalla = browser.get("/switch-account").get_data(as_text=True)
    assert "una@ejemplo.com" not in pantalla
    assert abiertas(browser, database) == [dos]


def test_una_suspendida_desaparece(client, database, outbox):
    browser, una, dos = two_accounts(client, database)
    accounts.set_status(database, una, accounts.SUSPENDED)

    pantalla = browser.get("/switch-account").get_data(as_text=True)
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
    assert respuesta.headers["Location"].endswith("/login/code")

    browser.post("/login/code", data={
        "csrf_token": csrf(browser, "/login/code"),
        "code": list(pyotp.TOTP(secreto).now())})

    una = accounts.by_email(database, "una@ejemplo.com")["_id"]
    dos = accounts.by_email(database, "dos@ejemplo.com")["_id"]
    assert quien(browser, database) == dos
    assert set(abiertas(browser, database)) == {una, dos}


def test_saltar_necesita_su_testigo(client, database, outbox):
    browser, una, dos = two_accounts(client, database)

    browser.post("/switch-account", data={"csrf_token": "no-es",
                                          "account": str(una)})

    assert quien(browser, database) == dos


def test_no_se_puede_saltar_a_una_cuenta_que_no_esta_abierta(client, database, outbox):
    """El identificador viaja en un formulario, así que nunca se cree solo."""
    browser, una, dos = two_accounts(client, database)
    register(client, email="ajena@ejemplo.com")
    ajena = accounts.by_email(database, "ajena@ejemplo.com")["_id"]

    switch_to(browser, ajena)

    assert quien(browser, database) == dos


def test_sin_ninguna_abierta_lleva_a_entrar(client, database):
    assert client.get("/switch-account").status_code == 302


def test_both_menus_offer_the_switch(client, database, outbox):
    """La regla de CLAUDE.md: lo que está en los dos sitios se cambia en los
    dos. El panel lo dibuja y el sitio público lo publica ya construido."""
    from pathlib import Path

    register(client)
    inside = other(client)
    login(inside)

    panel = inside.get("/dashboard").get_data(as_text=True)
    assert "Cambiar de cuenta" in panel
    assert "/switch-account" in panel

    raiz = Path(__file__).resolve().parent.parent.parent
    sitio = (raiz / "landing" / "index.html").read_text(encoding="utf-8")
    assert "Cambiar de cuenta" in sitio
    assert "/switch-account" in sitio


# ------------------------------------ crear otra cuenta sin cerrar la abierta

def register_another(browser, email, company="Otra Cooperativa"):
    """Registrar desde dentro de otra cuenta, como lo hace la pantalla."""
    browser.get("/signup?add=1")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    return browser.post("/signup?add=1", data={
        "csrf_token": token, "company_name": company, "contact_name": "Bea",
        "email": email, "phone_country": "PA", "phone": "60000000",
        "address": "Calle 10, Santiago de Veraguas",
        "password": PASSWORD})


def test_la_pantalla_de_agregar_ofrece_crear_una(client, database, outbox):
    """El pie decía «todavía no tienes cuenta», que estando dentro es mentira,
    y encima el enlace rebotaba a la portada."""
    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    pantalla = browser.get("/login?add=1").get_data(as_text=True)

    assert "<h1>Agregar una cuenta</h1>" in pantalla
    assert "¿Te gustaría crear otra cuenta?" in pantalla
    assert "no tienes cuenta" not in pantalla
    assert "/signup?add=1" in pantalla
    # Sin el recuadro que lo explicaba.
    assert "Vas a agregar otra cuenta" not in pantalla


def test_se_crea_otra_cuenta_y_la_primera_sigue_abierta(client, database, outbox):
    from conftest import code_from_outbox, confirm

    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    # El formulario se dibuja en vez de devolver a la portada, sin las dos
    # frases que tenía encima.
    formulario = browser.get("/signup?add=1")
    assert formulario.status_code == 200
    assert "Vas a crear otra cuenta" not in formulario.get_data(as_text=True)
    assert "Con tu cuenta puedes" not in formulario.get_data(as_text=True)
    # El pie es el del registro de siempre, y entrar sigue siendo agregar.
    pie = formulario.get_data(as_text=True).split('class="foot"')[1]
    assert "¿Ya tienes una cuenta?" in pie and "Esa cuenta ya existe" not in pie
    assert '<a href="/login?add=1">Iniciar sesión</a>' in pie

    register_another(browser, "dos@ejemplo.com")
    confirm(browser, code_from_outbox(outbox))

    una = accounts.by_email(database, "una@ejemplo.com")["_id"]
    dos = accounts.by_email(database, "dos@ejemplo.com")["_id"]
    assert quien(browser, database) == dos
    assert set(abiertas(browser, database)) == {una, dos}


def test_el_registro_sin_la_marca_sigue_devolviendo(client, database, outbox):
    """Quien ya está dentro y abre /signup sin más no tiene nada que hacer ahí."""
    from config import Config

    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    respuesta = browser.get("/signup")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == Config.PUBLIC_SITE_URL


def test_otro_codigo_al_crear_otra_va_a_la_nueva(client, database, outbox):
    """Estando dentro de una, el código de la que se está creando no va a la
    abierta: va a la que se escribió en el registro."""
    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")
    register_another(browser, "dos@ejemplo.com")

    browser.post("/resend-confirmation",
                 data={"csrf_token": csrf(browser, "/confirm")})

    ultimo = list(database.mail_log.find({"purpose": mail_log.CONFIRM}))[-1]
    assert ultimo["to"] == "dos@ejemplo.com"


def test_el_correo_ya_registrado_lleva_a_entrar_agregando(client, database, outbox):
    """El enlace del aviso llevaba a /login, que con una sesión abierta
    devuelve a la portada."""
    register(client, email="una@ejemplo.com")
    register(client, email="dos@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    pantalla = register_another(browser, "dos@ejemplo.com").get_data(as_text=True)

    aviso = pantalla.split('<p class="error">')[1].split("</p>")[0]
    assert '<a href="/login?add=1">Iniciar sesión</a>' in aviso
