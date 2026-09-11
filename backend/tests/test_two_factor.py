"""Two-step verification: the code from the app, the recovery codes, and the
device that does not have to answer again.

What these pin down is the part that is easy to get subtly wrong: that nothing
opens between the password and the code, that a code cannot be used twice, and
that nobody can take an account away from its owner from a session left open.
"""

from __future__ import annotations

import re
import time
from datetime import timedelta

import pyotp
from conftest import login, register

from config import Config
from models import account as accounts
from models import auth_event as events
from services import totp

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def prove(client, password=PASSWORD):
    """Paso uno: la contraseña, que es lo único que hay en esa pantalla."""
    page = client.get("/cuenta/dos-pasos").get_data(as_text=True)
    assert 'class="qr"' not in page           # todavía no se enseña ningún QR
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/cuenta/dos-pasos",
                       data={"csrf_token": csrf, "password": password})


def turn_on(client, database):
    """Enable two-step the way the screen does, and return (secret, codes)."""
    prove(client)
    page = client.get("/cuenta/dos-pasos/activar").get_data(as_text=True)
    assert 'class="qr"' in page               # the QR was drawn on the page
    with client.session_transaction() as sess:
        secret = sess["two_factor_setup"]
        csrf = sess["_csrf"]
    answer = client.post("/cuenta/dos-pasos/activar", data={
        "csrf_token": csrf, "code": list(pyotp.TOTP(secret).now()),
    })
    codes = re.findall(r"[A-Z2-9]{4}-[A-Z2-9]{4}", answer.get_data(as_text=True))
    return secret, codes


def manage(client, action, password=PASSWORD):
    """Paso dos de administrarla: la contraseña, para la acción ya elegida."""
    client.get(f"/cuenta/dos-pasos?accion={action}")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": action, "password": password})


def sign_in(client, password=PASSWORD):
    client.get("/entrar")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/entrar", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com", "password": password})


def second_step(client, code=None, recovery=None):
    client.get("/entrar/codigo")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    data = {"csrf_token": csrf}
    if code:
        data["code"] = list(code)
    if recovery:
        data["recovery"] = recovery
    return client.post("/entrar/codigo", data=data)


# ------------------------------------------------------------- turning it on

def test_the_qr_screen_does_not_open_without_the_password(client, database, outbox):
    """Es lo único que la abre.

    Sin esto, quien encuentre una sesión abierta escribe la dirección a mano y
    pone su propio teléfono como segundo paso, que es exactamente lo que la
    contraseña evita.
    """
    register(client)
    inside = other(client)
    login(inside)

    answer = inside.get("/cuenta/dos-pasos/activar")
    assert answer.status_code == 302
    assert "vencido" in answer.headers["Location"]
    with inside.session_transaction() as sess:
        assert "two_factor_setup" not in sess


