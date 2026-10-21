"""Revisar las direcciones antes de enviar (`services/address_check.py`).

Lo que se puede saber sin mandar nada: que el dominio reciba correo, y los
errores de dedo comunes. Lo que fijan estas pruebas, con el DNS simulado: que
una dirección de un dominio muerto **entre marcada** al importar, que al enviar
**se salte sin gastar cuota**, que se puedan **borrar todas de una vez** (y solo
esas), que un error de dedo se sugiera sin cambiar nada solo, y que el correo
individual pregunte «¿Quisiste decir…?».
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from test_campaigns import WHEN, catch, csrf as csrf_send, make, ready, send_it
from test_contacts import account_of, csrf, inside, upload

from models import account as accounts
from models import contact as contacts
from services import address_check

MUERTO = "dominio-muerto.com"


@pytest.fixture(autouse=True)
def dns(monkeypatch):
    """El DNS de mentira: todo dominio recibe correo, menos uno."""
    consultados: list[str] = []

    def receives(domain):
        consultados.append(domain)
        return domain != MUERTO

    monkeypatch.setattr(address_check, "domain_receives", receives)
    return consultados


def test_las_sugerencias_de_errores_de_dedo():
    assert address_check.suggestion("ana@gmial.com") == "ana@gmail.com"
    assert address_check.suggestion("ana@hotmial.com") == "ana@hotmail.com"
    assert address_check.suggestion("ana@gmail.com") is None
    # Un dominio de verdad que se parece a otro no se «corrige».
    assert address_check.suggestion("ana@yahoo.com.mx") is None
    assert address_check.suggestion("ana@coop.com") is None


def test_una_consulta_por_dominio(dns):
    malas = address_check.undeliverable(
        ["a@coop.com", "b@coop.com", f"c@{MUERTO}", f"d@{MUERTO}"])
    assert malas == {f"c@{MUERTO}", f"d@{MUERTO}"}
    assert sorted(dns) == ["coop.com", MUERTO]


def test_al_importar_entran_marcadas_y_se_cuentan(client, database, outbox):
    browser = inside(client)
    pantalla = upload(browser, "correo\nana@coop.com\n"
                               f"beto@{MUERTO}\ncarla@gmial.com\n").get_data(as_text=True)

    cuenta = account_of(database)
    beto = contacts.by_email(database, cuenta["_id"], f"beto@{MUERTO}")
    assert beto["invalid"]["reason"] == contacts.INVALID_DOMAIN
    assert "invalid" not in contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    # El error de dedo entra como está, y se sugiere.
    assert "invalid" not in contacts.by_email(database, cuenta["_id"], "carla@gmial.com")
    assert "De un dominio que no recibe correo" in pantalla
    assert "¿carla@gmail.com?" in pantalla

    lista = browser.get("/contacts").get_data(as_text=True)
    assert "Tienes 1 contactos con una dirección inválida" in lista
    assert "Dirección inválida" in lista


def test_al_enviar_se_saltan_sin_gastar_cuota(client, database, outbox, monkeypatch):
    browser, cuenta, pieza = ready(client, database, howmany=3)
    contacts.mark_invalid(database, cuenta["_id"], ["socio1@ejemplo.com"])
    salidos = catch(monkeypatch)
    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)
    make(browser, pieza, when="fecha", fecha=pronto)
    send_it(browser, database, cuenta["_id"])

    assert sorted(c["To"] for c in salidos) == ["socio0@ejemplo.com", "socio2@ejemplo.com"]
    assert sum(accounts.by_id(database, cuenta["_id"]).get("sent_counts", {}).values()) == 2


def test_borrar_las_invalidas_borra_solo_esas(client, database, outbox):
    browser = inside(client)
    upload(browser, f"correo\nana@coop.com\nbeto@{MUERTO}\ncesar@{MUERTO}\n")
    cuenta = account_of(database)

    pregunta = browser.get("/contacts/invalid/delete").get_data(as_text=True)
    assert "2" in pregunta
    browser.post("/contacts/invalid/delete",
                 data={"csrf_token": csrf(browser, "/contacts/invalid/delete")})

    assert contacts.count(database, cuenta["_id"]) == 1
    assert contacts.by_email(database, cuenta["_id"], "ana@coop.com") is not None


def test_a_mano_no_entra_una_de_un_dominio_muerto(client, database, outbox):
    browser = inside(client)
    pantalla = browser.post("/contacts/new", data={
        "csrf_token": csrf(browser, "/contacts/new"), "email": f"beto@{MUERTO}",
        "name": "Beto", "source": "members", "attest": "1"}).get_data(as_text=True)
    assert "no recibe correo" in pantalla
    assert contacts.count(database, account_of(database)["_id"]) == 0


def test_el_individual_pregunta_por_un_error_de_dedo(client, database, outbox,
                                                     monkeypatch):
    browser, _, _ = ready(client, database)
    salidos = catch(monkeypatch)

    def escribir(**extra):
        return browser.post("/campaigns/write", data={
            "csrf_token": csrf_send(browser), "para": "ana@gmial.com",
            "asunto": "Hola", "mensaje": "Hola", **extra},
            content_type="multipart/form-data")

    pantalla = escribir().get_data(as_text=True)
    assert "¿Quisiste decir ana@gmail.com?" in pantalla and salidos == []

    escribir(corregir="ana@gmail.com")
    assert salidos[-1]["To"] == "ana@gmail.com"
    escribir(confirmado="1")
    assert salidos[-1]["To"] == "ana@gmial.com"

    muerta = browser.post("/campaigns/write", data={
        "csrf_token": csrf_send(browser), "para": f"beto@{MUERTO}",
        "asunto": "Hola", "mensaje": "Hola"}, content_type="multipart/form-data")
    assert "no recibe correo" in muerta.get_data(as_text=True)
    assert len(salidos) == 2
