"""El correo individual: a una persona, con un archivo si hace falta.

Es una campaña de una persona, así que lleva **casi** lo mismo que una campaña:
la etiqueta de SES, la dirección postal, la cuota, la supresión y su detalle.
Desde octubre de 2026 cambia en tres cosas, y son las que fijan estas pruebas:

  * sale **sin baja y sin marca de agua**, ni en el Básico (la campaña normal
    sigue con las dos);
  * va **a cualquier dirección**, esté o no en Contactos, y sin guardarla;
  * el archivo **no va adjunto**: se guarda 30 días y el correo lleva un botón
    para bajarlo. Abrir el enlace no lo baja (los escáneres de correo los
    abren); pulsar «Descargar» sí, y eso anota `download`.
"""

from __future__ import annotations

import io
import re
from datetime import timedelta

from test_campaigns import catch, csrf, make, ready, send_it

from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from models import event as events
from models import suppression as suppressions
from services import attachments

PDF = b"%PDF-1.4\n% un documento de mentira\n%%EOF\n"


def escribir(browser, *, para="socio0@ejemplo.com", asunto="Tu estado de cuenta",
             mensaje="Hola,\n\nTe envío tu estado de cuenta.", archivo=None):
    data = {"csrf_token": csrf(browser), "para": para, "asunto": asunto,
            "mensaje": mensaje}
    if archivo is not None:
        data["archivo"] = archivo
    return browser.post("/campaigns/write", data=data,
                        content_type="multipart/form-data")


def html_de(correo):
    return correo.get_body(preferencelist=("html",)).get_content()


def enlace_de_descarga(correo):
    return re.search(r'href="https?://[^"/]+(/d/[^"]+)"', html_de(correo)).group(1)


def test_la_pantalla_sale_en_enviar_correos(client, database, outbox):
    browser, _, _ = ready(client, database)
    assert 'href="/campaigns/write"' in browser.get("/campaigns").get_data(as_text=True)
    pantalla = browser.get("/campaigns/write").get_data(as_text=True)
    for campo in ('name="para"', 'name="asunto"', 'name="mensaje"', 'name="archivo"'):
        assert campo in pantalla


def test_sale_sin_baja_ni_marca_de_agua_y_con_su_detalle(client, database, outbox,
                                                         monkeypatch):
    browser, cuenta, _ = ready(client, database)  # Básico: la campaña lleva marca
    salidos = catch(monkeypatch)

    respuesta = escribir(browser)

    correo, = salidos
    assert correo["To"] == "socio0@ejemplo.com"
    assert correo["Subject"] == "Tu estado de cuenta"
    assert "campaign=" in correo["X-SES-MESSAGE-TAGS"]
    # Ni la baja de un clic, ni el pie de baja, ni la marca de agua.
    assert correo["List-Unsubscribe"] is None
    html = html_de(correo)
    assert "Te envío tu estado de cuenta." in html
    assert "Anular la suscripción" not in html and "Enviado con" not in html
    # La dirección postal sí.
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) in html
    assert list(correo.iter_attachments()) == []
    # Cuenta uno de la cuota.
    assert sum(accounts.by_id(database, cuenta["_id"]).get("sent_counts", {}).values()) == 1

    # Aterriza en su detalle, que es un envío como cualquier otro.
    assert "/campaigns/sent/" in respuesta.headers["Location"]
    detalle = browser.get(respuesta.headers["Location"]).get_data(as_text=True)
    assert "Individual · socio0@ejemplo.com" in detalle
    envio, = runs.for_account(database, cuenta["_id"])
    assert envio["to"] == "socio0@ejemplo.com" and envio["sent"] == 1
    # No se edita ni se vuelve a mandar.
    suya = campaigns.for_account(database, cuenta["_id"])[0]
    assert suya["kind"] == campaigns.SINGLE
    assert browser.get(f"/campaigns/{suya['_id']}").headers["Location"].endswith("/campaigns")
    assert len(salidos) == 1


