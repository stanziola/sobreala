"""La página del archivo de un correo individual (octubre de 2026).

Antes enseñaba la barra de Sobreala y un botón que se quedaba girando, porque
una descarga no cambia de página. Ahora es una página propia, con el logo y el
nombre de quien lo manda, **que baja el archivo sola** y dice que ya se puede
cerrar. Lo que se fija aquí: que no traiga la barra ni el menú, que traiga el
guion con su `nonce` y el botón de respaldo sin giro, y que el POST siga
bajando el archivo y anotando la descarga.
"""

from __future__ import annotations

import io
import re

from test_campaigns import catch, ready
from test_logo import png, upload
from test_single import PDF, enlace_de_descarga, escribir

from models import account as accounts
from models import event as events


def test_la_pagina_baja_el_archivo_sola(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    upload(browser, png())
    logo = accounts.logo_of(accounts.by_id(database, cuenta["_id"]))
    salidos = catch(monkeypatch)
    escribir(browser, archivo=(io.BytesIO(PDF), "estado.pdf"))
    enlace = enlace_de_descarga(salidos[0])

    fuera = client.application.test_client()
    pagina = fuera.get(enlace)
    html = pagina.get_data(as_text=True)
    assert pagina.status_code == 200
    # Sin la barra ni el menú de Sobreala; con quien lo manda.
    assert 'class="bar"' not in html and "data-menu" not in html
    assert f'class="sender-head__logo" src="/img/{logo}"' in html
    assert cuenta["company_name"] in html
    assert "estado.pdf" in html
    # Baja sola: el guion manda el formulario, con su nonce.
    nonce = re.search(r'<script nonce="([^"]+)">\s*\(function \(\) \{\s*var form', html).group(1)
    assert nonce in pagina.headers["Content-Security-Policy"]
    assert "form.submit()" in html
    # Sin JavaScript, el botón; y no gira (la página no cambia al bajar).
    assert 'id="bajar" data-no-busy' in html
    assert 'data-started="Tu descarga empezó"' in html
    assert "Ya puedes cerrar esta pestaña." in html

    with fuera.session_transaction() as sess:
        token = sess["_csrf"]
    bajada = fuera.post(enlace, data={"csrf_token": token})
    assert bajada.status_code == 200 and bajada.get_data() == PDF
    assert database.events.count_documents(
        {"account_id": cuenta["_id"], "kind": events.DOWNLOAD}) == 1


def test_el_enlace_vencido_dice_que_ya_no_esta(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    salidos = catch(monkeypatch)
    escribir(browser, archivo=(io.BytesIO(PDF), "estado.pdf"))
    enlace = enlace_de_descarga(salidos[0])
    database.downloads.delete_many({})
    pagina = client.application.test_client().get(enlace)
    assert pagina.status_code == 410
    assert 'class="bar"' not in pagina.get_data(as_text=True)
