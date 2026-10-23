"""El proceso en segundo plano y lo que lo hace seguro (octubre de 2026).

Lo que fijan estas pruebas: que una campaña guardada con fecha sale sola a su
hora, por tandas, y una «ahora mismo» no; que el turno impide que dos la manden
a la vez y que `start()` en None no manda nada; que nadie recibe dos veces
aunque una tanda se caiga a la mitad; que borrar contactos a mitad de camino no
salta a nadie; que parar y que Amazon pida esperar no dan a nadie por fallado
ni gastan cuota; que una que no puede salir espera y lo dice; que la migración
no rearma campañas viejas; y que sin la llave del web no sale nada.
"""

from __future__ import annotations

from datetime import timedelta

from test_campaigns import WHEN, catch, csrf, make, ready, send_it

from config import Config
from models import account as accounts
from models import campaign as campaigns
from models import contact as contacts
from services import background, sender


def programada(database, browser, account, piece, *, minutes_ago=1):
    """Una campaña guardada con fecha, a la que ya le llegó la hora."""
    pronto = (accounts.now() + timedelta(days=1)).strftime(WHEN)
    make(browser, piece, subject="Boletín", when="fecha", fecha=pronto)
    one = campaigns.for_account(database, account["_id"])[0]
    database.campaigns.update_one({"_id": one["_id"]}, {"$set": {
        "scheduled_at": accounts.now() - timedelta(minutes=minutes_ago)}})
    return campaigns.by_id(database, account["_id"], one["_id"])


