"""Los correos de la API: transaccional y promocional (octubre de 2026).

Lo que fijan estas pruebas: que un transaccional va a cualquiera, sin baja ni
marca y sin contar clics, y solo lo frenan un rebote permanente o una queja
(la excepción a la regla 1); que un promocional va solo a un contacto completo
y sin supresiones, con su baja; que una marca sin dato no sale; que los datos
se escapan y no rompen el asunto; que la cuota se aparta antes de mandar y se
devuelve si no salió; que la demostración solo va a sus direcciones de prueba;
que una llave de prueba no manda ni guarda nada; que repetir con la misma
`Idempotency-Key` no manda dos veces; y que lo guardado no trae los datos.
"""

from __future__ import annotations

from bson import ObjectId
from test_api_contactos import llave
from test_campaigns import catch, ready

from models import account as accounts
from models import api_key as api_keys
from models import contact as contacts
from models import design as designs
from models import event as events
from models import message as messages
from models import suppression as suppressions
from services import sender

SEND = ("emails:send",)


def enviar(client, auth, **body):
    datos = {"to": "cliente@ejemplo.com", "type": "transactional",
             "subject": "Tu pedido", "text": "Gracias por tu compra."}
    datos.update(body)
    datos = {key: value for key, value in datos.items() if value is not None}
    headers = dict(auth)
    if "idem" in datos:
        headers["Idempotency-Key"] = datos.pop("idem")
    return client.post("/api/v1/emails", headers=headers, json=datos)


def html_de(message) -> str:
    return message.get_body(("html",)).get_content()


