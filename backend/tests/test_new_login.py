"""The notice when somebody signs in from a device the account never used, the
link that closes that session, and passwords that cannot be reused.

The three share a reason: an account is only as safe as what its owner finds
out. A sign-in nobody is told about, a session that cannot be closed without the
password, and a password that can be set again after it leaked all leave the
same hole.
"""

from __future__ import annotations

import re
from datetime import timedelta

from conftest import code_from_outbox, confirm, login, register

from models import account as accounts
from models import mail_log
from models import session as sessions
from models import token as tokens
from services.security import now

PHONE = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
LAPTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"


def other(client):
    return client.application.test_client()


def sign_in(client, agent, email="ana@ejemplo.com", password="Contrasena-Larga1"):
    client.get("/login", headers={"User-Agent": agent})
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/login", headers={"User-Agent": agent}, data={
        "csrf_token": csrf, "email": email, "password": password})


def notices(outbox):
    return [p.read_text(encoding="utf-8") for p in sorted(outbox.glob("*.txt"))
            if "dispositivo nuevo" in p.read_text(encoding="utf-8")]


def link_from(body):
    """The path of the link in the notice, whatever host it was built with.

    Not the development address written by hand: APP_BASE_URL comes from the
    environment, and a .env pointing at production used to break this test
    without anything being wrong with the code.
    """
    from config import Config

    found = re.findall(r"https?://[^\s]*/session/close/[^\s]+", body)
    assert found, "the notice carries no link to close the session"
    return found[0].replace(Config.APP_BASE_URL, "")


# ----------------------------------------------------------------- the notice

def test_a_new_device_is_announced(client, database, outbox):
    register(client)
    phone = other(client)
    sign_in(phone, PHONE)

    aviso = notices(outbox)
    assert len(aviso) == 1
    assert "Chrome en Android" in aviso[0]
    assert database.mail_log.count_documents({"purpose": mail_log.NEW_LOGIN}) == 1


def test_a_device_already_used_says_nothing(client, database, outbox):
    register(client)
    phone = other(client)
    sign_in(phone, PHONE)          # the first one warns
    sign_in(other(client), PHONE)  # same device, a second time

    assert len(notices(outbox)) == 1


def test_confirming_the_registration_does_not_announce_itself(client, database,
                                                              outbox):
    """Entering right after registering is the same device that registered."""
    register(client)
    confirm(client, code_from_outbox(outbox))

    assert notices(outbox) == []


def test_a_failed_notice_does_not_keep_anyone_out(client, database, outbox,
                                                  monkeypatch):
    register(client)

    from services import mailer
    original = mailer.send

    def only_the_notice_explodes(*args, **kwargs):
        if kwargs.get("purpose") == mail_log.NEW_LOGIN:
            raise RuntimeError("el proveedor rechazo el mensaje")
        return original(*args, **kwargs)

    monkeypatch.setattr(mailer, "send", only_the_notice_explodes)

    phone = other(client)
    assert sign_in(phone, PHONE).status_code == 302
    assert phone.get("/dashboard").status_code == 200


# ------------------------------------------------------------------- the link

def test_the_link_does_not_close_anything_until_it_is_pressed(client, database,
                                                              outbox):
    """A mail scanner opening the link must not close the session.

    Antivirus and mail filters follow the links of what they inspect. If the
    closing happened on GET, the session would be gone before its owner read
    the message.
    """
    register(client)
    phone = other(client)
    sign_in(phone, PHONE)
    link = link_from(notices(outbox)[0])

    reader = other(client)
    assert reader.get(link).status_code == 200
    assert phone.get("/dashboard").status_code == 200      # still inside

    with reader.session_transaction() as sess:
        csrf = sess["_csrf"]
    assert reader.post(link, data={"csrf_token": csrf}).status_code == 200
    assert phone.get("/dashboard").status_code == 302      # now it is out


def test_it_closes_that_session_and_no_other(client, database, outbox):
    register(client)
    phone, laptop = other(client), other(client)
    sign_in(phone, PHONE)
    sign_in(laptop, LAPTOP)

    # The phone's notice is the first of the two.
    link = link_from(notices(outbox)[0])
    reader = other(client)
    reader.get(link)
    with reader.session_transaction() as sess:
        csrf = sess["_csrf"]
    reader.post(link, data={"csrf_token": csrf})

    assert phone.get("/dashboard").status_code == 302
    assert laptop.get("/dashboard").status_code == 200


