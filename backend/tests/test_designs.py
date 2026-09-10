"""Plantillas: qué HTML entra, quién puede subirlo y quién lo aprueba.

Lo que se fija aquí es lo que no se puede aflojar después. Que una pieza con
`<script>`, con un atributo de evento o de más de 102 KB no se guarde —pasado
ese tamaño Gmail recorta el correo y lo que se pierde es el botón de anular la
suscripción—. Que subir HTML propio sea de Negocio en adelante, leído de
`docs/pricing.md` y comprobado en el servidor. Y que la primera de cada cliente
la apruebe un administrador.
"""

from __future__ import annotations

import io

from conftest import login, register

from models import account as accounts
from models import design as designs
from services import html_check


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


# --------------------------------------------- la primera se aprueba a mano

def test_la_primera_espera_y_la_siguiente_entra_sola(client, database, outbox):
    browser = inside(client)
    with_plan(database, "negocio")
    cuenta = accounts.by_email(database, "ana@ejemplo.com")

    subir(browser, LIMPIO, name="Primera")
    primera = designs.for_account(database, cuenta["_id"])[0]
    assert primera["status"] == designs.PENDING

    # Todavía no está aprobada, así que la segunda también espera.
    subir(browser, LIMPIO, name="Segunda")
    assert [d["status"] for d in designs.for_account(database, cuenta["_id"])] == \
        [designs.PENDING, designs.PENDING]

    designs.review(database, primera["_id"], status=designs.APPROVED)
    subir(browser, LIMPIO, name="Tercera")
    tercera = designs.for_account(database, cuenta["_id"])[0]
    assert tercera["name"] == "Tercera"
    assert tercera["status"] == designs.APPROVED


def test_aprobar_dos_veces_no_hace_nada(client, database, outbox):
    browser = inside(client)
    with_plan(database, "negocio")
    subir(browser, LIMPIO)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    una = designs.for_account(database, cuenta["_id"])[0]

    assert designs.review(database, una["_id"], status=designs.APPROVED) is True
    assert designs.review(database, una["_id"], status=designs.REJECTED,
                          reason="me arrepentí") is False
    assert designs.by_id(database, cuenta["_id"], una["_id"])["status"] == designs.APPROVED


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
