"""La búsqueda de la barra (octubre de 2026).

Lo que fijan estas pruebas: que **sin sesión no hay nada** (404), que se
encuentren pantallas por su nombre y por cómo se piden («csv», «bajas»), sin
acentos ni mayúsculas, que **cada cuenta vea solo lo que puede abrir** (un
usuario sus permisos, un administrador lo suyo), que encuentre lo suyo por
nombre y nada de otra cuenta, que sin JavaScript la página diga lo mismo, que
**Configuración no salga**, y que el campo vaya en la barra de arriba, al lado
del ala, solo en el Dashboard y en Administración.
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
    assert "/contacts/suppressions" in urls(sugerencias(browser, "bajas"))
    # Sin acentos: «estadisticas» encuentra Estadísticas.
    assert "/dashboard" in urls(sugerencias(browser, "estadisticas"))
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
    assert "/campaigns/write" not in urls(sugerencias(suyo, "redactar"))


def test_un_administrador_ve_lo_suyo(client, database, outbox):
    admin, _ = make_admin(client, database)
    assert "/admin/events" in urls(sugerencias(admin, "eventos"))
    assert "/contacts/import" not in urls(sugerencias(admin, "importar"))


def test_sin_javascript_la_pagina_dice_lo_mismo(client, database, outbox):
    browser, _, _ = ready(client, database)
    pagina = browser.get("/search?q=importar").get_data(as_text=True)
    assert 'href="/contacts/import"' in pagina
    assert "Nada coincide" in browser.get("/search?q=zzzz").get_data(as_text=True)


def test_configuracion_no_sale(client, database, outbox):
    """Solo lo del Dashboard (octubre de 2026): a Configuración se llega por el
    menú de la cuenta, y sus secciones ya no salen ni con «en Facturación»."""
    browser, _, _ = ready(client, database)
    admin, _ = make_admin(client, database)
    for quien in (browser, admin):
        for q in ("configuracion", "facturacion", "dos pasos", "contrasena", "usuarios",
                  "sesiones", "notificaciones", "metodos de pago", "direccion postal"):
            encontradas = sugerencias(quien, q)
            assert not any(one["url"].startswith("/settings") for one in encontradas), q
            assert not any(one["hint"].startswith("en ") for one in encontradas), q
    assert "Nada coincide" in browser.get("/search?q=facturacion").get_data(as_text=True)


def barra(html):
    return html.split("<header", 1)[1].split("</header>", 1)[0]


def test_va_en_la_barra_al_lado_del_ala(client, database, outbox):
    browser, _, _ = ready(client, database)
    for url in ("/dashboard", "/contacts", "/campaigns/sent", "/search?q=importar"):
        html = browser.get(url).get_data(as_text=True)
        arriba = barra(html)
        assert arriba.startswith(' class="bar bar--search">'), url
        # Solo el ala: el nombre, para el lector de pantalla.
        assert '<span class="bar__name visually-hidden">Sobreala</span>' in arriba, url
        # Al lado del ala, antes del menú.
        assert (arriba.index('class="bar__brand"') < arriba.index("data-search")
                < arriba.index('class="bar__actions"')), url
        # Y ya no en la barra lateral.
        assert html.count("data-search") == 1, url
    # Fuera del Dashboard, la barra de siempre, con el nombre y sin el campo.
    ajustes = barra(browser.get("/settings/account").get_data(as_text=True))
    assert ajustes.startswith(' class="bar">') and "data-search" not in ajustes
    assert '<span class="bar__name">Sobreala</span>' in ajustes

    admin, _ = make_admin(client, database)
    for url in ("/admin/accounts", "/admin/clients", "/search?q=cuentas"):
        html = admin.get(url).get_data(as_text=True)
        assert "data-search" in barra(html) and html.count("data-search") == 1, url
