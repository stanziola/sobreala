"""The two audit trails: mail_log and auth_events.

What these pin down is not that a document appears, but that it says the right
thing in the cases that are easy to get wrong: a duplicate registration, a
failed send, a wrong password against an address that does exist. Plus the two
rules that must never bend — the password never lands in either collection, and
the screen keeps its answers identical even though the log knows the difference.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

import pytest
from conftest import link_from_outbox, login, logout, register

import db as db_module
from config import Config
from models import account as accounts
from models import auth_event as events
from models import mail_log
from services import mailer
from services.security import now


def path_of(url: str) -> str:
    return urlparse(url).path


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
    # The body is kept so the exact message, link included, can be read back.
    assert "/confirmar/" in row["text"]
    assert "/confirmar/" in row["html"]

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


def test_a_failed_send_is_recorded_and_the_error_still_travels(client, database,
                                                               outbox, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("el proveedor rechazo el mensaje")

    monkeypatch.setattr(mailer, "_send_file", explode)

    with pytest.raises(RuntimeError):
        register(client)

    row = database.mail_log.find_one({})
    assert row["status"] == mail_log.FAILED
    assert "RuntimeError" in row["error"]
    assert "rechazo" in row["error"]
    assert row["provider_id"] is None
    # The body is kept on failure as well, which is what makes a retry possible.
    assert "/confirmar/" in row["text"]

    # And the trail shows the account did get created before the mail failed:
    # that pairing is the whole point of recording both.
    assert accounts.by_email(database, "ana@ejemplo.com") is not None
    assert outcomes(database, events.REGISTER) == [events.CREATED]


def test_a_log_failure_never_stops_the_mail(client, database, outbox, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("mongo se cayo justo ahora")

    monkeypatch.setattr(mail_log, "record", explode)

    response = register(client)
    assert response.status_code == 302
    # The mail went out even though nothing could be written about it.
    assert link_from_outbox(outbox)
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

    # The screen cannot tell the two apart, per rule 7 in CLAUDE.md...
    assert first.status_code == second.status_code
    assert first.headers["Location"] == second.headers["Location"]
    # ...but the log does, which is what it is for.
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
                                   "password": "contrasena-larga"})
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
    client.get(path_of(link_from_outbox(outbox)))
    confirmed = ask("ana@ejemplo.com")

    assert outcomes(database, events.RESEND) == [events.NO_ACCOUNT, events.SENT,
                                                 events.ALREADY_CONFIRMED]
    # All three answer identically, whatever the log says.
    assert {r.status_code for r in (unknown, pending, confirmed)} == {302}
    assert all(r.headers["Location"].endswith("/revisa-tu-correo")
               for r in (unknown, pending, confirmed))


def test_confirmation_outcomes_match_what_the_page_shows(client, database, outbox):
    register(client)
    link = path_of(link_from_outbox(outbox))
    client.get(link)
    client.get(link)
    client.get("/confirmar/no-existe-este-token")

    assert outcomes(database, events.CONFIRM) == ["ok", "already", "unknown"]


def test_an_expired_link_is_recorded_as_expired(client, database, outbox):
    register(client)
    link = path_of(link_from_outbox(outbox))
    database.account_tokens.update_one(
        {}, {"$set": {"expires_at": now() - timedelta(minutes=1)}})
    client.get(link)

    assert outcomes(database, events.CONFIRM) == ["expired"]


# ------------------------------------------------------------------- the rules

def test_the_password_never_reaches_either_collection(client, database, outbox):
    secret = "contrasena-secretisima"
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
        "password": "contrasena-larga"})
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
