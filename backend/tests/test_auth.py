"""Registration, confirmation and login."""

from __future__ import annotations

from datetime import timedelta

from conftest import code_from_outbox, confirm, login, page_shape, register

from models import account as accounts
from models import token as tokens
from services.security import hash_code, now

WRONG = "000000"


def other_code(code: str) -> str:
    """A code that is definitely not this one."""
    return WRONG if code != WRONG else "111111"


# ------------------------------------------------------------------ registration

def test_register_creates_account_and_sends_a_code(client, database, outbox):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/confirmar")

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert account is not None
    assert account["status"] == accounts.REGISTERED
    assert account["email_confirmed_at"] is None
    assert len(code_from_outbox(outbox)) == 6


def test_email_is_normalised(client, database):
    register(client, email="  ANA@Ejemplo.COM ")
    assert accounts.by_email(database, "ana@ejemplo.com") is not None
    assert database.accounts.count_documents({}) == 1


def test_password_is_never_stored_in_the_clear(client, database):
    register(client, password="Contrasena-Larga1")
    account = accounts.by_email(database, "ana@ejemplo.com")
    assert "Contrasena-Larga1" not in str(account)
    assert account["password_hash"].startswith("$2")


def test_code_in_the_email_is_not_the_one_stored(client, database, outbox):
    register(client)
    code = code_from_outbox(outbox)
    stored = database.account_tokens.find_one({})
    assert code not in str(stored)
    assert stored["code_hash"] == hash_code(code)


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
        "email": "sin@ejemplo.com", "password": "Contrasena-Larga1",
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

def test_confirmation_works_and_signs_in(client, database, outbox):
    register(client)
    response = confirm(client, code_from_outbox(outbox))

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/panel")
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"]
    # Confirming leaves the visitor inside, without asking for the password
    # they typed two screens ago.
    assert "Hola, Ana" in client.get("/panel").get_data(as_text=True)


def test_a_used_code_does_not_work_twice(client, database, outbox):
    register(client)
    code = code_from_outbox(outbox)
    confirm(client, code)

    again = confirm(client, code)
    assert again.status_code == 200
    assert "no es correcto o ya venció" in again.get_data(as_text=True)


def test_a_wrong_code_is_refused_and_counted(client, database, outbox):
    register(client)
    response = confirm(client, other_code(code_from_outbox(outbox)))

    assert response.status_code == 200
    assert "no es correcto o ya venció" in response.get_data(as_text=True)
    assert database.account_tokens.find_one({})["attempts"] == 1
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"] is None


def test_a_code_dies_after_five_wrong_tries(client, database, outbox):
    register(client)
    code = code_from_outbox(outbox)
    wrong = other_code(code)

    for _ in range(tokens.MAX_ATTEMPTS):
        last = confirm(client, wrong)
    assert "Demasiados intentos" in last.get_data(as_text=True)

    # And the real code is worth nothing now: the way back is a new one.
    dead = confirm(client, code)
    assert "Demasiados intentos" in dead.get_data(as_text=True)
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"] is None


def test_an_expired_code_is_refused(client, database, outbox):
    register(client)
    code = code_from_outbox(outbox)
    database.account_tokens.update_one(
        {}, {"$set": {"expires_at": now() - timedelta(minutes=1)}})

    response = confirm(client, code)
    assert "no es correcto o ya venció" in response.get_data(as_text=True)
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"] is None


def test_a_wrong_code_reads_the_same_with_and_without_an_account(client, database, outbox):
    """Rule 7 on the confirmation screen.

    Registering an address that is already taken issues no code at all, so the
    form has nothing to compare against. That must not be visible: the answer to
    a wrong code has to read exactly like the answer for an address that does
    have one waiting.
    """
    register(client)                     # ana@ejemplo.com now exists
    taken = register(client)             # same address again: no code issued
    assert taken.status_code == 302
    without = page_shape(confirm(client, WRONG))

    fresh = client.application.test_client()
    register(fresh, email="beto@ejemplo.com")
    with_code = page_shape(confirm(fresh, other_code(code_from_outbox(outbox))))

    assert without == with_code


def test_resending_replaces_the_previous_code(client, database, outbox):
    register(client)
    first = code_from_outbox(outbox)

    client.get("/reenviar-confirmacion")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    client.post("/reenviar-confirmacion", data={"csrf_token": csrf, "email": "ana@ejemplo.com"})
    second = code_from_outbox(outbox)

    assert first != second
    assert database.account_tokens.count_documents({}) == 1
    assert "no es correcto" in confirm(client, first).get_data(as_text=True)
    assert confirm(client, second).headers["Location"].endswith("/panel")


def test_resend_answers_the_same_for_an_unknown_address(client, database, outbox):
    client.get("/reenviar-confirmacion")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    response = client.post("/reenviar-confirmacion",
                           data={"csrf_token": csrf, "email": "nadie@ejemplo.com"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/confirmar")
    assert list(outbox.glob("*.txt")) == []


# ------------------------------------------------------------------------ login

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

    client.get("/reenviar-confirmacion")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    client.post("/reenviar-confirmacion", data={"csrf_token": csrf, "email": "ana@ejemplo.com"})
    confirm(client, code_from_outbox(outbox))
    assert "confirmas tu correo" not in client.get("/panel").get_data(as_text=True)


def test_panel_needs_a_session(client, database):
    assert client.get("/panel").status_code == 302


# ------------------------------------------------------------------------ model

def test_unique_index_rejects_a_repeated_address(client, database):
    register(client)
    assert accounts.create(database, company_name="Otra", contact_name="Beto",
                           email="ANA@ejemplo.com", password="Contrasena-Larga1") is None


def test_code_is_single_use_at_the_model_level(database):
    account = accounts.create(database, company_name="X", contact_name="Y",
                              email="uno@ejemplo.com", password="Contrasena-Larga1")
    code = tokens.issue(database, account["_id"])
    reason, doc = tokens.check(database, account["_id"], code)
    assert reason == tokens.VALID
    assert tokens.spend(database, doc) is True
    assert tokens.spend(database, doc) is False
    assert tokens.check(database, account["_id"], code)[0] == tokens.USED


def test_an_account_without_a_code_is_not_told_so_at_the_model_level(database):
    account = accounts.create(database, company_name="X", contact_name="Y",
                              email="dos@ejemplo.com", password="Contrasena-Larga1")
    # The distinction exists here, in the log's language, and dies at the screen.
    assert tokens.check(database, account["_id"], WRONG)[0] == tokens.UNKNOWN
    tokens.issue(database, account["_id"])
    assert tokens.check(database, account["_id"], WRONG)[0] == tokens.INVALID


def test_discard_throws_the_code_away(database):
    account = accounts.create(database, company_name="X", contact_name="Y",
                              email="tres@ejemplo.com", password="Contrasena-Larga1")
    tokens.issue(database, account["_id"])
    tokens.discard(database, account["_id"])
    assert database.account_tokens.count_documents({}) == 0
