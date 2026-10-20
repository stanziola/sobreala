"""Las campañas por la API (octubre de 2026).

Lo que fijan estas pruebas: que se arman con las mismas reglas que en Masivo
(plantilla de la cuenta, etiquetas que existen, hora que no pasó); que mandar
la deja en manos del proceso en segundo plano y responde enseguida; que una que
está saliendo no se toca; que programar y desprogramar encienden y apagan que
salga sola; que una llave de prueba solo dice a cuántos saldría; y que nada de
otra cuenta se ve.
"""

from __future__ import annotations

from datetime import timedelta

from test_api_contactos import llave
from test_campaigns import catch, ready

from models import account as accounts
from models import campaign as campaigns
from services import background

TODO = ("campaigns:read", "campaigns:write", "campaigns:send")


def crear(client, auth, **body):
    datos = {"subject": "Asamblea", "text": "Te esperamos el sábado."}
    datos.update(body)
    return client.post("/api/v1/campaigns", headers=auth,
                       json={k: v for k, v in datos.items() if v is not None})


def test_crear_con_las_reglas_de_masivo(client, database, outbox):
    _, cuenta, pieza = ready(client, database, howmany=2, tag="Socios")
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = crear(client, auth, tags=["Socios"])
    assert hecha.status_code == 201
    datos = hecha.get_json()
    assert datos["source"] == "text" and datos["tags"] == ["Socios"]
    assert datos["status"] == "scheduled" and datos["auto_send"] is False

    luego = (accounts.now() + timedelta(days=1)).isoformat()
    programada = crear(client, auth, template_id=str(pieza), text=None,
                       scheduled_at=luego).get_json()
    assert programada["auto_send"] is True and programada["template_id"] == str(pieza)

    ayer = (accounts.now() - timedelta(days=1)).isoformat()
    for malo in ({"scheduled_at": ayer}, {"scheduled_at": "2026-12-01T10:00:00"},
                 {"tags": ["Nadie"]}, {"text": None},
                 {"template_id": str(pieza)}, {"subject": "a\nb"},
                 {"template_id": "6533b1d2a1b2c3d4e5f60901", "text": None},
                 {"logo": True, "template_id": str(pieza), "text": None}):
        assert crear(client, auth, **malo).status_code == 422, malo
    assert campaigns.count(database, cuenta["_id"]) == 2


def test_mandar_la_deja_al_proceso_y_no_se_toca_mientras_sale(client, database, outbox,
                                                             monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=3)
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = crear(client, auth).get_json()
    url = f"/api/v1/campaigns/{hecha['id']}"
    mandada = client.post(f"{url}/send", headers=auth)
    assert mandada.status_code == 202 and mandada.get_json()["auto_send"] is True
    assert salidos == []
    database.campaigns.update_one({}, {"$set": {"status": campaigns.SENDING}})
    for intento in (client.patch(url, headers=auth, json={"subject": "Otro"}),
                    client.delete(url, headers=auth),
                    client.post(f"{url}/send", headers=auth),
                    client.delete(f"{url}/schedule", headers=auth)):
        assert intento.status_code == 409
        assert intento.get_json()["error"]["code"] == "campaign_sending"
    database.campaigns.update_one({}, {"$set": {"status": campaigns.SCHEDULED}})

    background.campaigns_tick(database, "w1")
    assert len(salidos) == 3
    salida = client.get(url, headers=auth).get_json()
    assert salida["status"] == "sent" and salida["progress"]["sent"] == 3
    assert salida["send_id"] and salida["audience"] == 3

    # Otra vez: sale entera de nuevo.
    assert client.post(f"{url}/send", headers=auth).status_code == 202
    background.campaigns_tick(database, "w1")
    assert len(salidos) == 6


def test_programar_y_desprogramar(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=1)
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = crear(client, auth).get_json()
    url = f"/api/v1/campaigns/{hecha['id']}/schedule"
    luego = (accounts.now() + timedelta(hours=1)).isoformat()
    programada = client.post(url, headers=auth, json={"at": luego}).get_json()
    assert programada["auto_send"] is True
    assert client.post(url, headers=auth, json={"at": "mañana"}).status_code == 422
    apagada = client.delete(url, headers=auth).get_json()
    assert apagada["auto_send"] is False
    database.campaigns.update_one({}, {"$set": {
        "scheduled_at": accounts.now() - timedelta(minutes=1)}})
    background.campaigns_tick(database, "w1")
    assert salidos == []


def test_cuenta_que_no_puede_y_llave_de_prueba(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=2)
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = crear(client, auth).get_json()
    prueba, _ = llave(database, cuenta, mode="test", scopes=("campaigns:read",
                                                            "campaigns:send"))
    simulada = client.post(f"/api/v1/campaigns/{hecha['id']}/send", headers=prueba)
    assert simulada.status_code == 200
    assert simulada.get_json() == {"status": "simulated", "audience": 2, "blocked": []}
    assert campaigns.by_id(database, cuenta["_id"], campaigns.for_account(
        database, cuenta["_id"])[0]["_id"])["auto_send"] is False
    assert crear(client, prueba).status_code == 403

    accounts.pause(database, cuenta["_id"], reason="bounces", note="5 %")
    negada = client.post(f"/api/v1/campaigns/{hecha['id']}/send", headers=auth)
    assert negada.status_code == 409
    assert negada.get_json()["error"]["blocked"][0]["code"] == "paused"
    assert salidos == []


def test_nada_de_otra_cuenta_ni_las_individuales(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    ajena, _ = llave(database, otra, scopes=TODO)
    hecha = crear(client, auth).get_json()
    for intento in (client.get(f"/api/v1/campaigns/{hecha['id']}", headers=ajena),
                    client.patch(f"/api/v1/campaigns/{hecha['id']}", headers=ajena,
                                 json={"subject": "x"}),
                    client.post(f"/api/v1/campaigns/{hecha['id']}/send", headers=ajena)):
        assert intento.status_code == 404
    individual = campaigns.create_single(database, cuenta["_id"], subject="Hola", body="x",
                                         contact_id=None, to="a@ejemplo.com")
    assert client.get(f"/api/v1/campaigns/{individual}", headers=auth).status_code == 404
    listadas = client.get("/api/v1/campaigns", headers=auth).get_json()["data"]
    assert [one["id"] for one in listadas] == [hecha["id"]]
    assert client.get("/api/v1/campaigns?status=nada", headers=auth).status_code == 422
