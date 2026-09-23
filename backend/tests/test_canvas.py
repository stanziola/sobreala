"""El lienzo de «Crear plantilla»: de coordenadas libres a un correo.

Lo que se fija aquí es lo que no puede aflojarse. Que cada caja salga en su
coordenada, medida en tablas que Outlook respeta. Que una foto llegue como
imagen de verdad y solo el texto sobre una foto use fondo. Que el texto salga
escapado y las columnas pasen para que el envío las llene. Que nada encimado,
fuera de la hoja o con un enlace que ejecuta código llegue a guardarse. Y que
las imágenes de otra cuenta no se puedan colar por el JSON.
"""

from __future__ import annotations

import io
import json
from io import BytesIO

from bson import ObjectId
from PIL import Image

from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import image as images
from services import canvas
from test_campaigns import catch, make, ready, send_it
from test_designs import csrf, foto, inside, other, subir, with_plan


def lienzo(*items, h=300, bg="#FFFFFF"):
    return {"v": 2, "h": h, "bg": bg, "items": list(items)}


def texto(x, y, w=200, h=40, text="Hola", **extra):
    return dict({"t": "text", "x": x, "y": y, "w": w, "h": h, "text": text,
                 "font": "Arial", "size": 18, "color": "#18181B"}, **extra)


def boton(x, y, w=160, h=44, **extra):
    return dict({"t": "button", "x": x, "y": y, "w": w, "h": h, "text": "Ver",
                 "href": "https://coop.com", "font": "Arial", "size": 16,
                 "color": "#FFFFFF", "bg": "#31A9E8"}, **extra)


def imagen(x, y, w, h, name="a.jpg", **extra):
    # Con descripción por defecto: sin ella no se guarda, y lo que fija esa
    # regla es su propia prueba, no todas las demás.
    return dict({"t": "image", "x": x, "y": y, "w": w, "h": h, "name": name,
                 "alt": "La sede de la cooperativa"}, **extra)


def rectangulo(x, y, w, h, bg="#0B3B5C", **extra):
    return dict({"t": "shape", "x": x, "y": y, "w": w, "h": h, "bg": bg}, **extra)


def leer(doc):
    return canvas.parse(json.dumps(doc))


def tipos(doc):
    return [one["kind"] for one in canvas.groups(leer(doc))]


# ------------------------------------------------------------ qué no se guarda

def test_un_texto_encimado_no_se_guarda():
    doc = leer(lienzo(texto(40, 40), boton(100, 60)))
    assert "overlap" in canvas.problems(doc)
    # Tocarse por el borde sí se puede.
    assert canvas.problems(leer(lienzo(texto(40, 40, w=100), boton(140, 40)))) == []


def test_lo_que_se_sale_de_la_hoja_no_se_guarda():
    assert "bounds" in canvas.problems(leer(lienzo(texto(500, 40, w=200))))
    assert "bounds" in canvas.problems(leer(lienzo(texto(40, 280, h=40))))


def test_la_hoja_no_pasa_de_su_tope():
    assert "height" in canvas.problems(leer(lienzo(texto(0, 0), h=canvas.MAX_HEIGHT + 1)))
    assert canvas.problems(leer(lienzo(texto(0, 0), h=canvas.MAX_HEIGHT))) == []


def test_solo_fuentes_de_correo_y_enlaces_seguros():
    assert "font" in canvas.problems(leer(lienzo(texto(0, 0, font="Comic Neue"))))
    assert "href" in canvas.problems(leer(lienzo(boton(0, 0, href="javascript:alert(1)"))))
    assert "href" in canvas.problems(leer(lienzo(boton(0, 0, href='https://x.com" onclick="x'))))
    assert "href" in canvas.problems(leer(lienzo(imagen(0, 0, 100, 100, href="javascript:x"))))
    assert canvas.problems(leer(lienzo(boton(0, 0, href="mailto:hola@coop.com")))) == []


def test_la_letra_no_baja_de_14():
    assert "size" in canvas.problems(leer(lienzo(texto(0, 0, size=10))))


def test_una_imagen_ajena_no_entra():
    doc = leer(lienzo(imagen(0, 0, 600, 300, name="de-otro.jpg")))
    assert "image" in canvas.problems(doc, owns=lambda name: False)


def test_una_foto_con_enlace_no_puede_tener_nada_encima():
    sola = leer(lienzo(imagen(0, 0, 300, 200, href="https://coop.com")))
    assert canvas.problems(sola) == []
    tapada = leer(lienzo(imagen(0, 0, 300, 200, href="https://coop.com"),
                         texto(20, 20, text="Oferta")))
    assert "link_overlap" in canvas.problems(tapada)
    assert canvas.linked_alone(tapada) == [0]


def test_un_molinillo_se_pide_mover():
    """Cuatro cajas que se rodean sin tocarse no caben en ninguna tabla."""
    doc = leer(lienzo(texto(0, 0, w=200, h=100), texto(200, 0, w=100, h=200),
                      texto(100, 200, w=200, h=100), texto(0, 100, w=100, h=200),
                      h=400))
    assert "tangled" in canvas.problems(doc)


def test_lo_que_no_es_un_lienzo():
    assert canvas.problems(canvas.parse("no es json")) == ["broken"]
    assert "empty" in canvas.problems(canvas.parse('{"items": [], "h": 300}'))


# ------------------------------------------------ lo que era por diapositivas

def test_las_diapositivas_se_apilan_en_una_hoja():
    viejo = {"slides": [
        {"h": 300, "bg": "#0B3B5C", "items": [texto(40, 40, text="Arriba")]},
        {"h": 200, "bg": "#FFFFFF", "items": [boton(40, 20)]}]}
    doc = leer(viejo)
    assert doc["v"] == canvas.VERSION and doc["h"] == 500
    # El color de la primera es un rectángulo del ancho entero, detrás.
    assert doc["items"][0] == {"t": "shape", "x": 0, "y": 0, "w": 600, "h": 300,
                               "bg": "#0B3B5C", "radius": 0}
    assert doc["items"][1]["text"] == "Arriba"
    # Lo de la segunda baja lo que medía la primera.
    assert doc["items"][2]["y"] == 320
    assert canvas.problems(doc) == []


# ------------------------------------------------------------ los grupos

def test_una_foto_sola_es_una_imagen_y_no_un_fondo():
    doc = leer(lienzo(imagen(150, 0, 300, 200, alt="La asamblea"), texto(40, 220, w=400)))
    assert tipos(lienzo(imagen(150, 0, 300, 200), texto(40, 220, w=400))) == ["picture", "front"]
    html = canvas.to_html(doc, ["https://panel/img/foto.jpg", None])
    assert '<img src="https://panel/img/foto.jpg" width="300" height="200"' in html
    assert 'alt="La asamblea"' in html
    assert "background-image" not in html


def test_una_foto_con_enlace_se_puede_pulsar():
    doc = leer(lienzo(imagen(0, 0, 300, 200, href="https://coop.com/oferta")))
    html = canvas.to_html(doc, ["https://panel/img/foto.jpg"])
    assert '<a href="https://coop.com/oferta" target="_blank"><img' in html


