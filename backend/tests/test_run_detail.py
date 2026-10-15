"""Enviar correos: los textos del formulario y el detalle de cada envío.

Lo que se fija aquí: que cada persona cuente una vez por envío aunque abra mil
veces, que el detalle diga de cada destinatario si le llegó, si lo abrió y si
pulsó, que se pueda filtrar por etiqueta y buscar, y que el envío de otra cuenta
no se abra.
"""

from __future__ import annotations

from datetime import timedelta

from bson import ObjectId

from models import account as accounts
from models import campaign_run as runs
from models import event as events
from test_campaigns import catch, make, ready, send_it
from test_designs import inside


def enviado(client, database, monkeypatch, **extra):
    """Una campaña que ya salió, con su envío en `campaign_runs`."""
    catch(monkeypatch)
    browser, account, piece = ready(client, database, **extra)
    make(browser, piece, subject="Asamblea anual", tag=extra.get("tag", ""))
    send_it(browser, database, account["_id"])
    run = runs.for_account(database, account["_id"])[0]
    return browser, account, run


# ------------------------------------------------------ una vez por persona

def test_mil_aperturas_son_una(client, database, outbox, monkeypatch):
    _, account, run = enviado(client, database, monkeypatch, howmany=1)
    primera = events.now() - timedelta(minutes=30)
    for minutos in (30, 20, 10, 5):
        events.record(database, account["_id"], kind=events.OPEN, run_id=run["_id"],
                      email="Socio0@Ejemplo.com",
                      at=events.now() - timedelta(minutes=minutos))
    aperturas = list(database.events.find({"run_id": run["_id"], "kind": events.OPEN}))
    assert len(aperturas) == 1
    # Queda la primera.
    assert abs(aperturas[0]["created_at"] - primera) < timedelta(seconds=2)

    # En otro envío sí vuelve a contar.
    events.record(database, account["_id"], kind=events.OPEN, run_id=ObjectId(),
                  email="socio0@ejemplo.com")
    assert database.events.count_documents({"kind": events.OPEN}) == 2


def test_sin_envio_se_anota_tal_cual(client, database, outbox):
    cuenta = ObjectId()
    events.record(database, cuenta, kind=events.SENT)
    events.record(database, cuenta, kind=events.SENT)
    assert database.events.count_documents({"account_id": cuenta}) == 2


# ------------------------------------------------------------ el detalle

def test_el_detalle_dice_que_paso_con_cada_uno(client, database, outbox, monkeypatch):
    browser, account, run = enviado(client, database, monkeypatch, howmany=3)
    uno = {"account_id": account["_id"], "run_id": run["_id"]}
    events.record(database, kind=events.DELIVERED, email="socio0@ejemplo.com", **uno)
    events.record(database, kind=events.OPEN, email="socio0@ejemplo.com", **uno)
    events.record(database, kind=events.CLICK, email="socio0@ejemplo.com", **uno)
    events.record(database, kind=events.BOUNCE, email="socio1@ejemplo.com", **uno)

    # Lo que salió vive en Enviados desde octubre de 2026.
    indice = browser.get("/campaigns/sent").get_data(as_text=True)
    assert f'href="/campaigns/sent/{run["_id"]}"' in indice and "Detalles" in indice

    pantalla = browser.get(f"/campaigns/sent/{run['_id']}").get_data(as_text=True)
    assert "Asamblea anual" in pantalla
    assert "3 personas" in pantalla
    assert "Socio 0" in pantalla and "Entregado" in pantalla
    assert "Rebotó" in pantalla
    # El tercero salió y Amazon todavía no dijo nada.
    assert "Enviado" in pantalla
    # Socio 0 abrió y pulsó; los otros dos, raya en las dos columnas.
    assert pantalla.count(">—</td>") == 4


def test_filtrar_por_etiqueta_y_buscar(client, database, outbox, monkeypatch):
    browser, account, run = enviado(client, database, monkeypatch, howmany=3,
                                    tag="Socios")
    # Uno de ellos cambia de etiqueta después: cuenta la de hoy.
    database.contacts.update_one({"account_id": account["_id"],
                                  "email_normalized": "socio2@ejemplo.com"},
                                 {"$set": {"tags": []}})
    base = f"/campaigns/sent/{run['_id']}"

    socios = browser.get(base + "?tag=Socios").get_data(as_text=True)
    assert "2 personas" in socios and "socio2@ejemplo.com" not in socios

    por_nombre = browser.get(base + "?q=socio 1").get_data(as_text=True)
    assert "1 persona" in por_nombre and "socio1@ejemplo.com" in por_nombre
    por_correo = browser.get(base + "?q=SOCIO0@").get_data(as_text=True)
    assert "socio0@ejemplo.com" in por_correo and "socio1@ejemplo.com" not in por_correo

    nadie = browser.get(base + "?q=zzz").get_data(as_text=True)
    assert "Nadie coincide con ese filtro." in nadie


