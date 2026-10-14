"""Eventos, en administración: lo que está pasando, y lo nuevo sin recargar.

Lo que se fija aquí: que sea **solo para quien administra**, que el filtro de
siempre enseñe lo que pide atención (rebotes, quejas, rechazos, pausas) y no las
entregas, que la consulta en vivo traiga **lo nuevo** desde la hora que tiene la
pantalla, que se pueda mirar una sola empresa, y que **del destinatario salga
solo el dominio**: ninguna dirección de un contacto, ni en la página ni en lo
que se pide cada pocos segundos.
"""

from __future__ import annotations

import re

from bson import ObjectId
from test_admin import make_admin, make_client_account
from test_pause import enviados, rebota, se_queja
from test_webhooks import campaign_event, configured, notify  # noqa: F401

from models import account as accounts


def entrega(client, cuenta_id, quien):
    notify(client, campaign_event(
        "Delivery", account=cuenta_id, campaign=ObjectId(), run=ObjectId(),
        to=quien, delivery={"recipients": [quien],
                            "timestamp": "2026-09-16T12:00:30.000Z"}))


def cuenta(client, database, email, empresa):
    _, una = make_client_account(client, database, email)
    # Un registro cuenta al confirmar el correo, como el aviso al administrador.
    database.accounts.update_one({"_id": una["_id"]},
                                 {"$set": {"company_name": empresa,
                                           "email_confirmed_at": accounts.now()}})
    return accounts.by_id(database, una["_id"])


def recientes(database):
    """Los avisos de prueba traen una hora de septiembre: se ponen en ahora,
    que es cuando habrían llegado."""
    database.events.update_many({}, {"$set": {"created_at": accounts.now()}})


def test_solo_para_quien_administra(client, database, outbox):
    browser, _ = make_client_account(client, database, "socia@ejemplo.com")
    assert browser.get("/admin/events").status_code == 404
    assert browser.get("/admin/events/feed").status_code == 404


def test_lo_que_pide_atencion_y_solo_el_dominio(client, database, outbox):
    admin, _ = make_admin(client, database)
    una = cuenta(client, database, "una@ejemplo.com", "Tienda Una")
    entrega(client, una["_id"], "ana@gmail.com")
    rebota(client, una["_id"], "beto@coop.com")
    recientes(database)

    pantalla = admin.get("/admin/events").get_data(as_text=True)
    assert "Rebote permanente" in pantalla and "a coop.com" in pantalla
    assert "Entregado" not in pantalla

    todo = admin.get("/admin/events?type=mail").get_data(as_text=True)
    assert "Entregado" in todo and "a gmail.com" in todo
    for vista in (pantalla, todo):
        assert "beto@coop.com" not in vista and "ana@gmail.com" not in vista


def test_lo_nuevo_llega_sin_recargar(client, database, outbox):
    admin, _ = make_admin(client, database)
    una = cuenta(client, database, "una@ejemplo.com", "Tienda Una")
    rebota(client, una["_id"], "beto@coop.com")
    recientes(database)
    pantalla = admin.get("/admin/events").get_data(as_text=True)
    newest = re.search(r'data-newest="([^"]+)"', pantalla).group(1)
    antes = set(re.findall(r'data-key="([^"]+)"', pantalla))

    se_queja(client, una["_id"], "carla@yahoo.com")
    recientes(database)
    respuesta = admin.get(f"/admin/events/feed?after={newest.replace('+', '%2B')}")

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    nuevas = set(re.findall(r'data-key="([^"]+)"', datos["html"])) - antes
    assert len(nuevas) == 1 and "Queja" in datos["html"]
    assert "carla@yahoo.com" not in datos["html"] and "a yahoo.com" in datos["html"]
    assert datos["newest"] >= newest
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_las_cuentas_y_una_sola_empresa(client, database, outbox):
    admin, _ = make_admin(client, database)
    una = cuenta(client, database, "una@ejemplo.com", "Tienda Una")
    otra = cuenta(client, database, "otra@ejemplo.com", "Colegio Otro")
    enviados(database, una["_id"], 100)
    rebota(client, una["_id"], *[f"p{i}@coop.com" for i in range(4)])  # pausa
    rebota(client, otra["_id"], "p9@coop.com")
    recientes(database)

    cuentas = admin.get("/admin/events?type=accounts").get_data(as_text=True)
    assert "Registro" in cuentas and "Pausa automática" in cuentas

    sola = admin.get(f"/admin/events?type=all&account={otra['_id']}").get_data(as_text=True)
    assert "Colegio Otro" in sola.split("<tbody", 1)[1]
    assert "Tienda Una" not in sola.split("<tbody", 1)[1]


def test_el_menu_la_tiene(client, database, outbox):
    admin, _ = make_admin(client, database)
    assert 'href="/admin/events"' in admin.get("/admin/accounts").get_data(as_text=True)
