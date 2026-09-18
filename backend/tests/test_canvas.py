"""El lienzo de «Crear plantilla»: de coordenadas libres a un correo.

Lo que se fija aquí es lo que no puede aflojarse. Que cada caja salga en su
coordenada, medida en tablas que Outlook respeta. Que el texto salga escapado y
las columnas pasen para que el envío las llene. Que nada encimado, fuera de su
diapositiva o con un enlace que ejecuta código llegue a guardarse. Y que las
imágenes de otra cuenta no se puedan colar por el JSON.
"""

from __future__ import annotations

import io
import json
from io import BytesIO

from PIL import Image

from models import account as accounts
from models import design as designs
from models import image as images
from services import canvas
from test_campaigns import catch, make, ready, send_it
from test_designs import csrf, foto, inside, other


def lienzo(*items, h=300, bg="#FFFFFF"):
    return {"slides": [{"h": h, "bg": bg, "items": list(items)}]}


def texto(x, y, w=200, h=40, text="Hola", **extra):
    return dict({"t": "text", "x": x, "y": y, "w": w, "h": h, "text": text,
                 "font": "Arial", "size": 18, "color": "#18181B"}, **extra)


def boton(x, y, w=160, h=44, **extra):
    return dict({"t": "button", "x": x, "y": y, "w": w, "h": h, "text": "Ver",
                 "href": "https://coop.com", "font": "Arial", "size": 16,
                 "color": "#FFFFFF", "bg": "#31A9E8"}, **extra)


def leer(doc):
    return canvas.parse(json.dumps(doc))


# ------------------------------------------------------------ qué no se guarda

def test_un_texto_encimado_no_se_guarda():
    doc = leer(lienzo(texto(40, 40), boton(100, 60)))
    assert "overlap" in canvas.problems(doc)
    # Tocarse por el borde sí se puede.
    assert canvas.problems(leer(lienzo(texto(40, 40, w=100), boton(140, 40)))) == []


def test_lo_que_se_sale_de_la_diapositiva_no_se_guarda():
    assert "bounds" in canvas.problems(leer(lienzo(texto(500, 40, w=200))))
    assert "bounds" in canvas.problems(leer(lienzo(texto(40, 280, h=40))))


def test_solo_fuentes_de_correo_y_enlaces_seguros():
    assert "font" in canvas.problems(leer(lienzo(texto(0, 0, font="Comic Neue"))))
    assert "href" in canvas.problems(leer(lienzo(boton(0, 0, href="javascript:alert(1)"))))
    assert "href" in canvas.problems(leer(lienzo(boton(0, 0, href='https://x.com" onclick="x'))))
    assert canvas.problems(leer(lienzo(boton(0, 0, href="mailto:hola@coop.com")))) == []


def test_la_letra_no_baja_de_14():
    assert "size" in canvas.problems(leer(lienzo(texto(0, 0, size=10))))


def test_una_imagen_ajena_no_entra():
    doc = leer(lienzo({"t": "image", "x": 0, "y": 0, "w": 600, "h": 300,
                       "name": "de-otro.jpg"}))
    assert "image" in canvas.problems(doc, owns=lambda name: False)


def test_un_molinillo_se_pide_mover():
    """Cuatro cajas que se rodean sin tocarse no caben en ninguna tabla."""
    doc = leer(lienzo(texto(0, 0, w=200, h=100), texto(200, 0, w=100, h=200),
                      texto(100, 200, w=200, h=100), texto(0, 100, w=100, h=200),
                      h=400))
    assert "tangled" in canvas.problems(doc)


def test_lo_que_no_es_un_lienzo():
    assert canvas.problems(canvas.parse("no es json")) == ["broken"]
    assert canvas.problems(canvas.parse('{"slides": []}')) == ["empty"]


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
    html = canvas.to_html(leer(lienzo(texto(40, 40, w=200), boton(400, 40))), [None])
    # El hueco entre las dos: de 240 a 400.
    assert 'width="160"' in html


def test_el_texto_sale_escapado_y_las_columnas_pasan():
    html = canvas.to_html(leer(lienzo(texto(0, 0, text="Hola *|EDAD|* <script>x</script>"))),
                          [None])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "*|EDAD|*" in html


def test_el_fondo_va_tambien_para_outlook():
    html = canvas.to_html(leer(lienzo(texto(0, 0))), ["https://panel/img/fondo.jpg"])
    assert "background-image:url('https://panel/img/fondo.jpg')" in html
    assert "<v:fill" in html and "https://panel/img/fondo.jpg" in html


