"""Recovering an account without the password, and changing it without the old
one.

Both walk the same three steps —address, code, new password— and the second is
just the first with the address already known. What these fix is what each step
is allowed to give away, and what the last one has to close behind it.
"""

from __future__ import annotations

from conftest import code_from_outbox, login, page_shape, register

from models import account as accounts
from models import auth_event as events
from models import mail_log
from models import session as sessions
from models import token as tokens
from services.security import verify_password

NEW = "Contrasena-Nueva2!"


def ask(client, email=None):
    """Step one: ask for a code. With no email, the signed-in account's own."""
    client.get("/recover")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    data = {"csrf_token": csrf}
    if email is not None:
        data["email"] = email
    return client.post("/recover", data=data)


def type_code(client, code):
    client.get("/recover/code")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    typed = list(digits) if len(digits) == 6 else [str(code)]
    return client.post("/recover/code", data={"csrf_token": csrf, "code": typed})


def set_new(client, password=NEW, repeat=None):
    client.get("/recover/new")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/recover/new", data={
        "csrf_token": csrf, "password": password,
        "repeat": password if repeat is None else repeat,
    })


def other(client):
    return client.application.test_client()


# ------------------------------------------------------------ the whole way

def test_recovering_the_account_from_scratch(client, database, outbox):
    register(client)

    stranger = other(client)               # a device that was never signed in
    ask(stranger, "ana@ejemplo.com")
    assert type_code(stranger, code_from_outbox(outbox)).headers["Location"].endswith(
        "/recover/new")
    done = set_new(stranger)

    assert done.status_code == 302
    assert done.headers["Location"].endswith("/dashboard?updated=1")
    # Signed in on this device, with the new password saved.
    assert stranger.get("/dashboard").status_code == 200
    account = accounts.by_email(database, "ana@ejemplo.com")
    assert verify_password(NEW, account["password_hash"])


def test_recovering_closes_every_other_session(client, database, outbox):
    """Whoever knew the old password stops being inside.

    That is the whole point of recovering it: if the reason was that somebody
    else got in, leaving their session open would make the change pointless.
    """
    register(client)
    phone, computer = other(client), other(client)
    login(phone)
    login(computer)

    stranger = other(client)
    ask(stranger, "ana@ejemplo.com")
    type_code(stranger, code_from_outbox(outbox))
    set_new(stranger)

    assert phone.get("/dashboard").status_code == 302
    assert computer.get("/dashboard").status_code == 302
    assert stranger.get("/dashboard").status_code == 200
    account = accounts.by_email(database, "ana@ejemplo.com")
    assert len(sessions.for_account(database, account["_id"])) == 1


def test_the_old_password_stops_working(client, database, outbox):
    register(client)
    stranger = other(client)
    ask(stranger, "ana@ejemplo.com")
    type_code(stranger, code_from_outbox(outbox))
    set_new(stranger)

    assert login(other(client)).status_code == 200                  # la vieja
    assert login(other(client), password=NEW).status_code == 302    # la nueva


# ------------------------------------------------------------- what it hides

def test_it_answers_the_same_for_an_address_with_no_account(client, database,
                                                            outbox):
    register(client)

    real, unknown = other(client), other(client)
    assert page_shape(ask(real, "ana@ejemplo.com")) == page_shape(
        ask(unknown, "nadie@ejemplo.com"))
    # And no mail was written for the address that does not exist.
    assert len([p for p in outbox.glob("*.txt")
                if "recuperar" in p.read_text(encoding="utf-8").lower()]) == 1


# ------------------------------------------------------ pedir otro código

def ask_again(client):
    """«Pedir otro código» en la pantalla del código: sin ninguna dirección."""
    client.get("/recover/code")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/recover", data={"csrf_token": csrf, "otro": "1"})


def test_otro_codigo_no_pregunta_la_direccion(client, database, outbox):
    """Sale a la que se escribió la primera vez, y el nuevo es el que vale."""
    register(client)
    stranger = other(client)
    ask(stranger, "ana@ejemplo.com")
    first = code_from_outbox(outbox)

    pantalla = stranger.get("/recover/code").get_data(as_text=True)
    assert 'action="/recover"' in pantalla and 'name="email"' not in pantalla

    answer = ask_again(stranger)
    assert answer.headers["Location"].endswith("/recover/code?resent=ok")
    assert "Te enviamos un código nuevo" in stranger.get(
        answer.headers["Location"]).get_data(as_text=True)
    second = code_from_outbox(outbox)
    assert second != first
    ultimo = list(database.mail_log.find({"purpose": mail_log.RECOVER}))[-1]
    assert ultimo["to"] == "ana@ejemplo.com"
    assert type_code(stranger, second).headers["Location"].endswith(
        "/recover/new")


def test_otro_codigo_contesta_igual_sin_cuenta(client, database, outbox):
    """La regla 7 sigue: pedir otro para una dirección sin cuenta se ve igual
    y no manda nada."""
    register(client)
    real, unknown = other(client), other(client)
    ask(real, "ana@ejemplo.com")
    ask(unknown, "nadie@ejemplo.com")

    one, two = ask_again(real), ask_again(unknown)

    assert one.headers["Location"] == two.headers["Location"]
    assert page_shape(real.get(one.headers["Location"])) == page_shape(
        unknown.get(two.headers["Location"]))
    assert database.mail_log.count_documents({"to": "nadie@ejemplo.com"}) == 0


