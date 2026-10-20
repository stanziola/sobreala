"""Contactos, etiquetas, columnas y supresiones por la API (octubre de 2026).

Lo que fijan estas pruebas: que cargar sigue las reglas de importar (nadie se
duplica, los nuevos necesitan sitio y todas sus columnas, las etiquetas se suman,
de dónde salieron queda escrito) y cada fila dice qué le pasó; que nada de otra
cuenta se ve ni se toca; que un valor con forma de operador de Mongo es un error
y nunca una consulta; que las supresiones solo se miran y borrar un contacto no
las borra; que una carga a la vez; que cada ruta pide su permiso y una llave de
prueba no escribe; y que repetir con la misma `Idempotency-Key` no carga dos
veces.
"""

from __future__ import annotations

from test_campaigns import csrf, ready

from models import account as accounts
from models import api_key as api_keys
from models import contact as contacts
from models import lock as locks
from models import suppression as suppressions


def llave(database, cuenta, *, mode="live", scopes=("contacts:read", "contacts:write")):
    raw, doc = api_keys.create(database, cuenta["_id"], name="Tienda", mode=mode,
                               scopes=list(scopes), ips=[], days=0)
    return {"Authorization": f"Bearer {raw}"}, doc


def cargar(client, auth, filas, **extra):
    data = {"consent": {"source": "customers", "note": "Clientes"}, "contacts": filas}
    data.update(extra)
    return client.post("/api/v1/contacts", json=data, headers=auth)