def test_un_transaccional_va_a_cualquiera_sin_baja_ni_clics(client, database, outbox,
                                                           monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, llave_doc = llave(database, cuenta, scopes=SEND)
    antes = accounts.used_this_month(cuenta)
    pieza = designs.save(database, cuenta["_id"], name="Pedido", html=(
        "<html><body><p>Tu pedido *|PEDIDO|*</p>"
        "<a href='https://tienda.com/p/1'>Verlo</a></body></html>"))
    respuesta = enviar(client, auth, template_id=str(pieza), text=None,
                       subject="Tu pedido *|PEDIDO|*", data={"PEDIDO": "A-1"})
    assert respuesta.status_code == 201, respuesta.get_json()
    datos = respuesta.get_json()
    assert datos["status"] == "sent" and datos["type"] == "transactional"
    assert datos["subject"] == "Tu pedido *|PEDIDO|*" and datos["contact_id"] is None

    [salido] = salidos
    assert salido["To"] == "cliente@ejemplo.com"
    assert str(salido["Subject"]) == "Tu pedido A-1"
    assert "List-Unsubscribe" not in salido
    html = html_de(salido)
    assert "/unsubscribe/" not in html and "Enviado con" not in html
    assert "<a ses:no-track href='https://tienda.com/p/1'" in html
    assert f"campaign={datos['id']}" in salido["X-SES-MESSAGE-TAGS"]

    guardado = database.messages.find_one({})
    assert guardado["key_id"] == llave_doc["_id"]
    assert "data" not in guardado and "html" not in guardado
    assert accounts.used_this_month(accounts.by_id(database, cuenta["_id"])) == antes + 1
    assert database.events.count_documents({"run_id": guardado["_id"],
                                            "kind": events.SENT}) == 1


def test_la_baja_no_frena_un_transaccional_y_el_rebote_si(client, database, outbox,
                                                         monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    suppressions.add(database, cuenta["_id"], "baja@ejemplo.com",
                     reason=suppressions.UNSUBSCRIBE)
    suppressions.add(database, cuenta["_id"], "rebote@ejemplo.com",
                     reason=suppressions.HARD_BOUNCE)
    suppressions.add(database, cuenta["_id"], "queja@ejemplo.com",
                     reason=suppressions.COMPLAINT)
    assert enviar(client, auth, to="baja@ejemplo.com").status_code == 201
    for to in ("rebote@ejemplo.com", "Queja@Ejemplo.com"):
        negado = enviar(client, auth, to=to)
        assert negado.status_code == 422 and negado.get_json()["error"]["code"] == "suppressed"
    # El promocional a quien se dio de baja, no.
    contacts.create(database, cuenta["_id"], email="baja@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS))
    assert enviar(client, auth, to="baja@ejemplo.com",
                  type="promotional").get_json()["error"]["code"] == "suppressed"
    assert len(salidos) == 1


def test_un_promocional_va_solo_a_un_contacto_completo(client, database, outbox,
                                                       monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=1, plan="negocio")
    auth, _ = llave(database, cuenta, scopes=SEND)
    fuera = enviar(client, auth, to="nadie@ejemplo.com", type="promotional")
    assert fuera.status_code == 422 and fuera.get_json()["error"]["code"] == "not_a_contact"

    accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    falta = enviar(client, auth, to="socio0@ejemplo.com", type="promotional")
    assert falta.get_json()["error"]["code"] == "contact_incomplete"
    assert falta.get_json()["error"]["missing"] == ["Ciudad"]

    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    contacts.update(database, cuenta["_id"], socio["_id"], email=socio["email"],
                    name="Socio 0", tags=[], values={"CIUDAD": "Santiago"})
    bien = enviar(client, auth, to="socio0@ejemplo.com", type="promotional",
                  text="Hola *|NOMBRE|* de *|CIUDAD|*", subject="Para *|NOMBRE|*")
    assert bien.status_code == 201
    assert bien.get_json()["contact_id"] == str(socio["_id"])
    [salido] = salidos
    assert salido["List-Unsubscribe"] and "List-Unsubscribe-Post" in salido
    html = html_de(salido)
    # Sin marca de agua: la API es desde Negocio (octubre de 2026).
    assert "Hola Socio 0 de Santiago" in html and "Enviado con" not in html
    assert str(salido["Subject"]) == "Para Socio 0"
    # Los clics de un promocional sí se cuentan (la baja nunca). Se comprobaba
    # con el enlace de la marca de agua, que ya no lleva: va con uno propio.
    pieza = designs.save(database, cuenta["_id"], name="Oferta", html=(
        "<html><body><p>Hola</p>"
        "<a href='https://tienda.com/p/1'>Verla</a></body></html>"))
    assert enviar(client, auth, to="socio0@ejemplo.com", type="promotional",
                  template_id=str(pieza), text=None).status_code == 201
    assert "<a href='https://tienda.com/p/1'" in html_de(salidos[-1])


def test_una_marca_sin_dato_no_sale_y_los_datos_se_escapan(client, database, outbox,
                                                           monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, pieza = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    designs.update_filled(database, cuenta["_id"], pieza, name="Aviso", filled={
        "titulo": "Pedido *|PEDIDO|*", "texto": "Hola *|NOMBRE|*"})
    falta = enviar(client, auth, template_id=str(pieza), text=None,
                   subject="Tu pedido *|PEDIDO|*")
    assert falta.status_code == 422
    assert falta.get_json()["error"]["missing"] == ["PEDIDO", "NOMBRE"]

    bien = enviar(client, auth, template_id=str(pieza), text=None,
                  subject="Tu pedido *|PEDIDO|* & más",
                  data={"PEDIDO": "<b>A-1</b>", "NOMBRE": "Ana"})
    assert bien.status_code == 201, bien.get_json()
    [salido] = salidos
    assert str(salido["Subject"]) == "Tu pedido <b>A-1</b> & más"
    html = html_de(salido)
    assert "&lt;b&gt;A-1&lt;/b&gt;" in html and "<b>A-1</b>" not in html
    assert bien.get_json()["template_id"] == str(pieza)

    for malo in ({"data": {"PEDIDO": "a\r\nBcc: x@y.com"}}, {"subject": "a\nb"},
                 {"to": "no-es-correo"}, {"type": "otro"},
                 {"template_id": str(pieza)}, {"text": None},
                 {"template_id": "6533b1d2a1b2c3d4e5f60901", "text": None},
                 {"logo": True, "template_id": str(pieza), "text": None},
                 {"from_id": "6531f2aa0b1c2d3e4f506172"}, {"reply_to": "x@y.com"},
                 {"text": "x" * 20001}):
        respuesta = enviar(client, auth, **malo)
        assert respuesta.status_code == 422, (malo, respuesta.get_json())
    assert len(salidos) == 1


def test_sale_del_remitente_elegido(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    remitente = accounts.default_from(cuenta)
    assert enviar(client, auth, from_id=str(remitente["id"])).status_code == 201
    assert remitente["address"] in salidos[0]["From"]
    assert database.messages.find_one({})["from"] == remitente["address"]


def test_una_llave_de_prueba_simula(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    prueba, _ = llave(database, cuenta, mode="test", scopes=SEND)
    antes = accounts.used_this_month(cuenta)
    respuesta = enviar(client, prueba, subject="Hola *|NOMBRE|*", data={"NOMBRE": "Ana"})
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["status"] == "simulated"
    assert datos["preview"]["subject"] == "Hola Ana"
    assert "Gracias por tu compra." in datos["preview"]["html"]
    assert "Gracias por tu compra." in datos["preview"]["text"]
    assert salidos == [] and database.messages.count_documents({}) == 0
    assert accounts.used_this_month(accounts.by_id(database, cuenta["_id"])) == antes
    # Y dice lo mismo que diría de verdad.
    assert enviar(client, prueba, type="promotional").get_json()["error"][
        "code"] == "not_a_contact"


def test_la_cuota_se_aparta_y_se_devuelve(client, database, outbox, monkeypatch):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    # Una a la vez: con una de cuota, la segunda no entra.
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {
        f"sent_counts.{accounts.quota_month()}": 0}})
    assert accounts.reserve_quota(database, cuenta["_id"], 1, 1)
    assert not accounts.reserve_quota(database, cuenta["_id"], 1, 1)
    accounts.release_quota(database, cuenta["_id"], 1)
    # El día 1 el contador del mes no existe.
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$unset": {"sent_counts": ""}})
    assert accounts.reserve_quota(database, cuenta["_id"], 1, 1)

    allowed = sender.plans.emails_a_month("negocio")
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {
        f"sent_counts.{accounts.quota_month()}": allowed}})
    sin_cuota = enviar(client, auth)
    assert sin_cuota.status_code == 409
    assert sin_cuota.get_json()["error"]["blocked"][0]["code"] == "quota"

    # Si no se pudo entregar, no gasta.
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {
        f"sent_counts.{accounts.quota_month()}": 0}})

    def roto(message, **_):
        raise RuntimeError("SES caído")

    monkeypatch.setattr(sender, "deliver", roto)
    fallo = enviar(client, auth, idem="pedido-9")
    assert fallo.status_code == 502
    assert fallo.get_json()["error"]["email"]["status"] == "failed"
    assert accounts.used_this_month(accounts.by_id(database, cuenta["_id"])) == 0
    # Repetir con la misma clave lo vuelve a intentar.
    salidos = catch(monkeypatch)
    assert enviar(client, auth, idem="pedido-9").status_code == 201
    assert len(salidos) == 1 and database.messages.count_documents({}) == 1