def test_filtrar_por_lo_que_paso(client, database, outbox, monkeypatch):
    browser, account, run = enviado(client, database, monkeypatch, howmany=4)
    uno = {"account_id": account["_id"], "run_id": run["_id"]}
    events.record(database, kind=events.DELIVERED, email="socio0@ejemplo.com", **uno)
    events.record(database, kind=events.OPEN, email="socio0@ejemplo.com", **uno)
    events.record(database, kind=events.BOUNCE, email="socio1@ejemplo.com", **uno)
    # Entregado y después lo marcó como spam: cuenta como spam, no como entregado.
    events.record(database, kind=events.DELIVERED, email="socio2@ejemplo.com", **uno)
    events.record(database, kind=events.COMPLAINT, email="socio2@ejemplo.com", **uno)
    base = f"/campaigns/sent/{run['_id']}?status="

    def quienes(estado):
        pantalla = browser.get(base + estado).get_data(as_text=True)
        return sorted(n for n in range(4) if f"socio{n}@ejemplo.com" in pantalla)

    assert quienes("rebotes") == [1]
    assert quienes("entregados") == [0]
    assert quienes("spam") == [2]
    assert quienes("abrieron") == [0]
    assert quienes("sin_abrir") == [1, 2, 3]
    # Uno inventado no filtra.
    assert quienes("cualquiera") == [0, 1, 2, 3]
    # Y se combina con el buscador.
    pantalla = browser.get(base + "rebotes&q=socio 0").get_data(as_text=True)
    assert "Nadie coincide con ese filtro." in pantalla


def test_quien_ya_no_esta_en_contactos_sale_con_su_correo(client, database, outbox,
                                                          monkeypatch):
    browser, account, run = enviado(client, database, monkeypatch, howmany=1)
    database.contacts.delete_many({"account_id": account["_id"]})
    pantalla = browser.get(f"/campaigns/sent/{run['_id']}").get_data(as_text=True)
    assert "socio0@ejemplo.com" in pantalla
    assert "Ya no está en tus contactos" in pantalla


def test_de_a_cincuenta_por_pagina(client, database, outbox, monkeypatch):
    browser, account, run = enviado(client, database, monkeypatch, howmany=1)
    for n in range(60):
        events.record(database, account["_id"], kind=events.SENT, run_id=run["_id"],
                      email=f"extra{n:02d}@coop.com")
    primera = browser.get(f"/campaigns/sent/{run['_id']}").get_data(as_text=True)
    assert "61 personas" in primera and "Página 1 de 2" in primera
    assert "Siguiente" in primera
    segunda = browser.get(f"/campaigns/sent/{run['_id']}?page=2").get_data(as_text=True)
    assert "Página 2 de 2" in segunda and "Anterior" in segunda
    assert "socio0@ejemplo.com" in segunda


def test_el_envio_de_otra_cuenta_no_se_abre(client, database, outbox, monkeypatch):
    _, _, run = enviado(client, database, monkeypatch)
    otra = inside(client, "bea@ejemplo.com")
    assert otra.get(f"/campaigns/sent/{run['_id']}").status_code == 404
    assert otra.get("/campaigns/sent/no-es-un-id").status_code == 404


# ------------------------------------------------------------ los textos

def test_el_formulario_dice_etiquetas_y_plantilla(client, database, outbox):
    browser, account, _ = ready(client, database)
    accounts.add_field(database, account["_id"], label="Edad", kind="number")
    pantalla = browser.get("/campaigns").get_data(as_text=True)
    assert "Elige a quién le escribes y qué plantilla." in pantalla
    assert ">Etiquetas<" in pantalla and ">Plantilla<" in pantalla
    assert "A quién" not in pantalla and "Con qué plantilla" not in pantalla
    assert "Se guardan armadas" not in pantalla
    # Las columnas se escriben en Plantillas, no aquí.
    assert "*|EDAD|*" not in pantalla
    assert "Escribir un dato de cada contacto" not in pantalla