def test_the_link_works_once(client, database, outbox):
    register(client)
    phone = other(client)
    sign_in(phone, PHONE)
    link = link_from(notices(outbox)[0])

    reader = other(client)
    reader.get(link)
    with reader.session_transaction() as sess:
        csrf = sess["_csrf"]
    reader.post(link, data={"csrf_token": csrf})

    assert reader.get(link).status_code == 410
    assert "ya no sirve" in reader.get(link).get_data(as_text=True)


def test_an_expired_link_is_refused(client, database, outbox):
    register(client)
    sign_in(other(client), PHONE)
    link = link_from(notices(outbox)[0])
    database.account_tokens.update_one(
        {"purpose": tokens.SESSION_REVOKE},
        {"$set": {"expires_at": now() - timedelta(minutes=1)}})

    assert other(client).get(link).status_code == 410


def test_only_the_hash_of_the_link_is_stored(client, database, outbox):
    register(client)
    sign_in(other(client), PHONE)
    raw = link_from(notices(outbox)[0]).rsplit("/", 1)[-1]

    doc = database.account_tokens.find_one({"purpose": tokens.SESSION_REVOKE})
    assert raw not in str(doc)


# --------------------------------------------------------- the swept accounts

def test_an_unconfirmed_account_is_marked_for_sweeping(client, database, outbox):
    register(client)
    account = accounts.by_email(database, "ana@ejemplo.com")

    assert account["purge_at"] > now()
    assert account["purge_at"] - account["created_at"] < timedelta(hours=25)

    confirm(client, code_from_outbox(outbox))
    # Confirming takes it off the list: Mongo never looks at what has no field.
    assert "purge_at" not in accounts.by_email(database, "ana@ejemplo.com")


def test_the_sweep_index_is_there(client, database):
    indexes = database.accounts.index_information()
    assert "ttl_purge_at" in indexes
    assert indexes["ttl_purge_at"].get("expireAfterSeconds") == 0


# ------------------------------------------------------- the password history

def test_a_password_cannot_be_used_twice(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)

    def change(current, fresh):
        inside.get("/change-password")
        with inside.session_transaction() as sess:
            csrf = sess["_csrf"]
        return inside.post("/change-password", data={
            "csrf_token": csrf, "current": current,
            "password": fresh, "repeat": fresh})

    assert change("Contrasena-Larga1", "Contrasena-Dos2!").status_code == 302
    # Back to the first one, which was already used.
    assert "ya la usaste antes" in change(
        "Contrasena-Dos2!", "Contrasena-Larga1").get_data(as_text=True)
    # And the current one is not available either.
    assert "ya la usaste antes" in change(
        "Contrasena-Dos2!", "Contrasena-Dos2!").get_data(as_text=True)

    account = accounts.by_email(database, "ana@ejemplo.com")
    assert len(account["password_history"]) == 1


def test_the_history_also_applies_to_recovering(client, database, outbox):
    register(client)
    stranger = other(client)
    stranger.get("/recover")
    with stranger.session_transaction() as sess:
        csrf = sess["_csrf"]
    stranger.post("/recover", data={"csrf_token": csrf,
                                      "email": "ana@ejemplo.com"})
    code = code_from_outbox(outbox)
    stranger.get("/recover/code")
    with stranger.session_transaction() as sess:
        csrf = sess["_csrf"]
    stranger.post("/recover/code",
                  data={"csrf_token": csrf, "code": list(code)})

    stranger.get("/recover/new")
    with stranger.session_transaction() as sess:
        csrf = sess["_csrf"]
    refused = stranger.post("/recover/new", data={
        "csrf_token": csrf, "password": "Contrasena-Larga1",
        "repeat": "Contrasena-Larga1"})

    assert "ya la usaste antes" in refused.get_data(as_text=True)


def test_the_stored_history_is_hashes_and_not_passwords(client, database, outbox):
    register(client)
    inside = other(client)
    login(inside)
    inside.get("/change-password")
    with inside.session_transaction() as sess:
        csrf = sess["_csrf"]
    inside.post("/change-password", data={
        "csrf_token": csrf, "current": "Contrasena-Larga1",
        "password": "Contrasena-Dos2!", "repeat": "Contrasena-Dos2!"})

    account = accounts.by_email(database, "ana@ejemplo.com")
    stored = str(account["password_history"])
    assert "Contrasena-Larga1" not in stored
    assert stored.count("$2") == 1          # one bcrypt hash, not a secret
