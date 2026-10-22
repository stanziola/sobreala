"""Guardar borrador (octubre de 2026).

Una plantilla del lienzo que no cumple las reglas se guarda como borrador para
poder dejarla a medias, pero **no se envía por ninguna puerta**: ni el Masivo,
ni Redactar con plantilla, ni lo programado del proceso en segundo plano, ni la
API. Una campaña cuya plantilla vuelve a borrador espera, no se da por
terminada, y sale cuando se corrige.
"""

from __future__ import annotations

from test_api_campanas import crear
from test_api_contactos import llave
from test_api_correos import enviar
from test_campaigns import catch, make, ready, send_it
from test_worker import programada
from test_write_or_template import redactar

from models import campaign as campaigns
from models import design as designs
from services import background


def borrador(database, piece):
    database.designs.update_one({"_id": piece}, {"$set": {
        "draft": True, "draft_issues": ["Tiene muy poco texto."]}})


def test_el_masivo_no_deja_elegir_un_borrador(client, database, outbox):
    browser, cuenta, pieza = ready(client, database)
    borrador(database, pieza)
    pantalla = browser.get("/campaigns").get_data(as_text=True)
    opcion = pantalla.split(f'value="{pieza}"')[1].split("</option>")[0]
    assert "disabled" in opcion and "Borrador" in opcion
    respuesta = make(browser, pieza)
    assert respuesta.status_code == 200
    assert "es un borrador" in respuesta.get_data(as_text=True)
    assert campaigns.for_account(database, cuenta["_id"]) == []


def test_una_campana_cuya_plantilla_vuelve_a_borrador_espera(client, database, outbox,
                                                             monkeypatch):
    salidos = catch(monkeypatch)
    browser, cuenta, pieza = ready(client, database, howmany=2)
    make(browser, pieza)
    borrador(database, pieza)
    una = campaigns.for_account(database, cuenta["_id"])[0]
    confirmar = browser.get(f"/campaigns/{una['_id']}/send").get_data(as_text=True)
    assert "guardada como borrador" in confirmar
    assert f'action="/campaigns/{una["_id"]}/send"' not in confirmar
    respuesta, _ = send_it(browser, database, cuenta["_id"])
    assert "done=draft" in respuesta.headers["Location"]
    assert salidos == []
    assert campaigns.by_id(database, cuenta["_id"], una["_id"])["status"] != campaigns.SENT
    # Corregida, sale.
    database.designs.update_one({"_id": pieza}, {"$unset": {"draft": "", "draft_issues": ""}})
    send_it(browser, database, cuenta["_id"])
    assert len(salidos) == 2


def test_lo_programado_espera_con_su_motivo(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, cuenta, pieza = ready(client, database, howmany=2)
    una = programada(database, browser, cuenta, pieza)
    borrador(database, pieza)
    assert background.campaigns_tick(database, "w1") == 0 and salidos == []
    esperando = campaigns.by_id(database, cuenta["_id"], una["_id"])
    assert esperando.get("waiting") == ["draft"]
    assert "guardada como borrador" in browser.get("/campaigns").get_data(as_text=True)


def test_redactar_con_un_borrador_no_sale(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, _, pieza = ready(client, database)
    borrador(database, pieza)
    respuesta = redactar(browser, modo="plantilla", pieza=str(pieza))
    assert "es un borrador" in respuesta.get_data(as_text=True)
    assert salidos == []


def test_la_api_no_envia_un_borrador(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, pieza = ready(client, database)
    borrador(database, pieza)
    auth, _ = llave(database, cuenta, scopes=("emails:send", "campaigns:write",
                                              "campaigns:read", "templates:read"))
    respuesta = enviar(client, auth, template_id=str(pieza), text=None)
    assert respuesta.status_code == 422
    assert "borrador" in respuesta.get_json()["error"]["fields"]["template_id"]
    respuesta = crear(client, auth, template_id=str(pieza), text=None)
    assert respuesta.status_code == 422
    assert salidos == []
    # Y la lista de plantillas lo dice, con lo que le falta.
    lista = client.get("/api/v1/templates", headers=auth).get_json()["data"]
    suya = next(one for one in lista if one["id"] == str(pieza))
    assert suya["draft"] is True and suya["issues"] == ["Tiene muy poco texto."]


def test_duplicar_un_borrador_da_otro_borrador(client, database, outbox):
    browser, cuenta, pieza = ready(client, database)
    borrador(database, pieza)
    copia = designs.duplicate(database, cuenta["_id"], pieza, name="Copia")
    assert designs.is_draft(designs.by_id(database, cuenta["_id"], copia))
