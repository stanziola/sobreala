"""Registration, confirmation and login."""

from __future__ import annotations

from datetime import timedelta

from conftest import code_from_outbox, confirm, login, page_shape, register

from models import account as accounts
from models import token as tokens
from services.security import hash_code, now

WRONG = "000000"
url_for_recover = "/recuperar"


def other_code(code: str) -> str:
    """A code that is definitely not this one."""
    return WRONG if code != WRONG else "111111"


def ask_recovery(client, email):
    """Ask for a recovery code and follow to the screen that comes next."""
    client.get("/recuperar")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    client.post("/recuperar", data={"csrf_token": csrf, "email": email})
    return client.get("/recuperar/codigo")


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


def test_a_taken_address_is_told_so(client, database, outbox):
    """The registration form says it, and the owner is told anyway.

    Hiding this used to leave people waiting for a code that was never coming.
    Rule 7 still holds where it costs little —signing in and recovering— and is
    lifted here, where it cost a lot.
    """
    first = register(client)
    second = register(client)

    assert first.status_code == 302                # straight to the code
    assert second.status_code == 200               # back to the form, with news
    body = second.get_data(as_text=True)
    assert "Ya existe una cuenta con ese correo" in body
    # And a way out of the dead end, not just the news.
    assert url_for_recover in body

    # Still one account, and the owner was warned by email.
    assert database.accounts.count_documents({}) == 1
    assert len(list(outbox.glob("*.txt"))) == 2
    assert "ya tiene una cuenta" in sorted(outbox.glob("*.txt"))[-1].read_text(encoding="utf-8")


# ------------------------------------------------------------------ confirmation

def test_confirmation_works_and_signs_in(client, database, outbox):
    register(client)
    response = confirm(client, code_from_outbox(outbox))

    assert response.status_code == 302
    # Confirmar ya no cae en Estadísticas: la primera pantalla es la bienvenida.
    assert response.headers["Location"].endswith("/bienvenida")
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"]
    # Confirming leaves the visitor inside, without asking for the password
    # they typed two screens ago.
    assert "Hola, Ana" in client.get("/panel").get_data(as_text=True)


def test_the_welcome_screen_says_what_comes_next(client, database, outbox):
    """La primera pantalla de una cuenta nueva no puede ser un cuadro vacio."""
    register(client)
    confirm(client, code_from_outbox(outbox))

    pantalla = client.get("/bienvenida").get_data(as_text=True)
    assert "te damos la bienvenida" in pantalla
    assert "Ana" in pantalla
    assert "Elige el plan" in pantalla
    # Los dos botones: los planes viven en el sitio publico.
    assert "/planes/" in pantalla
    assert "/configuracion" in pantalla


def test_the_welcome_screen_steps_aside_once_there_is_a_plan(client, database,
                                                             outbox):
    """No es para el dia del registro, donde no puede darse: es para cuando
    alguien vuelve a esa direccion meses despues."""
    register(client)
    confirm(client, code_from_outbox(outbox))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    accounts.set_plan(database, cuenta["_id"], "basico")

    respuesta = client.get("/bienvenida")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/panel")


def test_the_welcome_screen_needs_a_session(client, database):
    assert client.get("/bienvenida").status_code == 302


def test_confirming_sends_the_welcome(client, database, outbox):
    register(client)
    confirm(client, code_from_outbox(outbox))

    bodies = [p.read_text(encoding="utf-8") for p in sorted(outbox.glob("*.txt"))]
    assert len(bodies) == 2, "the code and the welcome"
    welcome = bodies[-1]
    assert "Te damos la bienvenida, Ana" in welcome
    assert "/panel" in welcome
    # Transactional: no unsubscribe and no watermark, as rule 8 requires.
    assert "baja" not in welcome.lower()
    assert "Enviado con Panamails" not in welcome


