"""La búsqueda de la barra (octubre de 2026).

Lo que fijan estas pruebas: que **sin sesión no hay nada** (404), que se
encuentren pantallas por su nombre y por cómo se piden («csv», «dos pasos»),
sin acentos ni mayúsculas, que **cada cuenta vea solo lo que puede abrir** (un
usuario sus permisos, un administrador lo suyo), que encuentre lo suyo por
nombre y nada de otra cuenta, y que sin JavaScript la página diga lo mismo.
"""

from __future__ import annotations

from datetime import timedelta

from test_admin import make_admin
from test_campaigns import WHEN, make, ready
from test_users import as_member

from models import account as accounts


def sugerencias(browser, q):
    respuesta = browser.get("/search/suggest", query_string={"q": q})
    assert respuesta.status_code == 200
    return respuesta.get_json()["items"]


def urls(items):
    return [one["url"] for one in items]


def test_sin_sesion_no_hay_nada(client, database, outbox):
    assert client.get("/search?q=contactos").status_code == 404
    assert client.get("/search/suggest?q=contactos").status_code == 404


def test_encuentra_pantallas_por_nombre_y_por_como_se_piden(client, database, outbox):
    browser, _, _ = ready(client, database)
    assert "/contacts/import" in urls(sugerencias(browser, "importar"))
    assert "/contacts/import" in urls(sugerencias(browser, "CSV"))
    assert "/settings/security/two-step" in urls(sugerencias(browser, "dos pasos"))
    # Sin acentos: «facturacion» encuentra lo de Facturación.
    assert "/settings/billing" in urls(sugerencias(browser, "facturacion"))
    # La barra lleva el campo, con sesión.
    assert 'data-search' in browser.get("/campaigns").get_data(as_text=True)
    assert 'data-search' not in client.get("/login").get_data(as_text=True)


def test_encuentra_lo_suyo_y_nada_de_otra_cuenta(client, database, outbox):
    browser, cuenta, pieza = ready(client, database, tag="Socios fundadores")
    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)
    make(browser, pieza, subject="Asamblea anual de octubre", when="fecha", fecha=pronto)

    encontradas = sugerencias(browser, "asamblea")
    assert any(one["kind"] == "campaign" and one["label"] == "Asamblea anual de octubre"
               for one in encontradas)
    assert any(one["kind"] == "tag" for one in sugerencias(browser, "socios fund"))

    otra, _, _ = ready(client, database, email="otra@ejemplo.com")
    assert not any(one["kind"] == "campaign" for one in sugerencias(otra, "asamblea"))


def test_un_usuario_ve_solo_sus_permisos(client, database, outbox):
    _, _, suyo = as_member(client, database, permisos=("contacts",), outbox=outbox)
    assert "/contacts/import" in urls(sugerencias(suyo, "importar"))
    assert "/campaigns" not in urls(sugerencias(suyo, "enviar"))
    assert "/settings/security/users" not in urls(sugerencias(suyo, "usuarios"))


def test_un_administrador_ve_lo_suyo(client, database, outbox):
    admin, _ = make_admin(client, database)
    assert "/admin/events" in urls(sugerencias(admin, "eventos"))
    assert "/contacts/import" not in urls(sugerencias(admin, "importar"))


def test_sin_javascript_la_pagina_dice_lo_mismo(client, database, outbox):
    browser, _, _ = ready(client, database)
    pagina = browser.get("/search?q=importar").get_data(as_text=True)
    assert 'href="/contacts/import"' in pagina
    assert "Nada coincide" in browser.get("/search?q=zzzz").get_data(as_text=True)
