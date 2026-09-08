"""What must not work: injection, cross-site scripting, weak passwords.

The point of these is not that the current code happens to be safe, but that
the guarantee is written down and breaks loudly if someone later reaches into
request.form with something other than a plain string, or drops the escaping.
"""

from __future__ import annotations

from conftest import login, page_shape, register

from models import account as accounts
from services.security import MIN_PASSWORD_LENGTH, password_problem

# What an operator injection looks like against Mongo: a form field that is not
# a string but a query. Sent as a repeated key and as the bracket syntax some
# frameworks decode into a dict.
INJECTIONS = [
    {"email": '{"$gt": ""}', "password": '{"$gt": ""}'},
    {"email[$gt]": "", "password[$gt]": ""},
    {"email": '{"$ne": null}', "password": '{"$ne": null}'},
    {"email": {"$gt": ""}, "password": {"$gt": ""}},
]


def csrf(client, path):
    client.get(path)
    with client.session_transaction() as sess:
        return sess["_csrf"]


# ------------------------------------------------------------------ injection

def test_an_operator_cannot_be_smuggled_into_the_login_query(client, database):
    register(client)

    for payload in INJECTIONS:
        data = {"csrf_token": csrf(client, "/entrar"), **payload}
        response = client.post("/entrar", data=data)
        # No redirect: nothing got in. A successful sign-in would answer 302.
        assert response.status_code == 200, payload
        assert client.get("/panel").status_code == 302, payload


def test_an_operator_is_stored_as_text_not_as_a_query(client, database):
    """A field that looks like a query has to end up as an ordinary string.

    This is the property that makes the whole application safe from operator
    injection: werkzeug hands over `str`, and every value that reaches Mongo
    passes through normalize_email() or ObjectId() first. If a future change
    started accepting JSON bodies, this test is what would notice.
    """
    data = {
        "csrf_token": csrf(client, "/registro"),
        "company_name": '{"$ne": null}',
        "contact_name": "Ana",
        "email": "ana@ejemplo.com",
        "phone": '{"$gt": ""}',
        "password": "Contrasena-Larga1",
    }
    client.post("/registro", data=data)

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert isinstance(account["company_name"], str)
    assert account["company_name"] == '{"$ne": null}'
    assert isinstance(account["phone"], str)


def test_a_forged_address_header_cannot_write_whatever_it_likes(client, database):
    """CF-Connecting-IP arrives from outside, so it is checked before use."""
    client.post("/entrar", headers={"CF-Connecting-IP": "no soy una ip"},
                data={"csrf_token": csrf(client, "/entrar"),
                      "email": "ana@ejemplo.com", "password": "loquesea"})

    keys = [d["key"] for d in database.rate_limits.find({})]
    assert keys and all("no soy una ip" not in k for k in keys)


# ------------------------------------------------------------------------ xss

def test_what_the_visitor_types_comes_back_escaped(client, database):
    payload = '"><script>alert(1)</script>'
    response = client.post("/registro", data={
        "csrf_token": csrf(client, "/registro"),
        "company_name": payload, "contact_name": "", "email": "ana@ejemplo.com",
        "password": "Contrasena-Larga1",
    })

    body = response.get_data(as_text=True)
    # The form redraws with what was typed, and it comes back inert.
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_every_page_carries_its_security_headers(client, database):
    response = client.get("/entrar")
    headers = response.headers

    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "script-src 'self' 'nonce-" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Cache-Control"] == "no-store"


def test_the_inline_script_is_the_only_one_allowed(client, database):
    """The theme script runs because it carries the nonce of that response.

    A script injected into the page cannot know the nonce, which is what makes
    the policy worth having.
    """
    body = client.get("/entrar").get_data(as_text=True)
    first = client.get("/entrar").headers["Content-Security-Policy"]
    second = client.get("/entrar").headers["Content-Security-Policy"]

    assert 'nonce="' in body
    assert first != second  # a fresh nonce on every response


# ------------------------------------------------------------------- passwords

def test_the_password_rules():
    assert password_problem("Corta1!") == "too_short"
    assert password_problem("A1!" + "a" * 80) == "too_long"
    assert password_problem("contrasena1!") == "no_upper"
    assert password_problem("Contrasenaa!") == "no_digit"
    assert password_problem("Contrasena12") == "no_symbol"
    assert password_problem("Contrasena-Larga1") is None
    # Punctuation from any keyboard counts, not a list of blessed characters.
    assert password_problem("Contrasena1¿") is None


def test_the_rules_on_screen_are_the_rules_the_server_applies(client, database):
    """The list on screen cannot promise something the server does not enforce.

    For every rule drawn in the form there is a password that fails only that
    one, and the server refuses it. Adding a tick without adding the check in
    password_problem() breaks this.
    """
    import re

    body = client.get("/registro").get_data(as_text=True)
    drawn = re.findall(r'data-rule="([a-z]+)"', body)
    assert drawn == ["length", "upper", "digit", "symbol"]

    fails_only = {
        "length": "Corta1!",
        "upper": "contrasena1!",
        "digit": "Contrasenaa!",
        "symbol": "Contrasena12",
    }
    for rule in drawn:
        assert password_problem(fails_only[rule]) is not None, rule

    # And the minimum the list announces is the one the code requires.
    assert f'data-min="{MIN_PASSWORD_LENGTH}"' in body


def test_a_weak_password_never_creates_an_account(client, database):
    for weak in ("contrasena-larga", "CONTRASENA-LARGA", "Contrasenalarga",
                 "Corta1!"):
        response = client.post("/registro", data={
            "csrf_token": csrf(client, "/registro"),
            "company_name": "Coop", "contact_name": "Ana",
            "email": "ana@ejemplo.com", "password": weak,
        })
        assert response.status_code == 200, weak
        assert database.accounts.count_documents({}) == 0, weak


def test_the_form_says_which_rule_was_missed(client, database):
    def refusal(password):
        response = client.post("/registro", data={
            "csrf_token": csrf(client, "/registro"),
            "company_name": "Coop", "contact_name": "Ana",
            "email": "ana@ejemplo.com", "password": password,
        })
        return response.get_data(as_text=True)

    assert "al menos una letra mayúscula" in refusal("contrasena1!")
    assert "al menos un número" in refusal("Contrasenaa!")
    assert "al menos un símbolo" in refusal("Contrasena12")


# ------------------------------------------------------- mail as a weapon

def test_an_address_cannot_be_flooded_with_notices(client, database, outbox):
    """Registering with someone else's address tells them by email.

    Without a budget of its own that is a way to fill a stranger's inbox, so the
    notice stops going out well before it becomes one — and the screen keeps
    saying exactly what it said the first time.
    """
    register(client)                       # ana@ejemplo.com now exists
    answers = [register(client) for _ in range(8)]

    notices = [p for p in outbox.glob("*.txt")
               if "ya tiene una cuenta" in p.read_text(encoding="utf-8")]
    assert len(notices) == 5               # REGISTER_PER_EMAIL

    # Every attempt, sent or skipped, answered the same.
    assert {r.status_code for r in answers} == {302}
    assert len({r.headers["Location"] for r in answers}) == 1


def test_the_screen_does_not_change_once_the_notice_stops(client, database, outbox):
    register(client)
    for _ in range(6):
        register(client)

    over_budget = client.get("/confirmar")
    fresh = client.application.test_client()
    register(fresh, email="beto@ejemplo.com")
    with_code = fresh.get("/confirmar")

    assert page_shape(over_budget) == page_shape(with_code)
