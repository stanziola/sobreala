"""La pantalla de estadísticas, que miran el cliente y el administrador.

Es la misma plantilla para los dos, así que lo que se fija aquí vale para las
dos entradas. Lo importante es que **sin datos no se rompe ni se esconde**: las
colecciones de envíos todavía no existen, y la pantalla tiene que dibujar el
cuadro vacío diciéndolo.
"""

from __future__ import annotations

from datetime import timedelta

import pyotp
from bson import ObjectId
from conftest import login, register

from i18n import t
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

    events.record(database, cuenta["_id"], kind=events.SENT, at=ahora, email="a@coop.com")
    events.record(database, cuenta["_id"], kind=events.SENT, at=ahora, email="b@coop.com")
    events.record(database, cuenta["_id"], kind=events.BOUNCE, at=ahora, email="b@coop.com")
    # Uno de hace tres días: fuera de las últimas 24 horas.
    events.record(database, cuenta["_id"], kind=events.SENT,
                  at=ahora - timedelta(days=3), email="c@coop.com")

    dia = events.totals(database, cuenta["_id"], period="24h")
    assert dia[events.SENT] == 2
    assert dia[events.BOUNCE] == 1

    mes = events.totals(database, cuenta["_id"], period="30d")
    assert mes[events.SENT] == 3

    serie = events.series(database, cuenta["_id"], period="24h")
    assert sum(row[events.SENT] for row in serie) == 2
    assert events.busiest(serie, (events.SENT, events.BOUNCE)) == 3


def test_la_grafica_cuenta_personas_como_como_le_fue(client, database, outbox):
    """Quien abre tres veces el mismo envío es una apertura, en el tramo en que
    abrió por primera vez: la gráfica y «Cómo le fue» cuentan lo mismo."""
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    ahora = events.now()
    envio = ObjectId()
    for minutos in (50, 20, 5):
        events.record(database, cuenta["_id"], kind=events.OPEN, run_id=envio,
                      email="ana@coop.com", at=ahora - timedelta(minutes=minutos))
    events.record(database, cuenta["_id"], kind=events.OPEN, run_id=envio,
                  email="luis@coop.com", at=ahora)

    serie = events.series(database, cuenta["_id"], period="1h",
                          kinds=(events.OPEN, events.CLICK))
    assert sum(row[events.OPEN] for row in serie) == 2
    assert events.people(database, cuenta["_id"], period="1h")[events.OPEN] == 2
    # La de Ana cae donde abrió la primera vez, hace 50 minutos.
    primero = next(i for i, row in enumerate(serie) if row[events.OPEN])
    assert primero < len(serie) - 5


