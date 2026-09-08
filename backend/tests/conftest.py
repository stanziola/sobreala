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


def register(client, email="ana@ejemplo.com", password="Contrasena-Larga1"):
    """Fill the registration form the way a browser would, CSRF included."""
    client.get("/registro")  # seeds the CSRF value in the session
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    return client.post("/registro", data={
        "csrf_token": token,
        "company_name": "Cooperativa Ejemplo",
        "contact_name": "Ana",
        "email": email,
        "phone": "60000000",
        "password": password,
    })


def login(client, email="ana@ejemplo.com", password="Contrasena-Larga1"):
    """Sign in the way a browser would, CSRF included."""
    client.get("/entrar")  # seeds the CSRF value in the session
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/entrar", data={"csrf_token": csrf, "email": email,
                                        "password": password})


def logout(client):
    """Sign out the way a browser would.

    The panel is fetched first because that page carries the logout form, and
    with it the CSRF field: signing in clears the session, so the token that was
    seeded by the login page is gone by now.
    """
    client.get("/panel")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/salir", data={"csrf_token": csrf})


def page_shape(response) -> str:
    """The page with everything the visitor typed, and the CSRF field, taken out.

    What is left is exactly what rule 7 governs: two answers that must be
    indistinguishable are compared through this, since a form that echoes the
    address back is allowed to differ and nothing else is.
    """
    import re
    body = response.get_data(as_text=True)
    body = re.sub(r'value="[^"]*"', 'value=""', body)
    # The CSP nonce is new on every response and says nothing about the visitor.
    return re.sub(r'nonce="[^"]*"', 'nonce=""', body)


def code_from_outbox(outbox) -> str:
    """The confirmation code, read back out of the message that was written."""
    texts = sorted(outbox.glob("*.txt"))
    assert texts, "no se escribió ningún correo"
    import re
    body = texts[-1].read_text(encoding="utf-8")
    found = re.findall(r"^\d{6}$", body, flags=re.M)
    assert found, "el correo no trae código"
    return found[0]


def confirm(client, code):
    """Type a code into the confirmation form, CSRF included."""
    client.get("/confirmar")  # seeds the CSRF value in the session
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/confirmar", data={"csrf_token": csrf, "code": code})