def test_amazon_pide_esperar(client, database, outbox, monkeypatch):
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)

    class Throttling(Exception):
        response = {"Error": {"Code": "Throttling"}}

    def lleno(message, **_):
        raise Throttling("Maximum sending rate exceeded.")

    monkeypatch.setattr(sender, "deliver", lleno)
    respuesta = enviar(client, auth)
    assert respuesta.status_code == 503 and respuesta.headers["Retry-After"]
    assert respuesta.get_json()["error"]["code"] == "throttled"
    assert database.messages.count_documents({}) == 0
    assert accounts.used_this_month(accounts.by_id(database, cuenta["_id"])) == 0


def test_repetir_con_la_misma_clave_no_manda_dos_veces(client, database, outbox,
                                                       monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    primera = enviar(client, auth, idem="pedido-1")
    segunda = enviar(client, auth, idem="pedido-1")
    assert primera.status_code == 201 and segunda.status_code == 201
    assert segunda.headers["Idempotent-Replayed"] == "true"
    assert primera.get_json()["id"] == segunda.get_json()["id"] and len(salidos) == 1

    # Uno que se quedó a medias, ya vencida la respuesta guardada de la puerta:
    # se devuelve tal cual, sin mandarlo.
    database.messages.update_one({}, {"$set": {"status": messages.PENDING}})
    database.api_idempotency.delete_many({})
    tercera = enviar(client, auth, idem="pedido-1")
    assert tercera.status_code == 202 and tercera.get_json()["status"] == "pending"
    assert len(salidos) == 1


def test_la_demostracion_no_usa_la_api(client, database, outbox, monkeypatch):
    """La API es desde el plan Negocio (octubre de 2026): la demostración tiene
    lo del Básico, así que ni a sus direcciones de prueba sale nada por aquí."""
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0, plan=None)
    assert accounts.in_demo(cuenta)
    accounts.add_test_address(database, cuenta["_id"], "yo@ejemplo.com")
    accounts.confirm_test_address(database, cuenta["_id"], "yo@ejemplo.com")
    raw, _ = api_keys.create(database, cuenta["_id"], name="Tienda", mode="live",
                             scopes=list(SEND), ips=[], days=0)
    respuesta = enviar(client, {"Authorization": f"Bearer {raw}"}, to="yo@ejemplo.com")
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["code"] == "plan_without_api"
    assert salidos == []


