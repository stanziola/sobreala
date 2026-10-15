"""Sessions as documents: devices, closing one, and changing the password.

The point of keeping a document per session is that the server can answer two
questions the signed cookie never could: which devices is this account open on,
and can this one be shut without touching the others. These fix both, plus the
rule that the cookie's value never reaches the database in the clear.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import login, register

from models import account as accounts
from models import auth_event as events
from models import mail_log
from models import session as sessions
from services.security import hash_token, now


def sid(client) -> str:
    """The identifier this client carries in its cookie."""
    with client.session_transaction() as sess:
        return sess.get("sid", "")


def session_cookie(response) -> str:
    """The Set-Cookie line for the session, ignoring any other cookie."""
    for line in response.headers.getlist("Set-Cookie"):
        if line.startswith("session="):
            return line
    return ""


def otro(client):
    """A second browser: same application, its own cookie jar."""
    return client.application.test_client()


def cambiar(client, current="Contrasena-Larga1", nueva="Contrasena-Nueva2!",
            repetir=None):
    client.get("/change-password")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/change-password", data={
        "csrf_token": csrf, "current": current, "password": nueva,
        "repeat": nueva if repetir is None else repetir,
    })


def cerrar(client, session_id):
    client.get("/dashboard")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/devices/close",
                       data={"csrf_token": csrf, "session_id": session_id})


# --------------------------------------------------------------- devices

def test_two_devices_can_be_signed_in_at_once(client, database, outbox):
    register(client)
    telefono = otro(client)
    computadora = otro(client)
    login(telefono)
    login(computadora)

    assert database.sessions.count_documents({"revoked_at": None}) == 2
    assert telefono.get("/dashboard").status_code == 200
    assert computadora.get("/dashboard").status_code == 200


def test_the_settings_screen_lists_the_devices(client, database, outbox):
    register(client)
    navegador = otro(client)
    navegador.get("/login")
    with navegador.session_transaction() as sess:
        csrf = sess["_csrf"]
    navegador.post("/login", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com",
        "password": "Contrasena-Larga1", "remember": "1",
    }, headers={"User-Agent": "Mozilla/5.0 (iPhone) AppleWebKit Safari/605.1"})

    body = navegador.get("/settings/security").get_data(as_text=True)
    assert "Tus dispositivos" in body
    assert "Safari en iPhone" in body
    assert "Este dispositivo" in body


def test_closing_one_device_leaves_the_other_inside(client, database, outbox):
    register(client)
    telefono = otro(client)
    computadora = otro(client)
    login(telefono)
    login(computadora)

    del_telefono = sessions.find(database, sid(telefono))
    cerrar(computadora, del_telefono["_id"])

    # El teléfono queda fuera y su cookie deja de servir; la computadora sigue.
    assert telefono.get("/dashboard").status_code == 302
    assert computadora.get("/dashboard").status_code == 200
    assert database.sessions.count_documents({"revoked_at": None}) == 1


def test_closing_the_others_leaves_only_this_one(client, database, outbox):
    register(client)
    uno, dos, tres = otro(client), otro(client), otro(client)
    for c in (uno, dos, tres):
        login(c)

    cerrar(tres, "otras")

    assert tres.get("/dashboard").status_code == 200
    assert uno.get("/dashboard").status_code == 302
    assert dos.get("/dashboard").status_code == 302
    vivas = sessions.for_account(database,
                                 accounts.by_email(database, "ana@ejemplo.com")["_id"])
    assert len(vivas) == 1


def test_closing_the_device_in_use_is_signing_out(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)

    respuesta = cerrar(navegador, sessions.find(database, sid(navegador))["_id"])
    assert respuesta.headers["Location"].endswith("/login")
    assert navegador.get("/dashboard").status_code == 302


def test_a_session_id_from_another_account_closes_nothing(client, database, outbox):
    register(client)
    ajena = otro(client)
    login(ajena)                       # la sesión de Ana
    register(otro(client), email="beto@ejemplo.com")

    beto = otro(client)
    login(beto, email="beto@ejemplo.com")
    cerrar(beto, sessions.find(database, sid(ajena))["_id"])

    # Beto no puede cerrar lo que no es suyo: el update va acotado a su cuenta.
    assert ajena.get("/dashboard").status_code == 200


# ------------------------------------------------------------- the cookie

def test_only_the_hash_of_the_cookie_is_stored(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)

    crudo = sid(navegador)
    guardada = database.sessions.find_one({})
    assert crudo not in str(guardada)
    assert guardada["token_hash"] == hash_token(crudo)


def test_without_the_checkbox_the_cookie_dies_with_the_browser(client, database,
                                                               outbox):
    register(client)
    navegador = otro(client)
    navegador.get("/login")
    with navegador.session_transaction() as sess:
        csrf = sess["_csrf"]
    respuesta = navegador.post("/login", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com",
        "password": "Contrasena-Larga1",
    })

    # The session one specifically: the same response also carries the crumb
    # the public site reads, and that one does have an expiry.
    galleta = session_cookie(respuesta)
    assert "Expires=" not in galleta and "Max-Age=" not in galleta
    # Y el documento tampoco se queda un mes esperando.
    doc = database.sessions.find_one({"revoked_at": None})
    assert doc["remembered"] is False
    assert doc["expires_at"] - doc["created_at"] < timedelta(days=1)


def test_with_the_checkbox_it_lasts_thirty_days(client, database, outbox):
    register(client)
    navegador = otro(client)
    navegador.get("/login")
    with navegador.session_transaction() as sess:
        csrf = sess["_csrf"]
    respuesta = navegador.post("/login", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com",
        "password": "Contrasena-Larga1", "remember": "1",
    })

    assert "Expires=" in session_cookie(respuesta)
    doc = database.sessions.find_one({"revoked_at": None})
    assert doc["remembered"] is True
    assert doc["expires_at"] - doc["created_at"] > timedelta(days=29)


def test_an_expired_session_does_not_get_in(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)
    database.sessions.update_one({}, {"$set": {"expires_at": now() - timedelta(minutes=1)}})

    assert navegador.get("/dashboard").status_code == 302
    # Y la cookie inservible se limpia, para no volver a preguntarle a Mongo.
    assert sid(navegador) == ""


def test_signing_out_closes_the_session_for_good(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)
    guardado = sid(navegador)

    navegador.get("/dashboard")
    with navegador.session_transaction() as sess:
        csrf = sess["_csrf"]
    navegador.post("/logout", data={"csrf_token": csrf})

    # Quien hubiera copiado la cookie tampoco entra: la sesión está revocada.
    assert sessions.find(database, guardado) is None
    assert database.sessions.find_one({})["revoked_at"] is not None


# ---------------------------------------------------------------- password

def test_changing_the_password_needs_the_current_one(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)

    respuesta = cambiar(navegador, current="otra-cosa")
    assert "no es tu contraseña actual" in respuesta.get_data(as_text=True)
    # Nada cambió: la de siempre sigue entrando.
    assert login(otro(client)).status_code == 302


def test_a_weak_new_password_is_refused(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)

    assert "mayúscula" in cambiar(navegador, nueva="contrasenalarga1!").get_data(as_text=True)
    assert "no coinciden" in cambiar(navegador, nueva="Contrasena-Nueva2!",
                                     repetir="otra").get_data(as_text=True)
    # The current one is one it has used, so the history catches it.
    assert "ya la usaste antes" in cambiar(
        navegador, nueva="Contrasena-Larga1").get_data(as_text=True)


def test_changing_it_closes_the_other_devices_and_keeps_this_one(client, database,
                                                                 outbox):
    register(client)
    telefono = otro(client)
    computadora = otro(client)
    login(telefono)
    login(computadora)

    respuesta = cambiar(computadora)
    assert respuesta.status_code == 302

    assert computadora.get("/dashboard").status_code == 200   # la que la cambió
    assert telefono.get("/dashboard").status_code == 302      # el resto, fuera
    assert login(otro(client), password="Contrasena-Nueva2!").status_code == 302
    assert login(otro(client)).status_code == 200         # la vieja ya no vale


def test_the_change_is_recorded_and_announced(client, database, outbox):
    register(client)
    navegador = otro(client)
    login(navegador)
    cambiar(navegador)

    fila = database.mail_log.find_one({"purpose": mail_log.PASSWORD_CHANGED})
    assert fila is not None and fila["status"] == mail_log.SENT
    assert "cambió" in fila["text"]

    desenlaces = [d["outcome"] for d in
                  database.auth_events.find({"kind": events.PASSWORD_CHANGE})]
    assert desenlaces == [events.OK]


def test_a_failed_notice_does_not_undo_the_change(client, database, outbox,
                                                  monkeypatch):
    register(client)
    navegador = otro(client)
    login(navegador)

    from services import mailer
    original = mailer.send

    def explota_el_aviso(*args, **kwargs):
        if kwargs.get("purpose") == mail_log.PASSWORD_CHANGED:
            raise RuntimeError("el proveedor rechazo el mensaje")
        return original(*args, **kwargs)

    monkeypatch.setattr(mailer, "send", explota_el_aviso)
    respuesta = cambiar(navegador)

    assert respuesta.status_code == 302
    assert login(otro(client), password="Contrasena-Nueva2!").status_code == 302