def test_la_campana_normal_sigue_con_baja_y_marca(client, database, outbox, monkeypatch):
    browser, cuenta, pieza = ready(client, database)
    salidos = catch(monkeypatch)
    pronto = (accounts.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    make(browser, pieza, when="fecha", fecha=pronto)
    send_it(browser, database, cuenta["_id"])

    assert salidos and all(c["List-Unsubscribe"] for c in salidos)
    assert "Anular la suscripción" in html_de(salidos[0])
    assert "Enviado con" in html_de(salidos[0])


def test_a_cualquier_direccion_sin_guardarla(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    antes = database.contacts.count_documents({"account_id": cuenta["_id"]})
    salidos = catch(monkeypatch)

    respuesta = escribir(browser, para="Nueva.Persona@Otro.com")

    correo, = salidos
    assert correo["To"] == "nueva.persona@otro.com"
    assert database.contacts.count_documents({"account_id": cuenta["_id"]}) == antes
    assert contacts.by_emails(database, cuenta["_id"], ["nueva.persona@otro.com"]) == {}
    detalle = browser.get(respuesta.headers["Location"]).get_data(as_text=True)
    assert "No está en tus contactos" in detalle


def test_una_direccion_mal_escrita_no_sale(client, database, outbox, monkeypatch):
    browser, _, _ = ready(client, database)
    salidos = catch(monkeypatch)
    pantalla = escribir(browser, para="esto no es un correo").get_data(as_text=True)
    assert "no es una dirección de correo" in pantalla and salidos == []


def test_a_quien_se_dio_de_baja_no_se_le_escribe(client, database, outbox, monkeypatch):
    browser, cuenta, _ = ready(client, database)
    suppressions.add(database, cuenta["_id"], "socio0@ejemplo.com")
    suppressions.add(database, cuenta["_id"], "fuera@otro.com",
                     reason=suppressions.HARD_BOUNCE)
    salidos = catch(monkeypatch)

    for para in ("socio0@ejemplo.com", "fuera@otro.com"):
        pantalla = escribir(browser, para=para).get_data(as_text=True)
        assert "se dio de baja" in pantalla

    assert salidos == []
    assert campaigns.for_account(database, cuenta["_id"]) == []


def test_el_archivo_va_como_enlace_y_se_sabe_si_lo_bajo(client, database, outbox,
                                                         monkeypatch):
    browser, cuenta, _ = ready(client, database)
    salidos = catch(monkeypatch)

    respuesta = escribir(browser, archivo=(io.BytesIO(PDF), "estado.pdf"))

    correo, = salidos
    assert list(correo.iter_attachments()) == []
    html = html_de(correo)
    assert "estado.pdf" in html and "Descargar el archivo" in html
    enlace = enlace_de_descarga(correo)
    guardado = database.downloads.find_one({"account_id": cuenta["_id"]})
    assert guardado["name"] == "estado.pdf" and bytes(guardado["data"]) == PDF

    # Quien lo recibe no tiene sesión. Abrir el enlace no lo baja ni lo anota.
    persona = client.application.test_client()
    pagina = persona.get(enlace)
    assert pagina.status_code == 200 and "estado.pdf" in pagina.get_data(as_text=True)
    assert database.events.count_documents({"kind": events.DOWNLOAD}) == 0

    # Pulsar «Descargar» sí.
    with persona.session_transaction() as sess:
        token = sess["_csrf"]
    bajada = persona.post(enlace, data={"csrf_token": token})
    assert bajada.data == PDF and bajada.mimetype == "application/pdf"
    assert "attachment" in bajada.headers["Content-Disposition"]
    hecho, = list(database.events.find({"kind": events.DOWNLOAD}))
    assert hecho["account_id"] == cuenta["_id"]
    assert hecho["email_normalized"] == "socio0@ejemplo.com"

    # Y el detalle lo dice.
    detalle = browser.get(respuesta.headers["Location"]).get_data(as_text=True)
    assert "Bajó el archivo" in detalle


def test_un_enlace_falso_o_vencido_no_baja_nada(client, database, outbox, monkeypatch):
    browser, _, _ = ready(client, database)
    salidos = catch(monkeypatch)
    escribir(browser, archivo=(io.BytesIO(PDF), "estado.pdf"))
    enlace = enlace_de_descarga(salidos[0])
    persona = client.application.test_client()

    falso = enlace[:-4] + ("0000" if not enlace.endswith("0000") else "1111")
    assert persona.get(falso).status_code == 404

    database.downloads.update_many({}, {"$set": {"expires_at": accounts.now()
                                                 - timedelta(minutes=1)}})
    vencido = persona.get(enlace)
    assert vencido.status_code == 410 and "ya no está" in vencido.get_data(as_text=True)


def test_un_archivo_de_otro_tipo_o_muy_grande_no_entra(client, database, outbox,
                                                       monkeypatch):
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
    assert database.downloads.count_documents({}) == 0


def test_sin_plan_no_sale(client, database, outbox, monkeypatch):
    browser, _, _ = ready(client, database, plan=None)
    salidos = catch(monkeypatch)

    pantalla = escribir(browser).get_data(as_text=True)

    assert "Todavía no puedes enviar" in pantalla
    assert salidos == []


def test_lo_que_se_reconoce_como_archivo():
    assert attachments.kind_of(PDF) == ("application", "pdf", "pdf")
    assert attachments.kind_of(b"\x89PNG\r\n\x1a\n" + b"0" * 10)[2] == "png"
    assert attachments.kind_of(b"\xff\xd8\xff\xe0" + b"0" * 10)[2] == "jpg"
    assert attachments.kind_of(b"MZ") is None
    assert attachments.kind_of(b"PK\x03\x04 no es un zip") is None
    assert attachments.safe_name("C:\\docs\\Estado de cuenta (1).PDF", "pdf") == \
        "Estado de cuenta 1.pdf"
    assert attachments.safe_name("../../etc/passwd", "pdf") == "passwd.pdf"