def test_en_pausa_no_sale(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    accounts.pause(database, cuenta["_id"], reason="bounces", note="5 %")
    negado = enviar(client, auth)
    assert negado.status_code == 409
    assert [one["code"] for one in negado.get_json()["error"]["blocked"]] == ["paused"]
    assert salidos == []


def test_ver_los_correos_y_lo_que_paso(client, database, outbox, monkeypatch):
    catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=0)
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    uno = enviar(client, auth, to="a@ejemplo.com").get_json()
    enviar(client, auth, to="b@ejemplo.com")
    # Lo que llega del aviso de SES, atado al id del correo.
    events.record(database, cuenta["_id"], kind=events.DELIVERED,
                  campaign_id=ObjectId(uno["id"]), run_id=ObjectId(uno["id"]),
                  email="a@ejemplo.com")
    todos = client.get("/api/v1/emails", headers=auth).get_json()
    assert [one["to"] for one in todos["data"]] == ["b@ejemplo.com", "a@ejemplo.com"]
    filtro = client.get("/api/v1/emails?to=A@ejemplo.com", headers=auth).get_json()
    assert [one["id"] for one in filtro["data"]] == [uno["id"]]
    assert client.get("/api/v1/emails?status=nada", headers=auth).status_code == 422
    detalle = client.get(f"/api/v1/emails/{uno['id']}", headers=auth).get_json()
    assert set(detalle["events"]) == {"sent", "delivery"}

    ajena, _ = llave(database, otra, scopes=SEND)
    assert client.get(f"/api/v1/emails/{uno['id']}", headers=ajena).status_code == 404
    sin_permiso, _ = llave(database, cuenta, scopes=("contacts:read",))
    assert client.get("/api/v1/emails", headers=sin_permiso).status_code == 403
    assert enviar(client, sin_permiso).status_code == 403


def test_la_pantalla_de_correos_del_panel(client, database, outbox, monkeypatch):
    catch(monkeypatch)
    browser, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=SEND)
    assert "todavía no ha mandado" in browser.get("/developers/emails").get_data(as_text=True)
    enviar(client, auth, to="a@ejemplo.com", subject="Tu recibo *|NUMERO|*",
           data={"NUMERO": "R-QX9Z"})
    pantalla = browser.get("/developers/emails").get_data(as_text=True)
    assert "a@ejemplo.com" in pantalla and "Tu recibo *|NUMERO|*" in pantalla
    assert "Transaccional" in pantalla and "Enviado" in pantalla and "R-QX9Z" not in pantalla
