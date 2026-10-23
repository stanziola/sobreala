"""El sitio público es una sola página: cada botón de la barra baja a su
sección, y las direcciones de antes llevan a la suya."""

from __future__ import annotations

import re
from pathlib import Path

LANDING = Path(__file__).resolve().parent.parent.parent / "landing"


def portada() -> str:
    return (LANDING / "index.html").read_text(encoding="utf-8")


def test_cada_boton_de_la_barra_tiene_su_seccion():
    html = portada()
    barra = html[html.index('id="site-nav"'):html.index("</nav>")]
    # Octubre de 2026: «Cómo funciona» dejó su sitio a la API, Funciones y
    # Plantillas.
    assert re.findall(r'href="/#([\w-]+)"', barra) == [
        "inicio", "api", "planes", "funciones", "plantillas"]
    for ancla in ("inicio", "api", "planes", "funciones", "plantillas"):
        assert f'id="{ancla}"' in html, ancla
    assert 'id="como-funciona"' not in html and "/#como-funciona" not in html
    # Nosotros se quitó (octubre de 2026): ni sección ni enlace en el pie.
    assert 'id="nosotros"' not in html and "/#nosotros" not in html
    # Contacto es el pie: «Hablemos de tu lista» se quitó, y con ella el id
    # repetido.
    assert html.count('id="contacto"') == 1
    assert '<footer class="site-footer" id="contacto"' in html
    assert "Hablemos de tu lista" not in html
    # En este orden, que es el que se pidió: la presentación, la API y el
    # lienzo, los planes, las funciones, las plantillas y las preguntas.
    orden = [html.index(f'id="{a}"') for a in
             ("inicio", "api", "lienzo", "planes", "funciones", "plantillas",
              "preguntas", "contacto")]
    assert orden == sorted(orden)
    # Las preguntas no tienen botón en la barra.
    assert 'href="/#preguntas"' not in barra
    # El pie también baja a Funciones y Plantillas.
    pie = html[html.index('<footer class="site-footer"'):]
    assert 'href="/#funciones"' in pie and 'href="/#plantillas"' in pie


def test_las_direcciones_de_antes_llevan_a_su_seccion():
    for pagina, ancla in (("pricing", "planes"), ("how-it-works", "funciones"),
                          ("about", "inicio"), ("contact", "contacto")):
        html = (LANDING / pagina / "index.html").read_text(encoding="utf-8")
        assert f'content="0; url=/#{ancla}"' in html, pagina
        assert 'name="robots" content="noindex"' in html, pagina


def test_la_pestana_separa_con_una_barra(client, database, outbox):
    """«Términos y condiciones | sobreala» y no con «·» (octubre de 2026), en
    las páginas del sitio y en las del panel. La marca, en minúscula, como el
    logo."""
    for pagina, titulo in (("privacy", "Política de privacidad"),
                           ("terms", "Términos y condiciones"),
                           ("pricing", "Precios"), ("how-it-works", "Cómo funciona"),
                           ("contact", "Contacto")):
        html = (LANDING / pagina / "index.html").read_text(encoding="utf-8")
        assert f"<title>{titulo} | sobreala</title>" in html, pagina
    entrar = client.get("/login").get_data(as_text=True)
    assert re.search(r"<title>[^<·|]+ \| sobreala</title>", entrar)


def test_las_tarjetas_sueltan_su_entrada():
    """Al terminar de subir, cada tarjeta suelta `reveal-rise` e `is-revealed`
    (octubre de 2026): con ellas, `transform: none` le ganaba al hover y los
    planes ya no se levantaban."""
    guion = (LANDING / "assets" / "js" / "reveal.js").read_text(encoding="utf-8")
    assert 'el.classList.remove("reveal-rise", "is-revealed")' in guion


def test_la_portada_dice_menos():
    """La pestaña dice solo «sobreala», y arriba van el título y dos botones."""
    html = portada()
    assert "<title>sobreala</title>" in html
    arriba = html[html.index('<section class="hero">'):html.index("</section>")]
    assert "Envía un correo a todos tus contactos" not in arriba
    assert "Escríbenos y te acompañamos" not in arriba
    assert re.findall(r'<a class="btn[^>]*>([^<]+)</a>', arriba) == [
        "Solicitar demo", "Ver planes"]
    # Pedir la demostración pide una cuenta; con sesión, nav.js la cambia
    # según en qué punto está la empresa (data-cta, octubre de 2026).
    assert 'href="https://app.sobreala.com/signup"' in arriba
    assert 'data-href-closed="https://app.sobreala.com/welcome"' in arriba
    assert 'href="/#planes" data-cta-backup>Ver planes</a>' in arriba


