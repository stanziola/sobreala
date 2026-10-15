"""Los avisos que bajan desde arriba (octubre de 2026).

La animación la hace `panel.js` y se revisa en Chrome. Lo que se fija aquí es
lo que le toca al servidor: que cada página traiga dónde caen los avisos y el
ícono del gris, y que **guardar lo mismo que ya había no escriba nada y lo
diga** (`?same=1`, «No se realizaron cambios.»), en Cuenta, Notificaciones,
Remitente y la verificación de la ficha; y que guardar algo distinto siga
diciendo lo suyo.
"""

from __future__ import annotations

from test_admin import make_admin, make_client_account
from test_campaigns import ready
from test_verificaciones import CLIENTA, csrf, decide, enviar

from models import account as accounts
from models import admin_event as decisions

SAME = "No se realizaron cambios."


def location(answer) -> str:
    return answer.headers.get("Location", "")


def test_la_pagina_trae_donde_caen_los_avisos(client, database, outbox):
    browser, _ = make_client_account(client, database, CLIENTA)
    pantalla = browser.get("/settings/account").get_data(as_text=True)
    assert 'class="toasts" id="toasts"' in pantalla and 'aria-live="polite"' in pantalla
    assert '<template id="icono-igual">' in pantalla
    # Con `same`, el aviso gris, igual en cualquier pantalla.
    assert f'<p class="notice notice--same">{SAME}</p>' in browser.get(
        "/settings/account?same=1").get_data(as_text=True)
    assert "notice--same" not in pantalla


def test_la_direccion_y_los_telefonos_iguales_no_se_guardan(client, database, outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)
    antes = accounts.by_id(database, cuenta["_id"])

    misma = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "address": accounts.postal_of(antes)})
    assert "same=1" in location(misma) and location(misma).endswith("#address")

    otra = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "address": "Apartado 0816-00001, Santiago"})
    assert "address=1" in location(otra)

    browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "phones",
        "phone_country": "PA", "phone": "6111-2222",
        "company_phone_country": ["PA"], "company_phone": ["998-0000"]})
    igual = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "phones",
        "phone_country": "PA", "phone": "6111-2222",
        "company_phone_country": ["PA"], "company_phone": ["998-0000"]})
    assert "same=1" in location(igual) and location(igual).endswith("#phones")


def test_los_avisos_iguales_no_se_guardan(client, database, outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)
    # Sin nada escrito valen «sí», así que mandarlos todos es no cambiar nada.
    todos = {"billing": "on", "plan_state": "on", "new_login": "on"}
    igual = browser.post("/settings/notifications", data={
        "csrf_token": csrf(browser, "/settings/notifications"), **todos})
    assert "same=1" in location(igual)
    assert "notifications" not in accounts.by_id(database, cuenta["_id"])

    cambio = browser.post("/settings/notifications", data={
        "csrf_token": csrf(browser, "/settings/notifications"), "billing": "on"})
    assert "saved=1" in location(cambio)
    assert accounts.wants(accounts.by_id(database, cuenta["_id"]), accounts.PLAN_STATE) is False


def test_el_remitente_igual_no_se_guarda(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    handle = accounts.sender_of(accounts.by_id(database, cuenta["_id"]))["handle"]
    igual = browser.post("/campaigns/sender", data={
        "csrf_token": csrf(browser, "/campaigns/sender"), "action": "handle",
        "handle": handle})
    assert "same=1" in location(igual)
    otro = browser.post("/campaigns/sender", data={
        "csrf_token": csrf(browser, "/campaigns/sender"), "action": "handle",
        "handle": "otro-nombre"})
    assert "done=handle" in location(otro)


def test_verificar_lo_ya_verificado_no_anota_nada(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    enviar(browser)
    primera = decide(admin, cuenta, "identity", "verified")
    assert "done=1" in location(primera)
    # El cliente vuelve a mandar un documento y se verifica otra vez.
    accounts.set_verification(database, cuenta["_id"], "identity", accounts.VERIFIED)
    database.verification_docs.insert_one({
        "account_id": cuenta["_id"], "kind": "identity", "data": b"x", "mime": "application/pdf",
        "ext": "pdf"})
    otra = decide(admin, cuenta, "identity", "verified")
    assert "same=1" in location(otra) and location(otra).endswith("#verificaciones")
    assert len([one for one in decisions.for_account(database, cuenta["_id"])
                if one["kind"] == decisions.VERIFY]) == 1
    assert database.verification_docs.count_documents(
        {"account_id": cuenta["_id"], "kind": "identity"}) == 0
