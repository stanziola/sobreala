"""El correo individual: a una persona, con un archivo si hace falta.

Es una campaña de una persona, así que lo que fijan estas pruebas es que **lleve
lo mismo que una campaña** (la baja y su cabecera, la etiqueta de SES, la marca
de agua, la cuota, la supresión) y su detalle, que el adjunto **se reconozca
por lo que es** y no por su nombre, y que **no se guarde**: va directo en el
correo, sin S3.
"""

from __future__ import annotations

import io

import pytest
from test_campaigns import catch, csrf, ready

from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import suppression as suppressions
from services import attachments, storage

PDF = b"%PDF-1.4\n% un documento de mentira\n%%EOF\n"


@pytest.fixture
def sin_s3(monkeypatch):
    """El adjunto no pasa por S3: si algo intenta guardarlo o leerlo, falla."""
    def no(*args, **kwargs):
        raise AssertionError("el adjunto no se guarda")
    monkeypatch.setattr(storage, "put", no)
    monkeypatch.setattr(storage, "get", no)


def escribir(browser, *, para="socio0@ejemplo.com", asunto="Tu estado de cuenta",
             mensaje="Hola,\n\nTe envío tu estado de cuenta.", archivo=None):
    data = {"csrf_token": csrf(browser), "para": para, "asunto": asunto,
            "mensaje": mensaje}
    if archivo is not None:
        data["archivo"] = archivo
    return browser.post("/campaigns/write", data=data,
                        content_type="multipart/form-data")


def test_la_pantalla_sale_en_enviar_correos(client, database, outbox):
    browser, _, _ = ready(client, database)
    assert 'href="/campaigns/write"' in browser.get("/campaigns").get_data(as_text=True)
    pantalla = browser.get("/campaigns/write").get_data(as_text=True)
    # El archivo no necesita S3: el campo está aunque no haya dónde guardar.
    for campo in ('name="para"', 'name="asunto"', 'name="mensaje"', 'name="archivo"'):
        assert campo in pantalla


def test_sale_a_esa_persona_con_su_baja_y_su_detalle(client, database, outbox,
                                                     monkeypatch, sin_s3):
    browser, cuenta, _ = ready(client, database)
    salidos = catch(monkeypatch)

    respuesta = escribir(browser, archivo=(io.BytesIO(PDF), "estado.pdf"))

    correo, = salidos
    assert correo["To"] == "socio0@ejemplo.com"
    assert correo["Subject"] == "Tu estado de cuenta"
    # Lo mismo que una campaña: la baja de un clic y la etiqueta de SES.
    assert correo["List-Unsubscribe"].startswith("<")
    assert "campaign=" in correo["X-SES-MESSAGE-TAGS"]
    html = correo.get_body(preferencelist=("html",)).get_content()
    assert "Te envío tu estado de cuenta." in html
    # Con su archivo, con el nombre que tenía y el tipo de lo que es.
    adjunto, = list(correo.iter_attachments())
    assert adjunto.get_filename() == "estado.pdf"
    assert adjunto.get_content_type() == "application/pdf"
    assert adjunto.get_content() == PDF
    # Cuenta uno de la cuota.
    assert sum(accounts.by_id(database, cuenta["_id"]).get("sent_counts", {}).values()) == 1

    # Aterriza en su detalle, que es un envío como cualquier otro.
    assert "/campaigns/sent/" in respuesta.headers["Location"]
    detalle = browser.get(respuesta.headers["Location"]).get_data(as_text=True)
    assert "Individual · socio0@ejemplo.com" in detalle
    assert "Todos mis contactos" not in detalle
    envio, = runs.for_account(database, cuenta["_id"])
    assert envio["to"] == "socio0@ejemplo.com" and envio["sent"] == 1
    lista = browser.get("/campaigns").get_data(as_text=True)
    assert "Individual · socio0@ejemplo.com" in lista
    # No sale en «Tus campañas»: no se edita ni se vuelve a mandar.
    suya = campaigns.for_account(database, cuenta["_id"])[0]
    assert suya["kind"] == campaigns.SINGLE
    # Del archivo no queda nada: ni él ni su nombre.
    assert "attachment" not in suya
    assert "estado.pdf" not in str(suya)
    assert browser.get(f"/campaigns/{suya['_id']}").headers["Location"].endswith("/campaigns")
    assert browser.post(f"/campaigns/{suya['_id']}/send",
                        data={"csrf_token": csrf(browser)}).headers["Location"].endswith("/campaigns")
    assert len(salidos) == 1


def test_sin_archivo_tambien_sale(client, database, outbox, monkeypatch):
    browser, _, _ = ready(client, database)
    salidos = catch(monkeypatch)

    escribir(browser)

    correo, = salidos
    assert list(correo.iter_attachments()) == []


def test_solo_a_alguien_de_sus_contactos(client, database, outbox, monkeypatch):
    browser, _, _ = ready(client, database)
    salidos = catch(monkeypatch)

    pantalla = escribir(browser, para="desconocido@otro.com").get_data(as_text=True)

    assert "no está en tus contactos" in pantalla
    assert salidos == []


def test_a_quien_se_dio_de_baja_no_se_le_escribe(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    suppressions.add(database, cuenta["_id"], "socio0@ejemplo.com")
    salidos = catch(monkeypatch)

    pantalla = escribir(browser).get_data(as_text=True)

    assert "se dio de baja" in pantalla
    assert salidos == []
    assert campaigns.for_account(database, cuenta["_id"]) == []


def test_un_archivo_de_otro_tipo_o_muy_grande_no_entra(client, database, outbox,
                                                       monkeypatch, sin_s3):
    browser, cuenta, _ = ready(client, database)
    salidos = catch(monkeypatch)

    # Un .pdf que por dentro no lo es.
    pantalla = escribir(browser, archivo=(io.BytesIO(b"MZ ejecutable"), "factura.pdf"))
    assert "no se puede adjuntar" in pantalla.get_data(as_text=True)

    grande = PDF + b"0" * attachments.MAX_BYTES
    pantalla = escribir(browser, archivo=(io.BytesIO(grande), "grande.pdf"))
    assert "pasa de 5 MB" in pantalla.get_data(as_text=True)

    assert salidos == []
    assert campaigns.for_account(database, cuenta["_id"]) == []


def test_sin_plan_no_sale(client, database, outbox, monkeypatch):
    browser, _, _ = ready(client, database, plan=None)
    salidos = catch(monkeypatch)

    pantalla = escribir(browser).get_data(as_text=True)

    assert "Todavía no puedes enviar" in pantalla
    assert salidos == []


def test_lo_que_se_reconoce_como_adjunto():
    assert attachments.kind_of(PDF) == ("application", "pdf", "pdf")
    assert attachments.kind_of(b"\x89PNG\r\n\x1a\n" + b"0" * 10)[2] == "png"
    assert attachments.kind_of(b"\xff\xd8\xff\xe0" + b"0" * 10)[2] == "jpg"
    assert attachments.kind_of(b"MZ") is None
    assert attachments.kind_of(b"PK\x03\x04 no es un zip") is None
    assert attachments.safe_name("C:\\docs\\Estado de cuenta (1).PDF", "pdf") == \
        "Estado de cuenta 1.pdf"
    assert attachments.safe_name("../../etc/passwd", "pdf") == "passwd.pdf"
