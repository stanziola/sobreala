"""Las listas dentro de un contacto y el id de su sistema (octubre de 2026).

Lo que fijan estas pruebas: que una lista se crea con sus datos y caben dos;
que sus filas se agregan, se cambian y se borran por su id, en el panel y por
la API, con sus topes; que una lista vacía no deja incompleto a nadie; que
editar la ficha no borra las listas; que en el correo la marca sola arma la
tabla, el bloque se repite por fila y el vacío sale cuando no hay filas, todo
escapado y en una sola pasada (una marca escondida en un dato sale tal cual);
que en el asunto una lista no escribe nada; que el id de tu sistema es único en
la cuenta y la carga por la API encuentra por él; y que exportar no pierde
nada.
"""

from __future__ import annotations

import re

from test_api_contactos import cargar, llave
from test_campaigns import csrf, ready

from models import account as accounts
from models import contact as contacts
from services import fields as columns
from services import importer

ITEMS = [("Fecha", "date"), ("Descripción", "text"), ("Monto", "number")]


def cuenta_con_lista(client, database, *, howmany=2, plan="negocio"):
    browser, cuenta, _ = ready(client, database, howmany=howmany, plan=plan)
    assert accounts.add_field(database, cuenta["_id"], label="Transacciones",
                              kind="list", items=ITEMS) == "TRANSACCIONES"
    return browser, accounts.by_id(database, cuenta["_id"])


def filas_de(database, cuenta, contacto) -> list[dict]:
    return contacts.by_id(database, cuenta["_id"], contacto["_id"])["fields"].get(
        "TRANSACCIONES", [])


# ------------------------------------------------------------ las columnas

def test_crear_una_lista_en_el_panel(client, database, outbox):
    browser, cuenta, _ = ready(client, database, plan="negocio")
    nueva = browser.post("/contacts/columns/new", data={
        "csrf_token": csrf(browser, "/contacts/columns/new"),
        "nombre": "Transacciones", "type": "list",
        "dato-0": "Fecha", "dato-tipo-0": "date",
        "dato-1": "Descripción", "dato-tipo-1": "text",
        "dato-2": "Monto", "dato-tipo-2": "number"})
    assert nueva.status_code == 302
    lista = accounts.field_by_key(accounts.by_id(database, cuenta["_id"]), "TRANSACCIONES")
    assert lista["type"] == "list"
    assert [(one["key"], one["type"]) for one in lista["items"]] == [
        ("FECHA", "date"), ("DESCRIPCION", "text"), ("MONTO", "number")]

    # Sin sus datos no se crea.
    sin_datos = browser.post("/contacts/columns/new", data={
        "csrf_token": csrf(browser, "/contacts/columns/new"),
        "nombre": "Pedidos", "type": "list"})
    assert sin_datos.status_code == 200
    assert accounts.field_by_key(accounts.by_id(database, cuenta["_id"]), "PEDIDOS") is None

    # Caben dos.
    assert accounts.add_field(database, cuenta["_id"], label="Pedidos", kind="list",
                              items=[("Producto", "text")]) == "PEDIDOS"
    tercera = browser.post("/contacts/columns/new", data={
        "csrf_token": csrf(browser, "/contacts/columns/new"),
        "nombre": "Pagos", "type": "list", "dato-0": "Monto", "dato-tipo-0": "number"})
    assert tercera.status_code == 200
    assert accounts.add_field(database, cuenta["_id"], label="Pagos", kind="list",
                              items=[("Monto", "number")]) is None
    assert accounts.field_by_key(accounts.by_id(database, cuenta["_id"]), "PAGOS") is None