def test_con_fecha_sale_sola_por_tandas(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    monkeypatch.setattr(sender, "BATCH", 2)
    browser, account, piece = ready(client, database, howmany=5)
    one = programada(database, browser, account, piece)
    assert one["auto_send"] is True

    assert background.campaigns_tick(database, "w1") == 2
    medio = campaigns.by_id(database, account["_id"], one["_id"])
    assert medio["status"] == campaigns.SENDING and medio["position"] == 2
    assert "lease_by" not in medio
    for _ in range(5):
        background.campaigns_tick(database, "w1")
    hecha = campaigns.by_id(database, account["_id"], one["_id"])
    assert hecha["status"] == campaigns.SENT and hecha["sent"] == 5
    assert sorted(m["To"] for m in salidos) == [f"socio{n}@ejemplo.com" for n in range(5)]
    assert database.campaign_runs.count_documents({"campaign_id": one["_id"]}) == 1
    # Terminada, ya no la toma.
    assert background.campaigns_tick(database, "w1") == 0


def test_ahora_mismo_espera_a_enviar(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    make(browser, piece, subject="Ya")
    one = campaigns.for_account(database, account["_id"])[0]
    assert one["auto_send"] is False
    assert background.campaigns_tick(database, "w1") == 0 and salidos == []


def test_enviar_desde_el_panel_deja_el_resto_al_proceso(client, database, outbox,
                                                        monkeypatch):
    salidos = catch(monkeypatch)
    monkeypatch.setattr(sender, "BATCH", 2)
    browser, account, piece = ready(client, database, howmany=3)
    make(browser, piece, subject="Ya")
    # «Enviar» ya no manda desde la página (octubre de 2026): la deja lista
    # para el proceso, que es el único que reparte el ritmo de Amazon.
    respuesta, one = send_it(browser, database, account["_id"], vueltas=0)
    assert "done=started" in respuesta.headers["Location"]
    lista = campaigns.by_id(database, account["_id"], one["_id"])
    assert lista["auto_send"] is True and "lease_by" not in lista and salidos == []
    assert background.campaigns_tick(database, "w1") == 2
    assert background.campaigns_tick(database, "w1") == 1
    assert campaigns.by_id(database, account["_id"], one["_id"])["status"] == campaigns.SENT

    # Si el proceso tiene el turno, el panel no manda.
    make(browser, piece, subject="Otra")
    otra = campaigns.for_account(database, account["_id"])[0]
    assert campaigns.take(database, account["_id"], otra["_id"], "w1")
    ocupada, _ = send_it(browser, database, account["_id"], vueltas=0)
    assert "done=busy" in ocupada.headers["Location"] and len(salidos) == 3


def test_el_turno_es_de_uno_y_se_vence(client, database, outbox):
    browser, account, piece = ready(client, database, howmany=1)
    one = programada(database, browser, account, piece)
    assert campaigns.take(database, account["_id"], one["_id"], "a")
    assert not campaigns.take(database, account["_id"], one["_id"], "b")
    assert campaigns.take(database, account["_id"], one["_id"], "a")
    database.campaigns.update_one({"_id": one["_id"]}, {"$set": {
        "lease_until": accounts.now() - timedelta(seconds=1)}})
    assert campaigns.take(database, account["_id"], one["_id"], "b")
    # Quien perdió el turno no anota nada.
    assert not campaigns.advance(database, account["_id"], one["_id"], position=9, sent=9,
                                 skipped=0, failed=0, errors=[], by="a")
    assert campaigns.by_id(database, account["_id"], one["_id"])["position"] == 0


def test_si_otro_la_arranco_no_se_manda_nada(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    one = programada(database, browser, account, piece)
    assert campaigns.start(database, account["_id"], one["_id"], 2)
    resultado = sender.run(database, account, one)
    assert resultado["blocked"] == ["busy"] and salidos == []


def test_nadie_recibe_dos_veces_tras_una_caida(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    monkeypatch.setattr(sender, "BATCH", 3)
    browser, account, piece = ready(client, database, howmany=3)
    one = programada(database, browser, account, piece)
    background.campaigns_tick(database, "w1")
    assert len(salidos) == 3
    # Como si la tanda se hubiera caído después de entregar y antes de anotar.
    database.campaigns.update_one({"_id": one["_id"]}, {"$set": {
        "status": campaigns.SENDING, "position": 0, "cursor_id": None,
        "auto_send": True, "finished_at": None}})
    database.campaign_runs.delete_many({})
    background.campaigns_tick(database, "w1")
    assert len(salidos) == 3


def test_borrar_contactos_a_mitad_no_salta_a_nadie(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    monkeypatch.setattr(sender, "BATCH", 2)
    browser, account, piece = ready(client, database, howmany=6)
    one = programada(database, browser, account, piece)
    background.campaigns_tick(database, "w1")
    primeros = {m["To"] for m in salidos}
    # Se borran los dos que ya recibieron: contar por posición saltaría a dos.
    for email in primeros:
        contacts.delete(database, account["_id"], email)
    for _ in range(5):
        background.campaigns_tick(database, "w1")
    assert len({m["To"] for m in salidos}) == 6
    assert campaigns.by_id(database, account["_id"], one["_id"])["status"] == campaigns.SENT


def test_parar_y_que_amazon_pida_esperar(client, database, outbox, monkeypatch):
    salidos = []

    class Throttling(Exception):
        response = {"Error": {"Code": "Throttling"}}

    def a_veces(message, **_):
        if len(salidos) == 2:
            salidos.append(None)
            raise Throttling("Maximum sending rate exceeded.")
        salidos.append(message)
        return "ok"

    monkeypatch.setattr(sender, "deliver", a_veces)
    browser, account, piece = ready(client, database, howmany=4)
    one = programada(database, browser, account, piece)
    antes = accounts.used_this_month(accounts.by_id(database, account["_id"]))
    background.campaigns_tick(database, "w1")
    medio = campaigns.by_id(database, account["_id"], one["_id"])
    assert medio["sent"] == 2 and medio["failed"] == 0 and medio["position"] == 2
    assert medio["status"] == campaigns.SENDING
    assert accounts.used_this_month(accounts.by_id(database, account["_id"])) == antes + 2

    # Parar entre un correo y otro: se anota hasta dónde llegó.
    monkeypatch.setattr(sender, "deliver", lambda message, **_: "ok")
    vistos = []
    resultado = sender.run(database, accounts.by_id(database, account["_id"]),
                           campaigns.by_id(database, account["_id"], one["_id"]),
                           stop=lambda: len(vistos.append(1) or vistos) > 1)
    assert resultado["stopped"] and resultado["sent"] == 1
    assert campaigns.by_id(database, account["_id"], one["_id"])["position"] == 3
    background.campaigns_tick(database, "w1")
    assert campaigns.by_id(database, account["_id"], one["_id"])["status"] == campaigns.SENT


def test_la_que_no_puede_salir_espera_y_lo_dice(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=2)
    one = programada(database, browser, account, piece)
    accounts.pause(database, account["_id"], reason="bounces", note="5 %")
    assert background.campaigns_tick(database, "w1") == 0
    esperando = campaigns.by_id(database, account["_id"], one["_id"])
    assert esperando["waiting"] == ["paused"] and esperando["retry_at"]
    assert "No pudo salir" in browser.get("/campaigns").get_data(as_text=True)
    # Hasta su reintento no se vuelve a mirar, aunque ya pueda.
    assert accounts.unlimit(database, account["_id"])
    assert background.campaigns_tick(database, "w1") == 0
    database.campaigns.update_one({"_id": one["_id"]}, {"$set": {
        "retry_at": accounts.now() - timedelta(seconds=1)}})
    assert background.campaigns_tick(database, "w1") == 2
    assert "waiting" not in campaigns.by_id(database, account["_id"], one["_id"])
    assert len(salidos) == 2

    # Una cuenta suspendida no manda nada por detrás.
    otra, cuenta, pieza = ready(client, database, email="otra@ejemplo.com", howmany=1)
    suya = programada(database, otra, cuenta, pieza)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"status": "suspended"}})
    background.campaigns_tick(database, "w1")
    assert campaigns.by_id(database, cuenta["_id"], suya["_id"])["waiting"] == ["suspended"]


def test_la_migracion_no_rearma_lo_viejo(client, database, outbox):
    _, account, piece = ready(client, database, howmany=0)
    base = {"account_id": account["_id"], "design_id": piece, "subject": "x",
            "tags": [], "position": 0}
    futura = database.campaigns.insert_one({**base, "status": campaigns.SCHEDULED,
        "scheduled_at": accounts.now() + timedelta(days=1)}).inserted_id
    pasada = database.campaigns.insert_one({**base, "status": campaigns.SCHEDULED,
        "scheduled_at": accounts.now() - timedelta(days=1)}).inserted_id
    apagada = database.campaigns.insert_one({**base, "status": campaigns.SCHEDULED,
        "auto_send": False, "scheduled_at": accounts.now() + timedelta(days=1)}).inserted_id
    assert campaigns.migrate_auto_send(database) == 1
    valor = {one["_id"]: one["auto_send"] for one in database.campaigns.find()}
    assert valor[futura] is True and valor[pasada] is False and valor[apagada] is False


def test_sin_la_llave_del_web_no_sale_nada(client, database, outbox, monkeypatch):
    assert background.key_ok(database) is None
    background.publish_web_key(database)
    assert background.key_ok(database) is True
    monkeypatch.setattr(Config, "SECRET_KEY", "otra-llave")
    assert background.key_ok(database) is False
    background.beat(database, "w1", key=False)
    estado = client.get("/health").get_json()
    assert estado["worker"] == "up" and estado["worker_key"] == "mismatch"
    database.worker_state.update_one({"_id": "worker"}, {"$set": {
        "at": accounts.now() - timedelta(minutes=5)}})
    assert client.get("/health").get_json()["worker"] == "down"