def test_dos_fotos_encimadas_son_una_sola_imagen():
    doc = lienzo(imagen(0, 0, 300, 200), imagen(200, 100, 300, 200, name="b.jpg"))
    assert tipos(doc) == ["picture"]
    grupo = canvas.groups(leer(doc))[0]
    assert (grupo["x"], grupo["y"], grupo["w"], grupo["h"]) == (0, 0, 500, 300)


def test_texto_sobre_foto_usa_un_fondo_de_su_zona():
    doc = leer(lienzo(imagen(100, 20, 400, 250),
                      texto(140, 60, w=300, text="Hola", color="#FFFFFF"),
                      texto(40, 290, w=500, text="Debajo")))
    assert [one["kind"] for one in canvas.groups(doc)] == ["backdrop", "front"]
    html = canvas.to_html(doc, ["https://panel/img/zona.jpg", None], ["#223344", None])
    # El fondo mide lo mismo que su celda: nadie tiene que escalarlo.
    assert "background-size:400px 250px" in html
    assert 'bgcolor="#223344"' in html
    assert "<v:fill" in html and "https://panel/img/zona.jpg" in html
    # Y el fondo va a uno, no al doble: mide lo mismo que la celda.
    fondo = canvas.parts(doc, lambda name: foto(800, 600))[0]
    with Image.open(BytesIO(fondo)) as hecho:
        assert hecho.size == (400, 250)


def test_un_rectangulo_sin_foto_es_una_celda_de_color():
    doc = leer(lienzo(rectangulo(0, 0, 600, 200, radius=12),
                      texto(40, 40, w=300, text="Franja", color="#FFFFFF")))
    assert [one["kind"] for one in canvas.groups(doc)] == ["color"]
    html = canvas.to_html(doc, [None])
    assert 'bgcolor="#0B3B5C"' in html and "border-radius:12px" in html
    assert "<img" not in html
    assert canvas.parts(doc, lambda name: None) == [None]


def test_la_foto_se_funde_al_doble():
    doc = leer(lienzo(imagen(0, 0, 300, 150)))
    hecha = canvas.parts(doc, lambda name: foto(800, 600))[0]
    with Image.open(BytesIO(hecha)) as abierta:
        assert abierta.size == (600, 300)


# ------------------------------------------------------------ la cuadrícula

def test_cada_caja_sale_en_su_coordenada():
    html = canvas.to_html(leer(lienzo(texto(40, 30, w=300))), [None])
    # 30 px de aire arriba y 40 a la izquierda, medidos en celdas.
    assert 'height="30"' in html
    assert 'width="40"' in html
    assert 'width="300"' in html
    # Y todo el ancho del correo.
    assert 'width="600"' in html


def test_dos_cajas_lado_a_lado_quedan_en_columnas():
    html = canvas.to_html(leer(lienzo(texto(40, 40, w=200), boton(400, 40))), [None, None])
    # El hueco entre las dos: de 240 a 400.
    assert 'width="160"' in html


def test_el_texto_sale_escapado_y_las_columnas_pasan():
    html = canvas.to_html(leer(lienzo(texto(0, 0, text="Hola *|EDAD|* <script>x</script>"))),
                          [None])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "*|EDAD|*" in html


def test_el_boton_lleva_su_version_para_outlook():
    html = canvas.to_html(leer(lienzo(boton(40, 40, radius=12))), [None])
    assert "<v:roundrect" in html and 'fillcolor="#31A9E8"' in html
    assert 'href="https://coop.com"' in html
    # Los demás leen el enlace de siempre.
    assert "<!--[if !mso]><!-->" in html


def test_el_modo_oscuro_no_cambia_los_colores():
    doc = leer(lienzo(texto(0, 0, color="#FFFFFF"), boton(0, 100, bg="#000000")))
    reglas = canvas.dark_css(doc)
    assert "[data-ogsc] .pmc-FFFFFF{color:#FFFFFF !important;}" in reglas
    assert "[data-ogsb] .pmb-000000{background-color:#000000 !important;}" in reglas
    html = canvas.to_html(doc, [None, None])
    assert 'class="pmc-FFFFFF"' in html and 'class="pmb-000000"' in html


# ------------------------------------------------------------ las rutas

# Un párrafo como el de un correo de verdad: con él, el lienzo pasa la revisión
# antispam (texto suficiente, sin mayúsculas ni palabras gancho).
PARRAFO = ("Te esperamos el sábado a las nueve de la mañana en el salón de la "
           "cooperativa para la asamblea anual de socios. Vamos a presentar el "
           "informe del año, elegir la nueva junta directiva y conversar sobre "
           "los proyectos del próximo periodo. Trae tu carné de socio y llega "
           "unos minutos antes para registrarte en la entrada.")


def con_texto(doc):
    """El lienzo con un párrafo más debajo, para que se pueda guardar: cada
    prueba mira otra cosa, no la revisión antispam. La hoja crece para que la
    foto no pase de la mitad."""
    return dict(doc, h=doc["h"] + 800,
                items=doc["items"] + [texto(20, doc["h"] + 20, w=560, h=320, text=PARRAFO)])


def guardar(browser, doc, *, url="/plantillas/crear", nombre="Asamblea",
            completar=True):
    doc = con_texto(doc) if completar else doc
    return browser.post(url, data={"csrf_token": csrf(browser, url),
                                   "nombre": nombre, "lienzo": json.dumps(doc)})


def test_crear_guarda_el_lienzo(client, database, outbox):
    browser = inside(client)
    respuesta = guardar(browser, lienzo(texto(40, 40, text="Asamblea anual")))
    assert respuesta.status_code == 302

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    hecha = designs.for_account(database, cuenta["_id"])[0]
    assert hecha["source"] == designs.CANVAS
    assert hecha["canvas"]["v"] == canvas.VERSION
    assert hecha["canvas"]["items"][0]["text"] == "Asamblea anual"
    assert "Hecha en el editor" in browser.get("/plantillas").get_data(as_text=True)


def test_lo_que_no_se_puede_guardar_vuelve_con_lo_escrito(client, database, outbox):
    browser = inside(client)
    respuesta = guardar(browser, lienzo(texto(40, 40, text="Mi texto"), boton(60, 50)))
    salida = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "encimados" in salida
    assert "Mi texto" in salida
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert designs.count(database, cuenta["_id"]) == 0


def subir_foto(browser, raw=None, nombre="foto.jpg"):
    return browser.post("/plantillas/lienzo/imagen", data={
        "csrf_token": csrf(browser), "archivo": (io.BytesIO(raw or foto()), nombre)},
        content_type="multipart/form-data")


def test_la_foto_del_lienzo_se_guarda_al_doble(client, database, outbox):
    browser = inside(client)
    respuesta = subir_foto(browser, foto(3000, 2000))
    datos = respuesta.get_json()
    assert datos["width"] == 1200
    assert datos["url"].endswith(datos["name"])


def test_un_png_con_borde_transparente_se_recorta_al_subir(client, database, outbox):
    browser = inside(client)
    logo = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    logo.paste((200, 10, 10, 255), (100, 50, 300, 250))
    buffer = BytesIO()
    logo.save(buffer, format="PNG")
    datos = subir_foto(browser, buffer.getvalue(), "logo.png").get_json()
    assert (datos["width"], datos["height"]) == (200, 200)