def test_una_lista_no_cambia_de_tipo_y_le_queda_un_dato(client, database, outbox):
    browser, cuenta = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    contacts.set_rows(database, cuenta["_id"], socio["_id"], "TRANSACCIONES",
                      [{"FECHA": "2026-10-01", "MONTO": "150", "id": "aaaaaa"}])
    assert not accounts.set_field_type(database, cuenta["_id"], "TRANSACCIONES", "text")
    browser.post("/contacts/columns/type", data={
        "csrf_token": csrf(browser, "/contacts/columns"),
        "columna": "TRANSACCIONES", "type": "text"})
    assert accounts.field_by_key(accounts.by_id(database, cuenta["_id"]),
                                 "TRANSACCIONES")["type"] == "list"

    # Quitar un dato lo borra de las filas de todos.
    browser.post("/contacts/columns/items", data={
        "csrf_token": csrf(browser, "/contacts/columns"), "columna": "TRANSACCIONES",
        "action": "remove", "dato": "MONTO"})
    lista = accounts.field_by_key(accounts.by_id(database, cuenta["_id"]), "TRANSACCIONES")
    assert [one["key"] for one in lista["items"]] == ["FECHA", "DESCRIPCION"]
    assert filas_de(database, cuenta, socio) == [{"FECHA": "2026-10-01", "id": "aaaaaa"}]

    # Agregar otro.
    browser.post("/contacts/columns/items", data={
        "csrf_token": csrf(browser, "/contacts/columns"), "columna": "TRANSACCIONES",
        "action": "add", "nombre": "Saldo", "type": "number"})
    lista = accounts.field_by_key(accounts.by_id(database, cuenta["_id"]), "TRANSACCIONES")
    assert [one["key"] for one in lista["items"]] == ["FECHA", "DESCRIPCION", "SALDO"]

    # El último que le queda no se quita.
    for dato in ("DESCRIPCION", "SALDO"):
        assert accounts.remove_list_item(database, cuenta["_id"], "TRANSACCIONES", dato)
    assert not accounts.remove_list_item(database, cuenta["_id"], "TRANSACCIONES", "FECHA")


# ------------------------------------------------------------ las filas en la ficha

def test_filas_en_la_ficha_del_contacto(client, database, outbox):
    browser, cuenta = cuenta_con_lista(client, database)
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    ficha = f"/contacts/edit/{socio['_id']}"
    filas = f"{ficha}/rows"
    assert "Transacciones" in browser.get(ficha).get_data(as_text=True)

    agregada = browser.post(filas, data={
        "csrf_token": csrf(browser, ficha), "lista": "TRANSACCIONES", "action": "add",
        "item-FECHA": "01/10/2026", "item-DESCRIPCION": "Depósito", "item-MONTO": "B/.150"})
    assert agregada.status_code == 302
    [fila] = filas_de(database, cuenta, socio)
    assert fila["FECHA"] == "2026-10-01" and fila["MONTO"] == "150"
    assert re.fullmatch(r"[0-9a-f]{6}", fila["id"])

    # Un valor que no es de su tipo no entra, y una fila vacía tampoco.
    mala = browser.post(filas, data={
        "csrf_token": csrf(browser, ficha), "lista": "TRANSACCIONES", "action": "add",
        "item-MONTO": "mucho"})
    assert mala.status_code == 200
    vacia = browser.post(filas, data={
        "csrf_token": csrf(browser, ficha), "lista": "TRANSACCIONES", "action": "add"})
    assert "Escribe al menos un dato" in vacia.get_data(as_text=True)
    assert len(filas_de(database, cuenta, socio)) == 1

    # Se cambia por su id y se queda con él.
    browser.post(filas, data={
        "csrf_token": csrf(browser, ficha), "lista": "TRANSACCIONES", "action": "save",
        "fila": fila["id"], "item-FECHA": "2026-10-02", "item-DESCRIPCION": "Depósito",
        "item-MONTO": "175"})
    assert filas_de(database, cuenta, socio) == [
        {"FECHA": "2026-10-02", "DESCRIPCION": "Depósito", "MONTO": "175", "id": fila["id"]}]

    # Editar la ficha no le borra las filas.
    browser.post(ficha, data={"csrf_token": csrf(browser, ficha),
                              "email": "socio0@ejemplo.com", "name": "Otro nombre"})
    despues = contacts.by_id(database, cuenta["_id"], socio["_id"])
    assert despues["name"] == "Otro nombre" and len(despues["fields"]["TRANSACCIONES"]) == 1

    # Sin el token del formulario no pasa nada.
    browser.post(filas, data={"lista": "TRANSACCIONES", "action": "delete",
                              "fila": fila["id"]})
    assert len(filas_de(database, cuenta, socio)) == 1
    browser.post(filas, data={"csrf_token": csrf(browser, ficha), "lista": "TRANSACCIONES",
                              "action": "delete", "fila": fila["id"]})
    assert filas_de(database, cuenta, socio) == []


