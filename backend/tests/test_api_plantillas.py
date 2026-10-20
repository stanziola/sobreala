"""Plantillas, carpetas y fotos por la API (octubre de 2026).

Lo que fijan estas pruebas: que un lienzo se guarda por la API solo si pasa lo
mismo que Guardar en el panel; que las fotos y las carpetas de otra cuenta no
se cuelan; que «Sale de» y «Responder a» son solo de la cuenta; que el ZIP se
baja y se vuelve a cargar; que la vista armada lleva o no la baja según la
clase, escapa los datos y dice qué falta; que caben 300 y lo pesado va de uno
en uno; y que una llave de prueba lee y revisa pero no escribe.
"""

from __future__ import annotations

import io
import json
import zipfile

from test_api_contactos import llave
from test_campaigns import ready
from test_canvas import boton, con_texto, imagen, lienzo, texto
from test_designs import foto

from blueprints.api.account import TEMPLATE_LIMIT
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import image as images
from models import lock as locks
from services import pieces

TODO = ("templates:read", "templates:write")


def bueno(*items, **extra):
    """Un lienzo que se puede guardar: lo que se pida, y un párrafo debajo."""
    return con_texto(lienzo(*(items or (texto(40, 40, text="Hola *|NOMBRE|*"),)), **extra))


def crear(client, auth, doc=None, **extra):
    return client.post("/api/v1/templates", headers=auth,
                       json={"name": "Estado de cuenta", "canvas": doc or bueno(), **extra})


def otro_minuto(database):
    """Como si hubiera pasado el minuto: el límite de cinco plantillas por
    minuto tiene su propia prueba, y las demás crean más."""
    database.rate_limits.delete_many({"key": {"$regex": "^api:templates:"}})


def subir(client, auth, raw, *, nombre="foto.jpg", **form):
    return client.post("/api/v1/images", headers=auth, content_type="multipart/form-data",
                       data={"file": (io.BytesIO(raw), nombre), **form})


def test_cada_ruta_pide_su_permiso_y_la_de_prueba_no_escribe(client, database, outbox):
    _, cuenta, pieza = ready(client, database)
    leer, _ = llave(database, cuenta, scopes=("templates:read",))
    assert client.get("/api/v1/templates", headers=leer).status_code == 200
    negado = crear(client, leer)
    assert negado.status_code == 403 and negado.get_json()["error"]["code"] == "missing_scope"

    prueba, _ = llave(database, cuenta, mode="test", scopes=("templates:read",))
    assert client.get(f"/api/v1/templates/{pieza}", headers=prueba).status_code == 200
    assert client.post(f"/api/v1/templates/{pieza}/render", headers=prueba,
                       json={}).status_code == 200
    assert client.post("/api/v1/templates/check", headers=prueba,
                       json={"canvas": bueno()}).status_code == 200
    database.api_keys.update_many({"mode": "test"}, {"$set": {"scopes": list(TODO)}})
    negado = crear(client, prueba)
    assert negado.status_code == 403
    assert negado.get_json()["error"]["code"] == "test_key_cannot"
    assert designs.count(database, cuenta["_id"]) == 1


