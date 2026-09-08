"""Two-step verification: the code from the app, the recovery codes, and the
device that does not have to answer again.

What these pin down is the part that is easy to get subtly wrong: that nothing
opens between the password and the code, that a code cannot be used twice, and
that nobody can take an account away from its owner from a session left open.
"""

from __future__ import annotations

import re
import time

import pyotp
from conftest import login, register

from models import account as accounts
from models import auth_event as events
from models import trusted_device as trusted
from services import totp

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def turn_on(client, database):
    """Enable two-step the way the screen does, and return (secret, codes)."""
    page = client.get("/cuenta/dos-pasos").get_data(as_text=True)
    with client.session_transaction() as sess:
        secret = sess["two_factor_setup"]
        csrf = sess["_csrf"]
    assert "<svg" in page                      # the QR was drawn on the page
    answer = client.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": "enable", "password": PASSWORD,
        "code": list(pyotp.TOTP(secret).now()),
    })
    codes = re.findall(r"[A-Z2-9]{4}-[A-Z2-9]{4}", answer.get_data(as_text=True))
    return secret, codes


def sign_in(client, password=PASSWORD):
    client.get("/entrar")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/entrar", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com", "password": password})


def second_step(client, code=None, recovery=None, trust=False):
    client.get("/entrar/codigo")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    data = {"csrf_token": csrf}
    if code:
        data["code"] = list(code)
    if recovery:
        data["recovery"] = recovery
    if trust:
        data["trust"] = "1"
    return client.post("/entrar/codigo", data=data)


# ------------------------------------------------------------- turning it on

def test_enabling_needs_the_password_and_a_working_code(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    inside.get("/cuenta/dos-pasos")
    with inside.session_transaction() as sess:
        secret, csrf = sess["two_factor_setup"], sess["_csrf"]

    # No password, no change: this is what stops whoever finds an open
    # session from taking the account away from its owner.
    inside.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": "enable", "password": "otra-cosa",
        "code": list(pyotp.TOTP(secret).now())})
    assert not accounts.two_factor_on(accounts.by_email(database, "ana@ejemplo.com"))

    # With the password but a code that does not match, no either: nobody
    # gets locked out for having scanned badly.
    inside.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": "enable", "password": PASSWORD,
        "code": list("000000")})
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
    assert second_step(phone, code=pyotp.TOTP(secret).now()).headers["Location"].endswith("/panel")
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


def test_regenerating_invalidates_the_old_codes(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    _, codes = turn_on(inside, database)

    with inside.session_transaction() as sess:
        csrf = sess["_csrf"]
    answer = inside.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": "regenerate", "password": PASSWORD})
    fresh = re.findall(r"[A-Z2-9]{4}-[A-Z2-9]{4}", answer.get_data(as_text=True))

    assert len(fresh) == totp.RECOVERY_CODES
    assert set(fresh).isdisjoint(codes)
    phone = other(client)
    sign_in(phone)
    assert second_step(phone, recovery=codes[0]).status_code == 200   # the old one no longer


# --------------------------------------------------------- trusted devices

def test_a_trusted_device_is_not_asked_again(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)

    phone = other(client)
    sign_in(phone)
    second_step(phone, code=pyotp.TOTP(secret).now(), trust=True)

    # Signs out and back in: the same browser no longer has to answer.
    phone.get("/panel")
    with phone.session_transaction() as sess:
        csrf = sess["_csrf"]
    phone.post("/salir", data={"csrf_token": csrf})
    assert sign_in(phone).headers["Location"].endswith("/panel")

    # Another browser does.
    assert sign_in(other(client)).headers["Location"].endswith("/entrar/codigo")


def test_turning_it_off_forgets_the_trusted_devices(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    secret, _ = turn_on(inside, database)
    phone = other(client)
    sign_in(phone)
    second_step(phone, code=pyotp.TOTP(secret).now(), trust=True)

    with inside.session_transaction() as sess:
        csrf = sess["_csrf"]
    inside.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": "disable", "password": PASSWORD})

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert not accounts.two_factor_on(account)
    assert trusted.for_account(database, account["_id"]) == []


def test_disabling_needs_the_password(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    turn_on(inside, database)

    with inside.session_transaction() as sess:
        csrf = sess["_csrf"]
    inside.post("/cuenta/dos-pasos", data={
        "csrf_token": csrf, "action": "disable", "password": "otra-cosa"})

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