def test_cada_ruta_pide_su_permiso(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    solo_enviar, _ = llave(database, cuenta, scopes=("emails:send",))
    negado = client.get("/api/v1/contacts", headers=solo_enviar)
    assert negado.status_code == 403
    assert negado.get_json()["error"]["code"] == "missing_scope"
    assert "contacts:read" in negado.get_json()["error"]["message"]
    leer, _ = llave(database, cuenta, scopes=("contacts:read",))
    assert client.get("/api/v1/contacts", headers=leer).status_code == 200
    assert cargar(client, leer, [{"email": "x@ejemplo.com"}]).status_code == 403


def test_una_llave_de_prueba_lee_y_no_escribe(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    prueba, doc = llave(database, cuenta, mode="test")
    assert client.get("/api/v1/contacts", headers=prueba).status_code == 200
    # Aunque alguien le escriba el permiso a mano en la base.
    database.api_keys.update_one({"_id": doc["_id"]},
                                 {"$set": {"scopes": ["contacts:write"]}})
    negado = cargar(client, prueba, [{"email": "x@ejemplo.com"}])
    assert negado.status_code == 403
    assert negado.get_json()["error"]["code"] == "test_key_cannot"
    assert contacts.by_email(database, cuenta["_id"], "x@ejemplo.com") is None


def test_lista_con_su_estado_y_por_paginas(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=5)
    suppressions.add(database, cuenta["_id"], "socio1@ejemplo.com",
                     reason=suppressions.UNSUBSCRIBE)
    auth, _ = llave(database, cuenta)
    primera = client.get("/api/v1/contacts?limit=3", headers=auth).get_json()
    assert len(primera["data"]) == 3 and primera["next_cursor"]
    segunda = client.get(f"/api/v1/contacts?limit=3&cursor={primera['next_cursor']}",
                         headers=auth).get_json()
    assert len(segunda["data"]) == 2 and segunda["next_cursor"] is None
    todos = {one["email"]: one for one in primera["data"] + segunda["data"]}
    assert len(todos) == 5
    assert todos["socio1@ejemplo.com"]["status"] == "suppressed"
    assert todos["socio1@ejemplo.com"]["suppression"]["reason"] == "unsubscribe"
    assert todos["socio0@ejemplo.com"]["status"] == "active"
    uno = client.get("/api/v1/contacts?email=SOCIO2@ejemplo.com", headers=auth).get_json()
    assert [one["email"] for one in uno["data"]] == ["socio2@ejemplo.com"]
    assert client.get("/api/v1/contacts?cursor=nope", headers=auth).status_code == 400


def test_nada_de_otra_cuenta(client, database, outbox):
    _, una, _ = ready(client, database)
    _, otra, _ = ready(client, database, email="otra@ejemplo.com")
    ajeno = contacts.by_email(database, otra["_id"], "socio0@ejemplo.com")
    auth, _ = llave(database, una)
    assert client.get(f"/api/v1/contacts/{ajeno['_id']}", headers=auth).status_code == 404
    assert client.patch(f"/api/v1/contacts/{ajeno['_id']}", json={"name": "X"},
                        headers=auth).status_code == 404
    assert client.delete(f"/api/v1/contacts/{ajeno['_id']}", headers=auth).status_code == 404
    assert client.get("/api/v1/contacts/no-es-un-id", headers=auth).status_code == 404
    assert contacts.by_id(database, otra["_id"], ajeno["_id"])["name"] == "Socio 0"
    listados = client.get("/api/v1/contacts", headers=auth).get_json()["data"]
    assert all(one["id"] != str(ajeno["_id"]) for one in listados)


def test_cargar_sigue_las_reglas_de_importar(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=1, tag="Socios")
    accounts.set_plan(database, cuenta["_id"], "negocio")
    accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    contacts.update(database, cuenta["_id"],
                    contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")["_id"],
                    email="socio0@ejemplo.com", name="Socio 0", tags=["Socios"],
                    values={"CIUDAD": "Santiago"})
    auth, _ = llave(database, cuenta)
    respuesta = cargar(client, auth, [
        {"email": "nueva@ejemplo.com", "name": "Nueva", "fields": {"CIUDAD": "David"}},
        {"email": "Socio0@Ejemplo.com", "tags": ["Socios"]},
        {"email": "nueva@ejemplo.com"},
        {"email": "sin-ciudad@ejemplo.com"},
        {"email": "no-es-correo"},
        {"email": "x@ejemplo.com", "fields": {"PAIS": "Panamá"}},
        {"email": {"$ne": ""}},
        "texto suelto",
    ], tags=["Socios"])
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    por_fila = {one["index"]: one for one in datos["results"]}
    assert por_fila[0]["result"] == "added"
    assert por_fila[1]["result"] == "updated"
    assert por_fila[2]["reason"] == "duplicate"
    assert por_fila[3]["reason"] == "incomplete" and por_fila[3]["missing"] == ["CIUDAD"]
    assert por_fila[4]["reason"] == "invalid_email"
    assert por_fila[5]["reason"] == "unknown_field"
    assert por_fila[6]["reason"] == "bad_row" or por_fila[6]["reason"] == "invalid_email"
    assert por_fila[7]["reason"] == "bad_row"
    assert datos["added"] == 1 and datos["updated"] == 1 and datos["rejected"] == 6

    nueva = contacts.by_email(database, cuenta["_id"], "nueva@ejemplo.com")
    assert nueva["added_by"] == "api" and nueva["tags"] == ["Socios"]
    assert nueva["consent"]["source"] == "customers"
    # A la que ya estaba se le suma, sin cambiarle de dónde salió.
    vieja = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    assert vieja["consent"]["source"] == "members"
    assert database.contacts.count_documents({"account_id": cuenta["_id"]}) == 2


def test_lo_que_no_va_se_dice_antes_de_escribir(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta)
    sin_origen = client.post("/api/v1/contacts", json={"contacts": [{"email": "a@ejemplo.com"}]},
                             headers=auth)
    assert sin_origen.status_code == 422
    mal_origen = cargar(client, auth, [{"email": "a@ejemplo.com"}],
                        consent={"source": {"$ne": 1}})
    assert mal_origen.status_code == 422 and "consent" in mal_origen.get_json()["error"]["fields"]
    etiqueta = cargar(client, auth, [{"email": "a@ejemplo.com"}], tags=["No existe"])
    assert etiqueta.status_code == 422 and etiqueta.get_json()["error"]["tags"] == ["No existe"]
    demas = cargar(client, auth, [{"email": "a@ejemplo.com"}], extra=1)
    assert demas.status_code == 422 and "extra" in demas.get_json()["error"]["fields"]
    texto = client.post("/api/v1/contacts", data="hola", headers=auth)
    assert texto.status_code == 415
    roto = client.post("/api/v1/contacts", data="{", headers={**auth,
                                                             "Content-Type": "application/json"})
    assert roto.status_code == 400
    assert database.contacts.count_documents({"account_id": cuenta["_id"]}) == 0


def test_el_tope_del_plan(client, database, outbox, monkeypatch):
    _, cuenta, _ = ready(client, database, howmany=2)
    monkeypatch.setitem(accounts.PLAN_CONTACTS, "basico", 3)
    auth, _ = llave(database, cuenta)
    datos = cargar(client, auth, [{"email": "nueva1@ejemplo.com"},
                                  {"email": "nueva2@ejemplo.com"},
                                  {"email": "socio0@ejemplo.com", "name": "Cambiado"}]).get_json()
    resultados = [one.get("reason", one["result"]) for one in datos["results"]]
    assert resultados == ["added", "limit", "updated"]
    assert contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")["name"] == "Cambiado"


def test_una_carga_a_la_vez(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    auth, _ = llave(database, cuenta)
    token = locks.acquire(database, f"contacts:{cuenta['_id']}", 60)
    ocupada = cargar(client, auth, [{"email": "a@ejemplo.com"}])
    assert ocupada.status_code == 409 and ocupada.get_json()["error"]["code"] == "busy"
    # Y el importador del panel tampoco entra mientras tanto.
    import io

    pantalla = browser.post("/contacts/import", data={
        "csrf_token": csrf(browser, "/contacts/import"), "source": "members",
        "archivo": (io.BytesIO(b"correo\nb@ejemplo.com\n"), "lista.csv")},
        content_type="multipart/form-data")
    assert "importación en curso" in pantalla.get_data(as_text=True)
    locks.release(database, f"contacts:{cuenta['_id']}", token)
    assert cargar(client, auth, [{"email": "a@ejemplo.com"}]).status_code == 200


def test_repetir_con_la_misma_clave_no_carga_dos_veces(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta)
    clave = {**auth, "Idempotency-Key": "carga-1"}
    filas = [{"email": "a@ejemplo.com", "name": "A"}]
    primera = cargar(client, clave, filas)
    contacts.delete(database, cuenta["_id"], "a@ejemplo.com")
    segunda = cargar(client, clave, filas)
    assert segunda.headers["Idempotent-Replayed"] == "true"
    assert segunda.get_json() == primera.get_json()
    assert contacts.by_email(database, cuenta["_id"], "a@ejemplo.com") is None
    otra = cargar(client, clave, [{"email": "b@ejemplo.com"}])
    assert otra.status_code == 422 and otra.get_json()["error"]["code"] == "idempotency_mismatch"


def test_cambiar_un_contacto(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=2, tag="Socios")
    accounts.set_plan(database, cuenta["_id"], "negocio")
    accounts.add_tag(database, cuenta["_id"], "Asamblea")
    auth, _ = llave(database, cuenta)
    uno = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    cambiado = client.patch(f"/api/v1/contacts/{uno['_id']}", headers=auth,
                            json={"name": "Ana", "tags": ["Asamblea"]})
    assert cambiado.status_code == 200
    assert cambiado.get_json()["tags"] == ["Asamblea"] and cambiado.get_json()["name"] == "Ana"
    tomado = client.patch(f"/api/v1/contacts/{uno['_id']}", headers=auth,
                          json={"email": "socio1@ejemplo.com"})
    assert tomado.status_code == 409 and tomado.get_json()["error"]["code"] == "email_taken"
    ajena = client.patch(f"/api/v1/contacts/{uno['_id']}", headers=auth,
                         json={"tags": ["Inventada"]})
    assert ajena.status_code == 422
    accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    falta = client.patch(f"/api/v1/contacts/{uno['_id']}", headers=auth, json={"name": "B"})
    assert falta.status_code == 422 and "CIUDAD" in falta.get_json()["error"]["fields"]["fields"]
    lleno = client.patch(f"/api/v1/contacts/{uno['_id']}", headers=auth,
                         json={"fields": {"CIUDAD": "David"}})
    assert lleno.status_code == 200 and lleno.get_json()["complete"] is True


def test_borrar_deja_la_supresion(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=1)
    suppressions.add(database, cuenta["_id"], "socio0@ejemplo.com",
                     reason=suppressions.UNSUBSCRIBE)
    auth, _ = llave(database, cuenta)
    uno = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    assert client.delete(f"/api/v1/contacts/{uno['_id']}", headers=auth).get_json()["deleted"]
    assert contacts.by_id(database, cuenta["_id"], uno["_id"]) is None
    assert suppressions.has(database, cuenta["_id"], "socio0@ejemplo.com")
    otra = cargar(client, auth, [{"email": "socio0@ejemplo.com"}]).get_json()
    assert otra["results"][0]["warning"] == "suppressed"
    lista = client.get("/api/v1/suppressions?reason=unsubscribe", headers=auth).get_json()
    assert [one["email"] for one in lista["data"]] == ["socio0@ejemplo.com"]
    assert client.get("/api/v1/suppressions?reason=inventado", headers=auth).status_code == 422


def test_etiquetas(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=1, tag="Socios fundadores")
    auth, _ = llave(database, cuenta)
    lista = client.get("/api/v1/tags", headers=auth).get_json()
    assert lista["data"] == [{"name": "Socios fundadores", "contacts": 1}]
    assert client.post("/api/v1/tags", json={"name": "socios FUNDADORES"},
                       headers=auth).get_json()["error"]["code"] == "tag_exists"
    llena = client.post("/api/v1/tags", json={"name": "Otra"}, headers=auth)
    assert llena.status_code == 409 and llena.get_json()["error"]["code"] == "limit_reached"
    accounts.set_plan(database, cuenta["_id"], "negocio")
    assert client.post("/api/v1/tags", json={"name": "Otra"}, headers=auth).status_code == 201
    borrada = client.delete("/api/v1/tags/Socios%20fundadores", headers=auth)
    assert borrada.status_code == 200 and borrada.get_json()["contacts"] == 1
    assert contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")["tags"] == []
    assert client.delete("/api/v1/tags/Nada", headers=auth).status_code == 404


def test_columnas(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=1)
    auth, _ = llave(database, cuenta)
    hecha = client.post("/api/v1/fields", json={"label": "Número de socio", "type": "text"},
                        headers=auth)
    assert hecha.status_code == 201 and hecha.get_json()["key"] == "NUMERO_DE_SOCIO"
    llena = client.post("/api/v1/fields", json={"label": "Ciudad", "type": "text"},
                        headers=auth)
    assert llena.get_json()["error"]["code"] == "limit_reached"
    accounts.set_plan(database, cuenta["_id"], "negocio")
    repetida = client.post("/api/v1/fields", json={"label": "Numero de socio", "type": "text"},
                           headers=auth)
    assert repetida.get_json()["error"]["code"] == "field_exists"
    assert client.post("/api/v1/fields", json={"label": "Nombre", "type": "text"},
                       headers=auth).get_json()["error"]["code"] == "field_exists"
    assert client.post("/api/v1/fields", json={"label": "X", "type": "lista"},
                       headers=auth).status_code == 422
    uno = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    database.contacts.update_one({"_id": uno["_id"]},
                                 {"$set": {"fields.NUMERO_DE_SOCIO": "A-12"}})
    choque = client.patch("/api/v1/fields/NUMERO_DE_SOCIO", json={"type": "number"},
                          headers=auth)
    assert choque.status_code == 409 and choque.get_json()["error"]["contacts"] == 1
    assert client.patch("/api/v1/fields/NUMERO_DE_SOCIO", json={"type": "yesno"},
                        headers=auth).status_code == 409
    borrada = client.delete("/api/v1/fields/NUMERO_DE_SOCIO", headers=auth)
    assert borrada.get_json()["contacts"] == 1
    assert "NUMERO_DE_SOCIO" not in (contacts.by_id(database, cuenta["_id"], uno["_id"])
                                     .get("fields") or {})
    assert client.delete("/api/v1/fields/NADA", headers=auth).status_code == 404


def test_las_filas_por_minuto(client, database, outbox, monkeypatch):
    from blueprints.api import contacts as api_contacts

    monkeypatch.setattr(api_contacts, "ROWS_PER_MINUTE", 3)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta)
    assert cargar(client, auth, [{"email": "a@ejemplo.com"}, {"email": "b@ejemplo.com"}]
                  ).status_code == 200
    tope = cargar(client, auth, [{"email": "c@ejemplo.com"}, {"email": "d@ejemplo.com"}])
    assert tope.status_code == 429 and tope.headers["Retry-After"]
