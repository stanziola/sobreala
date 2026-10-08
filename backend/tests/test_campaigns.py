"""Enviar correos: a quién sale, a quién no, y qué lleva dentro.

Lo que se fija aquí es lo que, si se afloja, se afloja con el correo de otra
gente. Que un suprimido no reciba nada y tampoco gaste cuota (regla 1). Que cada
destinatario reciba **su** enlace de baja y que uno firmado a mano no sirva
(regla 3). Que la marca de agua dependa del plan (regla 4). Y que una campaña
que ya empezó a salir no se pueda cambiar por debajo.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import login, register

from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from models import design as designs
from models import suppression as suppressions
from services import sender, unsubscribe

PASSWORD = "Contrasena-Larga1"
WHEN = "%Y-%m-%dT%H:%M"


def other(client):
    return client.application.test_client()


def csrf(client, url="/campaigns"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


POSTAL = "Apartado 0816-00001, Santiago, Veraguas"


def ready(client, database, *, email="ana@ejemplo.com", plan="basico",
          cleared=True, howmany=3, tag="", postal=POSTAL, handle=True):
    """Una cuenta que sí puede enviar, con sus contactos y una pieza guardada."""
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    account = accounts.by_email(database, email)

    if plan:
        accounts.set_plan(database, account["_id"], plan)
    if cleared:
        accounts.clear_sending(database, account["_id"], account["_id"])
    if postal:
        accounts.set_postal(database, account["_id"], postal)
    if handle:
        # Su usuario de envío: sin él una campaña no sale de ningún sitio.
        accounts.set_handle(database, account["_id"], "c" + str(account["_id"])[-8:])
    if tag:
        accounts.add_tag(database, account["_id"], tag)

    for n in range(howmany):
        contacts.create(database, account["_id"], email=f"socio{n}@ejemplo.com",
                        name=f"Socio {n}", tags=[tag] if tag else [],
                        consent=contacts.consent_of(contacts.MEMBERS))

    piece = designs.save_filled(database, account["_id"], name="Aviso",
                                template="aviso",
                                filled={"titulo": "Corte", "texto": "El martes"})
    return browser, accounts.by_id(database, account["_id"]), piece


def catch(monkeypatch) -> list:
    """Quedarse con los correos en vez de entregarlos."""
    salidos: list = []

    def fake(message):
        salidos.append(message)
        return "de-mentira"

    monkeypatch.setattr(sender, "deliver", fake)
    return salidos


def make(browser, piece, *, subject="Aviso", tag="", when="ahora", fecha=""):
    """`tag` es una etiqueta o varias, como las manda el navegador: una casilla
    marcada por cada una, todas con el mismo nombre de campo."""
    data = {"csrf_token": csrf(browser), "asunto": subject,
            "pieza": str(piece), "lista": tag, "cuando": when}
    if fecha:
        data["fecha"] = fecha
    return browser.post("/campaigns", data=data)


def send_it(browser, database, account_id):
    one = campaigns.for_account(database, account_id)[0]
    return browser.post(f"/campaigns/{one['_id']}/send",
                        data={"csrf_token": csrf(browser)}), one


# ------------------------------------------------------------- armar y editar

def test_se_arma_se_edita_y_se_borra(client, database, outbox):
    browser, account, piece = ready(client, database)
    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)

    make(browser, piece, subject="Asamblea", when="fecha", fecha=pronto)
    suya = campaigns.for_account(database, account["_id"])[0]
    assert suya["subject"] == "Asamblea"
    assert suya["status"] == campaigns.SCHEDULED

    browser.post(f"/campaigns/{suya['_id']}", data={
        "csrf_token": csrf(browser), "asunto": "Asamblea corregida",
        "pieza": str(piece), "lista": "", "cuando": "fecha", "fecha": pronto})
    assert campaigns.by_id(database, account["_id"],
                           suya["_id"])["subject"] == "Asamblea corregida"

    browser.post(f"/campaigns/{suya['_id']}/delete",
                 data={"csrf_token": csrf(browser)})
    assert campaigns.count(database, account["_id"]) == 0


def test_no_se_programa_para_una_hora_que_ya_paso(client, database, outbox):
    browser, account, piece = ready(client, database)
    ayer = (accounts.now() - timedelta(days=1)).strftime(WHEN)

    respuesta = make(browser, piece, when="fecha", fecha=ayer)

    assert campaigns.count(database, account["_id"]) == 0
    assert "ya pasó" in respuesta.get_data(as_text=True)


def test_la_que_esta_saliendo_no_se_toca(client, database, outbox, monkeypatch):
    """Cambiarle el asunto a algo que va por la mitad es mandarle dos cosas
    distintas a dos mitades de la misma lista."""
    catch(monkeypatch)
    monkeypatch.setattr(sender, "BATCH", 2)
    browser, account, piece = ready(client, database, howmany=5)
    make(browser, piece)
    _, suya = send_it(browser, database, account["_id"])

    mitad = campaigns.by_id(database, account["_id"], suya["_id"])
    assert mitad["status"] == campaigns.SENDING
    assert not campaigns.editable(mitad)

    browser.post(f"/campaigns/{suya['_id']}", data={
        "csrf_token": csrf(browser), "asunto": "Otro asunto",
        "pieza": str(piece), "lista": "", "cuando": "ahora"})
    browser.post(f"/campaigns/{suya['_id']}/delete",
                 data={"csrf_token": csrf(browser)})

    sigue = campaigns.by_id(database, account["_id"], suya["_id"])
    assert sigue is not None and sigue["subject"] == "Aviso"


def test_la_que_ya_salio_se_corrige_y_se_borra_sin_perder_lo_enviado(
        client, database, outbox, monkeypatch):
    """Una campaña guardada sigue viva después de salir. Lo que salió no
    cambia con ella: vive aparte, con el asunto copiado."""
    catch(monkeypatch)
    browser, account, piece = ready(client, database)
    make(browser, piece)
    _, suya = send_it(browser, database, account["_id"])

    despues = campaigns.by_id(database, account["_id"], suya["_id"])
    assert despues["status"] == campaigns.SENT
    assert campaigns.editable(despues)

    browser.post(f"/campaigns/{suya['_id']}", data={
        "csrf_token": csrf(browser), "asunto": "Aviso corregido",
        "pieza": str(piece), "lista": "", "cuando": "ahora"})
    assert campaigns.by_id(database, account["_id"],
                           suya["_id"])["subject"] == "Aviso corregido"

    browser.post(f"/campaigns/{suya['_id']}/delete",
                 data={"csrf_token": csrf(browser)})
    assert campaigns.count(database, account["_id"]) == 0
    # Lo que salió, salió: sigue escrito y con el asunto que llevaba.
    historial = runs.for_account(database, account["_id"])
    assert len(historial) == 1 and historial[0]["subject"] == "Aviso"


# ------------------------------------------------------------------ el envío

def test_sale_uno_por_contacto_con_su_propia_baja(client, database, outbox,
                                                  monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=3)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    assert len(salidos) == 3
    bajas = {one["List-Unsubscribe"] for one in salidos}
    # Una por destinatario, y distintas: la regla 3 pide justo eso.
    assert len(bajas) == 3
    for message in salidos:
        assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        cuerpo = message.get_body(("html",)).get_content()
        assert "Anular la suscripción" in cuerpo
        # Plan básico: lleva marca de agua (regla 4).
        assert "Enviado con" in cuerpo


def test_el_plan_decide_la_marca_de_agua(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, plan="negocio", howmany=1)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "Anular la suscripción" in cuerpo
    assert "Enviado con" not in cuerpo


def test_un_suprimido_se_salta_y_no_gasta_cuota(client, database, outbox,
                                                monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=3)
    suppressions.add(database, account["_id"], "socio1@ejemplo.com",
                     reason=suppressions.UNSUBSCRIBE)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    assert len(salidos) == 2
    assert "socio1@ejemplo.com" not in {one["To"] for one in salidos}
    fresca = accounts.by_id(database, account["_id"])
    assert accounts.sent_this_month(fresca) == 2


def test_la_tanda_tiene_tope_y_retoma_donde_iba(client, database, outbox,
                                                monkeypatch):
    salidos = catch(monkeypatch)
    monkeypatch.setattr(sender, "BATCH", 2)
    browser, account, piece = ready(client, database, howmany=5)
    make(browser, piece)

    _, suya = send_it(browser, database, account["_id"])
    mitad = campaigns.by_id(database, account["_id"], suya["_id"])
    assert len(salidos) == 2
    assert mitad["status"] == campaigns.SENDING
    assert mitad["position"] == 2

    browser.post(f"/campaigns/{suya['_id']}/send",
                 data={"csrf_token": csrf(browser)})
    browser.post(f"/campaigns/{suya['_id']}/send",
                 data={"csrf_token": csrf(browser)})

    final = campaigns.by_id(database, account["_id"], suya["_id"])
    assert final["status"] == campaigns.SENT
    assert final["sent"] == 5
    # Y nadie recibió dos veces.
    assert len({one["To"] for one in salidos}) == 5


def test_la_misma_campana_se_manda_las_veces_que_haga_falta(
        client, database, outbox, monkeypatch):
    """Un boletín se arma una vez y sale muchas. Cada vez es un envío suyo, con
    sus cifras, y a la lista entera otra vez."""
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    make(browser, piece)

    for _ in range(3):
        _, suya = send_it(browser, database, account["_id"])

    # Dos contactos por tres vueltas: seis correos, y nadie recibió uno solo.
    assert len(salidos) == 6
    historial = runs.for_account(database, account["_id"])
    assert len(historial) == 3
    assert [una["sent"] for una in historial] == [2, 2, 2]
    assert runs.times(database, account["_id"], suya["_id"]) == 3
    # Y sigue siendo una sola campaña guardada.
    assert campaigns.count(database, account["_id"]) == 1
    fresca = accounts.by_id(database, account["_id"])
    assert accounts.sent_this_month(fresca) == 6


def test_volver_a_mandarla_pone_los_contadores_a_cero(client, database, outbox,
                                                      monkeypatch):
    catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    make(browser, piece)
    _, suya = send_it(browser, database, account["_id"])

    assert campaigns.restart(database, account["_id"], suya["_id"],
                             when=accounts.now())

    lista = campaigns.by_id(database, account["_id"], suya["_id"])
    assert lista["status"] == campaigns.SCHEDULED
    assert (lista["sent"], lista["position"], lista["errors"]) == (0, 0, [])
    # Y lo de la vuelta anterior sigue escrito.
    assert runs.for_account(database, account["_id"])[0]["sent"] == 2


def test_la_pantalla_pregunta_antes_y_no_manda_nada(client, database, outbox,
                                                    monkeypatch):
    """El GET dibuja y pregunta; el que manda es el POST. Un correo que salió
    no se puede recoger."""
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    make(browser, piece)
    suya = campaigns.for_account(database, account["_id"])[0]

    pantalla = browser.get(f"/campaigns/{suya['_id']}/send").get_data(as_text=True)

    assert "¿Seguro que quieres enviarla?" in pantalla
    assert "2 contactos" in pantalla
    assert salidos == []
    assert campaigns.by_id(database, account["_id"],
                           suya["_id"])["status"] == campaigns.SCHEDULED


def test_la_pantalla_avisa_de_que_le_llega_otra_vez_a_todos(
        client, database, outbox, monkeypatch):
    catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    make(browser, piece)
    send_it(browser, database, account["_id"])
    suya = campaigns.for_account(database, account["_id"])[0]

    pantalla = browser.get(f"/campaigns/{suya['_id']}/send").get_data(as_text=True)

    assert "también a quienes ya la recibieron" in pantalla


def test_la_cuota_del_mes_manda(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=3)
    # Casi agotada: solo queda uno.
    accounts.add_sent(database, account["_id"],
                      accounts.quota_left(account) - 1)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    assert len(salidos) == 1


def test_sin_plan_no_sale_nada(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, plan=None)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    assert salidos == []
    assert "hace falta un plan" in browser.get("/campaigns").get_data(as_text=True)


def test_sin_habilitacion_no_sale_nada(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, cleared=False)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    assert salidos == []
    assert "habilitemos el envío" in browser.get("/campaigns").get_data(as_text=True)


def test_solo_le_llega_a_la_lista_elegida(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2, tag="Socios")
    # Uno más, fuera de esa etiqueta.
    contacts.create(database, account["_id"], email="suelto@ejemplo.com",
                    name="Suelto", tags=[],
                    consent=contacts.consent_of(contacts.MEMBERS))
    make(browser, piece, tag="Socios")

    send_it(browser, database, account["_id"])

    assert len(salidos) == 2
    assert "suelto@ejemplo.com" not in {one["To"] for one in salidos}


def test_sale_a_todas_las_etiquetas_marcadas_sin_repetirle_a_nadie(
        client, database, outbox, monkeypatch):
    """Marcar dos es escribirle a quien lleve cualquiera de las dos. Y quien
    lleve las dos recibe **un solo correo**: un contacto es un solo documento
    con sus etiquetas dentro, así que la consulta no lo devuelve dos veces."""
    salidos = catch(monkeypatch)
    # Negocio, que es el primer plan donde caben dos etiquetas.
    browser, account, piece = ready(client, database, howmany=0, plan="negocio")
    for name in ("Socios", "Junta"):
        assert accounts.add_tag(database, account["_id"], name)
    quienes = {"solo-socio@ejemplo.com": ["Socios"],
               "solo-junta@ejemplo.com": ["Junta"],
               "las-dos@ejemplo.com": ["Socios", "Junta"],
               "ninguna@ejemplo.com": []}
    for email, tags in quienes.items():
        contacts.create(database, account["_id"], email=email, tags=tags,
                        consent=contacts.consent_of(contacts.MEMBERS))

    make(browser, piece, tag=["Socios", "Junta"])
    send_it(browser, database, account["_id"])

    salieron = [one["To"] for one in salidos]
    assert sorted(salieron) == ["las-dos@ejemplo.com", "solo-junta@ejemplo.com",
                                "solo-socio@ejemplo.com"]
    # Una vez cada uno, también el que lleva las dos.
    assert len(salieron) == len(set(salieron))


def test_sin_marcar_ninguna_sale_a_toda_la_lista(client, database, outbox,
                                                 monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=3, tag="Socios")
    contacts.create(database, account["_id"], email="suelto@ejemplo.com",
                    tags=[], consent=contacts.consent_of(contacts.MEMBERS))

    make(browser, piece)
    send_it(browser, database, account["_id"])

    assert len(salidos) == 4


def test_una_etiqueta_que_no_es_suya_se_descarta(client, database, outbox,
                                                 monkeypatch):
    """El formulario se puede escribir a mano. Lo que no está en el registro de
    la cuenta no filtra nada, en vez de dejar la campaña sin destinatarios."""
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)

    make(browser, piece, tag="Inventada")
    suya = campaigns.for_account(database, account["_id"])[0]

    assert campaigns.tags_of(suya) == []
    send_it(browser, database, account["_id"])
    assert len(salidos) == 2


def test_una_campana_de_antes_sigue_saliendo_a_su_etiqueta(
        client, database, outbox, monkeypatch):
    """Las que se guardaron con una sola etiqueta, en el campo viejo, no se
    migran: se leen igual."""
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2, tag="Socios")
    contacts.create(database, account["_id"], email="suelto@ejemplo.com",
                    tags=[], consent=contacts.consent_of(contacts.MEMBERS))
    make(browser, piece)
    suya = campaigns.for_account(database, account["_id"])[0]
    # Como la escribía la versión anterior: `tag` suelto y sin `tags`.
    database.campaigns.update_one({"_id": suya["_id"]},
                                  {"$set": {"tag": "Socios"},
                                   "$unset": {"tags": ""}})

    assert campaigns.tags_of(
        campaigns.by_id(database, account["_id"], suya["_id"])) == ["Socios"]
    send_it(browser, database, account["_id"])
    assert len(salidos) == 2
    assert "suelto@ejemplo.com" not in {one["To"] for one in salidos}


# -------------------------------------------------------------- darse de baja

def test_abrir_el_enlace_no_da_de_baja_pero_el_boton_si(client, database,
                                                        outbox):
    browser, account, _ = ready(client, database, howmany=1)
    quien = contacts.page(database, account["_id"])[0][0]
    token = unsubscribe.sign(quien["_id"])

    fuera = other(client)
    abierto = fuera.get(f"/unsubscribe/{token}")
    assert abierto.status_code == 200
    assert not suppressions.has(database, account["_id"], quien["email"])

    fuera.post(f"/unsubscribe/{token}")
    assert suppressions.has(database, account["_id"], quien["email"])


def test_un_testigo_inventado_no_da_de_baja_a_nadie(client, database, outbox):
    browser, account, _ = ready(client, database, howmany=1)
    quien = contacts.page(database, account["_id"])[0][0]

    fuera = other(client)
    assert fuera.get(f"/unsubscribe/{quien['_id']}.0000000000000000").status_code == 404
    assert fuera.post(f"/unsubscribe/{quien['_id']}.0000000000000000").status_code == 404
    assert not suppressions.has(database, account["_id"], quien["email"])


def test_la_baja_no_se_puede_levantar_desde_el_panel(client, database, outbox):
    """Motivo `unsubscribe`: solo vuelve quien se vuelva a suscribir."""
    browser, account, _ = ready(client, database, howmany=1)
    quien = contacts.page(database, account["_id"])[0][0]
    other(client).post(f"/unsubscribe/{unsubscribe.sign(quien['_id'])}")

    assert suppressions.lift(database, account["_id"], quien["email"]) is False


# ------------------------------------------------------------ quién la ve

def test_la_pantalla_no_es_para_administradores(client, database, outbox):
    from test_admin import make_admin

    admin, _ = make_admin(client, database)

    respuesta = admin.get("/campaigns")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/admin/")


def test_la_fila_esta_en_los_dos_menus(client, database, outbox):
    from pathlib import Path

    browser, _, _ = ready(client, database)

    panel = browser.get("/dashboard").get_data(as_text=True)
    assert "Enviar correos" in panel
    assert "/campaigns" in panel

    raiz = Path(__file__).resolve().parent.parent.parent
    sitio = (raiz / "landing" / "index.html").read_text(encoding="utf-8")
    assert "Enviar correos" in sitio
    assert "/campaigns" in sitio


# --------------------------------------------------------- la rama de SES

def test_la_entrega_por_ses_llega_a_ses(monkeypatch):
    """Esta rama no la recorría ninguna prueba, porque todas sustituyen la
    entrega para no mandar correo de verdad.

    Por eso vivió escondido que leía una configuración que no existía: con SES
    de verdad, cada destinatario moría en un AttributeError y la campaña decía
    «0 salieron, 1 falló».
    """
    from email.message import EmailMessage

    import boto3

    from config import Config

    pedido = {}

    class Falso:
        def send_raw_email(self, **kwargs):
            pedido.update(kwargs)
            return {"MessageId": "mensaje-1"}

    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(boto3, "client", lambda *a, **k: Falso())

    mensaje = EmailMessage()
    mensaje["To"] = "socio@ejemplo.com"
    mensaje.set_content("hola")

    # Sin conjunto de configuración puesto, que es como está hoy: se envía igual.
    monkeypatch.setattr(Config, "SES_CONFIGURATION_SET", "")
    assert sender.deliver(mensaje) == "mensaje-1"
    assert b"socio@ejemplo.com" in pedido["RawMessage"]["Data"]
    assert "ConfigurationSetName" not in pedido

    # Y con él puesto, se le dice a SES dónde publicar los eventos.
    monkeypatch.setattr(Config, "SES_CONFIGURATION_SET", "campanas")
    sender.deliver(mensaje)
    assert pedido["ConfigurationSetName"] == "campanas"
