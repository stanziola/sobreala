"""La declaración del origen (octubre de 2026).

Lo que se fija aquí: que sin confirmar que esas personas aceptaron recibir
correos no entra nadie, ni importando, ni a mano, ni por la API; que cada
contacto guarda quién lo confirmó y en qué importación; que la ficha, el CSV y
la API lo enseñan entero; y que un contacto de antes dice que no se pedía, en
vez de inventar un sí.
"""

from __future__ import annotations

import io

from test_api_contactos import cargar, llave
from test_contacts import LISTA, account_of, csrf, export, inside

from models import contact as contacts
from models import import_job as imports


def subir(browser, *, attest=True):
    data = {"csrf_token": csrf(browser, "/contacts/import"), "source": "members",
            "note": "Padrón de socios 2026",
            "archivo": (io.BytesIO(LISTA.encode("utf-8")), "lista.csv")}
    if attest:
        data["attest"] = "1"
    return browser.post("/contacts/import", data=data, content_type="multipart/form-data")


def test_sin_la_confirmacion_no_entra_nadie(client, database, outbox):
    browser = inside(client)
    cuenta = account_of(database)
    pantalla = subir(browser, attest=False).get_data(as_text=True)
    assert "sin esa confirmación no guardamos los contactos" in pantalla
    a_mano = browser.post("/contacts/new", data={
        "csrf_token": csrf(browser, "/contacts/new"), "email": "bea@coop.com",
        "source": "members"}).get_data(as_text=True)
    assert "sin esa confirmación no guardamos los contactos" in a_mano
    assert contacts.count(database, cuenta["_id"]) == 0


def test_cada_contacto_guarda_quien_lo_confirmo_y_de_que_importacion(client, database,
                                                                    outbox):
    browser = inside(client)
    subir(browser)
    cuenta = account_of(database)
    trabajo = imports.for_account(database, cuenta["_id"])[0]
    gente = list(database.contacts.find({"account_id": cuenta["_id"]}))
    assert gente
    for uno in gente:
        origen = uno["consent"]
        assert origen["attested"] is True
        assert origen["by"]["email"] == "ana@ejemplo.com"
        assert origen["import_id"] == trabajo["_id"]
        assert origen["note"] == "Padrón de socios 2026"


def test_la_ficha_y_el_csv_lo_ensenan_entero(client, database, outbox):
    browser = inside(client)
    subir(browser)
    cuenta = account_of(database)
    # Uno de antes: no tiene la confirmación, porque no se pedía.
    database.contacts.insert_one({
        "account_id": cuenta["_id"], "email": "viejo@coop.com",
        "email_normalized": "viejo@coop.com", "tags": [], "created_at": contacts.now(),
        "consent": {"source": "members", "note": "", "recorded_at": None}})
    nuevo = database.contacts.find_one({"account_id": cuenta["_id"],
                                        "consent.attested": True})
    viejo = database.contacts.find_one({"email": "viejo@coop.com"})

    ficha = browser.get(f"/contacts/edit/{nuevo['_id']}").get_data(as_text=True)
    assert "Confirmó que aceptaron" in ficha and "ana@ejemplo.com" in ficha
    assert "Padrón de socios 2026" in ficha
    antes = browser.get(f"/contacts/edit/{viejo['_id']}").get_data(as_text=True)
    assert "No se pedía todavía" in antes

    csv = export(browser).get_data(as_text=True)
    cabecera = csv.splitlines()[0]
    for columna in ("Origen", "Nota del origen", "Origen registrado",
                    "Confirmó que aceptaron", "Lo declaró"):
        assert columna in cabecera
    assert "Padrón de socios 2026" in csv and "ana@ejemplo.com" in csv
    assert "No se pedía todavía" in csv


def test_la_api_pide_la_confirmacion_y_dice_quien(client, database, outbox):
    from test_campaigns import ready
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta)
    sin = client.post("/api/v1/contacts", headers=auth, json={
        "consent": {"source": "customers"}, "contacts": [{"email": "a@coop.com"}]})
    assert sin.status_code == 422 and "consent" in sin.get_json()["error"]["fields"]
    falso = client.post("/api/v1/contacts", headers=auth, json={
        "consent": {"source": "customers", "attested": "true"},
        "contacts": [{"email": "a@coop.com"}]})
    assert falso.status_code == 422

    assert cargar(client, auth, [{"email": "a@coop.com"}]).status_code == 200
    uno = client.get("/api/v1/contacts", headers=auth).get_json()["data"][0]
    assert uno["consent"]["attested"] is True
    assert uno["consent"]["by"] == {"type": "api_key", "name": "Tienda"}