def test_crear_pasa_lo_mismo_que_guardar(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = crear(client, auth)
    assert hecha.status_code == 201
    datos = hecha.get_json()
    assert datos["source"] == "canvas" and datos["name"] == "Estado de cuenta"
    assert datos["marks"] == ["NOMBRE"] and datos["blocks"] == []
    assert datos["canvas"]["items"][0]["text"] == "Hola *|NOMBRE|*"
    guardada = designs.by_id(database, cuenta["_id"], designs.for_account(
        database, cuenta["_id"])[0]["_id"])
    assert guardada["canvas"]["v"] == 2 and len(guardada["backgrounds"]) >= 1

    # Lo que no pasa la revisión no se guarda, y se dice por qué.
    poco = crear(client, auth, lienzo(texto(40, 40, text="Hola")))
    assert poco.status_code == 422
    assert "poco texto" in poco.get_json()["error"]["fields"]["canvas"]
    encimado = crear(client, auth, bueno(texto(40, 40), boton(60, 50)))
    assert encimado.status_code == 422
    for roto in ("no", {"items": "no"}, {"h": 400}, [1, 2]):
        otro_minuto(database)
        assert crear(client, auth, None, canvas=roto).status_code == 422, roto
    otro_minuto(database)
    sin_nombre = client.post("/api/v1/templates", headers=auth,
                             json={"name": "   ", "canvas": bueno()})
    assert sin_nombre.status_code == 422 and "name" in sin_nombre.get_json()["error"]["fields"]
    # NaN e Infinity no son JSON.
    infinito = client.post("/api/v1/templates", headers=auth, content_type="application/json",
                           data='{"name": "X", "canvas": {"h": Infinity, "items": []}}')
    assert infinito.status_code == 400
    # La de antes de `ready()` y la que se creó.
    assert designs.count(database, cuenta["_id"]) == 2


def test_las_fotos_y_las_carpetas_de_otra_cuenta_no_se_cuelan(client, database, outbox):
    _, una, _ = ready(client, database, howmany=0)
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    ajena = images.save(database, otra["_id"], data=foto(400, 300), ext="jpg",
                        mime="image/jpeg")
    carpeta_ajena, _ = designs.add_folder(database, otra, "Cobros", "blue")
    auth, _ = llave(database, una, scopes=TODO)
    con_foto = crear(client, auth, bueno(imagen(40, 40, 200, 100, name=ajena)))
    assert con_foto.status_code == 422
    en_carpeta = crear(client, auth, folder_id=str(carpeta_ajena))
    assert en_carpeta.status_code == 422
    assert en_carpeta.get_json()["error"]["fields"]["folder_id"]
    assert designs.count(database, una["_id"]) == 1

    # La propia sí: se sube y se usa.
    subida = subir(client, auth, foto(400, 300))
    assert subida.status_code == 201
    nombre = subida.get_json()["name"]
    assert subida.get_json()["url"].endswith(nombre)
    assert crear(client, auth, bueno(imagen(40, 40, 200, 100, name=nombre))).status_code == 201


def test_sale_de_y_responder_a_solo_de_la_cuenta(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    remitente = accounts.default_from(cuenta)
    for malo in ({"send_from": "6531f2aa0b1c2d3e4f506172"}, {"send_from": 12},
                 {"reply_to": "otro@ejemplo.com"}):
        respuesta = crear(client, auth, **malo)
        assert respuesta.status_code == 422, malo
    hecha = crear(client, auth, send_from=str(remitente["id"])).get_json()
    assert hecha["send_from"] == str(remitente["id"]) and hecha["reply_to"] is None
    vuelta = client.patch(f"/api/v1/templates/{hecha['id']}", headers=auth,
                          json={"send_from": None}).get_json()
    assert vuelta["send_from"] is None


def test_leer_listar_y_por_carpeta(client, database, outbox):
    _, cuenta, pieza = ready(client, database, howmany=0)
    _, otra, ajena = ready(client, database, email="otra@ejemplo.com", howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    carpeta = client.post("/api/v1/folders", headers=auth,
                          json={"name": "Cobros", "color": "blue"}).get_json()
    for n in range(3):
        crear(client, auth, name=f"Lienzo {n}", folder_id=carpeta["id"])
    todas = client.get("/api/v1/templates?limit=2", headers=auth).get_json()
    assert len(todas["data"]) == 2 and todas["next_cursor"] and todas["limit"] == TEMPLATE_LIMIT
    resto = client.get(f"/api/v1/templates?limit=2&cursor={todas['next_cursor']}",
                       headers=auth).get_json()
    assert len(resto["data"]) == 2 and resto["next_cursor"] is None
    sueltas = client.get("/api/v1/templates?folder_id=none", headers=auth).get_json()
    assert [one["id"] for one in sueltas["data"]] == [str(pieza)]
    dentro = client.get(f"/api/v1/templates?folder_id={carpeta['id']}", headers=auth).get_json()
    assert len(dentro["data"]) == 3
    assert all(one["folder_id"] == carpeta["id"] for one in dentro["data"])
    assert client.get("/api/v1/templates?source=nada", headers=auth).status_code == 422
    lienzos = client.get("/api/v1/templates?source=canvas", headers=auth).get_json()
    assert len(lienzos["data"]) == 3

    # La prediseñada de antes trae su plantilla y sus campos; la de otra cuenta
    # no existe.
    vieja = client.get(f"/api/v1/templates/{pieza}", headers=auth).get_json()
    assert vieja["source"] == "builtin" and vieja["template"] == "aviso"
    assert vieja["fields"]["titulo"] == "Corte"
    assert client.get(f"/api/v1/templates/{ajena}", headers=auth).status_code == 404
    assert client.get("/api/v1/templates/nada", headers=auth).status_code == 404


def test_la_vista_armada(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=1, plan="basico")
    accounts.add_field(database, cuenta["_id"], label="Saldo", kind="text")
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    contacts.update(database, cuenta["_id"], socio["_id"], email=socio["email"],
                    name="Ana <Pérez>", tags=[], values={"SALDO": "100"})
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = crear(client, auth, bueno(texto(40, 40, w=520, h=80,
                                            text="Hola *|NOMBRE|*, saldo *|SALDO|* *|PEDIDO|*"))
                  ).get_json()
    url = f"/api/v1/templates/{hecha['id']}/render"

    promo = client.post(url, headers=auth, json={"contact_id": str(socio["_id"])}).get_json()
    assert promo["type"] == "promotional"
    assert "/unsubscribe/ejemplo" in promo["html"]
    assert "Enviado con" in promo["html"]
    assert "Ana &lt;Pérez&gt;" in promo["html"] and "Ana <Pérez>" not in promo["html"]
    assert promo["missing"] == ["PEDIDO"]
    assert promo["marks"] == ["NOMBRE", "SALDO", "PEDIDO"]

    trans = client.post(url, headers=auth, json={
        "type": "transactional", "contact_id": str(socio["_id"]),
        "subject": "Tu saldo, *|NOMBRE|*", "data": {"SALDO": "250", "PEDIDO": "<b>A-1</b>"},
    }).get_json()
    assert "/unsubscribe/" not in trans["html"] and "Enviado con" not in trans["html"]
    assert trans["subject"] == "Tu saldo, Ana <Pérez>"
    assert "250" in trans["html"] and "&lt;b&gt;A-1&lt;/b&gt;" in trans["html"]
    assert trans["missing"] == [] and "Hola Ana" in trans["text"]

    # Sin contacto, los datos solos.
    solo = client.post(url, headers=auth, json={"data": {"NOMBRE": "Luis"}}).get_json()
    assert solo["missing"] == ["SALDO", "PEDIDO"]

    for malo in ({"type": "otro"}, {"contact_id": "6531f5c2a1b2c3d4e5f60801"},
                 {"data": {"SALDO": "una\nlínea"}}, {"data": {"SALDO": "x y"}},
                 {"data": {"CORREO": "x@y.com"}}, {"data": {"saldo": "1"}},
                 {"data": {"SALDO": True}}, {"data": {"L": [{"A": "1"}] * 51}},
                 {"data": {"L": [{"a": "1"}]}}, {"data": "no"},
                 {"subject": "Hola\r\nBcc: x@y.com"}, {"subject": "x" * 151}):
        assert client.post(url, headers=auth, json=malo).status_code == 422, malo


def test_revisar_un_lienzo_sin_guardarlo(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=("templates:read",))
    poco = client.post("/api/v1/templates/check", headers=auth,
                       json={"canvas": lienzo(texto(40, 40, text="Hola"))}).get_json()
    assert poco["ok"] is False and any("poco texto" in one for one in poco["issues"])
    assert poco["rules"][0] == {"group": "build", "ok": False, "text": "Tiene nombre."}
    bien = client.post("/api/v1/templates/check", headers=auth,
                       json={"canvas": bueno(), "name": "Asamblea"}).get_json()
    assert bien["ok"] is True and bien["issues"] == [] and bien["rules"][0]["ok"] is True
    roto = client.post("/api/v1/templates/check", headers=auth,
                       json={"canvas": {"h": 1}}).get_json()
    assert roto["ok"] is False and roto["rules"] == []
    assert designs.count(database, cuenta["_id"]) == 1


def test_bajar_el_zip_y_volverlo_a_cargar(client, database, outbox):
    _, cuenta, pieza = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    nombre = subir(client, auth, foto(400, 300)).get_json()["name"]
    hecha = crear(client, auth, bueno(imagen(40, 40, 200, 100, name=nombre))).get_json()

    bajado = client.get(f"/api/v1/templates/{hecha['id']}/zip", headers=auth)
    assert bajado.status_code == 200 and bajado.mimetype == "application/zip"
    assert 'filename="Estado de cuenta.zip"' in bajado.headers["Content-Disposition"]
    with zipfile.ZipFile(io.BytesIO(bajado.data)) as pack:
        tablero = json.loads(pack.read("lienzo.json"))
        assert tablero["name"] == "Estado de cuenta"
        assert any(name.startswith("fotos/") for name in pack.namelist())
    assert client.get(f"/api/v1/templates/{pieza}/zip", headers=auth).status_code == 404

    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    ajena, _ = llave(database, otra, scopes=TODO)
    cargada = client.post("/api/v1/templates/import", headers=ajena,
                          content_type="multipart/form-data",
                          data={"file": (io.BytesIO(bajado.data), "x.zip"), "name": "Copia"})
    assert cargada.status_code == 201
    datos = cargada.get_json()
    assert datos["name"] == "Copia" and datos["source"] == "canvas"
    # Sus fotos entran a la cuenta que carga, con otro nombre.
    [foto_nueva] = datos["images"]
    assert foto_nueva != nombre and images.owns(database, otra["_id"], foto_nueva)

    no_zip = client.post("/api/v1/templates/import", headers=ajena,
                         content_type="multipart/form-data",
                         data={"file": (io.BytesIO(b"hola"), "x.zip")})
    assert no_zip.status_code == 422
    sin_archivo = client.post("/api/v1/templates/import", headers=ajena,
                              content_type="multipart/form-data", data={"name": "X"})
    assert sin_archivo.status_code == 422
    de_mas = client.post("/api/v1/templates/import", headers=ajena,
                         content_type="multipart/form-data",
                         data={"file": (io.BytesIO(bajado.data), "x.zip"), "otro": "1"})
    assert de_mas.status_code == 422
    en_json = client.post("/api/v1/templates/import", headers=ajena, json={"file": "x"})
    assert en_json.status_code == 415


def test_cambiar_duplicar_mover_y_borrar(client, database, outbox):
    _, cuenta, pieza = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    nombre = subir(client, auth, foto(400, 300)).get_json()["name"]
    hecha = crear(client, auth, bueno(imagen(40, 40, 200, 100, name=nombre))).get_json()
    url = f"/api/v1/templates/{hecha['id']}"
    carpeta = client.post("/api/v1/folders", headers=auth, json={"name": "Cobros"}).get_json()

    cambiada = client.patch(url, headers=auth, json={
        "name": "Estado de noviembre", "folder_id": carpeta["id"]}).get_json()
    assert cambiada["name"] == "Estado de noviembre" and cambiada["folder_id"] == carpeta["id"]
    assert client.patch(url, headers=auth, json={"folder_id": None}).get_json()[
        "folder_id"] is None
    assert client.patch(url, headers=auth, json={"name": ""}).status_code == 422
    assert client.patch(f"/api/v1/templates/{pieza}", headers=auth,
                        json={"canvas": bueno()}).status_code == 422

    # El lienzo nuevo pasa la revisión; uno malo no cambia nada.
    malo = client.patch(url, headers=auth, json={"canvas": lienzo(texto(40, 40))})
    assert malo.status_code == 422
    assert designs.by_id(database, cuenta["_id"], designs.for_account(
        database, cuenta["_id"])[0]["_id"])["canvas"]["items"][0]["t"] == "image"
    nuevo = client.patch(url, headers=auth, json={"canvas": bueno(
        texto(40, 40, text="Otra cosa"))})
    assert nuevo.status_code == 200
    assert nuevo.get_json()["canvas"]["items"][0]["text"] == "Otra cosa"
    # La foto que el lienzo dejó de nombrar se borra.
    assert not images.owns(database, cuenta["_id"], nombre)

    copia = client.post(f"{url}/duplicate", headers=auth, json={}).get_json()
    assert copia["name"] == "Copia de Estado de noviembre" and copia["id"] != hecha["id"]
    movidas = client.post("/api/v1/templates/move", headers=auth, json={
        "ids": [copia["id"], str(pieza), "6533b1d2a1b2c3d4e5f60901"],
        "folder_id": carpeta["id"]}).get_json()
    assert movidas["moved"] == 2
    assert client.post("/api/v1/templates/move", headers=auth,
                       json={"ids": ["x"], "folder_id": None}).status_code == 422
    assert client.post("/api/v1/templates/move", headers=auth,
                       json={"ids": [copia["id"]]}).status_code == 422

    assert client.delete(f"/api/v1/templates/{copia['id']}", headers=auth).status_code == 200
    assert client.delete(f"/api/v1/templates/{copia['id']}", headers=auth).status_code == 404
    assert designs.count(database, cuenta["_id"]) == 2


def test_caben_300_y_lo_pesado_va_de_uno_en_uno(client, database, outbox):
    _, cuenta, pieza = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    database.designs.insert_many([{"account_id": cuenta["_id"], "source": "upload",
                                   "name": f"x{n}", "html": "<p>x</p>"}
                                  for n in range(TEMPLATE_LIMIT - 1)])
    lleno = client.post(f"/api/v1/templates/{pieza}/duplicate", headers=auth, json={})
    assert lleno.status_code == 409
    assert lleno.get_json()["error"]["code"] == "limit_reached"
    assert crear(client, auth).status_code == 409

    database.designs.delete_many({"account_id": cuenta["_id"], "source": "upload"})
    token = locks.acquire(database, f"templates:{cuenta['_id']}", 90)
    ocupado = crear(client, auth)
    assert ocupado.status_code == 409 and ocupado.get_json()["error"]["code"] == "busy"
    locks.release(database, f"templates:{cuenta['_id']}", token)
    # Las dos de arriba ya contaron para el límite de cinco por minuto.
    for _ in range(3):
        assert crear(client, auth).status_code == 201
    pasado = crear(client, auth)
    assert pasado.status_code == 429 and pasado.headers["Retry-After"]


def test_las_carpetas(client, database, outbox):
    _, cuenta, pieza = ready(client, database, howmany=0)
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    hecha = client.post("/api/v1/folders", headers=auth, json={"name": "Cobros"})
    assert hecha.status_code == 201
    carpeta = hecha.get_json()
    assert carpeta["color"] == "gray" and carpeta["templates"] == 0
    repetida = client.post("/api/v1/folders", headers=auth, json={"name": "cobros"})
    assert repetida.status_code == 422
    assert client.post("/api/v1/folders", headers=auth,
                       json={"name": "X", "color": "fucsia"}).status_code == 422

    client.post("/api/v1/templates/move", headers=auth,
                json={"ids": [str(pieza)], "folder_id": carpeta["id"]})
    listadas = client.get("/api/v1/folders", headers=auth).get_json()
    assert listadas["data"] == [{**carpeta, "templates": 1}]
    assert "teal" in listadas["colors"] and listadas["limit"] == designs.FOLDER_LIMIT

    cambiada = client.patch(f"/api/v1/folders/{carpeta['id']}", headers=auth,
                            json={"name": "Cobros", "color": "green"}).get_json()
    assert cambiada["color"] == "green" and cambiada["templates"] == 1
    ajena, _ = designs.add_folder(database, otra, "Suya", "blue")
    assert client.patch(f"/api/v1/folders/{ajena}", headers=auth,
                        json={"name": "Mía"}).status_code == 404
    assert client.delete(f"/api/v1/folders/{ajena}", headers=auth).status_code == 404

    # Borrarla no borra sus plantillas.
    assert client.delete(f"/api/v1/folders/{carpeta['id']}", headers=auth).status_code == 200
    assert designs.by_id(database, cuenta["_id"], pieza) is not None
    assert "folder_id" not in designs.by_id(database, cuenta["_id"], pieza)

    for n in range(designs.FOLDER_LIMIT):
        designs.add_folder(database, accounts.by_id(database, cuenta["_id"]), f"C{n}", "gray")
    llena = client.post("/api/v1/folders", headers=auth, json={"name": "Una más"})
    assert llena.status_code == 409 and llena.get_json()["error"]["code"] == "limit_reached"


def test_las_fotos(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=TODO)
    assert subir(client, auth, b"no soy una foto").status_code == 422
    assert subir(client, auth, foto(400, 300), otro="1").status_code == 422
    assert client.post("/api/v1/images", headers=auth, json={}).status_code == 415
    for _ in range(pieces.photo_limit(cuenta)):
        images.save(database, cuenta["_id"], data=foto(40, 30), ext="jpg", mime="image/jpeg")
    lleno = subir(client, auth, foto(400, 300))
    assert lleno.status_code == 409 and lleno.get_json()["error"]["code"] == "limit_reached"
