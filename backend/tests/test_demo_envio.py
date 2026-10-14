"""La demostración que envía (octubre de 2026).

Una cuenta abierta por la demostración, sin plan, puede enviar como en el
«sandbox» de Amazon: **solo a sus direcciones de prueba**, que se confirman
cada una desde su propio buzón, y **hasta 50 correos en total**. Lo que fijan
estas pruebas: que sin una confirmada no sale nada, que el enlace vale una vez,
que una campaña sale **solo** a las confirmadas, que se para en los 50, que el
correo individual tampoco puede ir a otra, y que con un plan pagado nada de esto
aplica.
"""

from __future__ import annotations

import re
from datetime import timedelta

from test_campaigns import WHEN, catch, csrf, make, ready, send_it

from models import account as accounts
from models import contact as contacts
from models import mail_log
from services import sender


def agregar(browser, email):
    return browser.post("/settings/test/add", data={
        "csrf_token": csrf(browser, "/settings/test"), "email": email})


def enlace(database, email):
    fila = database.mail_log.find_one({"purpose": mail_log.TEST_ADDRESS, "to": email},
                                      sort=[("created_at", -1)])
    return re.search(r'(/test-address/[^"\s<]+)', fila["html"]).group(1)


def confirmar(client, database, email):
    return client.application.test_client().get(enlace(database, email))


def fresca(database, cuenta):
    return accounts.by_id(database, cuenta["_id"])


def test_sin_direcciones_confirmadas_no_envia(client, database, outbox):
    browser, cuenta, _ = ready(client, database, plan=None)
    assert accounts.in_demo(fresca(database, cuenta))
    assert sender.blocked(fresca(database, cuenta)) == ["demo_addresses"]
    assert "Direcciones de prueba" in browser.get("/settings/test").get_data(as_text=True)


def test_el_enlace_confirma_una_vez_y_la_agrega_a_contactos(client, database, outbox):
    browser, cuenta, _ = ready(client, database, plan=None)
    agregar(browser, "prueba@gmail.com")
    assert "prueba@gmail.com" not in accounts.confirmed_test_addresses(fresca(database, cuenta))

    primera = confirmar(client, database, "prueba@gmail.com")
    assert primera.status_code == 200 and "prueba@gmail.com" in primera.get_data(as_text=True)
    assert accounts.confirmed_test_addresses(fresca(database, cuenta)) == {"prueba@gmail.com"}
    assert contacts.by_email(database, cuenta["_id"], "prueba@gmail.com") is not None
    assert sender.blocked(fresca(database, cuenta)) == []

    assert confirmar(client, database, "prueba@gmail.com").status_code == 404


def test_una_campana_sale_solo_a_las_confirmadas(client, database, outbox, monkeypatch):
    browser, cuenta, pieza = ready(client, database, plan=None, howmany=4)
    agregar(browser, "socio1@ejemplo.com")
    confirmar(client, database, "socio1@ejemplo.com")
    agregar(browser, "socio2@ejemplo.com")  # sin confirmar
    salidos = catch(monkeypatch)

    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)
    make(browser, pieza, when="fecha", fecha=pronto)
    send_it(browser, database, cuenta["_id"])

    assert [c["To"] for c in salidos] == ["socio1@ejemplo.com"]
    # Con la marca de agua y la baja, como cualquier campaña sin plan.
    html = salidos[0].get_body(preferencelist=("html",)).get_content()
    assert "Enviado con" in html and salidos[0]["List-Unsubscribe"]
    assert accounts.demo_left(fresca(database, cuenta)) == accounts.DEMO_SENDS - 1
    aviso = browser.get("/campaigns").get_data(as_text=True)
    assert "Estás en la demostración" in aviso


def test_se_para_en_los_cincuenta(client, database, outbox, monkeypatch):
    browser, cuenta, pieza = ready(client, database, plan=None, howmany=3)
    for quien in ("socio0@ejemplo.com", "socio1@ejemplo.com"):
        agregar(browser, quien)
        confirmar(client, database, quien)
    database.accounts.update_one({"_id": cuenta["_id"]},
                                 {"$set": {"demo_sent": accounts.DEMO_SENDS - 1}})
    salidos = catch(monkeypatch)

    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)
    make(browser, pieza, when="fecha", fecha=pronto)
    send_it(browser, database, cuenta["_id"])

    assert len(salidos) == 1
    assert sender.blocked(fresca(database, cuenta)) == ["demo_used"]


def test_el_individual_solo_a_una_de_prueba(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database, plan=None)
    agregar(browser, "prueba@gmail.com")
    confirmar(client, database, "prueba@gmail.com")
    salidos = catch(monkeypatch)

    def escribir(para):
        return browser.post("/campaigns/write", data={
            "csrf_token": csrf(browser), "para": para, "asunto": "Hola",
            "mensaje": "Hola"}, content_type="multipart/form-data")

    assert "direcciones de prueba" in escribir("otra@gmail.com").get_data(as_text=True)
    assert salidos == []
    escribir("prueba@gmail.com")
    assert [c["To"] for c in salidos] == ["prueba@gmail.com"]


def test_con_plan_no_aplica(client, database, outbox, monkeypatch):
    browser, cuenta, pieza = ready(client, database)  # Básico
    assert not accounts.in_demo(fresca(database, cuenta))
    assert "test" not in browser.get("/settings/test").headers.get("Location", "test")
    salidos = catch(monkeypatch)
    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)
    make(browser, pieza, when="fecha", fecha=pronto)
    send_it(browser, database, cuenta["_id"])
    assert len(salidos) == 3