def test_without_a_code_nothing_advances(client, database, outbox):
    register(client)
    unknown = other(client)
    ask(unknown, "nadie@ejemplo.com")

    refused = type_code(unknown, "000000")
    assert refused.status_code == 200
    assert "no es correcto" in refused.get_data(as_text=True)
    # And the last screen refuses to draw itself without a code behind it.
    assert unknown.get("/recover/new").headers["Location"].endswith("/recover")


def test_the_code_dies_after_five_tries(client, database, outbox):
    register(client)
    stranger = other(client)
    ask(stranger, "ana@ejemplo.com")
    code = code_from_outbox(outbox)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(tokens.MAX_ATTEMPTS):
        last = type_code(stranger, wrong)
    assert "Demasiados intentos" in last.get_data(as_text=True)
    assert "Demasiados intentos" in type_code(stranger, code).get_data(as_text=True)


def test_a_spent_code_cannot_be_used_twice(client, database, outbox):
    register(client)
    stranger = other(client)
    ask(stranger, "ana@ejemplo.com")
    code = code_from_outbox(outbox)
    type_code(stranger, code)
    set_new(stranger)

    again = other(client)
    ask(again, "ana@ejemplo.com")          # empieza de nuevo, sin código válido
    assert "no es correcto" in type_code(again, code).get_data(as_text=True)


# ------------------------------------------------- the door from the inside

def test_signed_in_the_form_does_not_ask_for_the_address(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    body = inside.get("/recover").get_data(as_text=True)
    assert "ana@ejemplo.com" in body
    assert 'name="email"' not in body


def test_changing_it_from_inside_without_the_old_one(client, database, outbox):
    """The second door: same path, address already known.

    It still asks for something —the code in the inbox— because a session left
    open on a borrowed computer must not be enough to lock its owner out.
    """
    register(client)
    inside = other(client)
    login(inside)

    ask(inside)                            # sin escribir el correo
    type_code(inside, code_from_outbox(outbox))
    assert set_new(inside).status_code == 302
    assert verify_password(NEW, accounts.by_email(database, "ana@ejemplo.com")["password_hash"])


# ------------------------------------------------------------------ the log

def test_every_step_is_recorded(client, database, outbox):
    register(client)
    stranger = other(client)
    ask(stranger, "ana@ejemplo.com")
    type_code(stranger, code_from_outbox(outbox))
    set_new(stranger)

    assert [d["outcome"] for d in
            database.auth_events.find({"kind": events.RECOVER}).sort("created_at", 1)] == [
        events.SENT, events.OK]
    # The code went out, and so did the notice that the password changed.
    assert database.mail_log.count_documents({"purpose": mail_log.RECOVER}) == 1
    assert database.mail_log.count_documents({"purpose": mail_log.PASSWORD_CHANGED}) == 1


def test_an_unknown_address_is_recorded_as_such(client, database, outbox):
    unknown = other(client)
    ask(unknown, "nadie@ejemplo.com")

    assert [d["outcome"] for d in database.auth_events.find({"kind": events.RECOVER})] == [
        events.NO_ACCOUNT]
    assert database.mail_log.count_documents({}) == 0


# ------------------------------------- recuperar mientras se agrega una cuenta

def other(client):
    return client.application.test_client()


def adding(browser):
    """Abrir la pantalla de entrar en modo «agregar otra cuenta»."""
    return browser.get("/login?add=1")


def test_agregando_una_cuenta_se_recupera_la_otra(client, database, outbox):
    """El fallo que había: estando dentro de A y agregando B, «olvidé la
    contraseña» mandaba el código al buzón de A, que es justo donde no hace
    falta."""
    register(client, email="una@ejemplo.com")
    register(client, email="dos@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")
    adding(browser)

    pantalla = browser.get("/recover").get_data(as_text=True)
    # Pregunta la dirección en vez de dar por hecho la de la sesión.
    assert "una@ejemplo.com" not in pantalla

    ask(browser, "dos@ejemplo.com")

    ultimo = list(database.mail_log.find({"purpose": mail_log.RECOVER}))[-1]
    assert ultimo["to"] == "dos@ejemplo.com"


def test_al_recuperar_la_segunda_la_primera_sigue_abierta(client, database,
                                                          outbox):
    register(client, email="una@ejemplo.com")
    register(client, email="dos@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")
    adding(browser)

    ask(browser, "dos@ejemplo.com")
    type_code(browser, code_from_outbox(outbox))
    browser.get("/recover/new")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    browser.post("/recover/new", data={"csrf_token": token,
                                           "password": NEW, "repeat": NEW})

    una = accounts.by_email(database, "una@ejemplo.com")["_id"]
    dos = accounts.by_email(database, "dos@ejemplo.com")["_id"]
    with browser.session_transaction() as sess:
        abiertas = [sessions.find(database, raw) for raw in sess.get("sids") or []]
    cuales = {doc["account_id"] for doc in abiertas if doc}
    assert cuales == {una, dos}


def test_dentro_de_la_propia_cuenta_sigue_sin_preguntar(client, database, outbox):
    """Lo de siempre: quien está en su cuenta y olvidó su contraseña no tiene
    que volver a escribir su dirección."""
    register(client, email="una@ejemplo.com")
    browser = other(client)
    login(browser, email="una@ejemplo.com")

    pantalla = browser.get("/recover").get_data(as_text=True)
    assert "una@ejemplo.com" in pantalla

    ask(browser)
    ultimo = list(database.mail_log.find({"purpose": mail_log.RECOVER}))[-1]
    assert ultimo["to"] == "una@ejemplo.com"
