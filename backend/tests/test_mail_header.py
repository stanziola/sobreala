"""La cabecera de los correos del sistema (octubre de 2026).

Una franja azul de lado a lado con el ala y «Sobreala» en la tipografía de la
marca, que va dentro de una imagen. Lo que se fija aquí es lo que la vez
anterior salió mal: la medida a la que se dibuja tiene que ser **la mitad exacta
de la imagen**, o sale achatada; y la franja tiene que estar en todos.
"""

from __future__ import annotations

from pathlib import Path

from flask import render_template
from PIL import Image

import build_assets
from services import mailer

BACKEND = Path(__file__).resolve().parent.parent
TEMPLATES = ("confirm", "exists", "new-login", "notice", "password-changed",
             "recover", "two-factor", "welcome")


def test_la_cabecera_no_se_achata():
    with Image.open(BACKEND / "static" / "img" / "mail" / build_assets.MAIL_HEADER) as image:
        assert image.size == build_assets.MAIL_HEADER_SIZE
        assert image.mode == "RGBA"
    width, height = mailer.HEADER_SIZE
    assert (width * 2, height * 2) == build_assets.MAIL_HEADER_SIZE


def test_la_franja_azul_esta_en_los_ocho(app):
    width, height = mailer.HEADER_SIZE
    fields = {"code": "123456", "minutes": 15, "link": "#", "device": "Chrome",
              "ip": "1.1.1.1", "recover": "#", "panel": "#", "on": True,
              "name": "Ana", "heading": "Hola", "paragraphs": ["Uno"],
              "button": None, "note": None, "foot": ""}
    with app.test_request_context("/"):
        for name in TEMPLATES:
            html = render_template(f"email/{name}.html", **fields)
            assert 'bgcolor="#3166A7"' in html, name
            assert "/static/img/mail/header.png" in html, name
            assert f'width="{width}"' in html and f'height="{height}"' in html, name
            assert 'alt="Sobreala"' in html, name
