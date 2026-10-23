"""La puerta de la API pública (octubre de 2026).

Lo que fijan estas pruebas: que solo entra una llave en `Authorization: Bearer`
(una mala, vencida o revocada responden igual), que la sesión del navegador no
cuenta ni se escribe, que una llave en la dirección se rechaza y se revoca sola,
que cada ruta pide su permiso y una llave de prueba no pasa de lo suyo, que la
lista de IP solo cree a `CF-Connecting-IP` cuando viene de Cloudflare, que los
límites responden 429 con `Retry-After` sin frenar a una llave buena por los
fallos de otra en la misma IP, que los errores salen en JSON y con las cabeceras
de la API, y que solo lo que falla con una llave buena queda en el registro.
"""

from __future__ import annotations

from datetime import timedelta

from test_api_contactos import con_api
from test_campaigns import ready

from blueprints.api import core
from models import account as accounts
from models import api_key as api_keys
from models import api_log
from models import idempotency
from models import mail_log


def llave(database, cuenta, *, mode="live", scopes=("emails:send",), ips=(), days=0):
    con_api(database, cuenta)
    raw, doc = api_keys.create(database, cuenta["_id"], name="Tienda", mode=mode,
                               scopes=list(scopes), ips=list(ips), days=days)
    return raw, doc


def con(raw):
    return {"Authorization": f"Bearer {raw}"}


