"""Envíos, estadísticas y eventos por la API (octubre de 2026), y que las rutas
respondan lo que dicen los ejemplos de la documentación.

Lo que fijan estas pruebas: que las cifras son las de Estadísticas (personas y
no eventos); que los destinatarios de un envío se filtran y se paginan; que los
filtros malos son un error y no una consulta; que nada de otra cuenta se ve; y
que cada respuesta trae, al menos, las claves de su ejemplo en `api_spec.py`.
"""

from __future__ import annotations

from test_api_contactos import llave
from test_campaigns import catch, make, ready, send_it

import api_spec
from models import campaign as campaigns
from models import event as events

LEER = ("campaigns:read", "stats:read", "contacts:read", "templates:read", "emails:send")


def con_un_envio(client, database, monkeypatch, *, email="ana@ejemplo.com"):
    catch(monkeypatch)
    browser, cuenta, pieza = ready(client, database, howmany=3, email=email)
    make(browser, pieza, subject="Boletín")
    send_it(browser, database, cuenta["_id"])
    hecha = campaigns.for_account(database, cuenta["_id"])[0]
    run = hecha["run_id"]
    # Lo que contaría el aviso de SES: dos aperturas de la misma persona son una.
    for _ in range(2):
        events.record(database, cuenta["_id"], kind=events.OPEN, campaign_id=hecha["_id"],
                      run_id=run, email="socio0@ejemplo.com")
    events.record(database, cuenta["_id"], kind=events.CLICK, campaign_id=hecha["_id"],
                  run_id=run, email="socio1@ejemplo.com", link="https://coop.com/a")
    events.record(database, cuenta["_id"], kind=events.BOUNCE, campaign_id=hecha["_id"],
                  run_id=run, email="socio2@ejemplo.com")
    return cuenta, hecha, run


def test_los_envios_y_sus_destinatarios(client, database, outbox, monkeypatch):
    cuenta, hecha, run = con_un_envio(client, database, monkeypatch)
    auth, _ = llave(database, cuenta, scopes=LEER)
    listados = client.get("/api/v1/sends", headers=auth).get_json()
    [uno] = listados["data"]
    assert uno["id"] == str(run) and uno["sent"] == 3 and uno["subject"] == "Boletín"
    assert uno["people"]["open"] == 1 and uno["people"]["click"] == 1
    assert client.get(f"/api/v1/sends?campaign_id={hecha['_id']}",
                      headers=auth).get_json()["data"][0]["id"] == str(run)
    assert client.get("/api/v1/sends?campaign_id=x", headers=auth).status_code == 422

    base = f"/api/v1/sends/{run}/recipients"
    todos = client.get(f"{base}?limit=2", headers=auth).get_json()
    assert todos["total"] == 3 and len(todos["data"]) == 2 and todos["next_offset"] == 2
    resto = client.get(f"{base}?limit=2&offset=2", headers=auth).get_json()
    assert len(resto["data"]) == 1 and resto["next_offset"] is None
    abrieron = client.get(f"{base}?outcome=opened", headers=auth).get_json()
    assert [one["email"] for one in abrieron["data"]] == ["socio0@ejemplo.com"]
    rebotes = client.get(f"{base}?outcome=bounced", headers=auth).get_json()
    assert rebotes["data"][0]["reached"] == "bounce"
    for malo in ("outcome=nada", "offset=-1", "offset=x"):
        assert client.get(f"{base}?{malo}", headers=auth).status_code == 422


