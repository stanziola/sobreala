"""The two audit trails: mail_log and auth_events.

What these pin down is not that a document appears, but that it says the right
thing in the cases that are easy to get wrong: a duplicate registration, a
failed send, a wrong password against an address that does exist. Plus the two
rules that must never bend — the password never lands in either collection, and
the screen keeps its answers identical even though the log knows the difference.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from conftest import (code_from_outbox, confirm, login, logout, page_shape,
                      register)

import db as db_module
from config import Config
from models import account as accounts
from models import auth_event as events
from models import mail_log
from services import mailer
from services.security import now


def has_a_code(body: str) -> bool:
    return bool(re.search(r"^\d{6}$", body, re.M))


def outcomes(database, kind: str) -> list[str]:
    """Every outcome recorded for one kind of attempt, oldest first."""
    return [d["outcome"] for d in
            database.auth_events.find({"kind": kind}).sort("created_at", 1)]


# --------------------------------------------------------------------- mail_log

def test_the_confirmation_mail_is_recorded_with_its_body(client, database, outbox):
    register(client)
    row = database.mail_log.find_one({"purpose": mail_log.CONFIRM})

    assert row is not None
    assert row["status"] == mail_log.SENT
    assert row["backend"] == "file"
    assert row["to"] == "ana@ejemplo.com"
    assert row["to_normalized"] == "ana@ejemplo.com"
    assert row["error"] is None
    assert row["provider_id"]
    # The body is kept so the exact message, code included, can be read back.
    code = code_from_outbox(outbox)
    assert code in row["text"]
    assert code in row["html"]

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert row["account_id"] == account["_id"]


def test_the_address_is_normalised_in_the_mail_log(client, database, outbox):
    register(client, email="  ANA@Ejemplo.COM ")
    row = database.mail_log.find_one({"purpose": mail_log.CONFIRM})
    assert row["to_normalized"] == "ana@ejemplo.com"


def test_the_already_registered_notice_is_recorded_too(client, database, outbox):
    register(client)
    register(client)

    assert database.mail_log.count_documents({"purpose": mail_log.CONFIRM}) == 1
    notice = database.mail_log.find_one({"purpose": mail_log.EXISTS})
    assert notice is not None
    assert notice["status"] == mail_log.SENT
    assert "ya tiene una cuenta" in notice["text"]


def test_the_welcome_is_recorded_with_its_own_purpose(client, database, outbox):
    register(client)
    confirm(client, code_from_outbox(outbox))

    row = database.mail_log.find_one({"purpose": mail_log.WELCOME})
    assert row is not None
    assert row["status"] == mail_log.SENT
    assert row["to"] == "ana@ejemplo.com"
    assert row["account_id"] == accounts.by_email(database, "ana@ejemplo.com")["_id"]
    # The logo travels as a hosted image, not embedded: mail clients do not
    # draw SVG and nobody wants 26 KB more of message.
    assert "/assets/img/logo-wing.png" in row["html"]


def test_a_failed_send_undoes_the_registration(client, database, outbox,
                                              monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("el proveedor rechazo el mensaje")

    monkeypatch.setattr(mailer, "_send_file", explode)

    response = register(client)
    assert response.status_code == 200
    assert "no creamos la cuenta" in response.get_data(as_text=True)

    # Nothing is left behind: no account, and no code pointing at one.
    assert accounts.by_email(database, "ana@ejemplo.com") is None
    assert database.accounts.count_documents({}) == 0
    assert database.account_tokens.count_documents({}) == 0

    row = database.mail_log.find_one({})
    assert row["status"] == mail_log.FAILED
    assert "RuntimeError" in row["error"]
    assert "rechazo" in row["error"]
    assert row["provider_id"] is None
    # The body is kept on failure as well, which is what keeps the attempt
    # readable afterwards even though the account is gone.
    assert has_a_code(row["text"])

    # And the trail tells the whole story: created, then the mail failed. The
    # account no longer exists; these two rows are what say it ever did.
    assert outcomes(database, events.REGISTER) == [events.CREATED, events.MAIL_FAILED]


def test_a_taken_address_is_told_so_even_when_the_mail_fails(
        client, database, outbox, monkeypatch):
    """The two branches now answer different things, and neither lies.

    A new address whose code cannot be sent is undone and says so. A taken one
    is not undone —there was nothing to undo— and says what is true: that the
    account exists. The notice to its owner failing changes nothing on screen.
    """
    register(client)  # ana@ejemplo.com exists, from back when mail worked

    def explode(*args, **kwargs):
        raise RuntimeError("el proveedor rechazo el mensaje")

    monkeypatch.setattr(mailer, "_send_file", explode)

    taken = register(client)
    fresh = register(client.application.test_client(), email="beto@ejemplo.com")

    assert "Ya existe una cuenta" in taken.get_data(as_text=True)
    assert "no creamos la cuenta" in fresh.get_data(as_text=True)
    # The new one was undone; the old one was never touched.
    assert database.accounts.count_documents({}) == 1


def test_a_log_failure_never_stops_the_mail(client, database, outbox, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("mongo se cayo justo ahora")

    monkeypatch.setattr(mail_log, "record", explode)

    response = register(client)
    assert response.status_code == 302
    # The mail went out even though nothing could be written about it.
    assert code_from_outbox(outbox)
    assert database.mail_log.count_documents({}) == 0


# ------------------------------------------------------------------ auth_events

def test_a_new_registration_is_recorded(client, database, outbox):
    register(client)
    row = database.auth_events.find_one({"kind": events.REGISTER})

    assert row["outcome"] == events.CREATED
    assert row["email"] == "ana@ejemplo.com"
    assert row["email_normalized"] == "ana@ejemplo.com"
    assert row["account_id"] == accounts.by_email(database, "ana@ejemplo.com")["_id"]
    assert row["ip"]


def test_a_duplicate_registration_is_recorded_as_such(client, database, outbox):
    first = register(client)
    second = register(client)

    # The screen tells them apart now, and so does the log, which is what the
    # log was always for.
    assert first.status_code == 302 and second.status_code == 200
    assert outcomes(database, events.REGISTER) == [events.CREATED,
                                                   events.ALREADY_REGISTERED]


def test_an_invalid_form_is_recorded(client, database):
    client.get("/registro")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    client.post("/registro", data={"csrf_token": csrf, "company_name": "X",
                                   "contact_name": "Y", "email": "corta@ejemplo.com",
                                   "password": "corta"})
    assert outcomes(database, events.REGISTER) == [events.INVALID]
    assert database.accounts.count_documents({}) == 0


def test_a_form_without_csrf_is_recorded(client, database):
    client.post("/registro", data={"company_name": "X", "contact_name": "Y",
                                   "email": "sin@ejemplo.com",
                                   "password": "Contrasena-Larga1"})
    assert outcomes(database, events.REGISTER) == [events.CSRF_FAILED]


def test_a_good_login_and_a_bad_one_are_told_apart(client, database, outbox):
    register(client)
    login(client)
    logout(client)  # you cannot attempt a sign-in while already signed in
    login(client, password="otra-contrasena")

    assert outcomes(database, events.LOGIN) == [events.OK, events.BAD_CREDENTIALS]

    good = database.auth_events.find_one({"kind": events.LOGIN,
                                          "outcome": events.OK})
    account = accounts.by_email(database, "ana@ejemplo.com")
    assert good["account_id"] == account["_id"]


def test_a_wrong_password_on_a_real_account_keeps_the_account_id(client, database,
                                                                 outbox):
    register(client)
    login(client, password="otra-contrasena")
    login(client, email="nadie@ejemplo.com")

    rows = list(database.auth_events.find({"kind": events.LOGIN}).sort("created_at", 1))
    account = accounts.by_email(database, "ana@ejemplo.com")
    # Same outcome for both, because the visitor is told the same thing. The id
    # separates them in the log, which is how an attack on a real account shows.
    assert [r["outcome"] for r in rows] == [events.BAD_CREDENTIALS] * 2
    assert rows[0]["account_id"] == account["_id"]
    assert rows[1]["account_id"] is None


def test_hitting_the_login_limit_is_recorded(client, database, outbox):
    register(client)
    # The budget is 20 per IP per 15 minutes; go one past it.
    for _ in range(22):
        login(client, password="otra-contrasena")

    recorded = outcomes(database, events.LOGIN)
    assert events.RATE_LIMITED in recorded
    assert recorded.count(events.BAD_CREDENTIALS) == 20


def test_logout_is_recorded_with_the_account_id(client, database, outbox):
    register(client)
    login(client)
    account = accounts.by_email(database, "ana@ejemplo.com")

    logout(client)

    row = database.auth_events.find_one({"kind": events.LOGOUT})
    assert row["outcome"] == events.OK
    # Stored as an ObjectId, not the string the session cookie carries, so the
    # field can be joined against accounts.
    assert row["account_id"] == account["_id"]


def test_the_three_resend_outcomes(client, database, outbox):
    def ask(email):
        client.get("/reenviar-confirmacion")
        with client.session_transaction() as sess:
            csrf = sess["_csrf"]
        return client.post("/reenviar-confirmacion",
                           data={"csrf_token": csrf, "email": email})

    unknown = ask("nadie@ejemplo.com")
    register(client)
    pending = ask("ana@ejemplo.com")
    confirm(client, code_from_outbox(outbox))
    confirmed = ask("ana@ejemplo.com")

    assert outcomes(database, events.RESEND) == [events.NO_ACCOUNT, events.SENT,
                                                 events.ALREADY_CONFIRMED]
    # All three answer identically, whatever the log says.
    assert {r.status_code for r in (unknown, pending, confirmed)} == {302}
    assert all(r.headers["Location"].endswith("/confirmar")
               for r in (unknown, pending, confirmed))


def test_the_log_separates_what_the_confirmation_screen_merges(client, database,
                                                               outbox):
    register(client)
    code = code_from_outbox(outbox)
    confirm(client, "000000" if code != "000000" else "111111")
    confirm(client, code)
    # Signing in cleared the session, so this last one has no code waiting.
    confirm(client, code)

    # Three rows for what the visitor saw as two identical refusals around one
    # success.
    assert outcomes(database, events.CONFIRM) == ["invalid_code", "ok", "no_code"]


def test_an_expired_code_is_recorded_as_expired(client, database, outbox):
    register(client)
    code = code_from_outbox(outbox)
    database.account_tokens.update_one(
        {}, {"$set": {"expires_at": now() - timedelta(minutes=1)}})
    confirm(client, code)

    assert outcomes(database, events.CONFIRM) == ["expired"]


# ------------------------------------------------------------------- the rules

def test_the_password_never_reaches_either_collection(client, database, outbox):
    secret = "Contrasena-Secreta1!"
    register(client, password=secret)
    login(client, password=secret)
    logout(client)
    login(client, password="otra-cosa")

    for name in ("auth_events", "mail_log"):
        for doc in database[name].find({}):
            assert secret not in str(doc), f"la contraseña apareció en {name}"


# ------------------------------------------------- the page when mongo is down

@pytest.fixture()
def unreachable_db(monkeypatch):
    """A client whose database refuses every connection.

    PROPAGATE_EXCEPTIONS is turned off on purpose: TESTING alone re-raises
    instead of running the error handlers, which is exactly what needs to be
    observed here.
    """
    monkeypatch.setattr(Config, "MONGODB_URI", "mongodb://127.0.0.1:1/")
    monkeypatch.setattr(db_module, "SERVER_SELECTION_TIMEOUT_MS", 200)
    db_module._client = None

    from app import create_app
    application = create_app({"TESTING": True, "SECRET_KEY": "test-key",
                              "SESSION_COOKIE_SECURE": False,
                              "PROPAGATE_EXCEPTIONS": False})
    yield application.test_client()
    db_module._client = None


def test_a_dead_database_gives_a_readable_page_not_a_bare_500(unreachable_db):
    # The form itself still draws: it never touches the database.
    assert unreachable_db.get("/entrar").status_code == 200
    with unreachable_db.session_transaction() as sess:
        csrf = sess["_csrf"]

    response = unreachable_db.post("/entrar", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com",
        "password": "Contrasena-Larga1"})
    body = response.get_data(as_text=True)

    # 503, not 500: the application is fine, its database is not.
    assert response.status_code == 503
    assert "no está disponible" in body
    assert "Internal Server Error" not in body
    # None of the technical detail may reach the visitor.
    assert "127.0.0.1" not in body
    assert "ServerSelectionTimeoutError" not in body
    assert "Traceback" not in body


def test_the_health_route_reports_a_dead_database(unreachable_db):
    response = unreachable_db.get("/salud")
    assert response.status_code == 503
    payload = response.get_json()
    assert payload["app"] == "up"
    assert payload["database"] == "down"
    assert payload["indexes"] is False