def test_a_failed_welcome_does_not_lock_anyone_out(client, database, outbox,
                                                   monkeypatch):
    """A registration undoes itself when its mail fails; the welcome must not.

    By the time it is sent the address is confirmed and the person did
    everything right: the mail provider cannot be a reason to lock them out.
    """
    register(client)
    code = code_from_outbox(outbox)

    from services import mailer
    original = mailer.send

    def only_the_welcome_explodes(*args, **kwargs):
        if kwargs.get("purpose") == "welcome":
            raise RuntimeError("el proveedor rechazo el mensaje")
        return original(*args, **kwargs)

    monkeypatch.setattr(mailer, "send", only_the_welcome_explodes)

    response = confirm(client, code)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/bienvenida")
    assert accounts.by_email(database, "ana@ejemplo.com")["email_confirmed_at"]
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


def test_recovering_reads_the_same_with_and_without_an_account(client, database,
                                                              outbox):
    """Rule 7 where it still stands.

    The registration form now says when an address is taken. Recovery must not:
    a screen that answered "no such account" would be exactly the customer
    finder that hiding it was meant to prevent, and here nobody is helped by
    knowing.
    """
    register(client)                     # ana@ejemplo.com exists

    real = client.application.test_client()
    unknown = client.application.test_client()
    con = page_shape(ask_recovery(real, "ana@ejemplo.com"))
    sin = page_shape(ask_recovery(unknown, "nadie@ejemplo.com"))

    assert con == sin


def test_the_code_arrives_in_six_pieces_or_in_one(client, database, outbox):
    """The browser sends one field per box; without JavaScript, a single one.

    Both have to work: the six boxes are an improvement on the screen, not a new
    protocol.
    """
    register(client)
    assert confirm(client, code_from_outbox(outbox)).headers["Location"].endswith("/bienvenida")

    fresh = client.application.test_client()
    register(fresh, email="beto@ejemplo.com")
    whole = confirm(fresh, code_from_outbox(outbox), split=False)
    assert whole.headers["Location"].endswith("/bienvenida")


def test_the_countdown_says_the_same_in_every_case(client, database, outbox):
    """Rule 7, now on the clock.

    The code screen is reached three ways: a fresh registration, one with an
    address that already exists, and a resend for an address that has no
    account. Only the first issues a code. If the countdown only ran when there
    was one, its absence would answer the question rule 7 forbids.
    """
    register(client)                       # ana@ejemplo.com exists now
    register(client)                       # taken: no code issued
    with_account = page_shape(client.get("/confirmar"))

    stranger = client.application.test_client()
    stranger.get("/reenviar-confirmacion")
    with stranger.session_transaction() as sess:
        csrf = sess["_csrf"]
    stranger.post("/reenviar-confirmacion",
                  data={"csrf_token": csrf, "email": "nadie@ejemplo.com"})
    without_account = page_shape(stranger.get("/confirmar"))

    assert "Vence en" in with_account
    assert with_account == without_account


def test_with_the_time_gone_the_screen_is_drawn_blocked(client, database, outbox):
    register(client)
    with client.session_transaction() as sess:
        sess["code_expires_at"] = "2020-01-01T00:00:00+00:00"

    body = client.get("/confirmar").get_data(as_text=True)
    assert "El código venció" in body
    assert 'class="code__box" type="text"' in body and "disabled" in body


def test_the_clock_on_screen_does_not_decide(client, database, outbox):
    """The countdown is what is shown; the database is what rules.

    A code still alive in account_tokens has to work even if the session's
    deadline already passed — the two can drift, and only one of them is the
    authority.
    """
    register(client)
    code = code_from_outbox(outbox)
    with client.session_transaction() as sess:
        sess["code_expires_at"] = "2020-01-01T00:00:00+00:00"

    assert confirm(client, code).headers["Location"].endswith("/bienvenida")


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
    assert confirm(client, second).headers["Location"].endswith("/bienvenida")


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


def test_the_logo_always_leads_back_to_the_site(client, database, outbox):
    """The logo is the way out to panamails.com, from every page.

    Before signing in it is the only way back to the pages someone may want to
    reread; after signing in it is still the only one, because the panel has no
    other link out.
    """
    outside = client.get("/entrar").get_data(as_text=True)
    assert 'class="bar__brand" href="https://panamails.com/"' in outside
    assert "Volver al sitio" in outside

    register(client)
    login(client)
    inside = client.get("/panel").get_data(as_text=True)
    assert 'class="bar__brand" href="https://panamails.com/"' in inside


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
