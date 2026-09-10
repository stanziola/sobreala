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
