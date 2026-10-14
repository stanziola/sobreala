"""Clientes, en administración: vigilar cómo envía cada uno.

Lo que se fija aquí: que la pantalla sea **solo para quien administra** (404 a
los demás), que las cifras de una empresa **no se mezclen** con las de otra, que
el color diga lo que tiene que decir (ámbar cerca del umbral de la pausa, rojo
pasado, gris sin volumen), que buscar, filtrar y ordenar funcionen, y que **no
salga ninguna dirección de los contactos** de un cliente: cifras, nunca listas.
"""

from __future__ import annotations

import re

from test_admin import make_admin, make_client_account
from test_pause import enviados, rebota
from test_webhooks import configured  # noqa: F401

from models import account as accounts


def cuenta(client, database, email, empresa, *, plan="basico"):
    _, una = make_client_account(client, database, email)
    database.accounts.update_one({"_id": una["_id"]},
                                 {"$set": {"company_name": empresa, "plan": plan}})
    return accounts.by_id(database, una["_id"])


def fila(pantalla, empresa):
    """La fila de la tabla de esa empresa."""
    for row in re.findall(r"<tr>(.*?)</tr>", pantalla, re.S):
        if empresa in row:
            return row
    raise AssertionError(f"{empresa} no está en la tabla")


def empresas(pantalla):
    """Las empresas de la tabla, en el orden en que salen."""
    return re.findall(r'href="/admin/accounts/[0-9a-f]+"><b>([^<]+)</b>', pantalla)


def test_solo_para_quien_administra(client, database, outbox):
    browser, _ = make_client_account(client, database, "socia@ejemplo.com")
    assert browser.get("/admin/clients").status_code == 404


def test_las_cifras_de_cada_empresa_y_su_color(client, database, outbox):
    admin, _ = make_admin(client, database)
    cerca = cuenta(client, database, "cerca@ejemplo.com", "Tienda Cerca")
    pasada = cuenta(client, database, "pasada@ejemplo.com", "Colegio Pasado",
                    plan="negocio")
    poca = cuenta(client, database, "poca@ejemplo.com", "Gremio Chico")

    enviados(database, cerca["_id"], 100)
    rebota(client, cerca["_id"], "p0@coop.com", "p1@coop.com")  # 2 %: ámbar
    enviados(database, pasada["_id"], 100)
    rebota(client, pasada["_id"], *[f"p{i}@coop.com" for i in range(4)])  # pausa
    enviados(database, poca["_id"], 10)
    rebota(client, poca["_id"], "p0@coop.com")  # 10 %, pero de diez correos

    pantalla = admin.get("/admin/clients").get_data(as_text=True)

    assert "is-warn" in fila(pantalla, "Tienda Cerca")
    assert "Cerca del límite" in fila(pantalla, "Tienda Cerca")
    assert "is-over" in fila(pantalla, "Colegio Pasado")
    assert "En pausa" in fila(pantalla, "Colegio Pasado")
    assert "is-few" in fila(pantalla, "Gremio Chico")
    assert "Bien" in fila(pantalla, "Gremio Chico")
    # Lo más grave arriba, sin elegir nada.
    assert empresas(pantalla)[0] == "Colegio Pasado"
    # La salud de la cuenta entera: 7 rebotes de 210 enviados.
    assert "3.3 %" in pantalla
    # Cifras, nunca direcciones de contactos.
    assert "@coop.com" not in pantalla


def test_buscar_filtrar_y_ordenar(client, database, outbox):
    admin, _ = make_admin(client, database)
    mucho = cuenta(client, database, "mucho@ejemplo.com", "Envia Mucho")
    poco = cuenta(client, database, "poco@ejemplo.com", "Envia Poco",
                  plan="negocio")
    enviados(database, mucho["_id"], 300)
    enviados(database, poco["_id"], 20)

    por_envios = admin.get("/admin/clients?sort=sent").get_data(as_text=True)
    assert empresas(por_envios)[:2] == ["Envia Mucho", "Envia Poco"]
    al_reves = admin.get("/admin/clients?sort=sent&dir=asc").get_data(as_text=True)
    assert empresas(al_reves).index("Envia Poco") < empresas(al_reves).index("Envia Mucho")

    assert empresas(admin.get("/admin/clients?q=Poco").get_data(as_text=True)) == ["Envia Poco"]
    solo_negocio = empresas(admin.get("/admin/clients?plan=negocio").get_data(as_text=True))
    assert "Envia Poco" in solo_negocio and "Envia Mucho" not in solo_negocio

    accounts.pause(database, mucho["_id"], reason=accounts.PAUSE_BOUNCES, note="x")
    assert empresas(admin.get("/admin/clients?state=paused").get_data(as_text=True)) == [
        "Envia Mucho"]


def test_el_menu_la_tiene(client, database, outbox):
    admin, _ = make_admin(client, database)
    assert 'href="/admin/clients"' in admin.get("/admin/accounts").get_data(as_text=True)