def test_pasada_la_ultima_se_va_la_mas_vieja(client, database, outbox):
    browser, cuenta = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    llenas = [{"MONTO": str(n), "id": f"{n:06x}"} for n in range(columns.LIST_ROWS_MAX)]
    contacts.set_rows(database, cuenta["_id"], socio["_id"], "TRANSACCIONES", llenas)
    ficha = f"/contacts/edit/{socio['_id']}"
    assert "al agregar otra se borra la más vieja" in browser.get(ficha).get_data(as_text=True)
    browser.post(f"{ficha}/rows", data={
        "csrf_token": csrf(browser, ficha), "lista": "TRANSACCIONES", "action": "add",
        "item-MONTO": "999"})
    ahora = filas_de(database, cuenta, socio)
    assert len(ahora) == columns.LIST_ROWS_MAX
    assert ahora[0]["MONTO"] == "1" and ahora[-1]["MONTO"] == "999"


def test_las_filas_de_otra_cuenta_no_se_tocan(client, database, outbox):
    _, una = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, una["_id"], "socio0@ejemplo.com")
    contacts.set_rows(database, una["_id"], socio["_id"], "TRANSACCIONES",
                      [{"MONTO": "1", "id": "aaaaaa"}])
    otra, cuenta_otra, _ = ready(client, database, email="otra@ejemplo.com", plan="negocio")
    accounts.add_field(database, cuenta_otra["_id"], label="Transacciones", kind="list",
                       items=ITEMS)
    respuesta = otra.post(f"/contacts/edit/{socio['_id']}/rows", data={
        "csrf_token": csrf(otra, "/contacts"), "lista": "TRANSACCIONES",
        "action": "delete", "fila": "aaaaaa"})
    assert respuesta.status_code == 404
    assert len(filas_de(database, una, socio)) == 1


def test_sin_filas_sigue_completo(client, database, outbox):
    _, cuenta = cuenta_con_lista(client, database, howmany=2)
    definiciones = accounts.fields_of(cuenta)
    assert contacts.incomplete_count(database, cuenta["_id"], definiciones) == 0
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    assert columns.missing(socio, definiciones) == []
    auth, _ = llave(database, cuenta)
    uno = client.get(f"/api/v1/contacts/{socio['_id']}", headers=auth).get_json()
    assert uno["complete"] is True and uno["fields"]["TRANSACCIONES"] == []


# ------------------------------------------------------------ el id de tu sistema