def test_sin_el_problema_ni_los_usos_ni_los_tutoriales():
    """Octubre de 2026: «¿Sigues enviando correos masivos desde Gmail o
    Outlook?», «Haz crecer tu negocio» y los tutoriales salieron de la portada,
    con sus guiones y sus fotos. Los tutoriales vuelven cuando se rehagan."""
    html = portada()
    for viejo in ("¿Sigues enviando correos masivos", "Haz crecer tu negocio",
                  'id="problema-title"', 'id="usos-title"', 'id="tutorials"',
                  "guide-step", "trouble.js", "stories.js", "tutorial.js",
                  "/assets/img/usos/", "Aprende a usar Sobreala"):
        assert viejo not in html, viejo
    assert not (LANDING / "assets" / "img" / "usos").exists()
    assert not (LANDING / "assets" / "js" / "trouble.js").exists()


def test_la_api_y_el_lienzo_van_arriba_en_grande():
    """Los dos bloques de debajo de la presentación: cada uno con su etiqueta,
    su título, cuatro puntos, su botón y su dibujo, que cambia de lado."""
    html = portada()
    api = html[html.index('id="api"'):html.index('id="lienzo"')]
    assert '<p class="eyebrow">Desde el plan Negocio</p>' in api
    assert 'id="api-title">Conecta tu tienda o tu sistema</h2>' in api
    assert api.count('<span class="highlight__mark"') == 4
    assert '<a class="btn btn--primary" href="/api/">Ver la documentación</a>' in api
    # La llamada es la de la documentación: su ruta, su clave y sus campos.
    tarjeta = api[api.index('class="highlight__art code-card"'):]
    assert "POST /api/v1/emails" in tarjeta and "Bearer sa_live_" in tarjeta
    for campo in ("to", "type", "subject", "template_id", "data"):
        assert f"&#34;{campo}&#34;:" in tarjeta, campo
    assert '<span class="code-card__status">201</span>' in tarjeta

    lienzo = html[html.index('id="lienzo"'):html.index('id="planes"')]
    assert 'highlight highlight--flip" id="lienzo"' in html
    assert 'id="lienzo-title">Diseña tus correos en el lienzo</h2>' in lienzo
    assert lienzo.count('<span class="highlight__mark"') == 4
    # Como el de la presentación, y quien ya puede usar el lienzo va a él.
    assert 'href="https://app.sobreala.com/signup" data-cta' in lienzo
    assert 'data-label-demo="Ir al lienzo"' in lienzo
    assert ('data-href-paid="https://app.sobreala.com/templates/create"'
            in lienzo)
    assert "data-hide-for-admin" in lienzo
    assert '<svg class="tour__art"' in lienzo
    # El dibujo del lienzo sale una sola vez: ya no está en Funciones.
    assert html.count('id="fe-drop"') == 1


def test_funciones_trae_sus_seis_dibujos():
    """Seis dibujos en vez de capturas del panel, cada uno con su barra, en el
    orden que se pidió (octubre de 2026): salieron etiquetas, el envío
    programado y los usuarios; anular la suscripción y los rebotes se juntaron;
    el dominio personalizado entró, al final; y el lienzo salió, porque tiene
    su bloque grande arriba."""
    html = portada()
    tira = html[html.index('class="tour"'):html.index('id="plantillas"')]
    assert tira.count('<svg class="tour__art"') == 6
    assert tira.count('name="tour"') == 6
    assert tira.count('<span class="tour__fill"></span>') == 6
    titulos = re.findall(r'<h3 class="tour__title">([^<]+)</h3>', tira)
    assert titulos == [
        "Campos personalizados", "Base de datos",
        "Resultados de cada campaña", "Actividad de tus clientes",
        "Bajas, rebotes y quejas, solos", "Dominio personalizado"], titulos
    for viejo in ("Organiza con etiquetas", "Envío inmediato o programado",
                  "Usuarios de la cuenta</h3>", "Rebotes y quejas fuera"):
        assert viejo not in tira, viejo
    # Sus colores son clases (.art-*): sin ellas los dibujos salen negros. Vivían
    # en el CSS de una sección que se quitó, y se fueron con ella un momento.
    css = (LANDING / "assets" / "css" / "site.css").read_text(encoding="utf-8")
    assert ".art-stage { fill: var(--art-stage); }" in css
    assert ".art-drop { flood-color: var(--art-shadow); }" in css
    # Sin flechas punteadas: los dibujos no las llevan. (La caja punteada del
    # editor es la selección de un texto, no una flecha.)
    assert "art-s-dash" not in tira
    # Las barras van antes que las flechas, debajo del texto.
    nav = tira[tira.index('class="tour__nav"'):]
    assert (nav.index('class="tour__dots"') < nav.index("data-tour-back")
            < nav.index("data-tour-next"))
    assert "/assets/img/panel/" not in html
    # Lo que no existe no se promete.
    assert "Reglas que funcionan solas" not in html
    assert "envíate una prueba" not in html


