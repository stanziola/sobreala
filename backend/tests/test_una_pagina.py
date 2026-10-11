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
             ("inicio", "planes", "como-funciona", "contacto")]
    assert orden == sorted(orden)
    # Las preguntas frecuentes se quitaron (octubre de 2026).
    assert 'id="preguntas"' not in html and "Lo que suelen preguntarnos" not in html
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


def test_el_problema_sin_numeros_y_con_su_barra():
    """Los cuatro puntos ya no llevan número, y cada tarjeta trae la barra que
    se llena mientras corre el paso automático."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    seccion = html[html.index('id="problema-title"'):html.index('id="usos-title"')]
    assert seccion.count('name="trouble"') == 4
    assert 'class="trouble__n"' not in seccion
    assert seccion.count('<span class="trouble__bar" aria-hidden="true">'
                         '<span class="trouble__fill"></span></span>') == 4
    assert '<script src="/assets/js/trouble.js" defer></script>' in html


def test_haz_crecer_tu_negocio_va_debajo_del_problema():
    """Cuatro casos, uno a la vez y con la florista primero, sin el encabezado
    de antes, con su paso automático y las flechas a los lados de las barras."""
    from PIL import Image

    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert (html.index('id="problema-title"') < html.index('id="usos-title"')
            < html.index('id="planes"'))
    assert 'id="usos-title">Haz crecer tu negocio</h2>' in html
    assert "Lo que puedes enviar con Sobreala" not in html
    seccion = html[html.index('id="usos-title"'):html.index('id="planes"')]
    assert seccion.count('name="usos"') == 4 and 'id="uso-1" checked' in seccion
    assert seccion.count('class="stories__dot"') == 4
    assert seccion.count('<span class="stories__fill"></span>') == 4
    # ‹, las barras y ›, en ese orden.
    nav = seccion[seccion.index('class="stories__nav"'):]
    assert (nav.index('data-stories-back') < nav.index('class="stories__dots"')
            < nav.index('data-stories-next'))
    assert 'aria-label="Ver el caso anterior"' in nav
    assert 'aria-label="Ver el caso siguiente"' in nav
    # Los textos de octubre de 2026.
    assert "Asambleas, recordatorios y estados de cuenta.</p>" in seccion
    assert "cada uno con su nombre y su monto" not in html
    assert 'id="uso-title-4">Mantén a todos informados</h3>' in seccion
    assert ("Circulares, eventos y el calendario del colegio para toda la "
            "comunidad educativa.") in seccion
    assert "cada familia" not in html
    fotos = re.findall(r'src="/assets/img/usos/(\w+)\.webp"', seccion)
    assert fotos == ["clientes", "equipo", "socios", "familias"]
    assert seccion.count('width="1280" height="800"') == 4
    for foto in fotos:
        with Image.open(LANDING / "assets" / "img" / "usos" / f"{foto}.webp") as im:
            assert im.size == (1280, 800), foto
    assert '<script src="/assets/js/stories.js" defer></script>' in html
    assert (LANDING / "assets" / "js" / "stories.js").exists()


def test_features_trae_sus_dibujos():
    """Cinco dibujos en vez de capturas del panel. La lista de debajo, que juntó
    «Reglas que funcionan solas» y «En todos los planes», se quitó."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    tira = html[html.index('class="tour"'):html.index('id="tutorials"')]
    assert tira.count('<svg class="tour__art"') == 5
    assert "/assets/img/panel/" not in html
    for punto in ("En todos los planes", "Rebotes y quejas fuera.",
                  "Sin sorpresas al llegar al límite.",
                  "Acompañamiento en tu primera campaña.", "Sin permanencia mínima."):
        assert punto not in html, punto
    assert 'class="included' not in html
    # Lo que no existe no se promete.
    assert "Reglas que funcionan solas" not in html
    assert "envíate una prueba" not in html


def test_los_tutoriales_llevan_solo_su_titulo():
    """Sin la etiqueta «Tutoriales» ni la entradilla; «Tutoriales» queda como
    el nombre de las pestañas para un lector de pantalla."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    cabeza = html[html.index('id="tutorials"'):html.index('class="tutorial"')]
    assert 'id="tutoriales-title">Aprende a usar el panel</h2>' in cabeza
    assert 'class="eyebrow"' not in cabeza and 'class="section__intro"' not in cabeza
    assert "Pulsa el punto que late" not in html
    assert '<nav class="tutorial__tabs" aria-label="Tutoriales">' in html


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


def test_las_cabezas_llevan_solo_su_titulo():
    """Planes, Funciones (lo que era «Cómo funciona» más «Features») y la tira
    de plantillas, sin etiqueta ni entradilla (octubre de 2026)."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")

    def cabeza(ancla):
        desde = html.index(ancla)
        return html[html.rindex('<div class="section__head">', 0, desde):
                    html.index("</div>", desde)]

    assert cabeza('id="planes-title"').count("<p") == 0
    assert 'id="planes-title">Planes</h2>' in html
    assert "Se ajustan a lo que necesites" not in html
    assert cabeza('id="como-funciona-title"').count("<p") == 0
    assert 'id="como-funciona-title">Funciones</h2>' in html
    for viejo in ("De tu base de datos", "Así vas a usar", ">Features<",
                  "Lo que puedes hacer con Sobreala"):
        assert viejo not in html, viejo
    assert '<p class="eyebrow">Cómo funciona</p>' not in html
    assert cabeza('id="pasos-title"').count('class="eyebrow"') == 0
    # La barra sigue diciendo «Cómo funciona» y bajando a su sección.
    assert 'href="/#como-funciona"' in html


def test_dominio_personalizado():
    """Lo que era «El envío»: cómo se conecta y sus dos ventajas, sin prometer
    que lo configuramos nosotros (el cliente lo conecta solo)."""
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    seccion = html[html.index('id="envio-title"'):html.index("</section>",
                                                            html.index('id="envio-title"'))]
    assert 'id="envio-title">Dominio personalizado</h2>' in html
    assert "tres registros" in seccion
    assert seccion.count("<li><strong>") == 2
    assert "Reputación propia:" in seccion and "Más confianza:" in seccion
    assert "Tu Empresa &lt;boletin@tuempresa.com&gt;" in seccion
    assert "El envío" not in html and "lo configuramos contigo" not in html