def test_las_estadisticas_cuentan_personas(client, database, outbox, monkeypatch):
    cuenta, _, _ = con_un_envio(client, database, monkeypatch)
    auth, _ = llave(database, cuenta, scopes=LEER)
    datos = client.get("/api/v1/stats?period=7d&tz=America/Panama", headers=auth).get_json()
    cifras = {one["key"]: one for one in datos["rates"]}
    assert cifras["sent"]["n"] == 3 and cifras["open"]["n"] == 1 and cifras["bounce"]["n"] == 1
    assert "leave" in cifras and datos["tz"] == "America/Panama"
    filtrada = client.get("/api/v1/stats?tag=Nadie", headers=auth).get_json()
    assert "leave" not in {one["key"] for one in filtrada["rates"]}

    serie = client.get("/api/v1/stats/series?period=24h", headers=auth).get_json()
    assert len(serie["data"]) == 24 and sum(one["sent"] for one in serie["data"]) == 3
    enlaces = client.get("/api/v1/stats/links?period=24h", headers=auth).get_json()
    assert enlaces["data"] == [{"link": "https://coop.com/a", "n": 1}]
    cuando = client.get("/api/v1/stats/timing", headers=auth).get_json()
    assert len(cuando["days"]) == 7 and len(cuando["hours"]) == 24 and sum(cuando["days"]) == 1
    altas = client.get("/api/v1/stats/growth", headers=auth).get_json()
    assert len(altas["data"]) == 12 and altas["data"][-1]["added"] == 3

    for malo in ("/api/v1/stats?period=1y", "/api/v1/stats?tz=Marte/Base",
                 "/api/v1/stats?campaign_id=x", "/api/v1/stats/timing?tz=../../etc"):
        assert client.get(malo, headers=auth).status_code == 422, malo


def test_los_eventos(client, database, outbox, monkeypatch):
    cuenta, hecha, run = con_un_envio(client, database, monkeypatch)
    auth, _ = llave(database, cuenta, scopes=LEER)
    rebotes = client.get("/api/v1/events?type=bounce", headers=auth).get_json()
    assert [one["email"] for one in rebotes["data"]] == ["socio2@ejemplo.com"]
    assert rebotes["data"][0]["send_id"] == str(run)
    de_uno = client.get("/api/v1/events?email=SOCIO1@ejemplo.com", headers=auth).get_json()
    assert {one["type"] for one in de_uno["data"]} == {"sent", "click"}
    pagina = client.get("/api/v1/events?limit=2", headers=auth).get_json()
    assert len(pagina["data"]) == 2 and pagina["next_cursor"]
    futuro = client.get("/api/v1/events?from=2099-01-01T00:00:00Z", headers=auth).get_json()
    assert futuro["data"] == []
    for malo in ("type=nada", "send_id=x", "from=ayer", "from=2026-10-01T00:00:00"):
        assert client.get(f"/api/v1/events?{malo}", headers=auth).status_code == 422, malo


def test_nada_de_otra_cuenta_y_los_permisos(client, database, outbox, monkeypatch):
    cuenta, _, run = con_un_envio(client, database, monkeypatch)
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    ajena, _ = llave(database, otra, scopes=LEER)
    assert client.get(f"/api/v1/sends/{run}", headers=ajena).status_code == 404
    assert client.get(f"/api/v1/sends/{run}/recipients", headers=ajena).status_code == 404
    assert client.get("/api/v1/sends", headers=ajena).get_json()["data"] == []
    assert client.get("/api/v1/events", headers=ajena).get_json()["data"] == []
    sin, _ = llave(database, cuenta, scopes=("contacts:read",))
    assert client.get("/api/v1/stats", headers=sin).status_code == 403
    assert client.get("/api/v1/sends", headers=sin).status_code == 403


def test_las_respuestas_traen_las_claves_de_sus_ejemplos(client, database, outbox,
                                                         monkeypatch):
    """Cada GET sin parámetros de ruta responde, al menos, con las claves de
    arriba de su ejemplo. Los ejemplos son de la documentación: si una clave
    cambia de nombre aquí y no allá, esto lo dice."""
    cuenta, _, _ = con_un_envio(client, database, monkeypatch)
    auth, _ = llave(database, cuenta, scopes=LEER)
    probadas = 0
    for one in api_spec.endpoints():
        if one["method"] != "GET" or "{" in one["path"] or not isinstance(
                one.get("response"), dict) or one["scope"] == api_spec.PUBLIC:
            continue
        respuesta = client.get("/api/v1" + one["path"], headers=auth)
        assert respuesta.status_code == 200, (one["path"], respuesta.get_json())
        faltan = set(one["response"]) - set(respuesta.get_json())
        assert not faltan, (one["path"], faltan)
        datos = respuesta.get_json().get("data")
        ejemplo = one["response"].get("data")
        if datos and ejemplo and isinstance(ejemplo[0], dict):
            faltan = set(ejemplo[0]) - set(datos[0])
            assert not faltan, (one["path"], faltan)
        probadas += 1
    assert probadas >= 15