def test_la_imagen_de_un_grupo_no_cuenta_contra_el_tope(client, database, outbox):
    browser = inside(client)
    nombre = subir_foto(browser).get_json()["name"]
    guardar(browser, lienzo(imagen(0, 0, 600, 300, name=nombre),
                            texto(40, 40, text="Oferta del mes")))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    hecha = designs.for_account(database, cuenta["_id"])[0]
    fondo = hecha["backgrounds"][0]

    assert fondo and fondo != nombre
    assert hecha["shades"][0].startswith("#")
    assert images.count(database, cuenta["_id"]) == 1
    assert other(client).get(f"/img/{fondo}").status_code == 200


def test_volver_a_guardar_borra_la_imagen_vieja_pero_no_la_de_la_copia(
        client, database, outbox):
    browser = inside(client)
    nombre = subir_foto(browser).get_json()["name"]
    doc = lienzo(imagen(0, 0, 600, 300, name=nombre), texto(40, 40, text="Oferta"))
    guardar(browser, doc)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    original = designs.for_account(database, cuenta["_id"])[0]
    viejo = original["backgrounds"][0]
    copia = designs.duplicate(database, cuenta["_id"], original["_id"], name="Copia")

    guardar(browser, doc, url=f"/plantillas/lienzo/{original['_id']}")
    assert other(client).get(f"/img/{viejo}").status_code == 200  # la copia lo usa

    browser.post("/plantillas/borrar", data={"csrf_token": csrf(browser), "id": str(copia)})
    assert other(client).get(f"/img/{viejo}").status_code == 404
    # Y la foto original sigue: la nombra la que queda.
    assert other(client).get(f"/img/{nombre}").status_code == 200


def test_una_foto_de_otra_cuenta_no_se_cuela(client, database, outbox):
    ana = inside(client)
    de_ana = subir_foto(ana).get_json()["name"]

    bea = inside(client, "bea@ejemplo.com")
    guardar(bea, lienzo(imagen(0, 0, 600, 300, name=de_ana), texto(40, 40)))
    suya = accounts.by_email(database, "bea@ejemplo.com")
    assert designs.count(database, suya["_id"]) == 0


def test_el_lienzo_de_otro_no_se_abre(client, database, outbox):
    ana = inside(client)
    guardar(ana, lienzo(texto(40, 40)))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    suya = designs.for_account(database, cuenta["_id"])[0]

    bea = inside(client, "bea@ejemplo.com")
    assert bea.get(f"/plantillas/lienzo/{suya['_id']}").status_code == 404


