"""El sitio público es una sola página: cada botón de la barra baja a su
sección, y las direcciones de antes llevan a la suya."""

from __future__ import annotations

from pathlib import Path

LANDING = Path(__file__).resolve().parent.parent.parent / "landing"


def test_cada_boton_de_la_barra_tiene_su_seccion():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    for ancla in ("inicio", "planes", "como-funciona", "nosotros"):
        assert f'href="/#{ancla}"' in html, ancla
        assert f'id="{ancla}"' in html, ancla
    assert 'id="contacto"' in html and 'id="preguntas"' in html
    # En este orden, que es el que se pidió.
    orden = [html.index(f'id="{a}"') for a in
             ("inicio", "planes", "como-funciona", "nosotros", "contacto", "preguntas")]
    assert orden == sorted(orden)
    # Features abre Cómo funciona.
    assert html.index('id="como-funciona"') < html.index('class="tour"') < html.index('id="tutorials"')


def test_las_direcciones_de_antes_llevan_a_su_seccion():
    for pagina, ancla in (("pricing", "planes"), ("how-it-works", "como-funciona"),
                          ("about", "nosotros"), ("contact", "contacto")):
        html = (LANDING / pagina / "index.html").read_text(encoding="utf-8")
        assert f'content="0; url=/#{ancla}"' in html, pagina
        assert 'name="robots" content="noindex"' in html, pagina
