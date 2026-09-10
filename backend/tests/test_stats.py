"""La pantalla de estadísticas, que miran el cliente y el administrador.

Es la misma plantilla para los dos, así que lo que se fija aquí vale para las
dos entradas. Lo importante es que **sin datos no se rompe ni se esconde**: las
colecciones de envíos todavía no existen, y la pantalla tiene que dibujar el
cuadro vacío diciéndolo.
"""

from __future__ import annotations

from datetime import timedelta

import pyotp
from conftest import login, register

from models import account as accounts
from models import event as events

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def make_admin(client, database, email="jefe@ejemplo.com"):
    """Un administrador: la cuenta, el rol y el doble factor, que /admin exige."""
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    cuenta = accounts.by_email(database, email)
    database.accounts.update_one(
        {"_id": cuenta["_id"]},
        {"$set": {"email_confirmed_at": cuenta["created_at"]}})
    accounts.set_role(database, cuenta["_id"], accounts.ADMIN)

    browser.get("/cuenta/dos-pasos")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    browser.post("/cuenta/dos-pasos", data={"csrf_token": token,
                                            "password": PASSWORD})
    browser.get("/cuenta/dos-pasos/activar")
    with browser.session_transaction() as sess:
        secret, token = sess["two_factor_setup"], sess["_csrf"]
    browser.post("/cuenta/dos-pasos/activar", data={
        "csrf_token": token, "code": list(pyotp.TOTP(secret).now())})
    return browser, accounts.by_email(database, email)


# ------------------------------------------------------ sin un solo envío

def test_sin_envios_la_grafica_se_dibuja_y_lo_dice(client, database, outbox):
    """Un cuadro vacío que se explica dice más que un hueco."""
    browser = inside(client)

    pantalla = browser.get("/panel")
    assert pantalla.status_code == 200
    texto = pantalla.get_data(as_text=True)
    assert "Todavía no se ha realizado ninguna acción" in texto
    # Y la gráfica está ahí, con sus ejes y su leyenda.
    assert "chart__svg" in texto
    assert "Enviados" in texto and "Rebotes" in texto


def test_sin_la_coleccion_los_totales_son_cero(client, database, outbox):
    """`events` no existe todavía; leerla no puede reventar."""
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")

    totals = events.totals(database, cuenta["_id"])
    assert set(totals) == set(events.KINDS)
    assert sum(totals.values()) == 0
    assert events.busiest(events.series(database, cuenta["_id"]),
                          (events.SENT, events.BOUNCE)) == 0


# ------------------------------------------------------------ con envíos

def test_la_serie_cuenta_cada_evento_en_su_tramo(client, database, outbox):
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    ahora = events.now()

    events.record(database, cuenta["_id"], kind=events.SENT, at=ahora)
    events.record(database, cuenta["_id"], kind=events.SENT, at=ahora)
    events.record(database, cuenta["_id"], kind=events.BOUNCE, at=ahora)
    # Uno de hace tres días: fuera de las últimas 24 horas.
    events.record(database, cuenta["_id"], kind=events.SENT,
                  at=ahora - timedelta(days=3))

    dia = events.totals(database, cuenta["_id"], period="24h")
    assert dia[events.SENT] == 2
    assert dia[events.BOUNCE] == 1

    mes = events.totals(database, cuenta["_id"], period="30d")
    assert mes[events.SENT] == 3

    serie = events.series(database, cuenta["_id"], period="24h")
    assert sum(row[events.SENT] for row in serie) == 2
    assert events.busiest(serie, (events.SENT, events.BOUNCE)) == 3


def test_los_eventos_de_otra_cuenta_no_se_mezclan(client, database, outbox):
    inside(client)
    inside(client, "bea@ejemplo.com")
    ana = accounts.by_email(database, "ana@ejemplo.com")
    bea = accounts.by_email(database, "bea@ejemplo.com")

    events.record(database, bea["_id"], kind=events.SENT)

    assert events.totals(database, ana["_id"])[events.SENT] == 0
    assert events.totals(database, bea["_id"])[events.SENT] == 1


def test_un_periodo_inventado_cae_en_el_de_siempre():
    assert events.clean_period("un-siglo") == events.DEFAULT_PERIOD
    assert events.clean_period(None) == events.DEFAULT_PERIOD
    assert events.clean_period("7d") == "7d"


# ------------------------------------------------------------- los filtros

def test_una_etiqueta_ajena_no_filtra_por_nada(client, database, outbox):
    """Lo que llega por la dirección se limpia: una etiqueta que no es de esta
    cuenta no puede filtrar por algo de otra."""
    from services import stats

    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    accounts.add_tag(database, cuenta["_id"], "socios")
    cuenta = accounts.by_id(database, cuenta["_id"])

    assert stats.screen(database, cuenta, tag="socios")["tag"] == "socios"
    assert stats.screen(database, cuenta, tag="de-otra")["tag"] == ""

    pantalla = browser.get("/panel?etiqueta=socios&periodo=7d")
    assert pantalla.status_code == 200
    assert "Últimos 7 días" in pantalla.get_data(as_text=True)


# --------------------------------------------------- las dos entradas

def test_el_cliente_no_ve_el_selector_de_cuentas(client, database, outbox):
    browser = inside(client)

    texto = browser.get("/panel").get_data(as_text=True)
    assert 'name="cuenta"' not in texto
    assert "Hola, Ana" in texto


def test_el_administrador_elige_de_quien_son(client, database, outbox):
    admin, _ = make_admin(client, database)
    inside(client, "socia@ejemplo.com")
    otra = accounts.by_email(database, "socia@ejemplo.com")

    pantalla = admin.get("/admin/")
    assert pantalla.status_code == 200
    texto = pantalla.get_data(as_text=True)
    assert 'name="cuenta"' in texto
    assert otra["company_name"] in texto

    # Una cuenta que no existe no enseña la de nadie más: cae en la primera.
    inventada = admin.get("/admin/?cuenta=000000000000000000000000")
    assert inventada.status_code == 200
    assert otra["company_name"] in inventada.get_data(as_text=True)


def test_sin_clientes_el_administrador_ve_por_que(client, database, outbox):
    admin, _ = make_admin(client, database)

    texto = admin.get("/admin/").get_data(as_text=True)
    assert "Todavía no hay clientes" in texto