def test_the_wrong_password_shows_no_qr(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    answer = prove(inside, password="otra-cosa")
    assert 'class="qr"' not in answer.get_data(as_text=True)
    assert inside.get("/cuenta/dos-pasos/activar").status_code == 302


def test_the_proof_expires(client, database, outbox, monkeypatch):
    """Una pestaña olvidada abierta no puede seguir siendo una puerta."""
    from blueprints.auth import routes

    register(client)
    inside = other(client)
    login(inside)
    prove(inside)
    assert inside.get("/cuenta/dos-pasos/activar").status_code == 200

    later = routes.security_now() + timedelta(minutes=routes.TWO_FACTOR_MINUTES + 1)
    monkeypatch.setattr(routes, "security_now", lambda: later)
    assert inside.get("/cuenta/dos-pasos/activar").status_code == 302


def test_enabling_needs_the_password_and_a_working_code(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    prove(inside)
    inside.get("/cuenta/dos-pasos/activar")
    with inside.session_transaction() as sess:
        csrf = sess["_csrf"]

    # Con un código que no cuadra no se enciende: nadie se queda fuera de su
    # cuenta por haber escaneado mal.
    inside.post("/cuenta/dos-pasos/activar", data={
        "csrf_token": csrf, "code": list("000000")})
    assert not accounts.two_factor_on(accounts.by_email(database, "ana@ejemplo.com"))

    secret, codes = turn_on(inside, database)
    assert accounts.two_factor_on(accounts.by_email(database, "ana@ejemplo.com"))
    assert len(codes) == totp.RECOVERY_CODES


def test_the_recovery_codes_are_stored_hashed(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    secret, codes = turn_on(inside, database)

    stored = accounts.by_email(database, "ana@ejemplo.com")["two_factor"]
    assert codes[0] not in str(stored["recovery"])
    assert totp.hash_recovery(codes[0]) in stored["recovery"]


# ------------------------------------------------------------- signing in

def test_the_password_alone_opens_nothing(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    turn_on(inside, database)

    phone = other(client)
    answer = sign_in(phone)

    assert answer.headers["Location"].endswith("/entrar/codigo")
    # Nothing is open while the second screen is up.
    assert phone.get("/panel").status_code == 302
    assert database.sessions.count_documents({"account_id":
        accounts.by_email(database, "ana@ejemplo.com")["_id"],
        "revoked_at": None}) == 1          # only the browser that enabled it


def test_a_good_code_gets_in(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)

    phone = other(client)
    sign_in(phone)
    assert second_step(phone, code=pyotp.TOTP(secret).now()
                       ).headers["Location"] == Config.PUBLIC_SITE_URL
    assert phone.get("/panel").status_code == 200


def test_the_same_code_does_not_work_twice(client, database, outbox):
    """A code read over someone's shoulder stops working once it is typed."""
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)
    code = pyotp.TOTP(secret).now()

    first = other(client)
    sign_in(first)
    assert second_step(first, code=code).status_code == 302

    thief = other(client)
    sign_in(thief)
    assert second_step(thief, code=code).status_code == 200      # refused
    assert thief.get("/panel").status_code == 302


def test_an_old_code_is_refused(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)
    old = pyotp.TOTP(secret).at(time.time() - 120)

    phone = other(client)
    sign_in(phone)
    assert second_step(phone, code=old).status_code == 200
    assert phone.get("/panel").status_code == 302


def test_a_recovery_code_gets_in_once(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    _, codes = turn_on(inside, database)

    phone = other(client)
    sign_in(phone)
    assert second_step(phone, recovery=codes[0]).status_code == 302
    assert phone.get("/panel").status_code == 200

    left = accounts.by_email(database, "ana@ejemplo.com")["two_factor"]["recovery"]
    assert len(left) == totp.RECOVERY_CODES - 1

    again = other(client)
    sign_in(again)
    assert second_step(again, recovery=codes[0]).status_code == 200


def test_a_recovery_code_is_forgiving_about_how_it_is_typed(client, database,
                                                            outbox):
    """En minúscula y sin guion entra igual, y eso está bien.

    El alfabeto ya excluye las minúsculas, así que `abcd` y `ABCD` no son dos
    posibilidades sino la misma tecleada de otra forma: aceptar ambas no quita
    entropía. Ser estricto solo dejaría fuera a quien copió el código de un
    papel, el día que perdió el teléfono.
    """
    register(client)
    inside = other(client)
    login(inside)
    _, codes = turn_on(inside, database)

    phone = other(client)
    sign_in(phone)
    escrito_a_mano = codes[0].replace("-", "").lower()
    assert second_step(phone, recovery=escrito_a_mano).status_code == 302
    assert phone.get("/panel").status_code == 200


def test_regenerating_invalidates_the_old_codes(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    _, codes = turn_on(inside, database)

    answer = manage(inside, "regenerate")
    fresh = re.findall(r"[A-Z2-9]{4}-[A-Z2-9]{4}", answer.get_data(as_text=True))

    assert len(fresh) == totp.RECOVERY_CODES
    assert set(fresh).isdisjoint(codes)
    phone = other(client)
    sign_in(phone)
    assert second_step(phone, recovery=codes[0]).status_code == 200   # the old one no longer


# ---------------------------------------------------------- turning it off

def test_signing_in_always_asks_for_the_code(client, database, outbox):
    """No hay dispositivo que se libre.

    Hubo una casilla de no volver a preguntar durante 30 días y se quitó: un
    dispositivo que deja de preguntar un mes es un segundo candado abierto un
    mes.
    """
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)

    phone = other(client)
    sign_in(phone)
    second_step(phone, code=pyotp.TOTP(secret).now())

    # El mismo navegador, otra vez: vuelve a pedirlo.
    phone.get("/panel")
    with phone.session_transaction() as sess:
        csrf = sess["_csrf"]
    phone.post("/salir", data={"csrf_token": csrf})
    assert sign_in(phone).headers["Location"].endswith("/entrar/codigo")


def test_turning_it_off_leaves_the_account_on_the_password(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    turn_on(inside, database)

    manage(inside, "disable")

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert not accounts.two_factor_on(account)
    assert sign_in(other(client)).headers["Location"] == Config.PUBLIC_SITE_URL


def test_disabling_needs_the_password(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    turn_on(inside, database)

    manage(inside, "disable", password="otra-cosa")

    assert accounts.two_factor_on(accounts.by_email(database, "ana@ejemplo.com"))


def test_an_action_that_is_not_in_the_form_does_nothing(client, database, outbox):
    """Lo que decide es el POST, no la dirección de la pantalla."""
    register(client)
    inside = other(client)
    login(inside)
    turn_on(inside, database)

    inside.get("/cuenta/dos-pasos?accion=disable")
    with inside.session_transaction() as sess:
        csrf = sess["_csrf"]
    inside.post("/cuenta/dos-pasos", data={"csrf_token": csrf, "password": PASSWORD})

    assert accounts.two_factor_on(accounts.by_email(database, "ana@ejemplo.com"))


# ------------------------------------------------------------------ the log

def test_the_two_steps_are_recorded_apart(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)

    phone = other(client)
    sign_in(phone)
    second_step(phone, code=pyotp.TOTP(secret).now())

    outcomes = [d["outcome"] for d in
                database.auth_events.find({"kind": events.LOGIN}).sort("created_at", 1)]
    # Signing in and clearing the second step are two different facts, and the
    # log counts them as two.
    assert outcomes[-2:] == [events.SECOND_STEP, events.OK]