def test_id_de_tu_sistema_en_el_panel(client, database, outbox):
    browser, cuenta, _ = ready(client, database, howmany=2, plan="negocio")
    uno = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    dos = contacts.by_email(database, cuenta["_id"], "socio1@ejemplo.com")
    ficha_uno = f"/contacts/edit/{uno['_id']}"
    ficha_dos = f"/contacts/edit/{dos['_id']}"
    browser.post(ficha_uno, data={"csrf_token": csrf(browser, ficha_uno),
                                  "email": "socio0@ejemplo.com", "name": "Socio 0",
                                  "external_id": "1043"})
    assert contacts.by_id(database, cuenta["_id"], uno["_id"])["external_id"] == "1043"

    # Ocupado: no se guarda nada de ese formulario.
    ocupado = browser.post(ficha_dos, data={"csrf_token": csrf(browser, ficha_dos),
                                            "email": "socio1@ejemplo.com",
                                            "name": "Nombre nuevo", "external_id": "1043"})
    assert ocupado.status_code == 200
    assert "Ese id ya lo tiene otro contacto" in ocupado.get_data(as_text=True)
    sigue = contacts.by_id(database, cuenta["_id"], dos["_id"])
    assert sigue["name"] == "Socio 1" and "external_id" not in sigue

    mal = browser.post(ficha_dos, data={"csrf_token": csrf(browser, ficha_dos),
                                        "email": "socio1@ejemplo.com", "name": "Socio 1",
                                        "external_id": "con espacio"})
    assert "Solo letras" in mal.get_data(as_text=True)

    # Vacío lo quita, y entonces lo puede tener otro.
    browser.post(ficha_uno, data={"csrf_token": csrf(browser, ficha_uno),
                                  "email": "socio0@ejemplo.com", "name": "Socio 0",
                                  "external_id": ""})
    assert "external_id" not in contacts.by_id(database, cuenta["_id"], uno["_id"])
    browser.post(ficha_dos, data={"csrf_token": csrf(browser, ficha_dos),
                                  "email": "socio1@ejemplo.com", "name": "Socio 1",
                                  "external_id": "1043"})
    assert contacts.by_id(database, cuenta["_id"], dos["_id"])["external_id"] == "1043"


def test_exportar_no_pierde_nada_e_importar_no_ofrece_las_listas(client, database, outbox):
    browser, cuenta = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    contacts.set_rows(database, cuenta["_id"], socio["_id"], "TRANSACCIONES",
                      [{"FECHA": "2026-10-01", "MONTO": "150", "id": "abc123"}])
    database.contacts.update_one({"_id": socio["_id"]}, {"$set": {"external_id": "1043"}})
    archivo = browser.post("/contacts/export", data={
        "csrf_token": csrf(browser, "/contacts/export")}).get_data(as_text=True)
    assert '[{""FECHA"": ""2026-10-01"", ""MONTO"": ""150""}]' in archivo
    assert "abc123" not in archivo
    assert "Id en tu sistema" in archivo and "1043" in archivo

    definiciones = columns.scalars(accounts.fields_of(cuenta))
    assert importer.matching(["Correo", "Transacciones"], definiciones) == {}


# ------------------------------------------------------------ en el correo

DEFS = [{"key": "CIUDAD", "label": "Ciudad", "type": "text"},
        {"key": "TRANSACCIONES", "label": "Transacciones", "type": "list", "items": [
            {"key": "FECHA", "label": "Fecha", "type": "date"},
            {"key": "DESCRIPCION", "label": "Descripción", "type": "text"},
            {"key": "MONTO", "label": "Monto", "type": "number"}]}]


def socio_con(filas, name="Ana"):
    return {"name": name, "email": "ana@ejemplo.com",
            "fields": {"CIUDAD": "Santiago", "TRANSACCIONES": filas}}


def test_la_marca_sola_arma_la_tabla_escapada():
    html = columns.fill("<p>*|TRANSACCIONES|*</p>", socio_con([
        {"FECHA": "2026-10-01", "DESCRIPCION": "<b>Depósito</b>", "MONTO": "150",
         "id": "aaaaaa"}]), DEFS)
    assert "<table" in html and "Descripción</th>" in html
    assert "1 de octubre de 2026" in html
    assert "&lt;b&gt;Depósito&lt;/b&gt;" in html and "<b>Depósito" not in html
    assert "text-align:right" in html
    assert "aaaaaa" not in html


def test_el_bloque_se_repite_y_el_vacio_sale_sin_filas():
    texto = ("*|#TRANSACCIONES|*[*|MONTO|* *|NOMBRE|*]*|/TRANSACCIONES|*"
             "*|^TRANSACCIONES|*Sin movimientos*|/TRANSACCIONES|*")
    filas = [{"MONTO": "150", "id": "a"}, {"MONTO": "85.5", "id": "b"}]
    assert columns.fill(texto, socio_con(filas), DEFS) == "[150 Ana][85.5 Ana]"
    assert columns.fill(texto, socio_con([]), DEFS) == "Sin movimientos"


