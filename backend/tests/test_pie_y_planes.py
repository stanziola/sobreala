"""Tres planes, el pie según el plan y la dirección de cada cliente.

Lo que se fija aquí: que Corporativo ya no existe en ningún lado, que el sitio no
ofrece soporte por plan ni diseño como servicio, que el pie del Básico lleva el
ala de Panamails y el de los demás no, y que la dirección postal del pie es la
de cada cliente y sin ella no se envía.
"""

from __future__ import annotations

from pathlib import Path

from models import account as accounts
from services import plans, render, sender
from test_campaigns import catch, make, ready, send_it
from test_designs import csrf, inside

ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------ los planes

def test_quedan_tres_planes_y_todos_se_compran():
    assert list(plans.PLANS) == ["basico", "negocio", "empresa"]
    assert not plans.buyable("corporativo")
    assert all(plans.buyable(one) for one in plans.PLANS)
    assert "corporativo" not in accounts.PLAN_CONTACTS


def test_el_sitio_no_ofrece_corporativo_ni_soporte_ni_diseno():
    precios = (ROOT / "docs" / "pricing.md").read_text(encoding="utf-8")
    assert "Corporativo" not in precios
    assert "| Soporte |" not in precios
    assert "Diseño personalizado de tu correo" not in precios

    for pagina in ("planes", "como-funciona", "nosotros", "terminos"):
        html = (ROOT / "landing" / pagina / "index.html").read_text(encoding="utf-8")
        assert "Corporativo" not in html, pagina
        assert "Plantillas personalizadas" not in html, pagina
        assert "diseñamos la pieza" not in html.lower(), pagina
        assert "diseño de las piezas de correo" not in html.lower(), pagina
    planes = (ROOT / "landing" / "planes" / "index.html").read_text(encoding="utf-8")
    assert ">Soporte<" not in planes


# ------------------------------------------------------------ el pie

def test_el_basico_lleva_el_ala_y_los_demas_nada():
    basico = render.email_from_body("<p>Hola</p>", plan="basico")
    assert "/static/img/email-logo.png" in basico
    assert "Enviado con" in basico
    negocio = render.email_from_body("<p>Hola</p>", plan="negocio")
    assert "email-logo.png" not in negocio and "Enviado con" not in negocio


def test_el_ala_existe_y_es_chica():
    ala = ROOT / "backend" / "static" / "img" / "email-logo.png"
    assert ala.exists() and ala.stat().st_size < 10_000


# ------------------------------------------------------------ la dirección

def test_la_direccion_se_guarda_y_sale_en_el_correo(client, database, outbox,
                                                     monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, postal="", howmany=1)
    assert "postal" in sender.blocked(account)
    assert "Falta la dirección postal" in browser.get("/envios").get_data(as_text=True)

    respuesta = browser.post("/configuracion/cuenta", data={
        "csrf_token": csrf(browser, "/configuracion/cuenta"),
        "direccion": "  Apartado 0816-00001,   Santiago, Veraguas "})
    assert respuesta.status_code == 302
    cuenta = accounts.by_id(database, account["_id"])
    assert accounts.postal_of(cuenta) == "Apartado 0816-00001, Santiago, Veraguas"
    assert "postal" not in sender.blocked(cuenta)
    assert "Apartado 0816-00001" in browser.get("/configuracion/cuenta").get_data(as_text=True)

    make(browser, piece)
    send_it(browser, database, account["_id"])
    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "Apartado 0816-00001, Santiago, Veraguas" in cuerpo


def test_una_direccion_vacia_o_larga_no_se_guarda(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    for mala in ("", "corta", "x" * 201):
        pantalla = browser.post("/configuracion/cuenta", data={
            "csrf_token": csrf(browser, "/configuracion/cuenta"),
            "direccion": mala}).get_data(as_text=True)
        assert "entre 10 y 200 caracteres" in pantalla
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) == ""


def test_sin_testigo_no_se_guarda(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    browser.post("/configuracion/cuenta", data={"direccion": "Calle 50, Panamá"})
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) == ""