def test_entra_solo_con_la_llave(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, _ = llave(database, cuenta)
    bien = client.get("/api/v1/me", headers=con(raw))
    assert bien.status_code == 200
    datos = bien.get_json()
    assert datos["account"]["company"] == "Cooperativa Ejemplo"
    assert datos["key"]["name"] == "Tienda" and "token_hash" not in datos["key"]
    assert raw not in bien.get_data(as_text=True)

    sin = client.get("/api/v1/me")
    assert sin.status_code == 401 and sin.get_json()["error"]["code"] == "unauthorized"
    assert sin.headers["WWW-Authenticate"].startswith("Bearer")
    otra = client.get("/api/v1/me", headers=con("sa_live_" + "x" * 43))
    basura = client.get("/api/v1/me", headers={"Authorization": "Basic abc"})
    assert otra.status_code == basura.status_code == 401
    assert otra.get_json()["error"]["message"] == sin.get_json()["error"]["message"]


def test_vencida_y_revocada_responden_igual_que_una_inventada(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, doc = llave(database, cuenta)
    database.api_keys.update_one({"_id": doc["_id"]}, {"$set": {
        "expires_at": accounts.now() - timedelta(minutes=1)}})
    assert client.get("/api/v1/me", headers=con(raw)).status_code == 401
    raw2, doc2 = llave(database, cuenta)
    api_keys.revoke(database, cuenta["_id"], doc2["_id"])
    assert client.get("/api/v1/me", headers=con(raw2)).status_code == 401


def test_solo_se_guarda_el_hash(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, doc = llave(database, cuenta)
    guardado = database.api_keys.find_one({"_id": doc["_id"]})
    assert raw not in str(guardado)
    assert guardado["prefix"] == raw[:12] and guardado["last4"] == raw[-4:]


def test_la_sesion_del_navegador_no_cuenta_ni_se_escribe(client, database, outbox):
    """Un navegador con sesión no entra a la API, y la llave de una cuenta con la
    galleta de otra ve solo lo suyo. Ninguna respuesta de la API pone galletas."""
    browser, una, _ = ready(client, database)
    _, dos, _ = ready(client, database, email="otra@ejemplo.com")
    con_sesion = browser.get("/api/v1/me")
    assert con_sesion.status_code == 401
    assert "Set-Cookie" not in con_sesion.headers
    raw, _ = llave(database, dos)
    cruzada = browser.get("/api/v1/me", headers=con(raw))
    assert cruzada.get_json()["account"]["id"] == str(dos["_id"])
    assert "Set-Cookie" not in cruzada.headers
    # Y la sesión del panel sigue viva.
    assert browser.get("/dashboard").status_code == 200


def test_una_llave_en_la_direccion_se_revoca_sola(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, doc = llave(database, cuenta)
    respuesta = client.get(f"/api/v1/me?api_key={raw}")
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["code"] == "key_in_url"
    assert database.api_keys.find_one({"_id": doc["_id"]})["revoked_at"] is not None
    assert database.mail_log.count_documents({"purpose": mail_log.API_KEY}) == 1
    assert client.get("/api/v1/me", headers=con(raw)).status_code == 401


def test_una_llave_de_prueba_nace_sin_permisos_de_escribir(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, doc = llave(database, cuenta, mode="test",
                     scopes=("contacts:write", "contacts:read", "emails:send"))
    assert doc["scopes"] == ["contacts:read", "emails:send"]
    assert raw.startswith("sa_test_")


def test_la_lista_de_ip_solo_cree_a_cloudflare(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, _ = llave(database, cuenta, ips=["203.0.113.7"])
    # En las pruebas la conexión es 127.0.0.1: la cabecera no cuenta.
    falsa = client.get("/api/v1/me", headers={**con(raw), "CF-Connecting-IP": "203.0.113.7"})
    assert falsa.status_code == 403 and falsa.get_json()["error"]["code"] == "ip_not_allowed"
    # Desde Cloudflare, sí.
    cloudflare = client.get("/api/v1/me", headers={**con(raw), "CF-Connecting-IP": "203.0.113.7"},
                            environ_base={"REMOTE_ADDR": "104.16.0.1"})
    assert cloudflare.status_code == 200
    otra = client.get("/api/v1/me", headers={**con(raw), "CF-Connecting-IP": "198.51.100.1"},
                      environ_base={"REMOTE_ADDR": "104.16.0.1"})
    assert otra.status_code == 403


def test_las_llaves_malas_frenan_esa_ip_pero_no_a_una_buena(client, database, outbox,
                                                            monkeypatch):
    monkeypatch.setattr(core, "BAD_KEYS", (3, 600))
    _, cuenta, _ = ready(client, database)
    raw, _ = llave(database, cuenta)
    for _ in range(3):
        assert client.get("/api/v1/me", headers=con("sa_live_" + "y" * 43)).status_code == 401
    frenada = client.get("/api/v1/me", headers=con("sa_live_" + "y" * 43))
    assert frenada.status_code == 429 and int(frenada.headers["Retry-After"]) > 0
    assert client.get("/api/v1/me", headers=con(raw)).status_code == 200


def test_el_limite_por_cuenta(client, database, outbox, monkeypatch):
    monkeypatch.setattr(core, "ACCOUNT_LIMIT", (2, 60))
    _, cuenta, _ = ready(client, database)
    raw, _ = llave(database, cuenta)
    assert client.get("/api/v1/me", headers=con(raw)).status_code == 200
    assert client.get("/api/v1/senders", headers=con(raw)).status_code == 200
    tope = client.get("/api/v1/me", headers=con(raw))
    assert tope.status_code == 429 and tope.headers["Retry-After"]
    assert tope.get_json()["error"]["code"] == "rate_limited"


def test_cuenta_suspendida_o_cerrada(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, _ = llave(database, cuenta)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"status": "suspended"}})
    assert client.get("/api/v1/me", headers=con(raw)).get_json()["error"]["code"] == \
        "account_suspended"
    database.accounts.update_one({"_id": cuenta["_id"]},
                                 {"$set": {"status": "registered"},
                                  "$unset": {"opened_at": "", "plan": ""}})
    assert client.get("/api/v1/me", headers=con(raw)).get_json()["error"]["code"] == \
        "account_closed"


def test_errores_en_json_con_las_cabeceras_de_la_api(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    raw, _ = llave(database, cuenta)
    for respuesta, estado, codigo in (
            (client.get("/api/v1/no-existe", headers=con(raw)), 404, "not_found"),
            (client.post("/api/v1/me", headers=con(raw)), 405, "method_not_allowed")):
        assert respuesta.status_code == estado
        assert respuesta.mimetype == "application/json"
        assert respuesta.get_json()["error"]["code"] == codigo
        assert respuesta.get_json()["error"]["request_id"].startswith("req_")
    bien = client.get("/api/v1/me", headers=con(raw))
    assert bien.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert "sandbox" in bien.headers["Content-Security-Policy"]
    assert bien.headers["Cache-Control"] == "no-store"
    assert bien.headers["X-Content-Type-Options"] == "nosniff"
    assert bien.headers["X-Request-Id"].startswith("req_")
    # Y el panel sigue con su 404 de siempre, en HTML.
    assert client.get("/no-existe").mimetype == "text/html"


def test_solo_lo_que_falla_con_una_llave_buena_queda_en_el_registro(client, database,
                                                                    outbox):
    _, cuenta, _ = ready(client, database)
    raw, doc = llave(database, cuenta)
    client.get("/api/v1/me", headers=con(raw))
    client.get("/api/v1/me", headers=con("sa_live_" + "z" * 43))
    client.post("/api/v1/me", headers=con(raw))
    assert database.api_log.count_documents({}) == 0
    client.get("/api/v1/nada", headers=con(raw))
    # El 404 de una ruta que no existe no pasa por la puerta: no se sabe de quién es.
    assert database.api_log.count_documents({}) == 0
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"status": "suspended"}})
    client.get("/api/v1/me", headers=con(raw))
    filas = api_log.recent(database, cuenta["_id"])
    assert len(filas) == 1 and filas[0]["status"] == 403
    assert filas[0]["key_id"] == doc["_id"] and raw not in str(filas[0])


def test_la_descripcion_es_publica(client, database, outbox):
    respuesta = client.get("/api/v1/openapi.json")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["openapi"].startswith("3.1")
    assert "/me" in respuesta.get_json()["paths"]


def test_idempotencia_por_llave_y_ruta(client, database, outbox):
    """El modelo: la misma clave con el mismo cuerpo repite, con otro cuerpo
    choca, y en curso espera; de otra llave o de otra ruta es otra cosa."""
    _, cuenta, _ = ready(client, database)
    _, una = llave(database, cuenta)
    _, dos = llave(database, cuenta)
    comun = {"account_id": cuenta["_id"], "method": "POST", "path": "/api/v1/emails",
             "key": "pedido-1"}
    estado, registro = idempotency.begin(database, key_id=una["_id"], body_hash="a", **comun)
    assert estado == idempotency.NEW
    assert idempotency.begin(database, key_id=una["_id"], body_hash="a", **comun)[0] == \
        idempotency.BUSY
    assert idempotency.begin(database, key_id=una["_id"], body_hash="b", **comun)[0] == \
        idempotency.MISMATCH
    idempotency.finish(database, registro["_id"], status=201, body={"id": "x"})
    estado, repetido = idempotency.begin(database, key_id=una["_id"], body_hash="a", **comun)
    assert estado == idempotency.REPLAY and repetido["body"] == {"id": "x"}
    assert idempotency.begin(database, key_id=dos["_id"], body_hash="a", **comun)[0] == \
        idempotency.NEW
    # Una que murió en curso no traba la clave: pasado su plazo, se retoma.
    otra = {**comun, "key": "pedido-2"}
    _, viva = idempotency.begin(database, key_id=una["_id"], body_hash="a", **otra)
    database.api_idempotency.update_one({"_id": viva["_id"]}, {"$set": {
        "pending_until": accounts.now() - timedelta(seconds=1)}})
    assert idempotency.begin(database, key_id=una["_id"], body_hash="a", **otra)[0] == \
        idempotency.NEW
