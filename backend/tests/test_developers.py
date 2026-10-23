"""La rama «API» del Dashboard: las llaves y el registro (octubre de 2026).

Lo que fijan estas pruebas: que la rama es del dueño (un usuario de la empresa y
un administrador no la tienen), que crear una llave pide la contraseña (o el
código del correo) y el de la app, y que esa prueba queda atada a la cuenta y a
la sesión: con dos cuentas abiertas en el navegador, probar una no sirve para la
otra. Que la llave se enseña solo en la respuesta que la crea y nunca pasa por
la sesión, que recargar no crea otra, que una de prueba se queda sin permisos de
escribir, que caben diez, que revocar pregunta y avisa, y que el administrador
la revoca desde la ficha con su motivo. Y que eliminar la cuenta se las lleva.
"""

from __future__ import annotations

import re

from conftest import code_from_outbox
from test_admin import make_admin
from test_campaigns import csrf
from test_campaigns import ready as lista
from test_settings import switch_to, two_accounts
from test_users import as_member

from models import account as accounts
from models import api_key as api_keys
from models import mail_log
from services import erase

CLAVE = "Contrasena-Larga1"


def ready(client, database, **datos):
    """Una cuenta lista, en el plan Negocio: la API es desde ahí (octubre de
    2026)."""
    datos.setdefault("plan", "negocio")
    return lista(client, database, **datos)


def formulario(browser):
    pagina = browser.get("/developers/keys/new").get_data(as_text=True)
    once = re.search(r'name="once" value="([^"]+)"', pagina).group(1)
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    return token, once, pagina


def crear(browser, **data):
    token, once, _ = formulario(browser)
    form = {"csrf_token": token, "once": once, "name": "Tienda", "mode": "live",
            "preset": "", "scope": ["emails:send", "contacts:write"], "days": "0",
            "ips": "", "password": CLAVE}
    form.update(data)
    return browser.post("/developers/keys/new", data=form)


def llave_de(respuesta) -> str:
    found = re.search(r'value="(sa_(?:live|test)_[A-Za-z0-9_-]+)"',
                      respuesta.get_data(as_text=True))
    return found.group(1) if found else ""


def test_la_rama_es_del_dueno(client, database, outbox):
    browser, _, _ = ready(client, database)
    arbol = browser.get("/dashboard").get_data(as_text=True).split("data-dash-nav")[1]
    assert 'href="/developers/keys"' in arbol and "/api/" in arbol
    dueno, _, suyo = as_member(client, database, permisos=("contacts",), outbox=outbox)
    assert suyo.get("/developers/keys").status_code == 302
    assert 'href="/developers/keys"' not in suyo.get("/contacts").get_data(as_text=True)
    admin, _ = make_admin(client, database)
    assert admin.get("/developers/keys").headers["Location"].endswith("/admin/")


def test_crear_pide_la_contrasena_y_la_ensena_una_vez(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    mala = crear(browser, password="mala")
    assert "no es correcta" in mala.get_data(as_text=True)
    assert database.api_keys.count_documents({}) == 0

    hecha = crear(browser)
    raw = llave_de(hecha)
    assert raw.startswith("sa_live_")
    assert hecha.headers["Cache-Control"] == "no-store"
    guardada = database.api_keys.find_one({"account_id": cuenta["_id"]})
    assert guardada["scopes"] == ["contacts:write", "emails:send"]
    assert raw not in str(guardada)
    # Nunca en la sesión ni en la lista.
    with browser.session_transaction() as sess:
        assert raw not in str(dict(sess))
    lista = browser.get("/developers/keys").get_data(as_text=True)
    assert raw not in lista and guardada["prefix"] in lista
    # Abre la API.
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {raw}"}).status_code == 200
    # Y le llegó el aviso.
    assert database.mail_log.count_documents({"purpose": mail_log.API_KEY}) == 1


def test_recargar_no_crea_otra(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    token, once, _ = formulario(browser)
    form = {"csrf_token": token, "once": once, "name": "Tienda", "mode": "live",
            "scope": ["emails:send"], "days": "0", "password": CLAVE}
    assert llave_de(browser.post("/developers/keys/new", data=form))
    otra = browser.post("/developers/keys/new", data=form)
    assert otra.status_code == 302
    assert database.api_keys.count_documents({"account_id": cuenta["_id"]}) == 1


def test_la_prueba_vale_diez_minutos_solo_para_esa_cuenta(client, database, outbox):
    """Con dos cuentas en el navegador, probar la contraseña en una y saltar a
    la otra no deja crear una llave en la otra sin su contraseña."""
    browser, una, dos = two_accounts(client, database)
    for one in (una, dos):
        accounts.open_account(database, one)
        accounts.set_plan(database, one, "negocio")
    # En uso está la segunda: se prueba ahí y se crea.
    assert llave_de(crear(browser))
    # Sin pedirla otra vez, mientras dure.
    assert llave_de(crear(browser, password=""))
    switch_to(browser, una)
    sin = crear(browser, password="")
    assert not llave_de(sin)
    assert "no es correcta" in sin.get_data(as_text=True)
    assert database.api_keys.count_documents({"account_id": una}) == 0


def test_sin_contrasena_pide_el_codigo_del_correo(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"password_hash": ""}})
    _, _, pagina = formulario(browser)
    assert 'name="email_code"' in pagina and 'name="password"' not in pagina
    for path in list(outbox.glob("*")):
        path.unlink()
    browser.post("/developers/keys/new",
                 data={"csrf_token": csrf(browser, "/developers/keys/new"), "action": "code"})
    codigo = code_from_outbox(outbox)
    assert not llave_de(crear(browser, password="", email_code="000000"))
    assert llave_de(crear(browser, password="", email_code=codigo))


