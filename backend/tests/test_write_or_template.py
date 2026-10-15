"""Escribir o Plantilla, en el individual y en el masivo (octubre de 2026).

Hasta entonces el individual solo se escribía y el masivo solo salía de una
plantilla. Lo que fijan estas pruebas:

  * un individual con plantilla sigue siendo individual: **sin baja ni marca
    de agua**, con la dirección postal y con el botón de su archivo;
  * si la plantilla nombra columnas o el nombre y a esa dirección le faltan,
    **no sale** y se dice cuáles: a quien le falta un dato no le llega nada;
  * un masivo escrito es una campaña: **con su baja y la marca del Básico**, y
    sin archivo;
  * el logo de la empresa va arriba de lo escrito cuando se pide, y queda
    anotado como enviado (cambiar el logo no rompe los correos que llegaron).
"""

from __future__ import annotations

import io
import json
import re

from test_campaigns import catch, csrf, ready, send_it
from test_logo import png, upload
from test_single import PDF, html_de

from models import account as accounts
from models import campaign as campaigns
from models import contact as contacts
from models import design as designs
from models import image as images
from services import canvas


def canvas_piece(database, account_id, text="Hola *|NOMBRE|*, tu ciudad es *|CIUDAD|*."):
    """Una plantilla de lienzo con un texto, como la guarda el editor."""
    piece = canvas.blank()
    piece["items"] = [{"t": "text", "x": 40, "y": 40, "w": 520, "h": 60, "text": text,
                       "font": "Arial", "size": 18, "color": "#18181B", "bold": False,
                       "italic": False, "align": "left", "line": 1.4}]
    doc = canvas.parse(json.dumps(piece))
    grounds, shades = canvas.store(database, account_id, doc, lambda name: None)
    return designs.save_canvas(database, account_id, name="Con datos", doc=doc,
                               backgrounds=grounds, shades=shades)


def redactar(browser, **data):
    form = {"csrf_token": csrf(browser, "/campaigns/write"), "para": "alguien@ejemplo.com",
            "asunto": "Hola"}
    form.update(data)
    return browser.post("/campaigns/write", data=form, content_type="multipart/form-data")


def test_las_dos_pantallas_ofrecen_escribir_o_plantilla(client, database, outbox):
    browser, _, piece = ready(client, database)
    for url in ("/campaigns/write", "/campaigns"):
        pantalla = browser.get(url).get_data(as_text=True)
        assert 'name="modo" value="escribir"' in pantalla, url
        assert 'name="modo" value="plantilla"' in pantalla, url
        assert f'<option value="{piece}"' in pantalla, url
        assert 'name="mensaje"' in pantalla, url
    # El archivo es solo del individual.
    assert 'name="archivo"' in browser.get("/campaigns/write").get_data(as_text=True)
    assert 'name="archivo"' not in browser.get("/campaigns").get_data(as_text=True)


def test_un_individual_con_plantilla_sale_como_individual(client, database, outbox,
                                                         monkeypatch):
    browser, cuenta, piece = ready(client, database)  # Básico
    salidos = catch(monkeypatch)
    respuesta = redactar(browser, modo="plantilla", pieza=str(piece),
                         archivo=(io.BytesIO(PDF), "estado.pdf"))
    assert respuesta.status_code == 302 and "/campaigns/sent/" in respuesta.headers["Location"]
    correo, = salidos
    assert correo["To"] == "alguien@ejemplo.com"
    assert correo["List-Unsubscribe"] is None
    html = html_de(correo)
    assert "Corte" in html and "El martes" in html
    assert "Anular la suscripción" not in html and "Enviado con" not in html
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) in html
    # El botón del archivo, justo encima del pie.
    assert "estado.pdf" in html and "/d/" in html
    guardado = campaigns.for_account(database, cuenta["_id"])[0]
    assert guardado["kind"] == campaigns.SINGLE and guardado["design_id"] == piece
    assert guardado["body"] == ""


