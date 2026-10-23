"""El ritmo de envío de todo Sobreala (octubre de 2026).

Lo que fijan estas pruebas: que entre todos no se pasa del límite por segundo
de Amazon; que las campañas dejan huecos para un código de confirmación; que
el tope del día frena las campañas (sin darlas por falladas) y la API, y deja
una reserva para los correos del sistema; que los límites se leen de Amazon y
las variables solo los bajan; que sin permiso en IAM se usan las variables; y
que un correo del sistema reintenta si Amazon pide esperar.
"""

from __future__ import annotations

import pytest

from config import Config
from models import campaign as campaigns
from services import background, mailer, send_rate
from test_api_contactos import llave
from test_api_correos import enviar
from test_campaigns import catch, make, ready, send_it


@pytest.fixture
def amazon(monkeypatch):
    """SES de verdad, con lo que diga este diccionario como su límite."""
    dice = {"rate": 1.0, "day": 200, "sent": 0}
    monkeypatch.setattr(send_rate, "enabled", lambda: True)
    monkeypatch.setattr(send_rate, "_ask_amazon", lambda: dict(dice))
    monkeypatch.setattr(Config, "SES_MAX_PER_SECOND", None)
    monkeypatch.setattr(Config, "SES_MAX_PER_DAY", None)
    return dice


class Reloj:
    def __init__(self):
        self.ahora, self.esperas = 1000.0, []

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.esperas.append(round(segundos, 2))


def test_nadie_pasa_del_limite_por_segundo(database, amazon):
    reloj = Reloj()
    for _ in range(3):
        send_rate.take(database, send_rate.SYSTEM, clock=reloj, sleep=reloj.dormir)
    # A 1 por segundo, el segundo espera 1 y el tercero 2.
    assert reloj.esperas == [1.0, 2.0]


def test_las_campanas_dejan_hueco_para_un_codigo(database, amazon):
    reloj = Reloj()
    send_rate.take(database, send_rate.CAMPAIGN, clock=reloj, sleep=reloj.dormir)
    send_rate.take(database, send_rate.SYSTEM, clock=reloj, sleep=reloj.dormir)
    # La campaña toma un turno de 1.25 s (el 80 % del ritmo); el código entra
    # detrás, sin esperar a que salga una campaña entera.
    assert reloj.esperas == [1.25]


def test_la_api_no_espera_mas_de_lo_suyo(database, amazon):
    reloj = Reloj()
    database.ses_limits.update_one({"_id": send_rate.CLOCK},
                                   {"$set": {"next_at": reloj.ahora + 30}}, upsert=True)
    with pytest.raises(send_rate.Busy):
        send_rate.take(database, send_rate.API, clock=reloj, sleep=reloj.dormir)


def test_los_limites_vienen_de_amazon_y_las_variables_solo_bajan(database, amazon,
                                                                monkeypatch):
    amazon.update(rate=14.0, day=50000)
    assert send_rate.limits(database)["per_second"] == 14.0
    monkeypatch.setattr(Config, "SES_MAX_PER_SECOND", 2)
    monkeypatch.setattr(Config, "SES_MAX_PER_DAY", 180)
    hechos = send_rate.limits(database)
    assert hechos["per_second"] == 2.0 and hechos["per_day"] == 180
    # Más alto que Amazon no sube nada.
    monkeypatch.setattr(Config, "SES_MAX_PER_SECOND", 50)
    assert send_rate.limits(database)["per_second"] == 14.0


def test_sin_permiso_en_iam_rigen_las_variables(database, monkeypatch):
    monkeypatch.setattr(send_rate, "enabled", lambda: True)
    monkeypatch.setattr(send_rate, "_ask_amazon", lambda: None)
    monkeypatch.setattr(Config, "SES_MAX_PER_SECOND", 3)
    monkeypatch.setattr(Config, "SES_MAX_PER_DAY", 150)
    hechos = send_rate.limits(database)
    assert hechos["per_second"] == 3.0 and hechos["per_day"] == 150
    assert send_rate.status(database)["ses_limits_from"] == "config"


def test_el_tope_del_dia_deja_una_reserva_para_el_sistema(database, amazon):
    amazon.update(day=200, sent=170)
    assert send_rate.day_room(database, send_rate.SYSTEM) == 30
    assert send_rate.day_room(database, send_rate.CAMPAIGN) == 10
    # Lo que sale se cuenta hasta la próxima pregunta a Amazon.
    reloj = Reloj()
    send_rate.take(database, send_rate.SYSTEM, clock=reloj, sleep=reloj.dormir)
    assert send_rate.day_room(database, send_rate.SYSTEM) == 29


def test_una_campana_sin_sitio_en_el_dia_espera_y_no_falla(client, database, outbox,
                                                           monkeypatch, amazon):
    salidos = catch(monkeypatch)
    amazon.update(day=200, sent=195)
    browser, account, piece = ready(client, database, howmany=2)
    make(browser, piece)
    respuesta, una = send_it(browser, database, account["_id"])
    assert "done=started" in respuesta.headers["Location"]
    assert salidos == []
    esperando = campaigns.by_id(database, account["_id"], una["_id"])
    assert esperando["waiting"] == ["daily_limit"] and esperando.get("failed", 0) == 0
    # Al día siguiente (Amazon cuenta de nuevo), sale sola.
    amazon.update(sent=0)
    database.ses_limits.delete_many({})
    database.campaigns.update_one({"_id": una["_id"]}, {"$unset": {"retry_at": ""}})
    background.campaigns_tick(database, "pruebas")
    assert len(salidos) == 2


def test_la_api_sin_sitio_en_el_dia_responde_429(client, database, outbox, monkeypatch,
                                                 amazon):
    catch(monkeypatch)
    amazon.update(day=200, sent=190)
    _, cuenta, _ = ready(client, database, howmany=0)
    auth, _ = llave(database, cuenta, scopes=("emails:send",))
    respuesta = enviar(client, auth)
    assert respuesta.status_code == 429
    assert respuesta.get_json()["error"]["code"] == "daily_limit"
    assert respuesta.headers["Retry-After"]


def test_un_correo_del_sistema_reintenta_si_amazon_pide_esperar(database, monkeypatch,
                                                               amazon):
    class Lleno(Exception):
        response = {"Error": {"Code": "Throttling"}}

    intentos = []

    class Ses:
        def send_email(self, **_):
            intentos.append(1)
            if len(intentos) < 3:
                raise Lleno()
            return {"MessageId": "ok-3"}

    from services import aws
    monkeypatch.setattr(aws, "client", lambda name: Ses())
    monkeypatch.setattr(mailer.time, "sleep", lambda s: None)
    monkeypatch.setattr(send_rate.time, "sleep", lambda s: None)
    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    assert mailer._send_ses("ana@ejemplo.com", "Código", "<p>1</p>", "1") == "ok-3"
    assert len(intentos) == 3


def test_health_dice_el_ritmo(client, database, amazon):
    estado = client.get("/health").get_json()
    assert estado["ses_rate"] == 1.0 and estado["ses_day_left"] == 200