def test_con_segundo_factor_pide_el_codigo_de_la_app(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    from services import totp

    secreto = totp.new_secret()
    accounts.enable_two_factor(database, cuenta["_id"], secreto, [])
    assert 'name="app_code"' in formulario(browser)[2]
    assert not llave_de(crear(browser, app_code="000000"))
    import pyotp

    assert llave_de(crear(browser, app_code=pyotp.TOTP(secreto).now()))


def test_una_de_prueba_se_queda_sin_escribir(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    raw = llave_de(crear(browser, mode="test", preset="all"))
    assert raw.startswith("sa_test_")
    guardada = database.api_keys.find_one({"account_id": cuenta["_id"]})
    assert set(guardada["scopes"]) == set(api_keys.TEST_SCOPES)


def test_caben_diez(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    for n in range(api_keys.KEY_LIMIT):
        api_keys.create(database, cuenta["_id"], name=f"L{n}", mode="live",
                        scopes=["emails:send"], ips=[], days=0)
    llena = crear(browser)
    assert not llave_de(llena)
    assert "máximo" in llena.get_data(as_text=True)


def test_las_ip_se_revisan(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    mala = crear(browser, ips="no-es-ip\n0.0.0.0/0")
    assert not llave_de(mala)
    assert llave_de(crear(browser, ips="203.0.113.7\n198.51.100.0/24"))
    assert database.api_keys.find_one({"account_id": cuenta["_id"]})["ips"] == [
        "203.0.113.7", "198.51.100.0/24"]


def test_revocar_pregunta_y_avisa(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    raw, doc = api_keys.create(database, cuenta["_id"], name="Vieja", mode="live",
                               scopes=["emails:send"], ips=[], days=0)
    pregunta = browser.get(f"/developers/keys/{doc['_id']}/revoke")
    assert "¿Revocar «Vieja»?" in pregunta.get_data(as_text=True)
    assert api_keys.find(database, raw) is not None
    hecha = browser.post(f"/developers/keys/{doc['_id']}/revoke",
                         data={"csrf_token": csrf(browser, "/developers/keys")})
    assert hecha.headers["Location"].endswith("/developers/keys?done=revoked")
    assert api_keys.find(database, raw) is None
    assert database.mail_log.count_documents({"purpose": mail_log.API_KEY}) == 1
    # La de otra cuenta no se toca.
    _, otra, _ = ready(client, database, email="otra@ejemplo.com")
    raw2, doc2 = api_keys.create(database, otra["_id"], name="Ajena", mode="live",
                                 scopes=["emails:send"], ips=[], days=0)
    browser.post(f"/developers/keys/{doc2['_id']}/revoke",
                 data={"csrf_token": csrf(browser, "/developers/keys")})
    assert api_keys.find(database, raw2) is not None


def test_el_registro_ensena_lo_que_fallo(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    raw, _ = api_keys.create(database, cuenta["_id"], name="Tienda", mode="live",
                             scopes=["emails:send"], ips=["203.0.113.7"], days=0)
    client.get("/api/v1/me", headers={"Authorization": f"Bearer {raw}"})
    pagina = browser.get("/developers/log").get_data(as_text=True)
    assert "ip_not_allowed" in pagina and "/api/v1/me" in pagina


def test_el_administrador_la_revoca_con_motivo(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, doc = api_keys.create(database, cuenta["_id"], name="Filtrada", mode="live",
                               scopes=["emails:send"], ips=[], days=0)
    admin, _ = make_admin(client, database)
    ficha = f"/admin/accounts/{cuenta['_id']}"
    assert "Filtrada" in admin.get(ficha).get_data(as_text=True)
    accion = f"{ficha}/api-keys/{doc['_id']}/revoke"
    admin.post(accion, data={"csrf_token": csrf(admin, ficha), "reason": ""})
    assert api_keys.find(database, raw) is not None
    hecha = admin.post(accion, data={"csrf_token": csrf(admin, ficha),
                                     "reason": "Se publicó en un repositorio"})
    assert "api=revoked" in hecha.headers["Location"]
    assert api_keys.find(database, raw) is None
    linea = database.admin_events.find_one({"account_id": cuenta["_id"], "kind": "api_key"})
    assert linea["reason"] == "Se publicó en un repositorio"


def test_eliminar_la_cuenta_se_lleva_las_llaves(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    api_keys.create(database, cuenta["_id"], name="Tienda", mode="live",
                    scopes=["emails:send"], ips=[], days=0)
    erase.erase(database, cuenta["_id"], by=cuenta["_id"], reason="prueba")
    assert database.api_keys.count_documents({"account_id": cuenta["_id"]}) == 0


def test_la_busqueda_encuentra_las_llaves(client, database, outbox):
    browser, _, _ = ready(client, database)
    encontradas = browser.get("/search/suggest", query_string={"q": "token"}).get_json()
    assert any(one["url"] == "/developers/keys" for one in encontradas["items"])
