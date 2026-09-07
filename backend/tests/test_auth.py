"""Registration, confirmation and login."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

import pytest
from conftest import link_from_outbox, register

from models import account as accounts
from models import token as tokens
from services.security import hash_token, now


def path_of(url: str) -> str:
    return urlparse(url).path


# ------------------------------------------------------------------ registration

def test_register_creates_account_and_sends_link(client, database, outbox):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/revisa-tu-correo")

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert account is not None
    assert account["status"] == accounts.REGISTERED
    assert account["email_confirmed_at"] is None
    assert link_from_outbox(outbox)


def test_email_is_normalised(client, database):
    register(client, email="  ANA@Ejemplo.COM ")
    assert accounts.by_email(database, "ana@ejemplo.com") is not None
    assert database.accounts.count_documents({}) == 1


def test_password_is_never_stored_in_the_clear(client, database):
    register(client, password="contrasena-larga")
    account = accounts.by_email(database, "ana@ejemplo.com")
    assert "contrasena-larga" not in str(account)
    assert account["password_hash"].startswith("$2")


def test_token_in_the_link_is_not_the_one_stored(client, database, outbox):
    register(client)
    raw = path_of(link_from_outbox(outbox)).rsplit("/", 1)[-1]
    stored = database.account_tokens.find_one({})
    assert stored["token_hash"] != raw
    assert stored["token_hash"] == hash_token(raw)


def test_short_password_is_refused(client, database):
    client.get("/registro")
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    response = client.post("/registro", data={
        "csrf_token": token, "company_name": "X", "contact_name": "Y",
        "email": "corta@ejemplo.com", "password": "corta",
    })
    assert response.status_code == 200
    assert database.accounts.count_documents({}) == 0


def test_password_over_the_bcrypt_limit_is_refused(client, database):
    client.get("/registro")
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    response = client.post("/registro", data={
        "csrf_token": token, "company_name": "X", "contact_name": "Y",
        "email": "larga@ejemplo.com", "password": "a" * 100,
    })
    assert response.status_code == 200
    assert database.accounts.count_documents({}) == 0


def test_registering_without_csrf_does_nothing(client, database):
    client.post("/registro", data={
        "company_name": "X", "contact_name": "Y",
        "email": "sin@ejemplo.com", "password": "contrasena-larga",
    })
    assert database.accounts.count_documents({}) == 0


def test_duplicate_address_answers_exactly_like_a_new_one(client, database, outbox):
    first = register(client)
    second = register(client)
    assert first.headers["Location"] == second.headers["Location"]
    assert first.status_code == second.status_code
    # Still one account, and the owner was warned by email.
    assert database.accounts.count_documents({}) == 1
    assert len(list(outbox.glob("*.txt"))) == 2
    assert "ya tiene una cuenta" in sorted(outbox.glob("*.txt"))[-1].read_text(encoding="utf-8")


# ------------------------------------------------------------------ confirmation

def test_confirmation_works_once(client, database, outbox):
    register(client)
    link = path_of(link_from_outbox(outbox))

    first = client.get(link)
    assert "quedó confirmado" in first.get_data(as_text=True)
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"]

    second = client.get(link)
    assert "ya estaba confirmado" in second.get_data(as_text=True)


def test_expired_link_says_so(client, database, outbox):
    register(client)
    link = path_of(link_from_outbox(outbox))
    database.account_tokens.update_one({}, {"$set": {"expires_at": now() - timedelta(minutes=1)}})

    response = client.get(link)
    assert "venció" in response.get_data(as_text=True)
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"] is None


def test_invented_link_is_refused(client, database):
    response = client.get("/confirmar/no-existe-este-token")
    assert "no sirve" in response.get_data(as_text=True)


def test_resending_invalidates_the_previous_link(client, database, outbox):
    register(client)
    first = path_of(link_from_outbox(outbox))

    client.get("/reenviar-confirmacion")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    client.post("/reenviar-confirmacion", data={"csrf_token": csrf, "email": "ana@ejemplo.com"})
    second = path_of(link_from_outbox(outbox))

    assert first != second
    assert "no sirve" in client.get(first).get_data(as_text=True)
    assert "quedó confirmado" in client.get(second).get_data(as_text=True)


def test_resend_answers_the_same_for_an_unknown_address(client, database, outbox):
    client.get("/reenviar-confirmacion")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    response = client.post("/reenviar-confirmacion",
                           data={"csrf_token": csrf, "email": "nadie@ejemplo.com"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/revisa-tu-correo")
    assert list(outbox.glob("*.txt")) == []


# ------------------------------------------------------------------------ login

def login(client, email="ana@ejemplo.com", password="contrasena-larga"):
    client.get("/entrar")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/entrar", data={"csrf_token": csrf, "email": email,
                                        "password": password})


def test_login_and_logout(client, database):
    register(client)
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/panel")

    panel = client.get("/panel")
    assert "Hola, Ana" in panel.get_data(as_text=True)

    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    client.post("/salir", data={"csrf_token": csrf})
    assert client.get("/panel").status_code == 302


def test_wrong_password_does_not_get_in(client, database):
    register(client)
    response = login(client, password="otra-contrasena")
    assert response.status_code == 200
    assert "no coinciden" in response.get_data(as_text=True)
    assert client.get("/panel").status_code == 302


def test_unknown_address_answers_like_a_wrong_password(client, database):
    register(client)
    wrong_password = login(client, password="otra-contrasena").get_data(as_text=True)
    unknown = login(client, email="nadie@ejemplo.com").get_data(as_text=True)
    assert "no coinciden" in wrong_password
    assert "no coinciden" in unknown


def test_panel_warns_until_the_address_is_confirmed(client, database, outbox):
    register(client)
    login(client)
    assert "confirmas tu correo" in client.get("/panel").get_data(as_text=True)

    client.get(path_of(link_from_outbox(outbox)))
    assert "confirmas tu correo" not in client.get("/panel").get_data(as_text=True)


def test_panel_needs_a_session(client, database):
    assert client.get("/panel").status_code == 302


# ------------------------------------------------------------------------ model

def test_unique_index_rejects_a_repeated_address(client, database):
    register(client)
    assert accounts.create(database, company_name="Otra", contact_name="Beto",
                           email="ANA@ejemplo.com", password="contrasena-larga") is None


def test_token_is_single_use_at_the_model_level(database):
    account = accounts.create(database, company_name="X", contact_name="Y",
                              email="uno@ejemplo.com", password="contrasena-larga")
    raw = tokens.issue(database, account["_id"])
    reason, doc = tokens.check(database, raw)
    assert reason == tokens.VALID
    assert tokens.spend(database, doc) is True
    assert tokens.spend(database, doc) is False
    assert tokens.check(database, raw)[0] == tokens.USED
