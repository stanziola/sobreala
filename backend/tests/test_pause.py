"""La pausa automática por rebotes y quejas (`services/reputation.py`).

Amazon mide la cuenta entera de Sobreala, así que un cliente con una lista mala
pone en riesgo a todos. Lo que fijan estas pruebas es **dónde está el corte**:
más de 3 % de rebotes permanentes desde 100 enviados, más de 0.1 % de quejas
desde 1,000, en los últimos 30 días. Que por debajo del volumen mínimo no se
pausa a nadie por una sola persona. Que la pausa **para el envío en la tanda
siguiente**, que avisa al cliente y a quien administra, y que **solo la quita el
administrador**: aprobar la verificación no la levanta.
"""

from __future__ import annotations

from datetime import timedelta

from bson import ObjectId
from test_admin import make_admin
from test_campaigns import WHEN, catch, make, ready
from test_verificaciones import decide, enviar, limit
from test_webhooks import bounce, campaign_event, configured, notify  # noqa: F401

from models import account as accounts
from models import admin_event as decisions
from models import campaign as campaigns
from models import event as events
from models import mail_log
from services import reputation, sender


def enviados(database, cuenta_id, n, *, hace=timedelta(0)):
    """`n` correos que ya salieron de esa cuenta, uno por persona."""
    when = events.now() - hace
    database.events.insert_many([
        {"account_id": cuenta_id, "campaign_id": None, "run_id": ObjectId(),
         "kind": events.SENT, "email_normalized": f"p{i}@coop.com",
         "created_at": when} for i in range(n)])


def rebota(client, cuenta_id, *personas):
    for quien in personas:
        notify(client, campaign_event(
            "Bounce", account=cuenta_id, campaign=ObjectId(), run=ObjectId(),
            to=quien, **bounce("Permanent", quien)))


def se_queja(client, cuenta_id, *personas):
    for quien in personas:
        notify(client, campaign_event(
            "Complaint", account=cuenta_id, campaign=ObjectId(), run=ObjectId(),
            to=quien, complaint={"timestamp": "2026-09-16T12:05:00.000Z",
                                 "complainedRecipients": [{"emailAddress": quien}]}))


def fresca(database, cuenta):
    return accounts.by_id(database, cuenta["_id"])


# ------------------------------------------------------------------ el corte

def test_tres_rebotes_de_cien_no_pausan_y_cuatro_si(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 100)

    rebota(client, cuenta["_id"], "p0@coop.com", "p1@coop.com", "p2@coop.com")
    assert not accounts.is_paused(fresca(database, cuenta))

    rebota(client, cuenta["_id"], "p3@coop.com")
    ahora = fresca(database, cuenta)
    assert accounts.is_paused(ahora)
    assert accounts.limited_of(ahora)["reason"] == accounts.PAUSE_BOUNCES
    assert "4.0 %" in accounts.limited_of(ahora)["note"]
    assert "paused" in sender.blocked(ahora) and "limited" not in sender.blocked(ahora)
    # Queda en el registro, sin administrador: lo hizo el panel.
    hecho = database.admin_events.find_one({"account_id": cuenta["_id"],
                                            "kind": decisions.LIMIT})
    assert hecho["admin_id"] is None and hecho["after"] == accounts.PAUSE_BOUNCES


def test_un_rebote_pasajero_no_cuenta(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 100)
    for i in range(10):
        quien = f"p{i}@coop.com"
        notify(client, campaign_event(
            "Bounce", account=cuenta["_id"], campaign=ObjectId(), run=ObjectId(),
            to=quien, **bounce("Transient", quien)))
    assert not accounts.is_paused(fresca(database, cuenta))


def test_con_poco_volumen_no_pausa(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 99)
    rebota(client, cuenta["_id"], *[f"p{i}@coop.com" for i in range(10)])
    assert not accounts.is_paused(fresca(database, cuenta))


def test_lo_de_hace_mas_de_treinta_dias_no_cuenta(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 100, hace=timedelta(days=31))
    enviados(database, cuenta["_id"], 50)
    rebota(client, cuenta["_id"], *[f"p{i}@coop.com" for i in range(10)])
    assert not accounts.is_paused(fresca(database, cuenta))


