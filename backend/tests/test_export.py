"""Bajarse lo que enseña Estadísticas, en CSV y en PDF.

`docs/pricing.md` los promete en los tres planes. Lo que se fija aquí es que lo
que baja sea lo mismo que se ve (el mismo `stats.screen()`, los mismos filtros)
y que no se pueda bajar lo de otra cuenta.
"""

from __future__ import annotations

from bson import ObjectId
from test_stats import inside, make_admin

from models import account as accounts
from models import event as events
from models import suppression as suppressions


def sembrar(database, cuenta):
    run = ObjectId()
    for quien in ("a", "b", "c", "d"):
        for kind in (events.SENT, events.DELIVERED):
            events.record(database, cuenta["_id"], kind=kind, run_id=run,
                          email=f"{quien}@coop.com")
    events.record(database, cuenta["_id"], kind=events.OPEN, run_id=run,
                  email="a@coop.com")
    events.record(database, cuenta["_id"], kind=events.CLICK, run_id=run,
                  email="a@coop.com", link="https://coop.com/asamblea")
    database.campaign_runs.insert_one({
        "_id": run, "account_id": cuenta["_id"], "campaign_id": ObjectId(),
        "subject": "Asamblea anual", "tags": [], "sent": 4, "skipped": 0,
        "failed": 0, "started_at": events.now(), "finished_at": events.now()})
    suppressions.add(database, cuenta["_id"], "d@coop.com",
                     reason=suppressions.UNSUBSCRIBE)
    return run


def test_el_csv_trae_lo_mismo_que_la_pantalla(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    sembrar(database, cuenta)

    respuesta = browser.get("/dashboard/export.csv?period=7d")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "text/csv"
    assert "estadisticas-" in respuesta.headers["Content-Disposition"]
    hoja = respuesta.get_data(as_text=True)

    # El BOM, que es lo que hace que Excel en español no parta los acentos.
    assert hoja.startswith("﻿")
    assert "Cómo le fue" in hoja
    assert "Enviados;4" in hoja
    assert "Aperturas;25 %" in hoja          # 1 de 4 entregados
    assert "Bajas;25 %" in hoja
    assert "Asamblea anual" in hoja
    assert "https://coop.com/asamblea;1" in hoja
    # Dice contra qué comparó, con el periodo puesto.
    assert "los 7 días anteriores" in hoja


def test_el_pdf_sale_y_es_un_pdf(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    sembrar(database, cuenta)

    respuesta = browser.get("/dashboard/export.pdf?period=7d")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/pdf"
    datos = respuesta.get_data()
    assert datos.startswith(b"%PDF-")
    assert len(datos) > 1500


def test_los_filtros_de_la_direccion_valen_tambien_al_bajar(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    sembrar(database, cuenta)
    accounts.add_tag(database, cuenta["_id"], "Socios")

    hoja = browser.get("/dashboard/export.csv?period=7d&tag=Socios").get_data(as_text=True)
    assert "Socios" in hoja
    # Con un filtro puesto las bajas no se cuentan, como en la pantalla.
    assert "Bajas;" not in hoja


def test_sin_sesion_y_de_otra_cuenta_no_se_baja_nada(client, database, outbox):
    de_fuera = client.application.test_client()
    assert de_fuera.get("/dashboard/export.csv").status_code == 302
    assert de_fuera.get("/dashboard/export.pdf").status_code == 302

    # Un administrador no tiene cifras propias que bajar: se le devuelve a
    # /admin, como en cualquier pantalla de cliente.
    jefe, _ = make_admin(client, database)
    respuesta = jefe.get("/dashboard/export.csv?account=" + str(ObjectId()))
    assert respuesta.status_code == 302
    assert "/admin" in respuesta.headers["Location"]