def test_una_marca_escondida_en_un_dato_sale_tal_cual():
    filas = [{"DESCRIPCION": "*|CORREO|* y *|CIUDAD|*", "id": "a"}]
    salida = columns.fill(
        "*|#TRANSACCIONES|*<i>*|DESCRIPCION|*</i>*|/TRANSACCIONES|* *|TRANSACCIONES|* "
        "*|NOMBRE|*", socio_con(filas, name="*|CIUDAD|*"), DEFS)
    assert "ana@ejemplo.com" not in salida and "Santiago" not in salida
    assert salida.count("*|CORREO|* y *|CIUDAD|*") == 2
    assert salida.endswith(" *|CIUDAD|*")


def test_en_el_asunto_una_lista_no_escribe_nada():
    filas = [{"MONTO": "150", "id": "a"}]
    assert columns.fill("Hola *|NOMBRE|*: *|TRANSACCIONES|*", socio_con(filas), DEFS,
                        html=False) == "Hola Ana: "


def test_los_datos_de_la_api_mandan_y_traen_sus_listas():
    salida = columns.fill("*|CIUDAD|* *|PRODUCTOS|*", socio_con([]), DEFS, data={
        "CIUDAD": "David", "PRODUCTOS": [{"NOMBRE_PRODUCTO": "Café <tostado>",
                                         "CANTIDAD": "2"}]})
    assert salida.startswith("David ")
    assert "Nombre producto</th>" in salida and "Café &lt;tostado&gt;" in salida


def test_la_vista_previa_dibuja_dos_filas_de_ejemplo():
    salida = columns.preview_fill("<p>*|TRANSACCIONES|*</p>", DEFS)
    assert salida.count("<tr>") == 3 and "Monto" in salida


# ------------------------------------------------------------ por la API

def test_crear_y_cambiar_una_lista_por_la_api(client, database, outbox):
    _, cuenta, _ = ready(client, database, plan="negocio")
    auth, _ = llave(database, cuenta)
    creada = client.post("/api/v1/fields", headers=auth, json={
        "label": "Transacciones", "type": "list",
        "items": [{"label": "Fecha", "type": "date"}, {"label": "Monto", "type": "number"}]})
    assert creada.status_code == 201
    assert creada.get_json()["items"] == [
        {"key": "FECHA", "label": "Fecha", "type": "date"},
        {"key": "MONTO", "label": "Monto", "type": "number"}]

    for malo in ({"label": "Pedidos", "type": "list"},
                 {"label": "Pedidos", "type": "list", "items": []},
                 {"label": "Pedidos", "type": "list", "items": [{"label": "X", "type": "list"}]},
                 {"label": "Pedidos", "type": "list",
                  "items": [{"label": "X", "type": "text"}, {"label": "x", "type": "text"}]},
                 {"label": "Ciudad", "type": "text", "items": []}):
        respuesta = client.post("/api/v1/fields", headers=auth, json=malo)
        assert respuesta.status_code == 422, malo
        assert "items" in respuesta.get_json()["error"]["fields"]

    agregado = client.patch("/api/v1/fields/TRANSACCIONES", headers=auth,
                            json={"add": {"label": "Descripción", "type": "text"}})
    assert agregado.status_code == 200
    assert [one["key"] for one in agregado.get_json()["items"]] == [
        "FECHA", "MONTO", "DESCRIPCION"]
    for malo in ({}, {"add": {"label": "A", "type": "text"}, "remove": "FECHA"},
                 {"type": "text"}, {"remove": "NO_EXISTE"}):
        assert client.patch("/api/v1/fields/TRANSACCIONES", headers=auth,
                            json=malo).status_code == 422, malo
    quitado = client.patch("/api/v1/fields/TRANSACCIONES", headers=auth,
                           json={"remove": "MONTO"})
    assert [one["key"] for one in quitado.get_json()["items"]] == ["FECHA", "DESCRIPCION"]

    client.post("/api/v1/fields", headers=auth, json={
        "label": "Pedidos", "type": "list", "items": [{"label": "Producto", "type": "text"}]})
    tercera = client.post("/api/v1/fields", headers=auth, json={
        "label": "Pagos", "type": "list", "items": [{"label": "Monto", "type": "number"}]})
    assert tercera.status_code == 409 and tercera.get_json()["error"]["code"] == "limit_reached"
    listadas = client.get("/api/v1/fields", headers=auth).get_json()
    assert listadas["lists_max"] == 2
    assert {one["key"]: one["type"] for one in listadas["data"]} == {
        "TRANSACCIONES": "list", "PEDIDOS": "list"}


