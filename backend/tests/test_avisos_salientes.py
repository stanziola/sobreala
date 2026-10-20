"""Los avisos a su sistema, webhooks (octubre de 2026).

Lo que fijan estas pruebas: que la dirección no sirve para entrar a la red
interna (ni por una IP, ni por un nombre que resuelve a una privada, ni por una
IPv6 que lleva una IPv4 dentro); que un servidor que no contesta no traba más
de cinco segundos; que la firma es la que dice la documentación, y el código de
la documentación la comprueba; que cada evento se avisa una vez aunque SNS lo
repita; que un fallo corre los pendientes de su destino y a las 72 horas se
apaga con aviso al dueño; y que crearlo en el panel pide la contraseña, enseña
el secreto una vez y avisa por correo.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from datetime import timedelta

from test_campaigns import catch, csrf, ready
from test_developers import CLAVE

import api_spec
from models import contact as contacts
from models import event as events
from models import mail_log
from models import webhook as hooks
from services import safe_http, ses_events, webhooks

URL = "https://hooks.tienda.com/sobreala"


def destino(database, cuenta, *, kinds=hooks.EVENTS, url=URL):
    new_id = hooks.create(database, cuenta["_id"], url=url, host="hooks.tienda.com",
                          events=list(kinds), description="Tienda")
    return hooks.by_id(database, cuenta["_id"], new_id)


class Servidor:
    """Lo que respondería su servidor, sin red."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.got = []

    def __call__(self, url, body, headers, **_):
        self.got.append((url, body, headers))
        ok = self.answers.pop(0) if self.answers else True
        return safe_http.Answer(ok, 200 if ok else 500, "" if ok else "http_500", 12)


# ------------------------------------------------------------ la red interna

def test_solo_direcciones_publicas():
    for ip in ("10.0.0.1", "127.0.0.1", "169.254.169.254", "::1", "fd00::1", "0.0.0.0",
               "::ffff:127.0.0.1", "64:ff9b::a00:1", "2002:a00:1::", "ff0e::1",
               "100.64.0.1", "192.168.1.1", "224.0.0.1"):
        assert not safe_http.public(ip), ip
    for ip in ("8.8.8.8", "2606:4700::1111"):
        assert safe_http.public(ip), ip
    for url in ("http://a.com/", "https://10.0.0.1/", "https://[::1]/",
                "https://a.com:8443/", "https://u:p@a.com/", "https://localhost/",
                "https://a.internal/", "https://a.com/x\r\nHost: b", "https://a.com/ñ",
                "https://a.com/#x", "https://a.com/" + "x" * 500):
        try:
            safe_http.check_url(url)
        except safe_http.Refused:
            continue
        raise AssertionError(url)


