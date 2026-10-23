"""La API es desde el plan Negocio (octubre de 2026), en la tabla y en el
producto.

Lo que fijan estas pruebas: que el plan lo dice la fila «Acceso a la API» de
docs/pricing.md; que en el Básico, en la demostración y con un plan vencido la
rama API del Dashboard enseña solo el aviso y no procesa ningún formulario; que
una clave de una cuenta así responde 403 `plan_without_api` y vuelve a abrir al
mejorar el plan, sin borrarse; y que los webhooks de esa cuenta no se anotan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import login, register
from test_campaigns import other, ready

from models import account as accounts
from models import api_key as api_keys
from models import webhook as hooks
from services import plans, webhooks

AVISO = "La API es desde el plan Negocio"


def clave(database, cuenta_id):
    raw, _ = api_keys.create(database, cuenta_id, name="Tienda", mode="live",
                             scopes=["emails:send"], ips=[], days=0)
    return {"Authorization": f"Bearer {raw}"}


def test_el_plan_lo_dice_la_tabla():
    assert not plans.has_api("basico")
    assert plans.has_api("negocio") and plans.has_api("empresa")
    assert not plans.has_api(None) and not plans.has_api("inventado")
    assert plans.first_with_api() == "Negocio"


def test_la_rama_api_sin_el_plan_solo_avisa(client, database, outbox):
    browser, cuenta, _ = ready(client, database)  # Básico
    for url in ("/developers/keys", "/developers/keys/new", "/developers/webhooks",
                "/developers/emails", "/developers/log"):
        pagina = browser.get(url)
        assert pagina.status_code == 200, url
        html = pagina.get_data(as_text=True)
        assert AVISO in html, url
        assert "/#planes" in html, url
        assert 'name="once"' not in html, url
    # Ningún formulario de la rama se procesa, ni siquiera sin su token.
    browser.post("/developers/keys/new", data={"name": "Tienda", "mode": "live"})
    assert database.api_keys.count_documents({"account_id": cuenta["_id"]}) == 0
    # Con el plan, la rama de siempre.
    accounts.set_plan(database, cuenta["_id"], "negocio")
    html = browser.get("/developers/keys").get_data(as_text=True)
    assert AVISO not in html and "Claves de API" in html


def test_la_demostracion_tampoco(client, database, outbox):
    register(client, email="demo@ejemplo.com")  # abierta, sin plan
    browser = other(client)
    login(browser, email="demo@ejemplo.com")
    cuenta = accounts.by_email(database, "demo@ejemplo.com")
    assert accounts.in_demo(cuenta)
    assert AVISO in browser.get("/developers/keys").get_data(as_text=True)
    respuesta = client.get("/api/v1/me", headers=clave(database, cuenta["_id"]))
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["code"] == "plan_without_api"


def test_la_clave_de_un_basico_no_abre_hasta_mejorar(client, database, outbox):
    _, cuenta, _ = ready(client, database)  # Básico
    auth = clave(database, cuenta["_id"])
    respuesta = client.get("/api/v1/me", headers=auth)
    assert respuesta.status_code == 403
    error = respuesta.get_json()["error"]
    assert error["code"] == "plan_without_api"
    assert error["message"] == "Tu plan no incluye la API. Mejora tu plan para usarla."
    # La clave sigue guardada y abre al mejorar.
    accounts.set_plan(database, cuenta["_id"], "negocio")
    assert client.get("/api/v1/me", headers=auth).status_code == 200
    # Con el plan vencido, ya no.
    database.accounts.update_one(
        {"_id": cuenta["_id"]},
        {"$set": {"plan_until": datetime.now(timezone.utc) - timedelta(days=1)}})
    assert client.get("/api/v1/me", headers=auth).status_code == 403


def test_quien_bajo_de_plan_sabe_que_sus_claves_siguen(client, database, outbox):
    browser, cuenta, _ = ready(client, database, plan="negocio")
    clave(database, cuenta["_id"])
    accounts.set_plan(database, cuenta["_id"], "basico")
    html = browser.get("/developers/keys").get_data(as_text=True)
    assert AVISO in html
    assert "Tus claves de API siguen guardadas" in html


def test_los_webhooks_de_un_basico_no_se_anotan(client, database, outbox):
    _, cuenta, _ = ready(client, database)  # Básico
    hooks.create(database, cuenta["_id"], url="https://hooks.tienda.com/x",
                 host="hooks.tienda.com", events=list(hooks.EVENTS), description="Tienda")
    kind = hooks.EVENTS[0]
    assert webhooks.emit(database, cuenta["_id"], kind, {"a": 1}, key="uno") == 0
    accounts.set_plan(database, cuenta["_id"], "negocio")
    assert webhooks.emit(database, cuenta["_id"], kind, {"a": 1}, key="dos") == 1