def test_bajas_rebotes_y_quejas_en_uno():
    html = portada()
    tira = html[html.index('class="tour"'):html.index('id="plantillas"')]
    texto = tira[tira.index("Bajas, rebotes y quejas, solos"):]
    texto = texto[:texto.index("</div>")]
    assert "anular la suscripción" in texto and "rebotan" in texto
    assert "no gastan cuota" in texto


def test_dominio_personalizado_es_una_funcion():
    """Lo que era su sección: cómo se conecta, sin prometer que lo
    configuramos nosotros (el cliente lo conecta solo), y de dónde sale sin
    dominio."""
    html = portada()
    assert 'id="envio-title"' not in html and 'class="mail-card' not in html
    tira = html[html.index('class="tour"'):html.index('id="plantillas"')]
    texto = tira[tira.index('<h3 class="tour__title">Dominio personalizado</h3>'):]
    texto = texto[:texto.index("</div>")]
    assert "tres registros DNS" in texto
    assert "boletin@tuempresa.com" in texto and "envios.sobreala.com" in texto
    assert "tuempresa@envios.sobreala.com" in tira
    assert "lo configuramos contigo" not in html


def test_planes_sin_glosario_y_con_la_tabla_corta():
    """«Qué significa cada fila» se quitó, y la tabla dejó de publicar tres
    filas que siguen en docs/pricing.md. La API, desde Negocio (octubre de
    2026)."""
    html = portada()
    assert "Qué significa cada fila" not in html
    tabla = html[html.index('id="tabla-title"'):html.index("</table>")]
    filas = [f.strip() for f in re.findall(r'<th scope="row">([^<]+)', tabla)]
    assert filas == ["Precio mensual", "Precio anual", "Contactos", "Correos por mes",
                     "Etiquetas", "Columnas de datos", "Correos sin marca de agua",
                     "API", "Usuarios de la cuenta"], filas


def test_las_cabezas_llevan_solo_su_titulo():
    """Planes y Funciones sin etiqueta ni entradilla (octubre de 2026), y
    Plantillas con la suya, que es la pregunta de antes."""
    html = portada()

    def cabeza(ancla):
        desde = html.index(ancla)
        return html[html.rindex('<div class="section__head">', 0, desde):
                    html.index("</div>", desde)]

    assert cabeza('id="planes-title"').count("<p") == 0
    assert 'id="planes-title">Planes</h2>' in html
    assert "Se ajustan a lo que necesites" not in html
    assert cabeza('id="funciones-title"').count("<p") == 0
    assert 'id="funciones-title">Funciones</h2>' in html
    for viejo in ("De tu base de datos", "Así vas a usar", ">Features<",
                  "Lo que puedes hacer con Sobreala"):
        assert viejo not in html, viejo
    assert cabeza('id="plantillas-title"').count('class="eyebrow"') == 0
    assert 'id="plantillas-title">Plantillas</h2>' in html
    assert "¿Aún no sabes por dónde empezar?" in cabeza('id="plantillas-title"')


def test_preguntas_frecuentes_cortas():
    """Volvieron al final (octubre de 2026): seis, la primera abierta, y sin las
    frases de antes que ya no eran ciertas."""
    html = portada()
    preguntas = html[html.index('id="preguntas"'):html.index("<footer")]
    assert 'id="faq-title">Lo que suelen preguntarnos</h2>' in preguntas
    assert preguntas.count('class="faq__item"') == 6
    assert preguntas.count("<details open>") == 1
    assert preguntas.index("<details open>") < preguntas.index("¿Cómo empiezo?")
    for vieja in ("lo configuramos contigo", "subir o bajar de plan"):
        assert vieja not in html, vieja


def test_el_pie_no_lleva_frase():
    """Debajo del logo del pie ya no va «Envía campañas de correo…»."""
    for pagina in ("index.html", "privacy/index.html", "terms/index.html"):
        html = (LANDING / pagina).read_text(encoding="utf-8")
        pie = html[html.index('<footer class="site-footer"'):]
        assert "Envía campañas de correo a toda tu lista" not in pie, pagina
        assert "site-footer__desc" not in pie, pagina