def test_un_nombre_que_mezcla_una_privada_no_pasa(monkeypatch):
    def falso(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", falso)
    try:
        safe_http.resolve("hooks.tienda.com")
    except safe_http.Refused as exc:
        assert str(exc) == "private"
    else:
        raise AssertionError("pasó")
    respuesta = safe_http.post(URL, b"{}", {})
    assert not respuesta.ok and respuesta.error == "refused:private"


def test_un_servidor_que_no_contesta_no_traba(monkeypatch):
    """Acepta la conexión y no dice nada: a los segundos dados, se corta."""
    escucha = socket.socket()
    escucha.bind(("127.0.0.1", 0))
    escucha.listen(1)
    puerto = escucha.getsockname()[1]
    vivas = []
    threading.Thread(target=lambda: vivas.append(escucha.accept()), daemon=True).start()
    real = socket.create_connection
    monkeypatch.setattr(socket, "create_connection",
                        lambda address, timeout=None: real(("127.0.0.1", puerto), timeout))
    antes = time.monotonic()
    respuesta = safe_http.post(URL, b"{}", {}, resolver=lambda host: "8.8.8.8", timeout=1.0)
    assert not respuesta.ok and time.monotonic() - antes < 3
    assert respuesta.error.startswith(("timeout", "connection"))
    escucha.close()


# ------------------------------------------------------------ la firma

def test_la_firma_es_la_de_la_documentacion(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    uno = destino(database, cuenta)
    servidor = Servidor()
    webhooks.attempt(uno, webhooks.test_payload(), poster=servidor)
    _, cuerpo, cabeceras = servidor.got[0]
    secreto = webhooks.secret_of(uno)
    assert secreto.startswith("whsec_")
    assert cabeceras["Sobreala-Event-Type"] == "test"
    # El código de Python de la documentación, tal cual.
    python = api_spec._VERIFY.split("// Node")[0]
    lugar: dict = {}
    exec(python, lugar)  # noqa: S102 - es el ejemplo publicado
    assert lugar["es_de_sobreala"](cuerpo, cabeceras["Sobreala-Signature"], secreto)
    assert not lugar["es_de_sobreala"](cuerpo + b" ", cabeceras["Sobreala-Signature"], secreto)
    # Otro aviso, otro secreto; cambiarlo invalida el de antes.
    assert webhooks.secret_of(destino(database, cuenta)) != secreto
    hooks.rotate(database, cuenta["_id"], uno["_id"])
    assert webhooks.secret_of(hooks.by_id(database, cuenta["_id"], uno["_id"])) != secreto


# ------------------------------------------------------------ anotar

def test_cada_evento_se_avisa_una_vez(client, database, outbox, monkeypatch):
    catch(monkeypatch)
    _, cuenta, _ = ready(client, database, howmany=1)
    destino(database, cuenta, kinds=[hooks.EMAIL_OPENED, hooks.EMAIL_BOUNCED])
    apagado = destino(database, cuenta, kinds=[hooks.EMAIL_OPENED])
    hooks.update(database, cuenta["_id"], apagado["_id"], enabled=False)
    run = events.record(database, cuenta["_id"], kind=events.SENT)  # cualquier id
    aviso = {"eventType": "Open", "mail": {
        "destination": ["socio0@ejemplo.com"], "timestamp": "2026-10-17T10:00:00.000Z",
        "tags": {"account": [str(cuenta["_id"])], "campaign": [str(run)],
                 "run": [str(run)]}}, "open": {"timestamp": "2026-10-17T10:00:00.000Z"}}
    for _ in range(3):
        ses_events.handle(database, aviso)
    filas = list(database.webhook_deliveries.find({}))
    assert len(filas) == 1 and filas[0]["kind"] == hooks.EMAIL_OPENED
    datos = filas[0]["payload"]["data"]
    assert datos["email"] == "socio0@ejemplo.com" and datos["source"] == "campaign"
    # Un evento que no quiere, no.
    rebote = {**aviso, "eventType": "Delivery", "delivery": {
        "recipients": ["socio0@ejemplo.com"], "timestamp": "2026-10-17T10:00:00.000Z"}}
    ses_events.handle(database, rebote)
    assert database.webhook_deliveries.count_documents({}) == 1


def test_la_baja_y_el_final_de_una_campana(client, database, outbox, monkeypatch):
    catch(monkeypatch)
    browser, cuenta, pieza = ready(client, database, howmany=1)
    destino(database, cuenta, kinds=[hooks.CONTACT_UNSUBSCRIBED, hooks.CAMPAIGN_FINISHED])
    from services import unsubscribe
    socio = contacts.by_email(database, cuenta["_id"], "socio0@ejemplo.com")
    enlace = unsubscribe.link(socio["_id"]).split("/unsubscribe/")[1]
    otro = client.application.test_client()
    pagina = otro.get(f"/unsubscribe/{enlace}")
    assert pagina.status_code == 200
    otro.post(f"/unsubscribe/{enlace}")
    otro.post(f"/unsubscribe/{enlace}")
    baja = list(database.webhook_deliveries.find({"kind": hooks.CONTACT_UNSUBSCRIBED}))
    assert len(baja) == 1 and baja[0]["payload"]["data"]["email"] == "socio0@ejemplo.com"

    from test_campaigns import make, send_it
    contacts.create(database, cuenta["_id"], email="otro@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS))
    make(browser, pieza, subject="Boletín")
    send_it(browser, database, cuenta["_id"])
    [final] = list(database.webhook_deliveries.find({"kind": hooks.CAMPAIGN_FINISHED}))
    assert final["payload"]["data"]["subject"] == "Boletín"
    assert final["payload"]["data"]["sent"] == 1 and final["payload"]["data"]["skipped"] == 1


# ------------------------------------------------------------ entregar

def test_entregar_reintentar_y_apagar(client, database, outbox):
    _, cuenta, _ = ready(client, database, howmany=0)
    uno = destino(database, cuenta)
    for n in range(3):
        hooks.queue(database, uno, event_key=f"k{n}", kind=hooks.EMAIL_OPENED,
                    payload={"id": f"evt_{n}", "type": hooks.EMAIL_OPENED, "data": {}})
    # El primero falla: los demás de ese destino esperan con él.
    servidor = Servidor(False)
    assert webhooks.deliver_tick(database, poster=servidor) == 1
    fresco = hooks.by_id(database, cuenta["_id"], uno["_id"])
    assert fresco["failing_since"] and fresco["next_try_at"] and fresco["last_status"] == 500
    assert database.webhook_deliveries.count_documents({"status": "pending"}) == 3
    assert len(servidor.got) == 1

    # Pasado el reintento, salen todos.
    database.webhook_endpoints.update_one({"_id": uno["_id"]}, {"$set": {"next_try_at": None}})
    database.webhook_deliveries.update_many({}, {"$set": {"next_at": hooks.now()}})
    servidor = Servidor(True, True, True)
    assert webhooks.deliver_tick(database, poster=servidor) == 3
    assert database.webhook_deliveries.count_documents({"status": "delivered"}) == 3
    assert hooks.by_id(database, cuenta["_id"], uno["_id"])["failing_since"] is None
    assert json.loads(servidor.got[0][1])["id"].startswith("evt_")

    # 72 horas fallando: se apaga y se le avisa al dueño.
    hooks.queue(database, uno, event_key="k9", kind=hooks.EMAIL_OPENED,
                payload={"id": "evt_9", "type": hooks.EMAIL_OPENED, "data": {}})
    database.webhook_endpoints.update_one({"_id": uno["_id"]}, {"$set": {
        "failing_since": hooks.now() - timedelta(hours=73)}})
    # Como en el proceso de fondo: dentro de un contexto, que el aviso arma enlaces.
    with client.application.test_request_context():
        webhooks.deliver_tick(database, poster=Servidor(False))
    apagado = hooks.by_id(database, cuenta["_id"], uno["_id"])
    assert apagado["enabled"] is False and apagado["disabled_reason"] == "failing"
    assert database.mail_log.count_documents({"purpose": mail_log.WEBHOOK}) == 1
    assert database.webhook_deliveries.find_one({"event_key": "k9"})["status"] == "failed"


# ------------------------------------------------------------ el panel

def test_crear_un_aviso_en_el_panel(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database, howmany=0)
    nuevo = "/developers/webhooks/new"
    base = {"url": URL, "description": "Tienda", "event": list(hooks.EVENTS)}
    mala = browser.post(nuevo, data={**base, "csrf_token": csrf(browser, nuevo),
                                     "password": "mala"})
    assert "no es correcta" in mala.get_data(as_text=True)
    for url in ("http://hooks.tienda.com/", "https://10.0.0.1/", "https://a.com:8080/"):
        respuesta = browser.post(nuevo, data={**base, "url": url, "password": CLAVE,
                                              "csrf_token": csrf(browser, nuevo)})
        assert respuesta.status_code == 200, url
    assert database.webhook_endpoints.count_documents({}) == 0

    hecha = browser.post(nuevo, data={**base, "password": CLAVE,
                                      "csrf_token": csrf(browser, nuevo)})
    assert hecha.headers["Cache-Control"] == "no-store"
    secreto = re.search(r'value="(whsec_[A-Za-z0-9_-]+)"', hecha.get_data(as_text=True)).group(1)
    guardado = database.webhook_endpoints.find_one({})
    assert secreto == webhooks.secret_of(guardado) and secreto not in str(guardado)
    assert database.mail_log.count_documents({"purpose": mail_log.WEBHOOK}) == 1
    assert secreto not in browser.get(f"/developers/webhooks/{guardado['_id']}").get_data(
        as_text=True)

    # Probar, apagar y borrar.
    monkeypatch.setattr(webhooks, "attempt", lambda *a, **k: safe_http.Answer(True, 204, "", 40))
    pagina = f"/developers/webhooks/{guardado['_id']}"
    probado = browser.post(f"{pagina}/test", data={"csrf_token": csrf(browser, pagina)})
    assert "prueba=ok" in probado.headers["Location"]
    browser.post(f"{pagina}/switch", data={"csrf_token": csrf(browser, pagina)})
    assert database.webhook_endpoints.find_one({})["enabled"] is False
    browser.post(f"{pagina}/delete", data={"csrf_token": csrf(browser, pagina)})
    assert database.webhook_endpoints.count_documents({}) == 0

    # El de otra cuenta no se abre.
    _, otra, _ = ready(client, database, email="otra@ejemplo.com", howmany=0)
    ajeno = destino(database, otra)
    assert browser.get(f"/developers/webhooks/{ajeno['_id']}").status_code == 302
    browser.post(f"/developers/webhooks/{ajeno['_id']}/delete",
                 data={"csrf_token": csrf(browser, "/developers/webhooks")})
    assert database.webhook_endpoints.count_documents({}) == 1
