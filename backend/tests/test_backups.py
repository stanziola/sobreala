"""Los respaldos que elige cada cliente.

S3 se sustituye por un diccionario (`fake_s3`): es lo único que no se puede
llamar desde una prueba. Lo que fijan estas pruebas es lo que sale mal con los
datos de alguien: que **un respaldo solo traiga lo de esa cuenta**, que **solo el
dueño lo baje**, que se guarden los últimos y no más, y que la tarea de cada hora
respalde a quien le toca y siga aunque una cuenta falle.
"""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta

import pytest
from conftest import login, register

from config import Config
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import suppression as suppressions
from services import backups, canvas, storage

EMAIL = "ana@ejemplo.com"


@pytest.fixture
def s3(monkeypatch):
    store: dict[str, bytes] = {}
    deleted: list[str] = []

    def put(key, data, content_type):
        store[key] = data

    def get(key):
        if key not in store:
            raise storage.StorageError("no está")
        return store[key]

    def delete(key):
        deleted.append(key)
        store.pop(key, None)

    monkeypatch.setattr(Config, "S3_BUCKET", "sobreala-respaldos")
    monkeypatch.setattr(storage, "put", put)
    monkeypatch.setattr(storage, "get", get)
    monkeypatch.setattr(storage, "delete", delete)
    return {"store": store, "deleted": deleted}


def other(client):
    return client.application.test_client()


def dentro(client, database, email=EMAIL):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser, accounts.by_email(database, email)


def csrf(browser, url="/settings/backups"):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def con_datos(database, cuenta, correo="socio@coop.com"):
    contacts.upsert_many(database, cuenta["_id"], [(correo, "Socio")],
                         tags=[], consent=contacts.consent_of("pantalla"))
    suppressions.add(database, cuenta["_id"], "baja@coop.com",
                     reason=suppressions.COMPLAINT)
    designs.save_canvas(database, cuenta["_id"], name="Asamblea",
                        doc=canvas.blank(), backgrounds=[])


def ahora(browser):
    return browser.post("/settings/backups/now", data={"csrf_token": csrf(browser)})


def abrir(datos: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(datos))


# --------------------------------------------------------------- la pantalla

def test_sin_s3_dice_que_no_esta_disponible(client, database, outbox):
    browser, _ = dentro(client, database)
    pantalla = browser.get("/settings/backups").get_data(as_text=True)
    assert "Respaldos" in pantalla
    assert "todavía no están disponibles" in pantalla
    assert "Respaldar ahora" not in pantalla


def test_el_dueno_elige_cada_cuanto(client, database, outbox, s3):
    browser, cuenta = dentro(client, database)
    pantalla = browser.get("/settings/backups").get_data(as_text=True)
    for opcion in ("Desactivado", "Cada día", "Cada semana", "Cada mes"):
        assert opcion in pantalla

    browser.post("/settings/backups/every", data={"csrf_token": csrf(browser),
                                                  "every": "weekly"})
    assert backups.setting(accounts.by_id(database, cuenta["_id"]))["every"] == "weekly"

    # Uno inventado se lee como desactivado, y sin testigo no cambia nada.
    browser.post("/settings/backups/every", data={"csrf_token": csrf(browser),
                                                  "every": "cada-minuto"})
    assert backups.setting(accounts.by_id(database, cuenta["_id"]))["every"] == ""
    browser.post("/settings/backups/every", data={"every": "daily"})
    assert backups.setting(accounts.by_id(database, cuenta["_id"]))["every"] == ""


# -------------------------------------------------------------- el respaldo

def test_respaldar_ahora_guarda_solo_lo_de_esta_cuenta(client, database, outbox, s3):
    browser, cuenta = dentro(client, database)
    con_datos(database, cuenta)
    _, ajena = dentro(client, database, email="otra@ejemplo.com")
    con_datos(database, ajena, correo="ajeno@otra.com")

    respuesta = ahora(browser)

    assert "done=1" in respuesta.headers["Location"]
    hecho, = backups.list_for(database, cuenta["_id"])
    assert hecho["key"].startswith(f"respaldos/{cuenta['_id']}/")
    zipped = abrir(s3["store"][hecho["key"]])
    nombres = zipped.namelist()
    assert {"contactos.csv", "bajas.csv", "campanas.csv"} <= set(nombres)
    assert any(n.startswith("plantillas/") and n.endswith(".zip") for n in nombres)
    contactos_csv = zipped.read("contactos.csv").decode("utf-8")
    assert "socio@coop.com" in contactos_csv and "ajeno@otra.com" not in contactos_csv
    assert "baja@coop.com" in zipped.read("bajas.csv").decode("utf-8")
    # La plantilla del respaldo se vuelve a cargar: trae su lienzo.
    plantilla = next(n for n in nombres if n.startswith("plantillas/"))
    assert "lienzo.json" in abrir(zipped.read(plantilla)).namelist()

    pantalla = browser.get("/settings/backups").get_data(as_text=True)
    assert "A mano" in pantalla and "Descargar" in pantalla


