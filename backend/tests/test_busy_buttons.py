"""Los botones que trabajan (octubre de 2026).

La animación la hace `panel.js` y se revisa en Chrome; lo que se fija aquí es
lo que le toca al servidor: que **una descarga devuelva la ficha** del botón que
la pidió en la galleta `sa_dl` (y nada si la ficha es rara o si la respuesta no
es un archivo), y que las páginas lleven los íconos y las marcas que el script
necesita.
"""

from __future__ import annotations

from test_campaigns import ready
from test_contacts import csrf


def galleta(respuesta):
    return [one for one in respuesta.headers.getlist("Set-Cookie") if one.startswith("sa_dl=")]


def test_una_descarga_devuelve_la_ficha(client, database, outbox):
    browser, _, _ = ready(client, database)
    bajada = browser.get("/dashboard/export.csv?dl=abc123def456")
    assert bajada.status_code == 200
    assert "attachment" in bajada.headers["Content-Disposition"]
    assert galleta(bajada) and galleta(bajada)[0].startswith("sa_dl=abc123def456;")

    # La exportación de contactos es un formulario: la ficha va en él.
    exportada = browser.post("/contacts/export", data={
        "csrf_token": csrf(browser, "/contacts/export"), "dl": "ficha0000ficha"})
    assert galleta(exportada)


def test_sin_ficha_buena_o_sin_archivo_no_hay_galleta(client, database, outbox):
    browser, _, _ = ready(client, database)
    assert not galleta(browser.get("/dashboard/export.csv"))
    assert not galleta(browser.get("/dashboard/export.csv?dl=<script>"))
    assert not galleta(browser.get("/dashboard/export.csv?dl=corta"))
    # Una página que no es un archivo no la devuelve aunque traiga ficha.
    assert not galleta(browser.get("/campaigns?dl=abc123def456"))


def test_las_paginas_llevan_los_iconos_y_las_marcas(client, database, outbox):
    browser, _, _ = ready(client, database)
    pantalla = browser.get("/dashboard").get_data(as_text=True)
    assert '<template id="icono-cargando">' in pantalla
    assert '<template id="icono-listo">' in pantalla
    assert pantalla.count("data-download") >= 2
    assert "data-download" in browser.get("/contacts/export").get_data(as_text=True)
