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
from models import contact as contacts
from models import design as designs
from models import suppression as suppressions
from services import sender, unsubscribe

PASSWORD = "Contrasena-Larga1"
WHEN = "%Y-%m-%dT%H:%M"


def other(client):
    return client.application.test_client()


def csrf(client, url="/envios"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def ready(client, database, *, email="ana@ejemplo.com", plan="basico",
          cleared=True, howmany=3, tag=""):
    """Una cuenta que sí puede enviar, con sus contactos y una pieza guardada."""
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    account = accounts.by_email(database, email)

    if plan:
        accounts.set_plan(database, account["_id"], plan)
    if cleared:
        accounts.clear_sending(database, account["_id"], account["_id"])
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
    data = {"csrf_token": csrf(browser), "asunto": subject,
            "pieza": str(piece), "lista": tag, "cuando": when}
    if fecha:
        data["fecha"] = fecha
    return browser.post("/envios", data=data)


def send_it(browser, database, account_id):
    one = campaigns.for_account(database, account_id)[0]
    return browser.post(f"/envios/{one['_id']}/mandar",
                        data={"csrf_token": csrf(browser)}), one


# ------------------------------------------------------------- armar y editar

def test_se_arma_se_edita_y_se_borra(client, database, outbox):
    browser, account, piece = ready(client, database)
    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)

    make(browser, piece, subject="Asamblea", when="fecha", fecha=pronto)
    suya = campaigns.for_account(database, account["_id"])[0]
    assert suya["subject"] == "Asamblea"
    assert suya["status"] == campaigns.SCHEDULED

    browser.post(f"/envios/{suya['_id']}", data={
        "csrf_token": csrf(browser), "asunto": "Asamblea corregida",
        "pieza": str(piece), "lista": "", "cuando": "fecha", "fecha": pronto})
    assert campaigns.by_id(database, account["_id"],
                           suya["_id"])["subject"] == "Asamblea corregida"

    browser.post(f"/envios/{suya['_id']}/borrar",
                 data={"csrf_token": csrf(browser)})
    assert campaigns.count(database, account["_id"]) == 0


def test_no_se_programa_para_una_hora_que_ya_paso(client, database, outbox):
    browser, account, piece = ready(client, database)
    ayer = (accounts.now() - timedelta(days=1)).strftime(WHEN)

    respuesta = make(browser, piece, when="fecha", fecha=ayer)

    assert campaigns.count(database, account["_id"]) == 0
    assert "ya pasó" in respuesta.get_data(as_text=True)


def test_lo_que_ya_salio_no_se_toca(client, database, outbox, monkeypatch):
    catch(monkeypatch)
    browser, account, piece = ready(client, database)
    make(browser, piece)
    respuesta, suya = send_it(browser, database, account["_id"])

    despues = campaigns.by_id(database, account["_id"], suya["_id"])
    assert despues["status"] == campaigns.SENT
    assert not campaigns.editable(despues)
    browser.post(f"/envios/{suya['_id']}/borrar",
                 data={"csrf_token": csrf(browser)})
    assert campaigns.count(database, account["_id"]) == 1


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

    browser.post(f"/envios/{suya['_id']}/mandar",
                 data={"csrf_token": csrf(browser)})
    browser.post(f"/envios/{suya['_id']}/mandar",
                 data={"csrf_token": csrf(browser)})

    final = campaigns.by_id(database, account["_id"], suya["_id"])
    assert final["status"] == campaigns.SENT
    assert final["sent"] == 5
    # Y nadie recibió dos veces.
    assert len({one["To"] for one in salidos}) == 5


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
    assert "hace falta un plan" in browser.get("/envios").get_data(as_text=True)


def test_sin_habilitacion_no_sale_nada(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, cleared=False)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    assert salidos == []
    assert "habilitemos el envío" in browser.get("/envios").get_data(as_text=True)


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


# -------------------------------------------------------------- darse de baja

def test_abrir_el_enlace_no_da_de_baja_pero_el_boton_si(client, database,
                                                        outbox):
    browser, account, _ = ready(client, database, howmany=1)
    quien = contacts.page(database, account["_id"])[0][0]
    token = unsubscribe.sign(quien["_id"])

    fuera = other(client)
    abierto = fuera.get(f"/baja/{token}")
    assert abierto.status_code == 200
    assert not suppressions.has(database, account["_id"], quien["email"])

    fuera.post(f"/baja/{token}")
    assert suppressions.has(database, account["_id"], quien["email"])


def test_un_testigo_inventado_no_da_de_baja_a_nadie(client, database, outbox):
    browser, account, _ = ready(client, database, howmany=1)
    quien = contacts.page(database, account["_id"])[0][0]

    fuera = other(client)
    assert fuera.get(f"/baja/{quien['_id']}.0000000000000000").status_code == 404
    assert fuera.post(f"/baja/{quien['_id']}.0000000000000000").status_code == 404
    assert not suppressions.has(database, account["_id"], quien["email"])


def test_la_baja_no_se_puede_levantar_desde_el_panel(client, database, outbox):
    """Motivo `unsubscribe`: solo vuelve quien se vuelva a suscribir."""
    browser, account, _ = ready(client, database, howmany=1)
    quien = contacts.page(database, account["_id"])[0][0]
    other(client).post(f"/baja/{unsubscribe.sign(quien['_id'])}")

    assert suppressions.lift(database, account["_id"], quien["email"]) is False


# ------------------------------------------------------------ quién la ve

def test_la_pantalla_no_es_para_administradores(client, database, outbox):
    from test_admin import make_admin

    admin, _ = make_admin(client, database)

    respuesta = admin.get("/envios")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/admin/")


def test_la_fila_esta_en_los_dos_menus(client, database, outbox):
    from pathlib import Path

    browser, _, _ = ready(client, database)

    panel = browser.get("/panel").get_data(as_text=True)
    assert "Enviar correos" in panel
    assert "/envios" in panel

    raiz = Path(__file__).resolve().parent.parent.parent
    sitio = (raiz / "landing" / "index.html").read_text(encoding="utf-8")
    assert "Enviar correos" in sitio
    assert "/envios" in sitio
