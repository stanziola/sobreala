"""Guardar no mueve la pantalla (octubre de 2026).

Al guardar, el panel vuelve a la misma página con un ancla (`#address`,
`#logo`, `#sessions`…) y el navegador bajaba hasta ella. Ahora `panel.js` anota
la altura antes de mandar un formulario, o de pulsar «Editar» y «Cancelar», y
un guion de la cabecera vuelve ahí. Que la altura se mantenga se revisa en
Chrome; lo que se fija aquí es lo que tiene que traer la página: el guion con
su `nonce`, la marca en esos enlaces, y que el ancla siga en la redirección
para quien no tiene JavaScript.
"""

from __future__ import annotations

import re
from pathlib import Path

from test_admin import make_client_account
from test_verificaciones import CLIENTA, csrf

PANEL_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "panel.js"


def test_la_cabecera_vuelve_a_la_altura_anotada(client, database, outbox):
    browser, _ = make_client_account(client, database, CLIENTA)
    pagina = browser.get("/settings/account")
    html = pagina.get_data(as_text=True)
    cabecera = html.split("</head>", 1)[0]
    nonce = re.search(r'<script nonce="([^"]+)">', cabecera).group(1)
    assert f"'nonce-{nonce}'" in pagina.headers["Content-Security-Policy"]
    guion = cabecera.split(f'<script nonce="{nonce}">', 1)[1].split("</script>", 1)[0]
    assert 'sessionStorage.getItem("sa_scroll")' in guion
    assert "history.replaceState" in guion and "window.scrollTo(0, kept.y)" in guion
    # Lo anota panel.js, en todos los formularios que mandan algo.
    js = PANEL_JS.read_text(encoding="utf-8")
    assert 'setItem("sa_scroll"' in js and "a[data-keep-scroll]" in js


def test_editar_y_cancelar_se_quedan_en_su_sitio(client, database, outbox):
    browser, _ = make_client_account(client, database, CLIENTA)
    cuenta = browser.get("/settings/account").get_data(as_text=True)
    for parte in ("address", "phones"):
        assert re.search(r'data-keep-scroll\s+href="/settings/account\?editar=' + parte
                         + f'#{parte}"', cuenta), parte
        abierta = browser.get(f"/settings/account?editar={parte}").get_data(as_text=True)
        assert f'data-keep-scroll href="/settings/account#{parte}"' in abierta, parte
    facturacion = browser.get("/settings/billing").get_data(as_text=True)
    assert 'data-open-dialog="agregar-metodo" data-keep-scroll' in facturacion
    eligiendo = browser.get("/settings/billing?agregar=1").get_data(as_text=True)
    assert re.search(r'data-keep-scroll\s+href="/settings/billing#methods"', eligiendo)


def test_sin_javascript_el_ancla_sigue(client, database, outbox):
    browser, _ = make_client_account(client, database, CLIENTA)
    respuesta = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "address": "Apartado 0816-00001, Santiago"})
    assert respuesta.headers["Location"].endswith("#address")
