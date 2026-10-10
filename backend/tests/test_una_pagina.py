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
    # Nosotros se quitó (octubre de 2026): ni sección ni enlace en el pie.
    assert 'id="nosotros"' not in html and "/#nosotros" not in html
    # Contacto es el pie: «Hablemos de tu lista» se quitó, y con ella el id
    # repetido.
    assert html.count('id="contacto"') == 1
    assert '<footer class="site-footer" id="contacto"' in html
    assert "Hablemos de tu lista" not in html
    # En este orden, que es el que se pidió.
    orden = [html.index(f'id="{a}"') for a in
             ("inicio", "planes", "como-funciona", "preguntas", "contacto")]
    assert orden == sorted(orden)
    # Cómo funciona: Features, los tutoriales, la tira de plantillas (sin su
    # botón, que llevaba a los tutoriales) y el envío.
    assert (html.index('id="como-funciona"') < html.index('class="tour"')
            < html.index('id="tutorials"') < html.index('id="pasos-title"')
            < html.index('id="envio-title"'))
    assert "Ver tutorial" not in html


def test_las_direcciones_de_antes_llevan_a_su_seccion():
    for pagina, ancla in (("pricing", "planes"), ("how-it-works", "como-funciona"),
                          ("about", "inicio"), ("contact", "contacto")):
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


def test_haz_crecer_tu_negocio_va_debajo_del_problema():
    """Cuatro casos, uno a la vez y con la florista primero, sin el encabezado
    de antes y con su paso automático."""
    from PIL import Image

    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert (html.index('id="problema-title"') < html.index('id="usos-title"')
            < html.index('id="planes"'))
    assert 'id="usos-title">Haz crecer tu negocio</h2>' in html
    assert "Lo que puedes enviar con Sobreala" not in html
    seccion = html[html.index('id="usos-title"'):html.index('id="planes"')]
    assert seccion.count('name="usos"') == 4 and 'id="uso-1" checked' in seccion
    assert seccion.count('class="stories__dot"') == 4
    fotos = re.findall(r'src="/assets/img/usos/(\w+)\.webp"', seccion)
    assert fotos == ["clientes", "equipo", "socios", "familias"]
    assert seccion.count('width="1280" height="800"') == 4
    for foto in fotos:
        with Image.open(LANDING / "assets" / "img" / "usos" / f"{foto}.webp") as im:
            assert im.size == (1280, 800), foto
    assert '<script src="/assets/js/stories.js" defer></script>' in html
    assert (LANDING / "assets" / "js" / "stories.js").exists()


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


def test_planes_sin_glosario_y_con_la_tabla_corta():
    """«Qué significa cada fila» se quitó, y la tabla dejó de publicar tres
    filas que siguen en docs/pricing.md."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert "Qué significa cada fila" not in html
    tabla = html[html.index('id="tabla-title"'):html.index("</table>")]
    filas = [f.strip() for f in re.findall(r'<th scope="row">([^<]+)', tabla)]
    assert filas == ["Precio mensual", "Precio anual", "Contactos", "Correos por mes",
                     "Etiquetas", "Columnas de datos", "Correos sin marca de agua",
                     "Usuarios de la cuenta"], filas