def test_solo_el_dueno_baja_el_suyo(client, database, outbox, s3):
    browser, cuenta = dentro(client, database)
    ahora(browser)
    hecho, = backups.list_for(database, cuenta["_id"])

    archivo = browser.get(f"/settings/backups/{hecho['_id']}")
    assert archivo.status_code == 200
    assert archivo.mimetype == "application/zip"
    assert archivo.headers["Content-Disposition"].startswith("attachment;")
    assert archivo.headers["Cache-Control"] == "no-store"

    ajeno, _ = dentro(client, database, email="otra@ejemplo.com")
    assert ajeno.get(f"/settings/backups/{hecho['_id']}").status_code == 404
    assert browser.get("/settings/backups/no-es-un-id").status_code == 404
    assert other(client).get(f"/settings/backups/{hecho['_id']}").status_code == 302


def test_respaldar_ahora_una_vez_por_hora(client, database, outbox, s3):
    browser, cuenta = dentro(client, database)
    ahora(browser)

    segunda = ahora(browser)

    assert "error=wait" in segunda.headers["Location"]
    assert len(backups.list_for(database, cuenta["_id"])) == 1


def test_se_guardan_los_ultimos_cinco(client, database, outbox, s3):
    _, cuenta = dentro(client, database)
    hechos = [backups.make(database, accounts.by_id(database, cuenta["_id"]), auto=True)
              for _ in range(backups.KEEP + 2)]

    quedan = backups.list_for(database, cuenta["_id"])
    assert len(quedan) == backups.KEEP
    assert database.backups.count_documents({"account_id": cuenta["_id"]}) == backups.KEEP
    # Los dos más viejos se borraron de S3.
    assert set(s3["deleted"]) == {hechos[0]["key"], hechos[1]["key"]}


def test_si_s3_falla_queda_escrito_y_no_se_anota(client, database, outbox, s3,
                                                 monkeypatch):
    browser, cuenta = dentro(client, database)

    def roto(key, data, content_type):
        raise storage.StorageError("s3 put")

    monkeypatch.setattr(storage, "put", roto)
    respuesta = ahora(browser)

    assert "error=failed" in respuesta.headers["Location"]
    assert backups.list_for(database, cuenta["_id"]) == []
    assert backups.setting(accounts.by_id(database, cuenta["_id"]))["last_error"]


# ------------------------------------------------------- la tarea de la hora

def test_a_quien_le_toca(client, database, outbox):
    momento = backups.now()
    assert not backups.due({}, momento)
    assert not backups.due({"backup": {"every": ""}}, momento)
    assert backups.due({"backup": {"every": "daily"}}, momento)
    ayer = momento - timedelta(days=1)
    assert backups.due({"backup": {"every": "daily", "last_at": ayer}}, momento)
    # Con margen: hecho a las 10:02, le vuelve a tocar a las 10:00.
    assert backups.due({"backup": {"every": "daily",
                                   "last_at": ayer + timedelta(minutes=2)}}, momento)
    assert not backups.due({"backup": {"every": "daily",
                                       "last_at": momento - timedelta(hours=3)}}, momento)
    assert not backups.due({"backup": {"every": "weekly", "last_at": ayer}}, momento)


def test_la_tarea_respalda_a_quien_le_toca_y_sigue_si_una_falla(client, database,
                                                               outbox, s3, monkeypatch):
    _, ana = dentro(client, database)
    _, luis = dentro(client, database, email="luis@ejemplo.com")
    _, eva = dentro(client, database, email="eva@ejemplo.com")
    backups.set_every(database, ana["_id"], "daily")
    backups.set_every(database, luis["_id"], "daily")
    database.accounts.update_one({"_id": luis["_id"]},
                                 {"$set": {"backup.last_at": backups.now()}})
    # Eva no los activó.

    original = backups.build

    def build(db, account):
        if account["_id"] == ana["_id"] and not getattr(build, "fallo", False):
            build.fallo = True
            raise RuntimeError("se cayó")
        return original(db, account)

    monkeypatch.setattr(backups, "build", build)
    resultado = backups.run_due(database)

    assert resultado == {"made": 0, "failed": 1}
    assert backups.list_for(database, luis["_id"]) == []
    assert backups.list_for(database, eva["_id"]) == []

    # La hora siguiente lo vuelve a intentar, y sale.
    assert backups.run_due(database) == {"made": 1, "failed": 0}
    hecho, = backups.list_for(database, ana["_id"])
    assert hecho["auto"] is True