def test_las_filas_por_la_api(client, database, outbox):
    _, cuenta = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    auth, _ = llave(database, cuenta)
    base = f"/api/v1/contacts/{socio['_id']}/lists/TRANSACCIONES"

    vacia = client.get(base, headers=auth).get_json()
    assert vacia["rows"] == [] and [one["key"] for one in vacia["items"]] == [
        "FECHA", "DESCRIPCION", "MONTO"]

    puesta = client.put(base, headers=auth, json={"rows": [
        {"FECHA": "2026-10-01", "DESCRIPCION": "Depósito", "MONTO": 150},
        {"FECHA": "09/10/2026", "DESCRIPCION": "Pago", "MONTO": "85.50"}]})
    assert puesta.status_code == 200
    filas = puesta.get_json()["rows"]
    assert [one["MONTO"] for one in filas] == ["150", "85.5"]
    assert filas[1]["FECHA"] == "2026-10-09"
    assert filas_de(database, cuenta, socio) == filas

    agregadas = client.post(base, headers=auth, json={
        "rows": [{"DESCRIPCION": "Retiro", "MONTO": 20}], "keep_last": 2})
    assert agregadas.status_code == 201
    ahora = filas_de(database, cuenta, socio)
    assert [one["DESCRIPCION"] for one in ahora] == ["Pago", "Retiro"]
    assert agregadas.get_json()["rows"] == ahora

    pago = ahora[0]
    cambiada = client.patch(f"{base}/{pago['id']}", headers=auth,
                            json={"MONTO": 90, "DESCRIPCION": None})
    assert cambiada.status_code == 200
    assert cambiada.get_json() == {"FECHA": "2026-10-09", "MONTO": "90", "id": pago["id"]}
    assert filas_de(database, cuenta, socio)[0] == cambiada.get_json()
    assert client.patch(f"{base}/{pago['id']}", headers=auth,
                        json={"MONTO": "mucho"}).status_code == 422
    assert client.patch(f"{base}/{pago['id']}", headers=auth,
                        json={"id": "ffffff"}).status_code == 422
    assert client.patch(f"{base}/no-existe", headers=auth,
                        json={"MONTO": 1}).status_code == 404

    assert client.delete(f"{base}/{pago['id']}", headers=auth).status_code == 200
    assert client.delete(f"{base}/{pago['id']}", headers=auth).status_code == 404
    assert len(filas_de(database, cuenta, socio)) == 1

    # Lo que no es una lista, o no existe: 404.
    accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    assert client.get(f"/api/v1/contacts/{socio['_id']}/lists/CIUDAD",
                      headers=auth).status_code == 404
    assert client.get(f"/api/v1/contacts/{socio['_id']}/lists/NADA",
                      headers=auth).status_code == 404