def test_la_barra_de_correos_del_mes(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    sin_plan = browser.get("/panel").get_data(as_text=True)
    assert "Sin plan contratado: no hay correos incluidos." in sin_plan

    accounts.activate_plan(database, cuenta["_id"], "negocio",
                           events.now() + timedelta(days=30))
    accounts.add_sent(database, cuenta["_id"], 12600)
    pantalla = browser.get("/panel").get_data(as_text=True)
    assert "12,600 de 15,000 correos" in pantalla
    # Sin fecha de renovación: todavía no hay renovación automática.
    assert "se renuevan" not in pantalla
    # Pasado el 80 %, ámbar.
    assert 'class="meter__svg is-high"' in pantalla
    assert '<rect class="meter__used" width="84"' in pantalla


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


# --------------------------------------------- comparar con el periodo anterior

def test_el_tramo_anterior_va_pegado_y_mide_lo_mismo():
    ahora = events.window("7d")
    antes = events.window("7d", back=1)
    assert ahora[1] is None, "el de ahora se deja abierto por arriba"
    assert antes[1] == ahora[0], "el de antes termina donde empieza el de ahora"
    assert antes[1] - antes[0] == timedelta(days=7)
    # «Hoy» se compara con ayer hasta la misma hora, no con un dia entero.
    hoy = events.window("hoy")
    ayer = events.window("hoy", back=1)
    assert ayer[1] == hoy[0]
    assert ayer[1] - ayer[0] == events.slots("hoy")[-1] + timedelta(hours=1) - hoy[0]


def test_la_pastilla_dice_cuanto_cambio_y_si_eso_es_mejor(client, database, outbox):
    """Verde es que mejoro y rojo que empeoro, no que subiera: el doble de
    aperturas es verde y el doble de rebotes es rojo."""
    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    ahora = events.now()
    antes = ahora - timedelta(days=8)          # dentro de los 7 dias anteriores

    for quien in ("a", "b", "c", "d"):
        events.record(database, cuenta["_id"], kind=events.SENT, at=ahora,
                      email=f"{quien}@coop.com")
        events.record(database, cuenta["_id"], kind=events.DELIVERED, at=ahora,
                      email=f"{quien}@coop.com")
        events.record(database, cuenta["_id"], kind=events.SENT, at=antes,
                      email=f"{quien}@coop.com")
        events.record(database, cuenta["_id"], kind=events.DELIVERED, at=antes,
                      email=f"{quien}@coop.com")
    # Aperturas: una antes, dos ahora. Rebotes: uno antes, dos ahora.
    events.record(database, cuenta["_id"], kind=events.OPEN, at=antes, email="a@coop.com")
    for quien in ("a", "b"):
        events.record(database, cuenta["_id"], kind=events.OPEN, at=ahora,
                      email=f"{quien}@coop.com")
    events.record(database, cuenta["_id"], kind=events.BOUNCE, at=antes, email="c@coop.com")
    for quien in ("c", "d"):
        events.record(database, cuenta["_id"], kind=events.BOUNCE, at=ahora,
                      email=f"{quien}@coop.com")

    from services import stats
    filas = {one["key"]: one for one in stats.rates(
        events.people(database, cuenta["_id"], period="7d"),
        events.people(database, cuenta["_id"], period="7d", back=1))}

    assert filas["open"]["change"] == {"pct": 100, "up": True, "good": True}
    assert filas["bounce"]["change"] == {"pct": 100, "up": True, "good": False}
    # Lo que no se movio no lleva pastilla, y tampoco los enviados, que son los
    # mismos cuatro en los dos tramos.
    assert filas["sent"]["change"] is None
    assert filas["delivery"]["change"] is None


def test_sin_nada_antes_no_hay_con_que_comparar(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    events.record(database, cuenta["_id"], kind=events.SENT, email="a@coop.com")

    from services import stats
    filas = stats.rates(
        events.people(database, cuenta["_id"], period="7d"),
        events.people(database, cuenta["_id"], period="7d", back=1))
    assert all(one["change"] is None for one in filas)
    pantalla = browser.get("/panel?periodo=7d").get_data(as_text=True)
    assert "trend" not in pantalla
    assert "comparan con los 7 días anteriores" in pantalla


def test_el_cambio_no_se_redondea_antes_de_comparar():
    """Con el 12.5 % redondeado a 12, un 25 % se leia como «+108 %»: la cuenta
    se hace con la proporcion exacta."""
    from services import stats

    ahora = {events.SENT: 8, events.DELIVERED: 8, events.BOUNCE: 2,
             events.OPEN: 0, events.CLICK: 0, events.COMPLAINT: 0}
    antes = dict(ahora, **{events.BOUNCE: 1})
    filas = {one["key"]: one for one in stats.rates(ahora, antes)}
    assert filas["bounce"]["pct"] == 25
    assert filas["bounce"]["change"] == {"pct": 100, "up": True, "good": False}


def test_la_nota_nombra_el_periodo_que_esta_puesto(client, database, outbox):
    """Decia «los 7 dias» siempre, y se leia como si solo comparara eso."""
    browser = inside(client)
    for periodo, frase in (("24h", "las 24 horas anteriores"),
                           ("hoy", "ayer hasta esta misma hora"),
                           ("1h", "la hora anterior"),
                           ("90d", "los 90 días anteriores")):
        pantalla = browser.get(f"/panel?periodo={periodo}").get_data(as_text=True)
        assert f"comparan con {frase}" in pantalla, periodo


# ------------------------------------------------- las tarjetas nuevas

def sembrar(database, cuenta, *, run=None, cuando=None, abren=(), pulsan=(),
            gente=("a", "b", "c", "d")):
    """Un envio: a `gente` le sale y le llega, y algunos abren y pulsan."""
    run = run or ObjectId()
    cuando = cuando or events.now()
    for quien in gente:
        for kind in (events.SENT, events.DELIVERED):
            events.record(database, cuenta["_id"], kind=kind, run_id=run,
                          email=f"{quien}@coop.com", at=cuando)
    for quien in abren:
        events.record(database, cuenta["_id"], kind=events.OPEN, run_id=run,
                      email=f"{quien}@coop.com", at=cuando)
    for quien in pulsan:
        events.record(database, cuenta["_id"], kind=events.CLICK, run_id=run,
                      email=f"{quien}@coop.com", at=cuando)
    return run


def test_las_bajas_se_cuentan_y_con_un_filtro_no_se_ensenan(client, database, outbox):
    """El enlace de baja firma el contacto, no la campana: con un filtro
    puesto no se pueden atribuir, y se dice en vez de enganar."""
    from models import suppression as suppressions
    from services import stats

    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    sembrar(database, cuenta)
    suppressions.add(database, cuenta["_id"], "a@coop.com",
                     reason=suppressions.UNSUBSCRIBE)
    suppressions.add(database, cuenta["_id"], "b@coop.com",
                     reason=suppressions.HARD_BOUNCE)

    filas = {one["key"]: one for one in stats.screen(database, cuenta, period="7d")["rates"]}
    # Solo la voluntaria: el rebote duro ya se cuenta como rebote.
    assert filas["leave"]["n"] == 1
    assert filas["leave"]["of"] == 4

    # La etiqueta tiene que ser de la cuenta: una ajena no filtra por nada.
    accounts.add_tag(database, cuenta["_id"], "Socios")
    cuenta = accounts.by_id(database, cuenta["_id"])
    con_filtro = stats.screen(database, cuenta, period="7d", tag="Socios")
    assert con_filtro["leaves_off"] is True
    assert all(one["key"] != "leave" for one in con_filtro["rates"])
    assert t("stats_leaves_off")[:30] in browser.get(
        "/panel?periodo=7d&etiqueta=Socios").get_data(as_text=True)


def test_las_mejores_campanas_van_de_mas_abierta_a_menos(client, database, outbox):
    from models import campaign_run as runs
    from services import stats

    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    floja = sembrar(database, cuenta, abren=("a",))
    buena = sembrar(database, cuenta, abren=("a", "b", "c"), pulsan=("a",))
    for run, asunto in ((floja, "Aviso de corte"), (buena, "Asamblea anual")):
        database.campaign_runs.insert_one({
            "_id": run, "account_id": cuenta["_id"], "campaign_id": ObjectId(),
            "subject": asunto, "tags": [], "sent": 4, "skipped": 0, "failed": 0,
            "started_at": events.now(), "finished_at": events.now()})

    mejores = stats.screen(database, cuenta, period="7d")["best"]
    assert [one["subject"] for one in mejores] == ["Asamblea anual", "Aviso de corte"]
    assert mejores[0]["open"] == 75 and mejores[0]["click"] == 25
    # Las mismas cifras que «Campanas enviadas» para ese envio.
    contadas = events.counts_by_run(database, cuenta["_id"], [buena])[buena]
    assert contadas[events.OPEN] == 3
    assert runs.between(database, cuenta["_id"], *events.window("7d"))


def test_cuando_abren_cuenta_en_la_hora_de_quien_mira(client, database, outbox):
    from zoneinfo import ZoneInfo

    from services import stats

    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    # Las 02:00 UTC de hoy son las 21:00 del dia anterior en Panama.
    cuando = events.now().astimezone(ZoneInfo("UTC")).replace(hour=2, minute=0)
    events.record(database, cuenta["_id"], kind=events.OPEN, run_id=ObjectId(),
                  email="a@coop.com", at=cuando)

    panama = stats.when_open(database, cuenta["_id"], ZoneInfo("America/Panama"))
    assert panama["total"] == 1
    assert panama["top_hour"] == "21:00"
    utc = stats.when_open(database, cuenta["_id"], ZoneInfo("UTC"))
    assert utc["top_hour"] == "2:00"


def test_el_crecimiento_cuenta_altas_y_bajas(client, database, outbox):
    from models import contact as contacts
    from models import suppression as suppressions
    from services import stats

    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    contacts.upsert_many(database, cuenta["_id"], [("nueva@coop.com", "Nueva")],
                         tags=[], consent=contacts.consent_of("pantalla"))
    suppressions.add(database, cuenta["_id"], "vieja@coop.com",
                     reason=suppressions.COMPLAINT)

    crecimiento = stats.screen(database, cuenta, period="7d")["growth"]
    ultimo = crecimiento["rows"][-1]["values"]
    assert ultimo["added"] == 1
    # Las bajas cuentan todas las supresiones, no solo el enlace de baja.
    assert ultimo["left"] == 1
    assert len(crecimiento["rows"]) == stats.GROWTH_MONTHS


def test_el_enlace_del_clic_se_guarda_y_dos_siguen_siendo_un_clic(client, database, outbox):
    """SES manda la direccion dentro del aviso de clic. Se suma al evento, no
    crea otro: el clic sigue siendo uno por persona."""
    from services import stats

    inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    run = ObjectId()
    for quien in ("a", "b"):
        for kind in (events.SENT, events.DELIVERED):
            events.record(database, cuenta["_id"], kind=kind, run_id=run,
                          email=f"{quien}@coop.com")
    # Ana pulsa dos enlaces distintos; Beto, uno.
    events.record(database, cuenta["_id"], kind=events.CLICK, run_id=run,
                  email="a@coop.com", link="https://coop.com/asamblea")
    events.record(database, cuenta["_id"], kind=events.CLICK, run_id=run,
                  email="a@coop.com", link="https://coop.com/horario")
    events.record(database, cuenta["_id"], kind=events.CLICK, run_id=run,
                  email="b@coop.com", link="https://coop.com/asamblea")

    assert database.events.count_documents(
        {"account_id": cuenta["_id"], "kind": events.CLICK}) == 2
    assert events.people(database, cuenta["_id"], period="7d")[events.CLICK] == 2

    enlaces = events.top_links(database, cuenta["_id"], period="7d")
    assert enlaces == [{"link": "https://coop.com/asamblea", "n": 2},
                       {"link": "https://coop.com/horario", "n": 1}]
    assert stats.screen(database, cuenta, period="7d")["links"] == enlaces
