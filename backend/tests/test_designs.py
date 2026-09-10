"""Plantillas: qué HTML entra, quién puede subirlo y quién lo aprueba.

Lo que se fija aquí es lo que no se puede aflojar después. Que una pieza con
`<script>`, con un atributo de evento o de más de 102 KB no se guarde —pasado
ese tamaño Gmail recorta el correo y lo que se pierde es el botón de anular la
suscripción—. Y que subir HTML propio sea de Negocio en adelante, leído de
`docs/pricing.md` y comprobado en el servidor.

Nadie aprueba una pieza a mano: lo que puede hacer daño lo rechaza el validador
al subirla, y la única mirada humana está una vez por cuenta, antes de su
primera campaña.
"""

from __future__ import annotations

import io

from conftest import login, register

from models import account as accounts
from models import design as designs
from models import image as images
from services import html_check, imaging, render


PASSWORD = "Contrasena-Larga1"

LIMPIO = (b"<html><body><h1>Hola socios</h1>"
          b"<img src=\"https://panamails.com/x.png\"></body></html>")


def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def csrf(client, url="/plantillas"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def foto(ancho=1600, alto=1200, formato="JPEG"):
    """Una imagen de verdad, del tamaño de la que sale de un teléfono."""
    from io import BytesIO

    from PIL import Image

    hecha = Image.new("RGB", (ancho, alto), (49, 169, 232))
    for x in range(0, ancho, 3):
        for y in range(0, alto, 5):
            hecha.putpixel((x, y), (x % 255, y % 255, (x + y) % 255))
    out = BytesIO()
    hecha.save(out, format=formato, quality=95)
    return out.getvalue()


def subir(client, raw, *, name="", filename="pieza.html"):
    return client.post("/plantillas", data={
        "csrf_token": csrf(client), "nombre": name,
        "archivo": (io.BytesIO(raw), filename)},
        content_type="multipart/form-data")


def with_plan(database, plan, email="ana@ejemplo.com"):
    accounts.set_plan(database, accounts.by_email(database, email)["_id"], plan)


# ------------------------------------------------------- el validador, solo

def test_lo_que_no_puede_entrar_en_un_correo():
    assert html_check.check(LIMPIO) == []
    assert "tag:script" in html_check.check(b"<html><body><script>x</script></body></html>")
    assert "tag:iframe" in html_check.check(b"<html><iframe src=x></iframe></html>")
    assert "tag:object" in html_check.check(b"<html><object data=x></object></html>")
    assert "tag:form" in html_check.check(b"<html><form action=/x></form></html>")
    assert "event:onclick" in html_check.check(b"<html><a onclick=x>ir</a></html>")
    assert "external:css" in html_check.check(
        b"<html><head><link rel=stylesheet href=https://x/a.css></head><body>x</body></html>")


def test_pasado_el_tope_de_gmail_no_entra():
    """102 KB: pasado eso Gmail recorta y se pierde el botón de la baja."""
    justo = b"<html><body>" + b"a" * (html_check.MAX_BYTES - 40) + b"</body></html>"
    assert len(justo) <= html_check.MAX_BYTES
    assert html_check.check(justo) == []

    pasado = b"<html><body>" + b"a" * html_check.MAX_BYTES + b"</body></html>"
    assert "too_big" in html_check.check(pasado)


def test_un_script_escrito_como_texto_no_es_un_script():
    """Se lee con un parser: «&lt;script&gt;» es texto, no código."""
    escapado = b"<html><body>&lt;script&gt;esto es un ejemplo&lt;/script&gt;</body></html>"
    assert html_check.check(escapado) == []


# ------------------------------------------------------------ quién sube

def test_el_basico_no_sube_html_y_la_pantalla_lo_dice(client, database, outbox):
    browser = inside(client)
    with_plan(database, "basico")

    pantalla = browser.get("/plantillas").get_data(as_text=True)
    assert "desde el plan Negocio" in pantalla

    subir(browser, LIMPIO)
    assert designs.count(database, accounts.by_email(database, "ana@ejemplo.com")["_id"]) == 0


def test_sin_plan_tampoco(client, database, outbox):
    browser = inside(client)
    subir(browser, LIMPIO)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert designs.count(database, cuenta["_id"]) == 0


def test_desde_negocio_si(client, database, outbox):
    browser = inside(client)
    with_plan(database, "negocio")

    subir(browser, LIMPIO, name="Boletín de socios")
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    guardadas = designs.for_account(database, cuenta["_id"])
    assert len(guardadas) == 1
    assert guardadas[0]["name"] == "Boletín de socios"
    # Y el archivo se guarda entero: es lo que hay que poder volver a mirar.
    assert "Hola socios" in guardadas[0]["html"]


def test_lo_que_no_pasa_la_revision_no_se_guarda(client, database, outbox):
    browser = inside(client)
    with_plan(database, "negocio")

    respuesta = subir(browser, b"<html><body><script>alert(1)</script></body></html>")
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert designs.count(database, cuenta["_id"]) == 0
    assert "&lt;script&gt;" in respuesta.get_data(as_text=True)


# -------------------------------------------- ninguna espera aprobación

def test_lo_que_pasa_el_validador_queda_listo(client, database, outbox):
    """Ya no hay una primera pieza en revisión: pasa el validador y se usa."""
    browser = inside(client)
    with_plan(database, "negocio")
    cuenta = accounts.by_email(database, "ana@ejemplo.com")

    respuesta = subir(browser, LIMPIO, name="Primera")
    assert "Listo, ya la puedes usar" in browser.get(
        respuesta.headers["Location"]).get_data(as_text=True)

    subir(browser, LIMPIO, name="Segunda")
    assert [d["name"] for d in designs.for_account(database, cuenta["_id"])] ==         ["Segunda", "Primera"]
    # Y no queda ningún campo de estado que alguien tenga que mover.
    assert "status" not in designs.for_account(database, cuenta["_id"])[0]


# ----------------------------------------------------- de quién es cada una

def test_la_plantilla_de_otro_no_se_borra(client, database, outbox):
    ana = inside(client)
    with_plan(database, "negocio")
    subir(ana, LIMPIO)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    suya = designs.for_account(database, cuenta["_id"])[0]

    bea = inside(client, "bea@ejemplo.com")
    bea.post("/plantillas/borrar", data={
        "csrf_token": csrf(bea), "id": str(suya["_id"])})

    assert designs.count(database, cuenta["_id"]) == 1


def test_plantillas_pide_sesion(client, database):
    assert client.get("/plantillas").status_code == 302


# ------------------------------------------------- las prediseñadas del producto

def llenar(client, key, data, *, accion="guardar"):
    body = {"csrf_token": csrf(client, f"/plantillas/nueva/{key}"),
            "accion": accion}
    body.update(data)
    return client.post(f"/plantillas/nueva/{key}", data=body)


AVISO = {"titulo": "Corte de agua", "texto": "El martes desde las 8.",
         "boton": "", "enlace": "", "nombre": "Aviso de corte"}


def test_las_prediseñadas_las_ve_tambien_el_basico(client, database, outbox):
    """Son de todos los planes; lo que es de Negocio en adelante es subir HTML."""
    browser = inside(client)
    with_plan(database, "basico")

    pantalla = browser.get("/plantillas").get_data(as_text=True)
    for name in ("Aviso", "Anuncio", "Boletín", "Convocatoria"):
        assert name in pantalla
    # Y la puerta del HTML propio sigue cerrada.
    assert "desde el plan Negocio" in pantalla


def test_cada_plantilla_se_arma_con_sus_campos():
    for key in ("aviso", "anuncio", "boletin", "convocatoria"):
        campos = {one["name"]: "x" for one in render.fields_of(key)}
        armado = render.email(key, campos, plan="negocio")
        assert "<html" in armado


def test_lo_que_escribe_el_cliente_sale_como_texto(client, database, outbox):
    """Un <script> en el título es texto, no una etiqueta."""
    browser = inside(client)
    respuesta = llenar(browser, "aviso",
                       dict(AVISO, titulo="<script>alert(1)</script>"),
                       accion="vista")
    salida = respuesta.get_data(as_text=True)
    assert "&lt;script&gt;" in salida
    assert "<script>" not in salida


def test_el_correo_siempre_trae_la_baja():
    """La regla 3: en todos los planes y sin excepción."""
    for plan in (None, "basico", "negocio", "empresa", "corporativo"):
        armado = render.email("aviso", AVISO, plan=plan)
        assert "Anular la suscripción" in armado


def test_la_marca_de_agua_es_solo_de_quien_no_la_ha_pagado():
    """La regla 4: al subir de plan desaparece sola, sin tocar la pieza."""
    assert "Enviado con" in render.email("aviso", AVISO, plan="basico")
    assert "Enviado con" in render.email("aviso", AVISO, plan=None)
    for plan in ("negocio", "empresa", "corporativo"):
        assert "Enviado con" not in render.email("aviso", AVISO, plan=plan)


def test_ni_la_baja_ni_la_marca_se_guardan_dentro_de_la_pieza(client, database, outbox):
    """Se inyectan al armar el correo, así que la pieza guardada no las lleva."""
    browser = inside(client)
    llenar(browser, "aviso", AVISO)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    guardada = designs.for_account(database, cuenta["_id"])[0]

    assert guardada["fields"]["titulo"] == "Corte de agua"
    assert "Anular" not in str(guardada["fields"])
    assert "Panamails" not in str(guardada["fields"])


def test_lo_escrito_vuelve_al_reabrirla(client, database, outbox):
    browser = inside(client)
    llenar(browser, "aviso", AVISO)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    guardada = designs.for_account(database, cuenta["_id"])[0]

    pantalla = browser.get(f"/plantillas/pieza/{guardada['_id']}").get_data(as_text=True)
    assert "Corte de agua" in pantalla
    assert "El martes desde las 8." in pantalla


def test_lo_obligatorio_no_se_puede_dejar_vacio(client, database, outbox):
    browser = inside(client)
    respuesta = llenar(browser, "aviso", dict(AVISO, texto=""))
    cuenta = accounts.by_email(database, "ana@ejemplo.com")

    assert designs.count(database, cuenta["_id"]) == 0
    assert "Falta llenar" in respuesta.get_data(as_text=True)


def test_la_pieza_de_otro_no_se_abre(client, database, outbox):
    ana = inside(client)
    llenar(ana, "aviso", AVISO)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    suya = designs.for_account(database, cuenta["_id"])[0]

    bea = inside(client, "bea@ejemplo.com")
    assert bea.get(f"/plantillas/pieza/{suya['_id']}").status_code == 404


def test_una_plantilla_que_no_existe_no_se_abre(client, database, outbox):
    browser = inside(client)
    assert browser.get("/plantillas/nueva/inventada").status_code == 404
    # Y el sobre no es una plantilla que se pueda elegir.
    assert browser.get("/plantillas/nueva/_wrap").status_code == 404


# ---------------------------------------------------------------- las imágenes

def poner_imagen(client, key, raw, *, campo="imagen", filename="foto.jpg"):
    """Elegir un archivo y pulsar «Subir imagen», como en la pantalla."""
    return client.post(f"/plantillas/nueva/{key}", data={
        "csrf_token": csrf(client, f"/plantillas/nueva/{key}"),
        "accion": f"imagen:{campo}",
        "archivo_" + campo: (io.BytesIO(raw), filename)},
        content_type="multipart/form-data")


def test_una_imagen_se_reconoce_por_dentro_y_no_por_el_nombre():
    """Un archivo llamado .png puede traer cualquier cosa."""
    assert imaging.kind(b"\x89PNG\r\n\x1a\n" + b"x" * 20) == ("png", "image/png")
    assert imaging.kind(b"\xff\xd8\xff\xe0") == ("jpg", "image/jpeg")
    assert imaging.kind(b"GIF89a" + b"x" * 10) == ("gif", "image/gif")
    assert imaging.kind(b"RIFF" + b"\x00" * 4 + b"WEBP" + b"x" * 10) == ("webp", "image/webp")
    assert imaging.kind(b"<html><script>alert(1)</script></html>") is None


def test_la_foto_del_telefono_entra_achicada():
    """Sin achicarla no cabría en la base ni abriría rápido en el correo."""
    from io import BytesIO

    from PIL import Image

    grande = foto(1600, 1200)
    data, ext, mime = imaging.shrink(grande)

    assert (ext, mime) == ("jpg", "image/jpeg")
    assert Image.open(BytesIO(data)).size[0] == imaging.WIDTH
    assert len(data) < len(grande)
    assert len(data) <= imaging.STORED_MAX


def test_lo_que_no_es_una_imagen_no_se_guarda(client, database, outbox):
    browser = inside(client)
    respuesta = poner_imagen(browser, "anuncio",
                             b"<html>esto no es una imagen</html>",
                             filename="trampa.png")

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert images.count(database, cuenta["_id"]) == 0
    assert "no es una imagen" in respuesta.get_data(as_text=True)


def test_la_imagen_se_guarda_y_el_correo_la_pide_por_su_direccion(
        client, database, outbox):
    browser = inside(client)
    poner_imagen(browser, "anuncio", foto())

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert images.count(database, cuenta["_id"]) == 1
    guardada = database.images.find_one({"account_id": cuenta["_id"]})
    assert imaging.valid_name(guardada["name"])

    # Y en el correo armado sale su dirección entera, que es lo que puede
    # pedir el buzón de quien lo recibe.
    armado = render.email("anuncio", {"titulo": "Oferta", "texto": "Hoy",
                                      "imagen": guardada["name"]},
                          plan="negocio")
    assert imaging.url_of(guardada["name"]) in armado


def test_la_imagen_se_sirve_sin_sesion_y_se_puede_guardar_un_ano(
        client, database, outbox):
    """La pide el lector de correo de cada destinatario, que no tiene sesión."""
    browser = inside(client)
    poner_imagen(browser, "anuncio", foto())
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    guardada = database.images.find_one({"account_id": cuenta["_id"]})

    fuera = other(client)
    respuesta = fuera.get(f"/img/{guardada['name']}")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "image/jpeg"
    assert respuesta.get_data() == bytes(guardada["data"])
    assert "max-age=31536000" in respuesta.headers["Cache-Control"]

    assert fuera.get("/img/noexiste123456789.jpg").status_code == 404
    # Y una dirección que ni siquiera tiene forma de nombre no llega a ser
    # una consulta.
    assert fuera.get("/img/../../etc/passwd").status_code == 404


def test_borrar_la_pieza_borra_sus_imagenes(client, database, outbox):
    browser = inside(client)
    poner_imagen(browser, "anuncio", foto())
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    nombre = database.images.find_one({"account_id": cuenta["_id"]})["name"]

    llenar(browser, "anuncio", {"titulo": "Oferta", "texto": "Hasta el viernes",
                                "boton": "", "enlace": "", "imagen": nombre,
                                "nombre": "Oferta"})
    guardada = designs.for_account(database, cuenta["_id"])[0]
    assert guardada["fields"]["imagen"] == nombre

    browser.post("/plantillas/borrar", data={
        "csrf_token": csrf(browser), "id": str(guardada["_id"])})
    assert images.count(database, cuenta["_id"]) == 0
    assert other(client).get(f"/img/{nombre}").status_code == 404


def test_la_imagen_de_otro_no_se_puede_poner_en_la_propia(client, database, outbox):
    """El campo va escondido en el formulario, así que se comprueba al llegar."""
    ana = inside(client)
    poner_imagen(ana, "anuncio", foto())
    de_ana = database.images.find_one()["name"]

    bea = inside(client, "bea@ejemplo.com")
    llenar(bea, "anuncio", {"titulo": "Oferta", "texto": "Hasta el viernes",
                            "boton": "", "enlace": "", "imagen": de_ana,
                            "nombre": "Oferta"})

    suya = accounts.by_email(database, "bea@ejemplo.com")
    assert designs.for_account(database, suya["_id"])[0]["fields"]["imagen"] == ""


def test_un_nombre_inventado_tampoco(client, database, outbox):
    browser = inside(client)
    llenar(browser, "anuncio", {
        "titulo": "Oferta", "texto": "Hasta el viernes", "boton": "", "enlace": "",
        "imagen": "https://otro-sitio.com/rastreador.png", "nombre": "Oferta"})

    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    guardada = designs.for_account(database, cuenta["_id"])[0]
    assert guardada["fields"]["imagen"] == ""


def test_hay_un_tope_de_imagenes_por_cuenta(client, database, outbox):
    """Es lo que impide que esto crezca sin control."""
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    for _ in range(images.LIMIT):
        images.save(database, cuenta["_id"], data=b"x" * 10, ext="jpg",
                    mime="image/jpeg")

    respuesta = poner_imagen(browser, "anuncio", foto())
    assert images.count(database, cuenta["_id"]) == images.LIMIT
    assert "es el máximo" in respuesta.get_data(as_text=True)