def test_los_topes_de_una_lista(client, database, outbox):
    _, cuenta = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    auth, _ = llave(database, cuenta)
    base = f"/api/v1/contacts/{socio['_id']}/lists/TRANSACCIONES"

    muchas = [{"MONTO": n} for n in range(columns.LIST_ROWS_MAX + 1)]
    assert client.put(base, headers=auth, json={"rows": muchas}).status_code == 422
    largas = [{"DESCRIPCION": "x" * 120} for _ in range(30)]
    demasiado = client.put(base, headers=auth, json={"rows": largas})
    assert demasiado.status_code == 422
    assert "too_big" in demasiado.get_json()["error"]["fields"]["rows"]
    for mala in ([{"PAIS": "Panamá"}], [{}], ["texto"], [{"MONTO": {"$gt": 0}}], "no"):
        assert client.put(base, headers=auth, json={"rows": mala}).status_code == 422, mala

    # Agregar tampoco pasa del tamaño: se mira con lo que ya tenía.
    assert client.put(base, headers=auth, json={"rows": largas[:15]}).status_code == 200
    mas = client.post(base, headers=auth, json={"rows": largas[:10]})
    assert mas.status_code == 422
    assert len(filas_de(database, cuenta, socio)) == 15
    assert client.post(base, headers=auth, json={"rows": [{"MONTO": 1}],
                                                  "keep_last": 0}).status_code == 422


def test_las_listas_de_otra_cuenta_y_los_permisos(client, database, outbox):
    _, una = cuenta_con_lista(client, database, howmany=1)
    socio = contacts.by_email(database, una["_id"], "socio0@ejemplo.com")
    contacts.set_rows(database, una["_id"], socio["_id"], "TRANSACCIONES",
                      [{"MONTO": "1", "id": "aaaaaa"}])
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", plan="negocio")
    accounts.add_field(database, otra["_id"], label="Transacciones", kind="list",
                       items=ITEMS)
    ajena, _ = llave(database, otra)
    base = f"/api/v1/contacts/{socio['_id']}/lists/TRANSACCIONES"
    assert client.get(base, headers=ajena).status_code == 404
    assert client.put(base, headers=ajena, json={"rows": []}).status_code == 404
    assert client.delete(f"{base}/aaaaaa", headers=ajena).status_code == 404
    assert len(filas_de(database, una, socio)) == 1

    prueba, _ = llave(database, una, mode="test", scopes=("contacts:read",))
    assert client.get(base, headers=prueba).status_code == 200
    negado = client.post(base, headers=prueba, json={"rows": [{"MONTO": 2}]})
    assert negado.status_code == 403
    leer, _ = llave(database, una, scopes=("contacts:read",))
    assert client.delete(f"{base}/aaaaaa", headers=leer).status_code == 403
    assert len(filas_de(database, una, socio)) == 1


def test_cargar_con_listas_e_id_de_tu_sistema(client, database, outbox):
    _, cuenta = cuenta_con_lista(client, database, howmany=0)
    auth, _ = llave(database, cuenta)
    primera = cargar(client, auth, [
        {"email": "ana@ejemplo.com", "name": "Ana", "external_id": "1043",
         "fields": {"TRANSACCIONES": [{"FECHA": "2026-10-01", "MONTO": 150}]}},
        {"email": "luis@ejemplo.com", "external_id": "1044"},
    ]).get_json()
    assert [one["result"] for one in primera["results"]] == ["added", "added"]
    ana = contacts.by_email(database, cuenta["_id"], "ana@ejemplo.com")
    assert ana["external_id"] == "1043"
    assert [one["MONTO"] for one in ana["fields"]["TRANSACCIONES"]] == ["150"]

    # Por su id: cambia de correo, y la lista que llega reemplaza la que tenía.
    segunda = cargar(client, auth, [
        {"email": "ana.nueva@ejemplo.com", "external_id": "1043",
         "fields": {"TRANSACCIONES": [{"MONTO": 1}, {"MONTO": 2}]}},
    ]).get_json()
    assert segunda["results"][0]["result"] == "updated"
    misma = contacts.by_id(database, cuenta["_id"], ana["_id"])
    assert misma["email"] == "ana.nueva@ejemplo.com"
    assert [one["MONTO"] for one in misma["fields"]["TRANSACCIONES"]] == ["1", "2"]
    assert contacts.by_email(database, cuenta["_id"], "ana@ejemplo.com") is None

    # La dirección que dejó libre es de alguien nuevo, aunque vaya en la misma
    # carga que el cambio.
    tercera = cargar(client, auth, [
        {"email": "ana.otra@ejemplo.com", "external_id": "1043"},
        {"email": "ana.nueva@ejemplo.com"},
    ]).get_json()
    assert [one["result"] for one in tercera["results"]] == ["updated", "added"]

    conflictos = cargar(client, auth, [
        # Ese correo es de un contacto con otro id.
        {"email": "luis@ejemplo.com", "external_id": "9999"},
        # El contacto de ese id pasaría a un correo que ya es de otro.
        {"email": "ana.nueva@ejemplo.com", "external_id": "1044"},
        {"email": "x@ejemplo.com", "external_id": "con espacio"},
        {"email": "y@ejemplo.com", "external_id": "1050"},
        {"email": "z@ejemplo.com", "external_id": "1050"},
        {"email": "w@ejemplo.com", "fields": {"TRANSACCIONES": [{"PAIS": "Panamá"}]}},
    ]).get_json()
    motivos = [one.get("reason", one["result"]) for one in conflictos["results"]]
    assert motivos == ["external_id_conflict", "email_taken", "bad_external_id", "added",
                       "duplicate", "bad_list"]
    assert "TRANSACCIONES" in conflictos["results"][5]["detail"]
    assert contacts.by_email(database, cuenta["_id"], "luis@ejemplo.com")["external_id"] == "1044"

    encontrado = client.get("/api/v1/contacts?external_id=1043", headers=auth).get_json()
    assert [one["email"] for one in encontrado["data"]] == ["ana.otra@ejemplo.com"]
    assert encontrado["data"][0]["external_id"] == "1043"


