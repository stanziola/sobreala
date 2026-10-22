"""Test fixtures.

The tests run against MONGODB_TEST_URI, never the real cluster: the database is
dropped between tests. Mail goes to a temporary directory, so nothing is sent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from config import Config  # noqa: E402
import db as db_module  # noqa: E402


@pytest.fixture(autouse=True)
def outbox(tmp_path, monkeypatch):
    box = tmp_path / "outbox"
    monkeypatch.setattr(Config, "MAIL_BACKEND", "file")
    monkeypatch.setattr(Config, "MAIL_OUTBOX_DIR", str(box))
    return box


@pytest.fixture(autouse=True)
def no_dns_for_dmarc(monkeypatch):
    """Las pruebas no le preguntan al DNS de verdad por el DMARC de un dominio
    (octubre de 2026): sin saberlo, «sin comprobar». La que lo prueba lo cambia."""
    from services import ses_identity
    monkeypatch.setattr(ses_identity, "_lookup_dmarc",
                        lambda domain: ses_identity.DMARC_UNKNOWN)
    monkeypatch.setattr(ses_identity, "_dmarc_seen", {})


@pytest.fixture()
def database(monkeypatch):
    monkeypatch.setattr(Config, "MONGODB_URI", Config.MONGODB_TEST_URI)
    monkeypatch.setattr(Config, "MONGODB_DB", Config.MONGODB_TEST_DB)
    db_module._client = None  # force a client bound to the test URI

    client = db_module.get_client()
    client.drop_database(Config.MONGODB_TEST_DB)
    database = client[Config.MONGODB_TEST_DB]
    db_module.ensure_indexes(database)
    yield database
    client.drop_database(Config.MONGODB_TEST_DB)
    db_module._client = None


@pytest.fixture()
def app(database):
    from app import create_app
    application = create_app({"TESTING": True, "SECRET_KEY": "test-key",
                              "SESSION_COOKIE_SECURE": False})
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# La dirección por partes, como la mandan el registro y Configuración (octubre
# de 2026), y lo que el registro pide además: la casilla de los términos.
ADDRESS = {"address_line1": "Calle 10", "address_line2": "",
           "address_city": "Santiago de Veraguas", "address_region": "Veraguas",
           "address_postal_code": "", "address_country": "PA"}
SIGNUP_EXTRA = {**ADDRESS, "terms": "1"}


def register(client, email="ana@ejemplo.com", password="Contrasena-Larga1", *,
             abierta=True):
    """Fill the registration form the way a browser would, CSRF included.

    La cuenta queda abierta, como si ya hubiera tenido su demostración: casi
    todas las pruebas son de lo que se hace dentro del panel, no de la puerta.
    Las que prueban la puerta piden `abierta=False`. Desde octubre de 2026 el
    registro trae el teléfono y la dirección.
    """
    client.get("/signup")  # seeds the CSRF value in the session
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    response = client.post("/signup", data={
        "csrf_token": token,
        "company_name": "Cooperativa Ejemplo",
        "contact_name": "Ana",
        "email": email,
        "phone_country": "PA",
        "phone": "60000000",
        **SIGNUP_EXTRA,
        "password": password,
    })
    if abierta:
        from models import account as accounts
        database = db_module.get_client()[Config.MONGODB_TEST_DB]
        found = accounts.by_email(database, email)
        if found is not None:
            accounts.open_account(database, found["_id"])
    return response


def login(client, email="ana@ejemplo.com", password="Contrasena-Larga1"):
    """Sign in the way a browser would, CSRF included."""
    client.get("/login")  # seeds the CSRF value in the session
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/login", data={"csrf_token": csrf, "email": email,
                                        "password": password})


def logout(client):
    """Sign out the way a browser would.

    The panel is fetched first because that page carries the logout form, and
    with it the CSRF field: signing in clears the session, so the token that was
    seeded by the login page is gone by now.
    """
    client.get("/dashboard")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/logout", data={"csrf_token": csrf})


def page_shape(response) -> str:
    """The page with everything the visitor typed, and the CSRF field, taken out.

    What is left is exactly what rule 7 governs: two answers that must be
    indistinguishable are compared through this, since a form that echoes the
    address back is allowed to differ and nothing else is.
    """
    import re
    body = response.get_data(as_text=True)
    body = re.sub(r'value="[^"]*"', 'value=""', body)
    # The CSP nonce is new on every response, and the countdown ticks between
    # two requests: neither says anything about the visitor.
    body = re.sub(r'nonce="[^"]*"', 'nonce=""', body)
    return re.sub(r'data-countdown="\d+"', 'data-countdown=""', body)


def code_from_outbox(outbox) -> str:
    """The confirmation code, read back out of the message that was written."""
    texts = sorted(outbox.glob("*.txt"))
    assert texts, "no se escribió ningún correo"
    import re
    body = texts[-1].read_text(encoding="utf-8")
    found = re.findall(r"^\d{6}$", body, flags=re.M)
    assert found, "el correo no trae código"
    return found[0]


def confirm(client, code, split=True):
    """Type a code into the confirmation form, CSRF included.

    The browser sends six fields called `code`, one per box. `split=False` sends
    a single one, which is the same form without JavaScript.
    """
    client.get("/confirm")  # seeds the CSRF value in the session
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    typed = list(digits) if split and len(digits) == 6 else [str(code)]
    return client.post("/confirm", data={"csrf_token": csrf, "code": typed})
