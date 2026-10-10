"""El sitio público es una sola página: cada botón de la barra baja a su
sección, y las direcciones de antes llevan a la suya."""

from __future__ import annotations

import re
from pathlib import Path

LANDING = Path(__file__).resolve().parent.parent.parent / "landing"


def test_cada_boton_de_la_barra_tiene_su_seccion():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    barra = html[html.index('id="site-nav"'):html.index("</nav>")]
    for ancla in ("inicio", "planes", "como-funciona"):
        assert f'href="/#{ancla}"' in barra, ancla
        assert f'id="{ancla}"' in html, ancla
    # Nosotros no está arriba: se llega desde el pie, y su sección sigue.
    assert 'href="/#nosotros"' not in barra
    assert 'href="/#nosotros"' in html[html.index("<footer"):]
    # Contacto es el pie: «Hablemos de tu lista» se quitó, y con ella el id
    # repetido.
    assert html.count('id="contacto"') == 1
    assert '<footer class="site-footer" id="contacto"' in html
    assert "Hablemos de tu lista" not in html
    # En este orden, que es el que se pidió.
    orden = [html.index(f'id="{a}"') for a in
             ("inicio", "planes", "como-funciona", "nosotros", "preguntas", "contacto")]
    assert orden == sorted(orden)
    # Features abre Cómo funciona.
    assert html.index('id="como-funciona"') < html.index('class="tour"') < html.index('id="tutorials"')


def test_las_direcciones_de_antes_llevan_a_su_seccion():
    for pagina, ancla in (("pricing", "planes"), ("how-it-works", "como-funciona"),
                          ("about", "nosotros"), ("contact", "contacto")):
        html = (LANDING / pagina / "index.html").read_text(encoding="utf-8")
        assert f'content="0; url=/#{ancla}"' in html, pagina
        assert 'name="robots" content="noindex"' in html, pagina


def test_la_portada_dice_menos():
    """La pestaña dice solo «Sobreala», y arriba van el título y dos botones."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert "<title>Sobreala</title>" in html
    portada = html[html.index('<section class="hero">'):html.index("</section>")]
    assert "Envía un correo a todos tus contactos" not in portada
    assert "Escríbenos y te acompañamos" not in portada
    assert re.findall(r'<a class="btn[^>]*>([^<]+)</a>', portada) == [
        "Solicitar demo", "Ver planes"]
    # Pedir la demostración pide una cuenta; con sesión, nav.js la cambia por
    # la bienvenida.
    assert 'href="https://app.sobreala.com/signup"' in portada
    assert 'data-signed-href="https://app.sobreala.com/welcome"' in portada
    assert 'href="/#planes">Ver planes</a>' in portada


def test_los_usos_van_debajo_del_problema_con_sus_cuatro_fotos():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert (html.index('id="problema-title"') < html.index('id="usos-title"')
            < html.index('id="planes"'))
    for foto in ("equipo", "clientes", "socios", "familias"):
        assert f'src="/assets/img/usos/{foto}.webp"' in html, foto
        assert (LANDING / "assets" / "img" / "usos" / f"{foto}.webp").exists(), foto


def test_features_trae_sus_dibujos_y_su_lista():
    """Cinco dibujos en vez de capturas del panel, y debajo la lista que juntó
    «Reglas que funcionan solas» y «En todos los planes»."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    tira = html[html.index('class="tour"'):html.index('id="tutorials"')]
    assert tira.count('<svg class="tour__art"') == 5
    assert "/assets/img/panel/" not in html
    for punto in ("En todos los planes, sin excepción", "Rebotes y quejas fuera.",
                  "Sin sorpresas al llegar al límite.",
                  "Acompañamiento en tu primera campaña.", "Sin permanencia mínima."):
        assert punto in tira, punto
    # Lo que se juntó no sale dos veces, y lo que no existe no se promete.
    assert html.count("En todos los planes, sin excepción") == 1
    assert "Reglas que funcionan solas" not in html
    assert "envíate una prueba" not in html
