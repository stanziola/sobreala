"""Eliminar la cuenta y sus datos (octubre de 2026).

Antes se borraba a mano el documento de `accounts` y todo lo demás quedaba para
siempre. Lo que fijan estas pruebas: que se borre lo que la página dice que se
borra y se quede lo que dice que se queda (las supresiones, los pagos y las
facturas, la bitácora), que los usuarios de la empresa se vayan con ella y otra
empresa no se toque, que sin el nombre exacto o sin la contraseña no se borre
nada, que sin contraseña haga falta el código del correo, que un usuario de la
empresa no pueda, y que el administrador lo haga desde la ficha.
"""

from __future__ import annotations

from conftest import code_from_outbox, login
from test_admin import make_admin
from test_campaigns import csrf, ready
from test_users import as_member

from models import account as accounts
from models import mail_log
from services import erase as erasing

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def llenar(database, account_id):
    """Un documento en cada colección que guarda `account_id`."""
    for name in erasing.ERASED + erasing.KEPT:
        unico = f"{account_id}-{name}"
        # Los campos que llevan un índice único en alguna colección.
        database[name].insert_one({"account_id": account_id, "prueba": True,
                                   "name": unico, "email": unico,
                                   "email_normalized": unico, "token_hash": unico,
                                   "order_id": unico, "number": unico,
                                   "payment_id": unico})


def cuantos(database, ids):
    return {name: database[name].count_documents({"account_id": {"$in": ids}})
            for name in erasing.ERASED + erasing.KEPT}


def borrar(browser, **data):
    form = {"csrf_token": csrf(browser, "/settings/delete"), "action": "erase",
            "company": "Cooperativa Ejemplo", "password": PASSWORD}
    form.update(data)
    return browser.post("/settings/delete", data=form)


def test_borra_lo_dicho_y_deja_lo_dicho(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    otra_browser, otra, _ = ready(client, database, email="otra@ejemplo.com")
    llenar(database, cuenta["_id"])
    llenar(database, otra["_id"])

    pagina = browser.get("/settings/delete").get_data(as_text=True)
    assert "Se borra" in pagina and "Se queda" in pagina
    # En la configuración de la cuenta, con su menú y Cuenta marcada.
    assert "data-dash-nav" not in pagina
    assert 'is-current"\n       href="/settings/account" aria-current="page"' in pagina
    assert "Las bajas y supresiones" in pagina and 'href="/contacts/export"' in pagina
    # La fila, al final de Cuenta, lleva ahí.
    assert 'href="/settings/delete"' in browser.get("/settings/account").get_data(as_text=True)

    # Sin el nombre exacto, o con la contraseña mala, no se borra nada.
    assert "no coincide" in borrar(browser, company="Otra cosa").get_data(as_text=True)
    assert "no es correcta" in borrar(browser, password="mala").get_data(as_text=True)
    assert accounts.by_id(database, cuenta["_id"]) is not None

    # Sin fijarse en mayúsculas ni espacios de más.
    salida = borrar(browser, company="  cooperativa   ejemplo ")
    assert salida.status_code == 302 and salida.headers["Location"].endswith("/login?deleted=1")
    assert accounts.by_id(database, cuenta["_id"]) is None
    quedan = cuantos(database, [cuenta["_id"]])
    for name in erasing.ERASED:
        assert quedan[name] == 0, name
    for name in erasing.KEPT:
        assert quedan[name] > 0, name
    # Queda escrito quién, cuándo y cuánto, y le llega el aviso.
    linea = database.admin_events.find_one({"account_id": cuenta["_id"], "kind": "erase"})
    assert linea and linea["after"]["counts"]["contacts"] >= 1
    assert database.mail_log.count_documents({"purpose": mail_log.ERASED}) == 1
    # La otra empresa, intacta, y este navegador ya no tiene sesión.
    assert cuantos(database, [otra["_id"]])["contacts"] > 1
    assert browser.get("/settings").status_code == 302
    assert "se eliminaron" in browser.get("/login?deleted=1").get_data(as_text=True)


def test_los_usuarios_se_van_con_la_empresa(client, database, outbox):
    dueno, empresa, suyo = as_member(client, database, outbox=outbox)
    miembro = database.accounts.find_one({"owner_id": empresa["_id"]})
    # Un usuario no puede, ni ve la fila.
    assert suyo.get("/settings/delete").headers["Location"].endswith("/settings/security")
    llenar(database, miembro["_id"])
    salida = dueno.post("/settings/delete", data={
        "csrf_token": csrf(dueno, "/settings/delete"), "action": "erase",
        "company": empresa["company_name"], "password": PASSWORD})
    assert salida.status_code == 302
    assert database.accounts.count_documents({"_id": {"$in": [empresa["_id"], miembro["_id"]]}}) == 0
    assert cuantos(database, [miembro["_id"]])["sessions"] == 0


def test_sin_contrasena_pide_el_codigo_del_correo(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"password_hash": ""}})
    pagina = browser.get("/settings/delete").get_data(as_text=True)
    assert 'name="email_code"' in pagina and 'name="password"' not in pagina

    for path in list(outbox.glob("*")):
        path.unlink()
    browser.post("/settings/delete", data={
        "csrf_token": csrf(browser, "/settings/delete"), "action": "code"})
    codigo = code_from_outbox(outbox)
    assert "no es correcto" in borrar(browser, email_code="000000").get_data(as_text=True)
    assert borrar(browser, email_code=codigo).status_code == 302
    assert accounts.by_id(database, cuenta["_id"]) is None