def test_el_fondo_se_funde_al_doble():
    foto_raw = foto(800, 600)
    doc = leer(lienzo({"t": "image", "x": 0, "y": 0, "w": 600, "h": 300,
                       "name": "a.jpg"}, h=300))
    fondo = canvas.backgrounds(doc, lambda name: foto_raw)[0]
    with Image.open(BytesIO(fondo)) as hecho:
        assert hecho.size == (1200, 600)
    # Sin imágenes no hay fondo: basta el color.
    assert canvas.backgrounds(leer(lienzo(texto(0, 0))), lambda n: None) == [None]


# ------------------------------------------------------------ las rutas

def guardar(browser, doc, *, url="/plantillas/crear", nombre="Asamblea"):
    return browser.post(url, data={"csrf_token": csrf(browser, url),
                                   "nombre": nombre, "lienzo": json.dumps(doc)})


def test_crear_guarda_el_lienzo(client, database, outbox):
    browser = inside(client)
    respuesta = guardar(browser, lienzo(texto(40, 40, text="Asamblea anual")))
    assert respuesta.status_code == 302

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    hecha = designs.for_account(database, cuenta["_id"])[0]
    assert hecha["source"] == designs.CANVAS
    assert hecha["canvas"]["slides"][0]["items"][0]["text"] == "Asamblea anual"
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


def subir_foto(browser, raw=None):
    return browser.post("/plantillas/lienzo/imagen", data={
        "csrf_token": csrf(browser), "archivo": (io.BytesIO(raw or foto()), "foto.jpg")},
        content_type="multipart/form-data")


def test_la_foto_del_lienzo_se_guarda_al_doble(client, database, outbox):
    browser = inside(client)
    respuesta = subir_foto(browser, foto(3000, 2000))
    datos = respuesta.get_json()
    assert datos["width"] == 1200
    assert datos["url"].endswith(datos["name"])


def test_el_fondo_fundido_no_cuenta_contra_el_tope(client, database, outbox):
    browser = inside(client)
    nombre = subir_foto(browser).get_json()["name"]
    guardar(browser, lienzo({"t": "image", "x": 0, "y": 0, "w": 600, "h": 300,
                             "name": nombre}, texto(40, 40, text="Oferta del mes")))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    hecha = designs.for_account(database, cuenta["_id"])[0]
    fondo = hecha["backgrounds"][0]

    assert fondo and fondo != nombre
    assert images.count(database, cuenta["_id"]) == 1
    assert other(client).get(f"/img/{fondo}").status_code == 200


def test_volver_a_guardar_borra_el_fondo_viejo_pero_no_el_de_la_copia(
        client, database, outbox):
    browser = inside(client)
    nombre = subir_foto(browser).get_json()["name"]
    doc = lienzo({"t": "image", "x": 0, "y": 0, "w": 600, "h": 300, "name": nombre},
                 texto(40, 40, text="Oferta"))
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
    guardar(bea, lienzo({"t": "image", "x": 0, "y": 0, "w": 600, "h": 300,
                         "name": de_ana}, texto(40, 40)))
    suya = accounts.by_email(database, "bea@ejemplo.com")
    assert designs.count(database, suya["_id"]) == 0


def test_el_lienzo_de_otro_no_se_abre(client, database, outbox):
    ana = inside(client)
    guardar(ana, lienzo(texto(40, 40)))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    suya = designs.for_account(database, cuenta["_id"])[0]

    bea = inside(client, "bea@ejemplo.com")
    assert bea.get(f"/plantillas/lienzo/{suya['_id']}").status_code == 404


def test_la_vista_previa_es_un_correo_aislado(client, database, outbox):
    browser = inside(client)
    respuesta = browser.post("/plantillas/lienzo/vista", data={
        "csrf_token": csrf(browser, "/plantillas/crear"),
        "lienzo": json.dumps(lienzo(texto(40, 40, text="Hola <b>socio</b>")))})
    assert "default-src 'none'" in respuesta.headers["Content-Security-Policy"]
    salida = respuesta.get_data(as_text=True)
    assert "Hola &lt;b&gt;socio&lt;/b&gt;" in salida
    assert "Anular la suscripción" in salida


def test_un_lienzo_sale_en_una_campana_con_su_baja(client, database, outbox,
                                                   monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, _ = ready(client, database, howmany=2)
    pieza = designs.save_canvas(
        database, account["_id"], name="Asamblea",
        doc=leer(lienzo(texto(40, 40, w=400, text="Asamblea anual de socios"),
                        boton(40, 120))),
        backgrounds=[None])
    make(browser, pieza)

    send_it(browser, database, account["_id"])

    assert len(salidos) == 2
    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "Asamblea anual de socios" in cuerpo
    assert 'href="https://coop.com"' in cuerpo
    assert "Anular la suscripción" in cuerpo