def test_una_queja_de_mil_no_pausa_y_dos_si(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 1000)

    se_queja(client, cuenta["_id"], "p0@coop.com")
    assert not accounts.is_paused(fresca(database, cuenta))

    se_queja(client, cuenta["_id"], "p1@coop.com")
    ahora = fresca(database, cuenta)
    assert accounts.limited_of(ahora)["reason"] == accounts.PAUSE_COMPLAINTS
    assert "0.20 %" in accounts.limited_of(ahora)["note"]


def test_las_cifras_de_otra_cuenta_no_se_mezclan(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    otra = ObjectId()
    enviados(database, cuenta["_id"], 100)
    rebota(client, otra, *[f"p{i}@coop.com" for i in range(10)])
    assert not accounts.is_paused(fresca(database, cuenta))
    cifras = reputation.figures(database, [cuenta["_id"], otra])
    assert cifras[cuenta["_id"]]["bounces"] == 0 and cifras[otra]["bounces"] == 10


# --------------------------------------------------------- lo que hace la pausa

def test_una_campana_a_medias_para_en_la_tanda_siguiente(client, database, outbox,
                                                          monkeypatch):
    browser, cuenta, pieza = ready(client, database, howmany=4)
    salidos = catch(monkeypatch)
    pronto = (accounts.now() + timedelta(days=2)).strftime(WHEN)
    make(browser, pieza, when="fecha", fecha=pronto)
    campana = campaigns.for_account(database, cuenta["_id"])[0]

    primera = sender.run(database, fresca(database, cuenta), campana, limit=2)
    assert primera["sent"] == 2 and primera["left"] == 2

    accounts.pause(database, cuenta["_id"], reason=accounts.PAUSE_BOUNCES, note="x")
    campana = campaigns.for_account(database, cuenta["_id"])[0]
    segunda = sender.run(database, fresca(database, cuenta), campana, limit=2)

    assert segunda["blocked"] == ["paused"] and len(salidos) == 2


def test_avisa_al_cliente_y_a_quien_administra(client, database, outbox):
    make_admin(client, database)
    browser, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 100)
    rebota(client, cuenta["_id"], *[f"p{i}@coop.com" for i in range(4)])

    al_cliente = list(database.mail_log.find({"purpose": mail_log.PAUSED}))
    assert len(al_cliente) == 1 and al_cliente[0]["to"] == cuenta["email"]
    assert len(list(database.mail_log.find({"purpose": mail_log.ADMIN_PAUSE}))) == 1

    # Los rebotes que siguen llegando no vuelven a avisar.
    rebota(client, cuenta["_id"], "p5@coop.com", "p6@coop.com")
    assert database.mail_log.count_documents({"purpose": mail_log.PAUSED}) == 1

    # El cliente lo ve en sus pantallas, y no como el límite de verificación,
    # que se arregla subiendo documentos.
    for url in ("/campaigns", "/settings/account"):
        pantalla = browser.get(url).get_data(as_text=True)
        assert "Tus envíos están en pausa" in pantalla
        assert "Tu cuenta está limitada" not in pantalla


def test_solo_el_administrador_la_quita(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 100)
    rebota(client, cuenta["_id"], *[f"p{i}@coop.com" for i in range(4)])

    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Pausa automática por rebotes" in ficha

    limit(admin, cuenta, lift=True, nota="limpió su lista")

    assert "paused" not in sender.blocked(fresca(database, cuenta))


def test_aprobar_la_verificacion_no_levanta_la_pausa(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta, _ = ready(client, database)
    enviados(database, cuenta["_id"], 100)
    rebota(client, cuenta["_id"], *[f"p{i}@coop.com" for i in range(4)])

    enviar(browser)
    decide(admin, cuenta, accounts.IDENTITY, "verified")
    decide(admin, cuenta, accounts.ADDRESS, "verified")

    assert accounts.is_paused(fresca(database, cuenta))
