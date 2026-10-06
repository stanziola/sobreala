"""La hora del dispositivo, las gráficas nuevas, Facturación y borrar con aviso.

Lo que se fija aquí:

  * Todo se guarda en UTC y se **escribe** en la zona de quien mira: un evento
    de las 2:00 UTC es del día de antes en Panamá, y «Hoy» empieza a su
    medianoche. Una hora escrita para programar se lee en su zona.
  * Los porcentajes cuentan personas, y el filtro por campaña o por etiqueta no
    deja mirar lo de otra cuenta.
  * Una factura solo la baja su dueño, siempre como archivo, y solo entra si es
    un PDF.
  * Borrar un contacto pregunta primero, y dice cuántos.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from models import account as accounts
from models import campaign_run as runs
from models import contact as contacts
from models import event as events
from models import invoice as invoices
from models import payment as payments
from services import clock, stats
from test_admin import make_admin
from test_campaigns import csrf as campaigns_csrf
from test_campaigns import ready
from test_payments import buy, come_back, confirm, fake_paypal
from test_stats import inside

PANAMA = ZoneInfo("America/Panama")


def en_panama(browser):
    browser.set_cookie("sa_tz", "America/Panama")
    return browser


# ------------------------------------------------------------ la zona

def test_una_zona_inventada_cae_en_panama():
    assert clock.zone_named("Marte/Olimpo") is None
    assert clock.zone_named("../../etc/passwd") is None
    assert clock.for_account({"time_zone": "no-existe"}).key == "America/Panama"
    assert clock.for_account({"time_zone": "Europe/Madrid"}).key == "Europe/Madrid"


def test_hoy_empieza_a_la_medianoche_de_la_zona():
    primero = events.slots("today", PANAMA)[0].astimezone(PANAMA)
    assert (primero.hour, primero.minute) == (0, 0)
    assert primero.date() == datetime.now(PANAMA).date()


def test_un_evento_de_las_dos_utc_es_del_dia_anterior_en_panama(client, database, outbox):
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    hoy_utc = datetime.now(timezone.utc).replace(hour=2, minute=0, second=0,
                                                  microsecond=0)
    if hoy_utc > datetime.now(timezone.utc):
        hoy_utc -= timedelta(days=1)
    events.record(database, cuenta["_id"], kind=events.SENT, at=hoy_utc)

    serie = events.series(database, cuenta["_id"], period="7d", zone=PANAMA)
    con_envio = [row for row in serie if row[events.SENT]]
    assert len(con_envio) == 1
    # Las 2:00 UTC son las 21:00 del día anterior en Panamá.
    dia = con_envio[0]["at"].astimezone(PANAMA).date()
    assert dia == (hoy_utc.astimezone(PANAMA)).date()
    assert dia == hoy_utc.date() - timedelta(days=1)


def test_programar_se_entiende_en_la_hora_del_dispositivo(client, database, outbox):
    browser, account, piece = ready(client, database)
    en_panama(browser)
    manana = (datetime.now(PANAMA) + timedelta(days=1)).strftime("%Y-%m-%d")
    browser.post("/campaigns", data={
        "csrf_token": campaigns_csrf(browser), "asunto": "Asamblea",
        "pieza": str(piece), "lista": "", "cuando": "luego",
        "fecha": f"{manana}T15:00"})

    campana = database.campaigns.find_one({"account_id": account["_id"]})
    guardada = campana["scheduled_at"]
    # Las 3:00 p. m. de Panamá son las 20:00 UTC.
    assert (guardada.hour, guardada.minute) == (20, 0)
    pantalla = browser.get(f"/campaigns/{campana['_id']}").get_data(as_text=True)
    assert f"{manana}T15:00" in pantalla


def test_la_zona_llega_codificada_como_la_guarda_el_navegador(client, database, outbox):
    browser = inside(client)
    browser.set_cookie("sa_tz", "Europe%2FMadrid")
    browser.get("/dashboard")
    assert accounts.by_email(database, "ana@ejemplo.com")["time_zone"] == "Europe/Madrid"


def test_la_cuenta_recuerda_su_ultima_zona(client, database, outbox):
    browser = inside(client)
    browser.set_cookie("sa_tz", "Europe/Madrid")
    browser.get("/dashboard")
    assert accounts.by_email(database, "ana@ejemplo.com")["time_zone"] == "Europe/Madrid"


# ------------------------------------------------------------ las gráficas

def test_la_escala_tiene_numeros_redondos():
    assert stats.nice_top(0) == (0, [])
    assert stats.nice_top(3) == (4, [0, 1, 2, 3, 4])
    assert stats.nice_top(100) == (100, [0, 25, 50, 75, 100])


def test_el_eje_trae_marcas_en_la_hora_de_la_zona(client, database, outbox):
    browser = en_panama(inside(client))
    pantalla = browser.get("/dashboard?period=24h").get_data(as_text=True)
    assert "chart__axis-x" in pantalla
    assert " a. m." in pantalla or " p. m." in pantalla
    semana = browser.get("/dashboard?period=7d").get_data(as_text=True)
    assert any(dia in semana for dia in ("lun ", "mar ", "mié ", "jue ", "vie ", "sáb ", "dom "))


def test_estadisticas_ya_no_trae_contactos_importaciones_ni_plan(client, database, outbox):
    browser = inside(client)
    pantalla = browser.get("/dashboard").get_data(as_text=True)
    for fuera in ("Tus contactos", "Importaciones", "Tu plan", "Correos al mes"):
        assert fuera not in pantalla
    assert "Aperturas y clics" in pantalla
    assert "Cómo le fue" in pantalla


def _envio(database, cuenta, campana, tags=()):
    run_id = ObjectId()
    runs.record(database, {"_id": campana, "account_id": cuenta, "subject": "Asamblea",
                           "tags": list(tags)}, run_id=run_id)
    return run_id


def test_los_porcentajes_cuentan_personas(client, database, outbox):
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")["_id"]
    campana = ObjectId()
    envio = _envio(database, cuenta, campana)
    for quien in ("a@x.com", "b@x.com", "c@x.com", "d@x.com"):
        events.record(database, cuenta, kind=events.SENT, campaign_id=campana,
                      run_id=envio, email=quien)
        events.record(database, cuenta, kind=events.DELIVERED, campaign_id=campana,
                      run_id=envio, email=quien)
    for _ in range(3):
        events.record(database, cuenta, kind=events.OPEN, campaign_id=campana,
                      run_id=envio, email="a@x.com")

    cifras = {one["key"]: one for one in
              stats.rates(events.people(database, cuenta, period="24h"))}
    assert cifras["delivery"]["pct"] == 100
    # Una persona que abrió tres veces es una de cuatro.
    assert cifras["open"]["n"] == 1
    assert cifras["open"]["pct"] == 25


def test_el_filtro_por_campana_no_mira_la_de_otra_cuenta(client, database, outbox):
    inside(client)
    ana = accounts.by_email(database, "ana@ejemplo.com")
    inside(client, "bea@ejemplo.com")
    bea = accounts.by_email(database, "bea@ejemplo.com")
    de_bea = ObjectId()
    _envio(database, bea["_id"], de_bea)

    with client.application.test_request_context("/dashboard"):
        pantalla = stats.screen(database, ana, campaign=str(de_bea))
    assert pantalla["campaign"] is None


def test_el_filtro_por_etiqueta_ya_filtra(client, database, outbox):
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")["_id"]
    socios = _envio(database, cuenta, ObjectId(), tags=["Socios"])
    otros = _envio(database, cuenta, ObjectId(), tags=["Junta"])
    events.record(database, cuenta, kind=events.SENT, run_id=socios, email="a@x.com")
    events.record(database, cuenta, kind=events.SENT, run_id=otros, email="b@x.com")
    events.record(database, cuenta, kind=events.SENT, run_id=otros, email="c@x.com")

    assert events.totals(database, cuenta, tag="Socios")[events.SENT] == 1
    assert events.totals(database, cuenta, tag="Junta")[events.SENT] == 2


# ------------------------------------------------------------ facturación

def pagado(client, database, monkeypatch):
    # Las facturas están escondidas por ahora (`invoices.SHOWN`); estas pruebas
    # fijan cómo funcionan el día que se enciendan.
    monkeypatch.setattr(invoices, "SHOWN", True)
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser)
    come_back(browser)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    pago = payments.for_account(database, cuenta["_id"], only_paid=True)[0]
    return browser, cuenta, pago


PDF = b"%PDF-1.4\n% factura de mentira\n"


def test_facturacion_ensena_la_fecha_exacta_y_la_factura_en_camino(
        client, database, outbox, monkeypatch):
    browser, cuenta, pago = pagado(client, database, monkeypatch)
    en_panama(browser)
    pantalla = browser.get("/settings/billing").get_data(as_text=True)
    assert "Facturación" in pantalla
    hasta = accounts.plan_until(accounts.by_email(database, "ana@ejemplo.com"))
    local = hasta.astimezone(PANAMA)
    assert f"hasta el {local.day} de" in pantalla
    assert "Factura en camino" in pantalla


def test_el_admin_sube_la_factura_y_el_cliente_la_baja(client, database, outbox,
                                                       monkeypatch):
    browser, cuenta, pago = pagado(client, database, monkeypatch)
    admin, _ = make_admin(client, database)
    url = f"/admin/accounts/{cuenta['_id']}"
    admin.get(url)
    with admin.session_transaction() as sess:
        token = sess["_csrf"]

    # Lo que no es PDF no entra.
    admin.post(f"{url}/invoice", data={"csrf_token": token, "pago": str(pago["_id"]),
                                       "archivo": (io.BytesIO(b"<html>no</html>"), "f.pdf")},
               content_type="multipart/form-data")
    assert database.invoices.count_documents({}) == 0

    admin.post(f"{url}/invoice", data={"csrf_token": token, "pago": str(pago["_id"]),
                                       "archivo": (io.BytesIO(PDF), "f.pdf")},
               content_type="multipart/form-data")
    assert database.invoices.count_documents({}) == 1

    bajada = browser.get(f"/settings/billing/invoice/{pago['_id']}")
    assert bajada.status_code == 200
    assert bajada.mimetype == "application/pdf"
    assert bajada.headers["Content-Disposition"].startswith("attachment")
    assert bajada.get_data() == PDF

    # Y la de otra cuenta no existe para nadie más.
    bea = inside(client, "bea@ejemplo.com")
    assert bea.get(f"/settings/billing/invoice/{pago['_id']}").status_code == 404


def test_al_cobrar_se_guarda_quien_pago(client, database, outbox, monkeypatch):
    from services import paypal

    fake_paypal(monkeypatch)
    original = paypal.capture
    monkeypatch.setattr(paypal, "capture", lambda order: {**original(order),
                                                          "payer": "ana@coop.com"})
    browser = inside(client)
    confirm(database)
    buy(browser)
    come_back(browser)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert payments.for_account(database, cuenta["_id"])[0]["payer_email"] == "ana@coop.com"
    # Se guarda, pero no se enseña: es para cuando haya cobros recurrentes.
    assert "ana@coop.com" not in browser.get("/settings/billing").get_data(as_text=True)


def test_con_las_facturas_escondidas_no_se_ven_ni_se_suben(client, database, outbox,
                                                          monkeypatch):
    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)
    buy(browser)
    come_back(browser)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    pago = payments.for_account(database, cuenta["_id"], only_paid=True)[0]

    pantalla = browser.get("/settings/billing").get_data(as_text=True)
    assert "Factura en camino" not in pantalla
    admin, _ = make_admin(client, database)
    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Pagos y facturas" not in ficha
    assert browser.get(f"/settings/billing/invoice/{pago['_id']}").status_code == 404


# ------------------------------------------------------------ borrar contactos

def test_borrar_un_contacto_pregunta_primero(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    contacts.create(database, cuenta["_id"], email="ana@coop.com", name="Ana",
                    consent=contacts.consent_of(contacts.MEMBERS))
    fila = database.contacts.find_one({"email_normalized": "ana@coop.com"})

    lista = browser.get("/contacts").get_data(as_text=True)
    assert f"/contacts/delete/{fila['_id']}" in lista

    pregunta = browser.get(f"/contacts/delete/{fila['_id']}").get_data(as_text=True)
    assert "Vas a eliminar 1 contacto" in pregunta
    # Mirar la pregunta no borra nada.
    assert contacts.count(database, cuenta["_id"]) == 1


def test_eliminar_los_anulados_dice_cuantos(client, database, outbox):
    from models import suppression as suppressions

    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    for email in ("a@coop.com", "b@coop.com", "c@coop.com"):
        contacts.create(database, cuenta["_id"], email=email, name="x",
                        consent=contacts.consent_of(contacts.MEMBERS))
    for email in ("a@coop.com", "b@coop.com"):
        suppressions.add(database, cuenta["_id"], email, reason=suppressions.UNSUBSCRIBE)

    pregunta = browser.get("/contacts/suppressed/delete").get_data(as_text=True)
    assert "Vas a eliminar 2 contactos" in pregunta
    assert contacts.count(database, cuenta["_id"]) == 3