def test_sin_los_datos_que_nombra_la_plantilla_no_sale(client, database, outbox,
                                                       monkeypatch):
    browser, cuenta, _ = ready(client, database)
    accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    piece = canvas_piece(database, cuenta["_id"])
    salidos = catch(monkeypatch)

    # Fuera de Contactos: le falta todo lo que se nombra, menos su correo.
    fuera = redactar(browser, modo="plantilla", pieza=str(piece)).get_data(as_text=True)
    assert "Esta plantilla usa Ciudad, Nombre" in fuera
    # En Contactos, pero sin la ciudad.
    dentro = redactar(browser, modo="plantilla", pieza=str(piece),
                      para="socio0@ejemplo.com").get_data(as_text=True)
    assert "Esta plantilla usa Ciudad" in dentro and "Nombre" not in dentro.split(
        "Esta plantilla usa")[1].split("</p>")[0]
    assert salidos == []

    database.contacts.update_one({"account_id": cuenta["_id"],
                                  "email_normalized": "socio0@ejemplo.com"},
                                 {"$set": {"fields.CIUDAD": "Santiago"}})
    respuesta = redactar(browser, modo="plantilla", pieza=str(piece), para="socio0@ejemplo.com")
    assert respuesta.status_code == 302, re.findall(
        r'class="error[^"]*">([^<]+)<', respuesta.get_data(as_text=True))
    correo, = salidos
    assert "Hola Socio 0, tu ciudad es Santiago." in html_de(correo)


def test_un_masivo_escrito_es_una_campana(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)  # Básico
    browser.post("/campaigns", data={
        "csrf_token": csrf(browser), "asunto": "Aviso escrito", "modo": "escribir",
        "mensaje": "Mañana no hay atención.", "cuando": "ahora"})
    guardada = campaigns.for_account(database, cuenta["_id"])[0]
    assert guardada["design_id"] is None and guardada["body"] == "Mañana no hay atención."
    assert "Texto escrito" in browser.get(
        f"/campaigns/{guardada['_id']}/send").get_data(as_text=True)

    salidos = catch(monkeypatch)
    send_it(browser, database, cuenta["_id"])
    assert len(salidos) == 3
    correo = salidos[0]
    assert correo["List-Unsubscribe"]
    html = html_de(correo)
    assert "Mañana no hay atención." in html
    assert "Anular la suscripción" in html and "Enviado con" in html

    # Editarla respeta lo que eligió.
    pantalla = browser.get(f"/campaigns/{guardada['_id']}").get_data(as_text=True)
    assert 'value="escribir" checked' in pantalla and "Mañana no hay atención." in pantalla


def test_un_masivo_escrito_sin_texto_no_se_guarda(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    pantalla = browser.post("/campaigns", data={
        "csrf_token": csrf(browser), "asunto": "Vacío", "modo": "escribir",
        "mensaje": "  ", "cuando": "ahora"}).get_data(as_text=True)
    assert campaigns.for_account(database, cuenta["_id"]) == []
    assert 'id="mensaje"' in pantalla


def test_el_logo_va_arriba_de_lo_escrito(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    upload(browser, png(120, 40))
    logo = accounts.logo_of(accounts.by_id(database, cuenta["_id"]))
    assert 'name="logo"' in browser.get("/campaigns/write").get_data(as_text=True)
    salidos = catch(monkeypatch)
    redactar(browser, mensaje="Con logo.", logo="1")
    html = html_de(salidos[0])
    # A su medida: 120×40 cabe entero en 180×64.
    assert f'/img/{logo}" width="120" height="40"' in html
    # Salió en un correo: cambiar el logo ya no lo borra, se retira.
    assert database.images.find_one({"name": logo}).get("sent_at")
    upload(browser, png(color=(0, 0, 0, 255)))
    assert database.images.find_one({"name": logo}).get("expires_at")

    redactar(browser, mensaje="Sin logo.")
    assert "/img/" not in html_de(salidos[1])