def test_cambiar_un_contacto_con_su_id_y_sus_listas(client, database, outbox):
    _, cuenta = cuenta_con_lista(client, database, howmany=2)
    accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    uno = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    dos = contacts.by_email(database, cuenta["_id"], "socio1@ejemplo.com")
    for socio in (uno, dos):
        contacts.update(database, cuenta["_id"], socio["_id"], email=socio["email"],
                        name=socio["name"], tags=[], values={"CIUDAD": "Santiago"})
    contacts.set_rows(database, cuenta["_id"], uno["_id"], "TRANSACCIONES",
                      [{"MONTO": "1", "id": "aaaaaa"}])
    auth, _ = llave(database, cuenta)
    url = f"/api/v1/contacts/{uno['_id']}"

    puesto = client.patch(url, headers=auth, json={"external_id": "1043"})
    assert puesto.status_code == 200 and puesto.get_json()["external_id"] == "1043"
    # Cambiar otra cosa no le borra la lista.
    assert puesto.get_json()["fields"]["TRANSACCIONES"] == [{"MONTO": "1", "id": "aaaaaa"}]

    ocupado = client.patch(f"/api/v1/contacts/{dos['_id']}", headers=auth,
                           json={"external_id": "1043", "name": "Otro"})
    assert ocupado.status_code == 409
    assert ocupado.get_json()["error"]["code"] == "external_id_taken"
    assert contacts.by_id(database, cuenta["_id"], dos["_id"])["name"] == "Socio 1"

    for malo in ({"external_id": "con espacio"}, {"external_id": 1043},
                 {"external_id": "x" * 65},
                 {"fields": {"TRANSACCIONES": [{"PAIS": "Panamá"}]}},
                 {"fields": {"TRANSACCIONES": "no"}}):
        assert client.patch(url, headers=auth, json=malo).status_code == 422, malo

    reemplazada = client.patch(url, headers=auth, json={
        "fields": {"TRANSACCIONES": [{"MONTO": 5}], "CIUDAD": "David"}}).get_json()
    assert [one["MONTO"] for one in reemplazada["fields"]["TRANSACCIONES"]] == ["5"]
    assert reemplazada["fields"]["CIUDAD"] == "David"

    quitado = client.patch(url, headers=auth, json={"external_id": None}).get_json()
    assert quitado["external_id"] is None
    assert "external_id" not in contacts.by_id(database, cuenta["_id"], uno["_id"])
    assert quitado["fields"]["TRANSACCIONES"] == reemplazada["fields"]["TRANSACCIONES"]