def test_el_administrador_borra_desde_la_ficha(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    admin, _ = make_admin(client, database)
    ficha = f"/admin/accounts/{cuenta['_id']}"
    assert "Eliminar esta cuenta" in admin.get(ficha).get_data(as_text=True)

    def mandar(**data):
        form = {"csrf_token": csrf(admin, ficha), "company": "Cooperativa Ejemplo",
                "reason": "Lo pidió por teléfono"}
        form.update(data)
        return admin.post(f"{ficha}/erase", data=form)

    assert "erase_error=1" in mandar(company="Otra").headers["Location"]
    assert "erase_error=1" in mandar(reason="").headers["Location"]
    assert accounts.by_id(database, cuenta["_id"]) is not None
    assert mandar().headers["Location"].endswith("/admin/accounts?erased=1")
    assert accounts.by_id(database, cuenta["_id"]) is None
    linea = database.admin_events.find_one({"account_id": cuenta["_id"], "kind": "erase"})
    assert linea["reason"] == "Lo pidió por teléfono"


def test_lo_de_afuera_se_suelta(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    # Sus dominios, todos (octubre de 2026: puede tener varios).
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {
        "sender.domains": [{"name": "coop.com", "status": "verified", "dkim_tokens": []},
                           {"name": "coop-tienda.com", "status": "pending",
                            "dkim_tokens": []}],
        "paypal_vaults": [{"id": "VAULT-1", "payer": "ana@coop.com"}],
        "subscription": {"id": "I-SUB", "status": "active"}}})
    soltado = []
    from services import paypal, renewals, ses_identity
    monkeypatch.setattr(ses_identity, "delete", lambda domain: soltado.append(("ses", domain)))
    monkeypatch.setattr(paypal, "delete_payment_token",
                        lambda token: soltado.append(("vault", token)))
    monkeypatch.setattr(renewals, "cancel",
                        lambda db, account, reason="": soltado.append(("sub", reason)) or True)
    assert borrar(browser).status_code == 302
    assert ("ses", "coop.com") in soltado and ("ses", "coop-tienda.com") in soltado
    assert ("vault", "VAULT-1") in soltado
    assert any(one[0] == "sub" for one in soltado)