def test_una_guardada_por_diapositivas_se_abre_como_hoja(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    vieja = designs.save_canvas(database, cuenta["_id"], name="Vieja", doc={"slides": [
        {"h": 300, "bg": "#0B3B5C", "items": [texto(40, 40, text="De antes")]}]},
        backgrounds=[None])
    pantalla = browser.get(f"/plantillas/lienzo/{vieja}").get_data(as_text=True)
    assert '"v": 2' in pantalla and "De antes" in pantalla
    assert "Diapositiva" not in pantalla


def vista(browser, doc, **extra):
    return browser.post("/plantillas/lienzo/vista", data=dict({
        "csrf_token": csrf(browser, "/plantillas/crear"),
        "lienzo": json.dumps(doc)}, **extra))


def test_la_vista_previa_es_un_correo_aislado(client, database, outbox):
    browser = inside(client)
    respuesta = vista(browser, lienzo(texto(40, 40, text="Hola <b>socio</b>")))
    assert "default-src 'none'" in respuesta.headers["Content-Security-Policy"]
    salida = respuesta.get_data(as_text=True)
    assert "Hola &lt;b&gt;socio&lt;/b&gt;" in salida
    assert "Anular la suscripción" in salida
    # El sobre: sin agrandar la letra y en claro. Sin viewport, para que el
    # teléfono lo siga achicando: mide 600 fijos.
    assert "-webkit-text-size-adjust:100%" in salida and 'name="viewport"' not in salida
    assert 'name="color-scheme" content="light"' in salida
    assert "[data-ogsc] .pmc-18181B" in salida


def test_la_vista_previa_con_un_contacto_de_verdad(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    contacts.create(database, cuenta["_id"], email="luis@coop.com", name="Luis <b>Pérez</b>",
                    consent={"source": "form"})
    luis = database.contacts.find_one({"account_id": cuenta["_id"]})
    doc = lienzo(texto(40, 40, w=400, text="Hola *|NOMBRE|*"))

    salida = vista(browser, doc, contacto=str(luis["_id"])).get_data(as_text=True)
    assert "Hola Luis &lt;b&gt;Pérez&lt;/b&gt;" in salida
    # Sin elegir a nadie: la pastilla con el nombre de la columna.
    assert "background:#E0F2FE" in vista(browser, doc).get_data(as_text=True)
    # Y en la pantalla, el selector lo ofrece.
    assert "luis@coop.com" in browser.get("/plantillas/crear").get_data(as_text=True)


def test_el_contacto_de_otra_cuenta_no_llena_la_vista(client, database, outbox):
    inside(client)
    ana = accounts.by_email(database, "ana@ejemplo.com")
    contacts.create(database, ana["_id"], email="secreto@coop.com", name="Secreto",
                    consent={"source": "form"})
    de_ana = database.contacts.find_one({"account_id": ana["_id"]})

    bea = inside(client, "bea@ejemplo.com")
    salida = vista(bea, lienzo(texto(40, 40, w=400, text="Hola *|NOMBRE|*")),
                   contacto=str(de_ana["_id"])).get_data(as_text=True)
    assert "Secreto" not in salida
    assert "background:#E0F2FE" in salida
    assert vista(bea, lienzo(texto(40, 40)), contacto=str(ObjectId())).status_code == 200


def test_un_lienzo_sale_en_una_campana_con_su_baja(client, database, outbox,
                                                   monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, _ = ready(client, database, howmany=2)
    pieza = designs.save_canvas(
        database, account["_id"], name="Asamblea",
        doc=leer(lienzo(texto(40, 40, w=400, text="Asamblea anual de socios"),
                        boton(40, 120))),
        backgrounds=[None, None])
    make(browser, pieza)

    send_it(browser, database, account["_id"])

    assert len(salidos) == 2
    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "Asamblea anual de socios" in cuerpo
    assert 'href="https://coop.com"' in cuerpo
    assert "Anular la suscripción" in cuerpo
    assert "[data-ogsc]" in cuerpo


def test_una_pieza_por_diapositivas_se_rehace_antes_de_salir(client, database, outbox,
                                                             monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, _ = ready(client, database, howmany=1)
    raw = foto(800, 600)
    nombre = images.save(database, account["_id"], data=raw, ext="jpg", mime="image/jpeg")
    viejo = images.save(database, account["_id"], data=raw, ext="jpg", mime="image/jpeg",
                        kind=images.BACKGROUND)
    pieza = designs.save_canvas(database, account["_id"], name="De antes", doc={"slides": [
        {"h": 300, "bg": "#FFFFFF", "items": [imagen(0, 0, 300, 300, name=nombre),
                                               texto(320, 40, w=240, text="Vieja")]}]},
        backgrounds=[viejo])
    make(browser, pieza)

    send_it(browser, database, account["_id"])

    cuerpo = salidos[0].get_body(("html",)).get_content()
    rehecha = designs.by_id(database, account["_id"], pieza)
    assert rehecha["canvas"]["v"] == canvas.VERSION
    nueva = rehecha["backgrounds"][0]
    assert nueva and nueva != viejo and nueva in cuerpo
    assert "Vieja" in cuerpo
    # La imagen de antes ya no la nombra nadie.
    assert other(client).get(f"/img/{viejo}").status_code == 404


# ------------------------------------------------ nombre, correo y la pastilla

def test_nombre_y_correo_se_llenan_sin_crear_columnas():
    from services import fields

    contacto = {"name": "Ana Moreno", "email": "ana@coop.com", "fields": {}}
    assert fields.fill("Hola *|NOMBRE|*, *|CORREO|*", contacto, []) == \
        "Hola Ana Moreno, ana@coop.com"
    # Escapado dentro del correo, como cualquier dato de otro.
    assert fields.fill("*|NOMBRE|*", {"name": "<b>Ana</b>"}, []) == "&lt;b&gt;Ana&lt;/b&gt;"


def test_no_se_puede_crear_una_columna_nombre(client, database, outbox):
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert accounts.add_field(database, cuenta["_id"], label="Nombre", kind="text") is None
    assert accounts.add_field(database, cuenta["_id"], label="Correo", kind="text") is None


def test_la_vista_previa_ensena_la_marca_como_pastilla():
    from services import fields

    html = ('<p>Hola *|NOMBRE|*</p>'
            '<a href="https://coop.com/?q=*|EDAD|*">Ver *|EDAD|*</a>')
    salida = fields.preview_fill(html, [{"key": "EDAD", "label": "Edad", "type": "number"}])
    assert '<span style="background:#E0F2FE' in salida and ">Nombre</span>" in salida
    # Dentro de un atributo, sin etiqueta: rompería el enlace.
    assert 'href="https://coop.com/?q=Edad"' in salida


# ------------------------------------------------------- la revisión antispam

def revisar(*items, h=400):
    doc = leer(lienzo(*items, h=h))
    return [one["key"] for one in canvas.review(doc, 20000, limit=102 * 1024)]


def test_un_correo_con_texto_suficiente_pasa():
    assert revisar(texto(20, 20, w=560, h=320, text=PARRAFO)) == []


def test_poco_texto_no_se_guarda():
    assert "few_text" in revisar(texto(20, 20, text="Hola"))


def test_mas_imagen_que_texto_no_se_guarda():
    claves = revisar(imagen(0, 0, 600, 400), texto(20, 20, w=560, h=320, text=PARRAFO))
    assert "image_heavy" in claves


def test_dos_imagenes_encimadas_no_cuentan_dos_veces():
    # Media hoja de foto y media de texto: justo en el límite. La segunda foto
    # va encima de la primera y no tapa nada nuevo.
    claves = revisar(imagen(0, 0, 600, 400), imagen(150, 100, 300, 200, name="b.jpg"),
                     texto(20, 420, w=560, h=320, text=PARRAFO), h=800)
    assert "image_heavy" not in claves


def test_un_rectangulo_de_color_no_cuenta_como_imagen():
    claves = revisar(rectangulo(0, 0, 600, 800), texto(20, 20, w=560, h=320, text=PARRAFO),
                     h=800)
    assert "image_heavy" not in claves


def test_enlaces_acortados_mayusculas_gritos_y_palabras_gancho():
    assert "shortener" in revisar(texto(20, 20, w=560, h=300, text=PARRAFO),
                                  boton(20, 340, href="https://bit.ly/abc"))
    assert "shortener" in revisar(texto(20, 20, w=560, h=300, text=PARRAFO),
                                  imagen(20, 340, 60, 40, href="https://bit.ly/abc"))
    assert "caps" in revisar(texto(20, 20, w=560, h=320, text=PARRAFO.upper()))
    assert "shouting" in revisar(texto(20, 20, w=560, h=320, text=PARRAFO + " ¡Ven!!"))
    assert "trigger" in revisar(texto(20, 20, w=560, h=320, text=PARRAFO + " Es gratis."))


def test_lo_que_puede_ir_a_spam_no_se_guarda(client, database, outbox):
    browser = inside(client)
    respuesta = guardar(browser, lienzo(texto(40, 40, text="Hola")), completar=False)
    assert respuesta.status_code == 200
    assert "muy poco texto" in respuesta.get_data(as_text=True)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert designs.count(database, cuenta["_id"]) == 0


def test_la_revision_dice_cuanto_pesa_y_que_falta(client, database, outbox):
    browser = inside(client)
    respuesta = browser.post("/plantillas/lienzo/revisar", data={
        "csrf_token": csrf(browser, "/plantillas/crear"),
        "lienzo": json.dumps(lienzo(texto(40, 40, text="Hola")))})
    datos = respuesta.get_json()
    assert datos["ok"] is False
    assert datos["max"] == 102 * 1024
    assert 0 < datos["bytes"] < datos["max"]
    assert any("muy poco texto" in one for one in datos["issues"])


def test_estadisticas_ya_no_lleva_a_configuracion(client, database, outbox):
    browser = inside(client)
    assert "Ir a configuración" not in browser.get("/panel").get_data(as_text=True)


# ------------------------------------------------ el grupo del editor

def test_el_grupo_se_guarda_y_no_cambia_el_correo():
    """Agrupar es para mover junto: viaja con la pieza y el correo sale igual.

    Lo que decide las celdas sigue siendo qué cajas se enciman, así que dos
    cosas agrupadas pero separadas caen en celdas distintas.
    """
    suelto = lienzo(texto(20, 20), texto(20, 200))
    junto = lienzo(texto(20, 20, g=3), texto(20, 200, g=3))

    leido = leer(junto)
    assert [one.get("g") for one in leido["items"]] == [3, 3]
    assert tipos(junto) == ["front", "front"]
    assert canvas.to_html(leido, [None, None]) == canvas.to_html(leer(suelto), [None, None])


def test_un_grupo_inventado_no_entra():
    """El navegador lo escribe cualquiera: lo que no es un número entre 1 y 999
    se cae, como todo lo demás."""
    for malo in ("<script>", 0, -2, 1000, None, 1.5e9):
        leido = leer(lienzo(texto(20, 20, g=malo)))
        assert "g" not in leido["items"][0], malo
    assert leer(lienzo(texto(20, 20, g="7")))["items"][0]["g"] == 7


# ------------------------------------------- geometria, giro y fuentes

def test_un_circulo_no_es_celda_de_color_y_se_pinta():
    """Outlook de escritorio ignora border-radius: un circulo dibujado como
    celda saldria cuadrado, asi que viaja como imagen."""
    assert tipos(lienzo(rectangulo(0, 0, 200, 200))) == ["color"]
    assert tipos(lienzo(rectangulo(0, 0, 200, 200, shape="ellipse"))) == ["picture"]

    doc = leer(lienzo(rectangulo(0, 0, 200, 200, shape="ellipse", bg="#0B3B5C")))
    pintadas = canvas.parts(doc, lambda name: None)
    assert pintadas[0], "el circulo tiene que traer su imagen"
    from io import BytesIO

    from PIL import Image
    with Image.open(BytesIO(pintadas[0])) as hecha:
        medio = hecha.getpixel((hecha.width // 2, hecha.height // 2))
        esquina = hecha.getpixel((2, 2))
    assert medio[2] > 60 and medio[0] < 60, medio       # el centro, pintado
    assert esquina == (255, 255, 255), esquina          # la esquina, la hoja


def test_una_figura_inventada_es_un_rectangulo():
    leido = leer(lienzo(rectangulo(0, 0, 100, 100, shape="<script>")))
    assert leido["items"][0]["shape"] == "rect"


def test_lo_girado_ocupa_mas_y_eso_es_lo_que_manda():
    """La caja que se arrastra no cambia; la huella si, y es la que decide."""
    recta = imagen(100, 100, 200, 100)
    torcida = imagen(100, 100, 200, 100, rot=90)
    assert canvas.bounds(leer(lienzo(recta))["items"][0])["w"] == 200
    girada = canvas.bounds(leer(lienzo(torcida))["items"][0])
    assert (girada["w"], girada["h"]) == (100, 200)
    assert girada["x"] == 150 and girada["y"] == 50

    # Dos cosas que no se tocan derechas, se tocan al girar una.
    quieto = lienzo(imagen(20, 20, 200, 40), texto(20, 80, w=200, h=40))
    assert tipos(quieto) == ["picture", "front"]
    movido = lienzo(imagen(20, 20, 200, 40, rot=80), texto(20, 80, w=200, h=40))
    assert tipos(movido) == ["backdrop"]


def test_lo_que_se_sale_al_girar_no_se_guarda():
    dentro = leer(lienzo(imagen(200, 100, 200, 100), h=300))
    assert "bounds" not in canvas.problems(dentro, owns=lambda n: True)
    fuera = leer(lienzo(imagen(200, 20, 200, 100, rot=90), h=300))
    assert "bounds" in canvas.problems(fuera, owns=lambda n: True)
    assert leer(lienzo(imagen(20, 20, 100, 100, rot=725)))["items"][0]["rot"] == 5


def test_el_texto_no_gira():
    leido = leer(lienzo(texto(20, 20, rot=45), boton(20, 120, rot=45)))
    assert all("rot" not in one for one in leido["items"])


def test_las_fuentes_nuevas_valen_y_las_de_fuera_no():
    viejas = ("Arial", "Helvetica", "Verdana", "Tahoma", "Trebuchet MS",
              "Georgia", "Times New Roman", "Courier New")
    for nombre in ("Palatino", "Garamond", "Lucida Sans", "Century Gothic"):
        assert "font" not in canvas.problems(leer(lienzo(texto(20, 20, font=nombre))))
        pila = canvas.FONTS[nombre]
        # Quien no la tenga (Android, por ejemplo) cae en una de las de
        # siempre, no en una cualquiera.
        assert any(una in pila for una in viejas), pila
        assert pila.rsplit(",", 1)[-1].strip() in ("serif", "sans-serif", "monospace")
    assert "font" in canvas.problems(leer(lienzo(texto(20, 20, font="Comic Sans MS"))))


def test_lo_girado_se_pinta_girado():
    """El giro se hornea en la imagen del grupo: ningun lector de correo
    entiende una transformacion."""
    from io import BytesIO

    from PIL import Image

    alto = lienzo(rectangulo(200, 100, 200, 60, shape="rect", rot=45, bg="#0B3B5C"), h=400)
    doc = leer(alto)
    grupo = canvas.groups(doc)[0]
    # A 45 grados, una banda de 200x60 ocupa un cuadrado de 184: mas alto que
    # su caja y un poco mas angosto.
    assert (grupo["w"], grupo["h"]) == (184, 184)
    pintada = canvas.parts(doc, lambda name: None)[0]
    assert pintada
    with Image.open(BytesIO(pintada)) as hecha:
        medio = hecha.getpixel((hecha.width // 2, hecha.height // 2))
        esquina = hecha.getpixel((2, 2))
    assert medio[2] > 60 and medio[0] < 60, medio    # el centro, pintado
    assert esquina == (255, 255, 255), esquina       # la esquina, la hoja


# ------------------------------------------------------------ el recorte

def test_la_foto_se_guarda_recortada_y_se_pinta_asi():
    """El recorte vive en la pieza y la imagen subida no se toca: se puede
    cambiar mañana."""
    from io import BytesIO

    from PIL import Image

    # Una foto de dos mitades: arriba azul, abajo roja.
    fuente = Image.new("RGB", (400, 400), (20, 60, 200))
    fuente.paste((200, 30, 30), (0, 200, 400, 400))
    crudo = BytesIO()
    fuente.save(crudo, format="JPEG", quality=90)
    datos = crudo.getvalue()

    def mitad(cut):
        doc = leer(lienzo(imagen(0, 0, 200, 100, crop=cut), h=200))
        pintada = canvas.parts(doc, lambda name: datos)[0]
        with Image.open(BytesIO(pintada)) as hecha:
            return hecha.getpixel((hecha.width // 2, hecha.height // 2))

    arriba = mitad([0, 0, 1, 0.5])
    abajo = mitad([0, 0.5, 1, 0.5])
    assert arriba[2] > 120 and arriba[0] < 90, arriba     # azul
    assert abajo[0] > 120 and abajo[2] < 90, abajo        # rojo


def test_un_recorte_inventado_no_entra():
    for malo in ("todo", [0, 0], [0, 0, 0.01, 0.5], [0.9, 0, 0.5, 0.5],
                 [-0.1, 0, 0.5, 0.5], [0, 0, 1, 1], None):
        leido = leer(lienzo(imagen(0, 0, 200, 100, crop=malo)))
        assert "crop" not in leido["items"][0], malo
    bueno = leer(lienzo(imagen(0, 0, 200, 100, crop=[0.1, 0.2, 0.5, 0.25])))
    assert bueno["items"][0]["crop"] == [0.1, 0.2, 0.5, 0.25]


def test_sin_descripcion_una_foto_no_se_guarda(client, database, outbox):
    """Es lo que se lee cuando el buzon bloquea las imagenes."""
    doc = leer(lienzo(imagen(0, 0, 200, 100, alt=""), texto(0, 120, w=560, h=160)))
    assert "alt" in canvas.problems(doc)
    assert "alt" not in canvas.problems(
        leer(lienzo(imagen(0, 0, 200, 100), texto(0, 120, w=560, h=160))))

    browser = inside(client)
    respuesta = guardar(browser, lienzo(imagen(0, 0, 600, 200, alt="  "),
                                        texto(20, 220, w=560, h=200, text=PARRAFO)),
                        completar=False)
    assert "falta la descripción" in respuesta.get_data(as_text=True)


def test_las_figuras_nuevas_se_pintan_y_la_linea_sigue_siendo_color():
    from io import BytesIO

    from PIL import Image

    # La linea y el rectangulo, celda de color; las otras cuatro, imagen.
    assert tipos(lienzo(rectangulo(0, 0, 600, 8, shape="line"))) == ["color"]
    for figura in ("ellipse", "triangle", "star", "arrow"):
        assert tipos(lienzo(rectangulo(0, 0, 200, 200, shape=figura))) == ["picture"], figura

    for figura in ("triangle", "star", "arrow"):
        doc = leer(lienzo(rectangulo(0, 0, 200, 200, shape=figura, bg="#0B3B5C")))
        pintada = canvas.parts(doc, lambda name: None)[0]
        with Image.open(BytesIO(pintada)) as hecha:
            medio = hecha.getpixel((hecha.width // 2, hecha.height // 2))
            esquina = hecha.getpixel((2, 2))
        assert medio[2] > 60 and medio[0] < 60, (figura, medio)
        assert esquina == (255, 255, 255), (figura, esquina)


# ------------------------------------------------------- bajarse la pieza en PDF

def pedir_pdf(browser, doc, nombre="Asamblea anual"):
    return browser.post("/plantillas/lienzo/pdf", data={
        "csrf_token": csrf(browser), "nombre": nombre,
        "lienzo": json.dumps(doc)})


def test_el_pdf_sale_del_tamano_de_la_hoja(client, database, outbox):
    browser = inside(client)
    respuesta = pedir_pdf(browser, lienzo(texto(40, 40, text="Asamblea"), h=420))
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/pdf"
    assert "asamblea-anual.pdf" in respuesta.headers["Content-Disposition"].lower()         or "Asamblea anual.pdf" in respuesta.headers["Content-Disposition"]
    raw = respuesta.get_data()
    assert raw.startswith(b"%PDF-")
    # La página mide los 600 del correo por el alto de la hoja.
    assert b"/MediaBox [ 0 0 600 420 ]" in raw


def test_el_pdf_dibuja_las_seis_figuras_giradas_y_no_se_rompe():
    from services import canvas_pdf

    for figura in canvas.SHAPES:
        doc = leer(lienzo(rectangulo(20, 20, 160, 120, shape=figura, rot=40),
                          texto(220, 40, w=300)))
        raw = canvas_pdf.to_pdf(doc, lambda name: None)
        assert raw.startswith(b"%PDF-"), figura


def test_el_pdf_lleva_la_foto_y_respeta_el_recorte(client, database, outbox):
    browser = inside(client)
    nombre = subir_foto(browser).get_json()["name"]
    entera = pedir_pdf(browser, lienzo(imagen(0, 0, 600, 200, name=nombre),
                                       texto(40, 220))).get_data()
    recortada = pedir_pdf(browser, lienzo(
        imagen(0, 0, 600, 200, name=nombre, crop=[0.25, 0.25, 0.5, 0.5]),
        texto(40, 220))).get_data()
    assert entera.startswith(b"%PDF-") and recortada.startswith(b"%PDF-")
    # Dos fotos distintas: el recorte no se ignora.
    assert entera != recortada


def test_la_foto_de_otra_cuenta_no_se_dibuja_en_el_pdf(client, database, outbox):
    ana = inside(client)
    de_ana = subir_foto(ana).get_json()["name"]

    bea = inside(client, "bea@ejemplo.com")
    con = pedir_pdf(bea, lienzo(imagen(0, 0, 600, 200, name=de_ana),
                                texto(40, 220))).get_data()
    sin = pedir_pdf(bea, lienzo(texto(40, 220))).get_data()
    # La foto se salta, como en el correo: el PDF no la trae dentro.
    assert len(con) < len(sin) + 400


def test_el_pdf_pide_sesion_y_testigo(client, database, outbox):
    assert other(client).post("/plantillas/lienzo/pdf", data={
        "lienzo": json.dumps(lienzo(texto(40, 40)))}).status_code in (302, 403)

    browser = inside(client)
    assert browser.post("/plantillas/lienzo/pdf", data={
        "csrf_token": "no", "lienzo": json.dumps(lienzo(texto(40, 40)))
    }).status_code == 403
    assert browser.post("/plantillas/lienzo/pdf", data={
        "csrf_token": csrf(browser), "lienzo": "{no es json"}).status_code == 400


def test_la_letra_del_pdf_cae_en_una_de_las_catorce():
    from services import canvas_pdf

    # Todas las del lienzo tienen a dónde caer, y la negrita cursiva existe.
    for name in canvas.FONTS:
        cursiva = canvas_pdf.face_of({"font": name, "bold": True, "italic": True})
        assert cursiva
        assert canvas_pdf.face_of({"font": name})


def test_el_pdf_parte_las_lineas_al_ancho_de_la_caja():
    from services import canvas_pdf

    largo = "palabra " * 40
    lineas = canvas_pdf.wrap(largo, "Helvetica", 16, 200)
    assert len(lineas) > 1
    # Los saltos escritos se respetan tal cual.
    assert canvas_pdf.wrap("uno\n\ndos", "Helvetica", 16, 400) == ["uno", "", "dos"]


# ------------------------------------------- el HTML, listo para volver a cargar

def guardada(browser, database, doc):
    """Guarda el lienzo (con el párrafo que lo deja pasar) y devuelve la pieza."""
    guardar(browser, doc)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    return designs.for_account(database, cuenta["_id"])[0]


def pedir_html(browser, pieza):
    return browser.get(f"/plantillas/lienzo/{pieza['_id']}/html")


def test_la_pieza_se_baja_como_html_sin_nuestro_pie(client, database, outbox):
    browser = inside(client)
    pieza = guardada(browser, database, lienzo(texto(40, 40, text="Asamblea anual")))
    respuesta = pedir_html(browser, pieza)
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "text/html"
    assert "attachment" in respuesta.headers["Content-Disposition"]
    assert "Asamblea.html" in respuesta.headers["Content-Disposition"]
    salida = respuesta.get_data(as_text=True)
    assert "Asamblea anual" in salida and "<table" in salida
    # Sin la baja, la dirección ni la marca de agua: se ponen al enviar, y
    # dentro saldrían dos veces.
    assert "suscripción" not in salida and "Enviado con" not in salida


def test_el_html_bajado_enlaza_las_fotos_y_pesa_lo_que_la_barra(client, database, outbox):
    browser = inside(client)
    nombre = subir_foto(browser).get_json()["name"]
    pieza = guardada(browser, database, lienzo(imagen(0, 0, 600, 300, name=nombre),
                                               texto(40, 320, text="Oferta"), h=400))
    salida = pedir_html(browser, pieza).get_data(as_text=True)
    # Enlazadas al panel, como en el correo que sale, y no dentro del archivo:
    # dentro, una sola foto ya pasaba de los 102 KB.
    assert "data:image/" not in salida
    assert f"/img/{pieza['backgrounds'][0]}" in salida
    # Lo que dice la barra o menos: la barra pesa lo mismo, con el pie.
    barra = browser.post("/plantillas/lienzo/revisar", data={
        "csrf_token": csrf(browser, "/plantillas/crear"),
        "lienzo": json.dumps(pieza["canvas"])}).get_json()["bytes"]
    assert len(salida.encode("utf-8")) <= barra


def test_el_html_bajado_se_vuelve_a_cargar(client, database, outbox, monkeypatch):
    from config import Config
    from services import render

    # Como en producción: la carga solo acepta imágenes por https, y el
    # desarrollo corre en http.
    monkeypatch.setattr(Config, "APP_BASE_URL", "https://panel.panamails.com")
    browser = inside(client)
    with_plan(database, "negocio")
    nombre = subir_foto(browser).get_json()["name"]
    pieza = guardada(browser, database, lienzo(imagen(0, 0, 600, 300, name=nombre),
                                               texto(40, 320, text="Oferta"), h=400))
    assert subir(browser, pedir_html(browser, pieza).get_data(),
                 name="Copia cargada").status_code == 302

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    cargada = [one for one in designs.for_account(database, cuenta["_id"])
               if one["source"] == designs.UPLOAD][0]
    # Al enviarla lleva un solo pie: el que se le pone al enviar.
    correo = render.email_from_html(cargada["html"], plan="negocio")
    assert correo.count("Anular la suscripción") == 1

    # Borrar el lienzo no borra la imagen que sigue usando la copia cargada.
    fondo = pieza["backgrounds"][0]
    browser.post("/plantillas/borrar", data={"csrf_token": csrf(browser),
                                             "id": str(pieza["_id"])})
    assert other(client).get(f"/img/{fondo}").status_code == 200


def test_el_html_bajado_deja_las_marcas_escritas(client, database, outbox):
    browser = inside(client)
    pieza = guardada(browser, database, lienzo(texto(40, 40, text="Hola *|NOMBRE|*")))
    # Lo que se baja es la plantilla, no el correo de nadie.
    assert "*|NOMBRE|*" in pedir_html(browser, pieza).get_data(as_text=True)


def test_el_html_bajado_de_una_por_diapositivas_se_rehace(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    vieja = designs.save_canvas(database, cuenta["_id"], name="Vieja", doc={"slides": [
        {"h": 300, "bg": "#0B3B5C", "items": [texto(40, 40, text="De antes")]}]},
        backgrounds=[None])
    respuesta = browser.get(f"/plantillas/lienzo/{vieja}/html")
    assert respuesta.status_code == 200 and "De antes" in respuesta.get_data(as_text=True)
    assert designs.by_id(database, cuenta["_id"], vieja)["canvas"]["v"] == canvas.VERSION


def test_el_html_pide_sesion_y_es_de_la_cuenta(client, database, outbox):
    browser = inside(client)
    pieza = guardada(browser, database, lienzo(texto(40, 40)))
    url = f"/plantillas/lienzo/{pieza['_id']}/html"
    assert other(client).get(url).status_code in (302, 403)
    assert inside(client, email="beto@ejemplo.com").get(url).status_code == 404
    assert browser.get(f"/plantillas/lienzo/{ObjectId()}/html").status_code == 404
    # La ruta de antes, que bajaba lo de pantalla con las fotos dentro, ya no está.
    assert browser.post("/plantillas/lienzo/html", data={
        "csrf_token": csrf(browser),
        "lienzo": json.dumps(lienzo(texto(40, 40)))}).status_code == 404


def test_el_editor_baja_el_html_solo_de_la_guardada(client, database, outbox):
    browser = inside(client)
    nueva = browser.get("/plantillas/crear").get_data(as_text=True)
    # Sin guardar, el botón está pero no lleva a ningún archivo.
    assert "data-canvas-html" in nueva and '/html"' not in nueva
    pieza = guardada(browser, database, lienzo(texto(40, 40)))
    abierta = browser.get(f"/plantillas/lienzo/{pieza['_id']}").get_data(as_text=True)
    assert f'href="/plantillas/lienzo/{pieza["_id"]}/html"' in abierta


# ---------------------------------------------------- la lista de requisitos

def requisitos(doc, size=20000):
    doc = leer(doc)
    found = canvas.review(doc, size, limit=102 * 1024)
    return {one["key"]: one for one in canvas.checklist(
        doc, size, limit=102 * 1024, failed=canvas.problems(doc), found=found)}


def test_la_lista_trae_todas_las_reglas_con_sus_cifras():
    reglas = requisitos(lienzo(texto(20, 20, w=560, h=320, text=PARRAFO), h=400))
    assert list(reglas) == list(canvas.BUILD_RULES) + list(canvas.SPAM_RULES)
    assert all(one["ok"] for one in reglas.values())
    assert reglas["few_text"]["n"] == len(PARRAFO) and reglas["few_text"]["min"] == 200
    assert reglas["image_heavy"]["pct"] == 0 and reglas["image_heavy"]["max"] == 60
    assert reglas["too_big"]["kb"] == 20 and reglas["too_big"]["max"] == 102
    assert reglas["height"]["h"] == 400


def test_la_lista_dice_lo_que_falla():
    reglas = requisitos(lienzo(texto(20, 20, text="Hola"), texto(40, 30, text="Otro"),
                               boton(20, 200, href="https://bit.ly/x")))
    assert not reglas["overlap"]["ok"]
    assert not reglas["few_text"]["ok"]
    assert not reglas["shortener"]["ok"] and reglas["shortener"]["what"] == "bit.ly"
    assert reglas["bounds"]["ok"] and reglas["alt"]["ok"]


def test_cada_regla_que_no_deja_guardar_esta_en_la_lista():
    """Una regla nueva en `problems()` o en `review()` tiene que estar en la
    ventana, o esa diría que todo se cumple con Guardar apagado."""
    import re
    from pathlib import Path

    fuente = Path(canvas.__file__).read_text(encoding="utf-8")
    dichas = set(re.findall(r'add\("([a-z_]+)"\)', fuente)) - {"broken"}
    dichas |= set(re.findall(r'"key": "([a-z_]+)"', fuente))
    assert dichas and dichas <= set(canvas.BUILD_RULES) | set(canvas.SPAM_RULES)


def test_la_revision_devuelve_la_lista_con_sus_frases(client, database, outbox):
    browser = inside(client)
    datos = browser.post("/plantillas/lienzo/revisar", data={
        "csrf_token": csrf(browser, "/plantillas/crear"), "nombre": "",
        "lienzo": json.dumps(lienzo(texto(40, 40, text="Hola")))}).get_json()
    reglas = datos["rules"]
    assert len(reglas) == 1 + len(canvas.BUILD_RULES) + len(canvas.SPAM_RULES)
    assert reglas[0] == {"group": "build", "ok": False, "text": "Tiene nombre."}
    textos = " ".join(one["text"] for one in reglas)
    assert "Al menos 200 caracteres de texto (tiene 4)." in textos
    assert "La hoja mide entre 80 y 4,000 px" in textos
    # `ok` sigue siendo lo de siempre: el nombre no apaga Guardar.
    assert datos["ok"] is False
    assert not any("nombre" in one.lower() for one in datos["issues"])

    con_nombre = browser.post("/plantillas/lienzo/revisar", data={
        "csrf_token": csrf(browser, "/plantillas/crear"), "nombre": "Boletín",
        "lienzo": json.dumps(lienzo(texto(40, 40, text="Hola")))}).get_json()
    assert con_nombre["rules"][0]["ok"] is True


def test_el_editor_tiene_la_ventana_de_requisitos(client, database, outbox):
    pantalla = inside(client).get("/plantillas/crear").get_data(as_text=True)
    assert 'data-open-dialog="requisitos"' in pantalla and 'id="requisitos"' in pantalla


# ------------------------------------------------- la revisión, menos estricta

def texto_de(n):
    """Un texto de exactamente n caracteres, sin mayúsculas ni palabras gancho."""
    return ("dato " * n)[:n - 1] + "x"


def test_doscientos_caracteres_ya_alcanzan():
    assert "few_text" not in revisar(texto(20, 20, w=560, h=200, text=texto_de(250)))
    assert "few_text" in revisar(texto(20, 20, w=560, h=200, text=texto_de(150)))


def test_hasta_el_sesenta_por_ciento_de_imagen():
    # El 55 % de foto pasa, que con la mitad no pasaba; el 65 %, no.
    assert "image_heavy" not in revisar(imagen(0, 0, 600, 550),
                                        texto(20, 560, w=560, h=300, text=PARRAFO), h=1000)
    assert "image_heavy" in revisar(imagen(0, 0, 600, 650),
                                    texto(20, 660, w=560, h=300, text=PARRAFO), h=1000)


def test_el_aviso_de_imagen_dice_el_maximo():
    from i18n import t

    assert "como mucho el 60 %" in t("canvas_spam_image_heavy", pct=70, max=60)


# ------------------------------------------------------------ las líneas

def linea(x, y, w, h=2, **extra):
    return rectangulo(x, y, w, h, shape="line", **extra)


def test_una_linea_fina_se_guarda_y_una_gorda_no_es_linea():
    assert canvas.problems(leer(lienzo(linea(100, 40, 400)))) == []
    assert canvas.problems(leer(lienzo(linea(100, 40, 400, h=1)))) == []
    # Grosor 0: no hay línea.
    assert "line" in canvas.problems(leer(lienzo(linea(100, 40, 400, h=0))))
    # Una «línea» de antes, alta, se lee como el rectángulo que parecía.
    assert leer(lienzo(linea(0, 0, 600, h=160)))["items"][0]["shape"] == "rect"
    # Y un rectángulo sigue sin poder bajar de 16.
    assert "bounds" in canvas.problems(leer(lienzo(rectangulo(0, 0, 600, 4))))


def test_una_linea_derecha_es_una_celda_de_2_px_que_outlook_respeta():
    assert tipos(lienzo(linea(100, 80, 400), h=200)) == ["color"]
    doc = leer(lienzo(texto(20, 20, w=560, h=40), linea(100, 80, 400), h=200))
    html = canvas.to_html(doc, [None, None])
    assert 'height="2"' in html
    assert "line-height:2px;mso-line-height-rule:exactly" in html


def test_una_linea_girada_va_en_imagen():
    assert tipos(lienzo(linea(100, 100, 400, rot=45), h=400)) == ["picture"]
    assert canvas.problems(leer(lienzo(linea(100, 250, 400, rot=90), h=500))) == []


def test_el_editor_ofrece_la_linea_en_geometria(client, database, outbox):
    pantalla = inside(client).get("/plantillas/crear").get_data(as_text=True)
    assert 'data-shape="line"' in pantalla and ">Línea<" in pantalla
    assert 'data-prop="h"' in pantalla


# ------------------------------------------------------------ las viñetas

def test_las_vinetas_se_guardan_y_salen_una_fila_por_renglon():
    doc = leer(lienzo(texto(20, 20, w=400, h=120, text="Uno\nDos\n\nTres",
                            list=True, align="center")))
    assert doc["items"][0]["list"] is True
    html = canvas.to_html(doc, [None])
    assert html.count("&#8226;") == 3
    for renglon in ("Uno", "Dos", "Tres"):
        assert f">{renglon}</span>" in html
    # A la izquierda aunque dijera centro: si no, la viñeta de cada renglón
    # quedaría en otro sitio.
    assert 'align="left"' in html
    # Sin viñetas la clave ni se escribe: los textos de antes se leen igual.
    assert "list" not in leer(lienzo(texto(20, 20)))["items"][0]


def test_las_vinetas_salen_escapadas():
    doc = leer(lienzo(texto(20, 20, w=400, h=80, text="<b>uno</b>", list=True)))
    html = canvas.to_html(doc, [None])
    assert "<b>uno</b>" not in html and "&lt;b&gt;uno&lt;/b&gt;" in html


def test_el_pdf_dibuja_las_vinetas():
    from services import canvas_pdf

    doc = leer(lienzo(texto(20, 20, w=400, h=80, text="Uno\nDos", list=True)))
    assert canvas_pdf.to_pdf(doc, lambda name: None).startswith(b"%PDF")


def test_el_editor_ofrece_las_vinetas(client, database, outbox):
    pantalla = inside(client).get("/plantillas/crear").get_data(as_text=True)
    assert 'data-prop="list"' in pantalla and "Viñetas" in pantalla


# ------------------------------------- el HTML bajado, cargado por otra cuenta

def test_otra_cuenta_carga_el_html_con_sus_propias_copias(client, database, outbox,
                                                           monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "APP_BASE_URL", "https://panel.panamails.com")
    ana = inside(client)
    nombre = subir_foto(ana).get_json()["name"]
    pieza = guardada(ana, database, lienzo(imagen(0, 0, 600, 300, name=nombre),
                                           texto(40, 320, text="Oferta"), h=400))
    fondo = pieza["backgrounds"][0]
    bajado = pedir_html(ana, pieza).get_data()

    beto = inside(client, email="beto@ejemplo.com")
    with_plan(database, "negocio", email="beto@ejemplo.com")
    assert subir(beto, bajado, name="De Ana").status_code == 302
    de_beto = accounts.by_email(database, "beto@ejemplo.com")
    cargada = designs.for_account(database, de_beto["_id"])[0]
    # Nombra una copia suya, no la imagen de Ana.
    assert fondo not in cargada["html"]
    [copia] = __import__("services.imaging", fromlist=["x"]).names_in(cargada["html"])
    assert images.owns(database, de_beto["_id"], copia)
    # Y no le gasta ninguna de sus veinte.
    assert images.count(database, de_beto["_id"]) == 0

    # Ana borra su lienzo: la de Ana se va, la copia de Beto se queda.
    ana.post("/plantillas/borrar", data={"csrf_token": csrf(ana), "id": str(pieza["_id"])})
    assert other(client).get(f"/img/{fondo}").status_code == 404
    assert other(client).get(f"/img/{copia}").status_code == 200


def test_cargar_un_html_con_imagenes_propias_no_copia_nada(client, database, outbox,
                                                           monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "APP_BASE_URL", "https://panel.panamails.com")
    ana = inside(client)
    with_plan(database, "negocio")
    nombre = subir_foto(ana).get_json()["name"]
    pieza = guardada(ana, database, lienzo(imagen(0, 0, 600, 300, name=nombre),
                                           texto(40, 320, text="Oferta"), h=400))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    antes = database.images.count_documents({"account_id": cuenta["_id"]})
    subir(ana, pedir_html(ana, pieza).get_data(), name="Copia")
    assert database.images.count_documents({"account_id": cuenta["_id"]}) == antes
    cargada = [one for one in designs.for_account(database, cuenta["_id"])
               if one["source"] == designs.UPLOAD][0]
    assert pieza["backgrounds"][0] in cargada["html"]
