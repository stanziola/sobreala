"""Las plantillas de muestra de la portada: pulsar una la deja como plantilla
de la cuenta y abre su lienzo."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from conftest import login, register
from test_admin import make_admin
from test_designs import inside, other

from models import design as designs

ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLES_DIR = ROOT / "backend" / "sample_templates"
PICTURES_DIR = ROOT / "landing" / "assets" / "img" / "samples"


def site_samples():
    """`SAMPLES` del sitio, leído del mismo content.py que lo construye."""
    spec = importlib.util.spec_from_file_location("site_content",
                                                  ROOT / "landing" / "content.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SAMPLES


def test_cada_tarjeta_tiene_su_zip_y_al_reves():
    del_sitio = {one["slug"] for one in site_samples()}
    en_disco = {path.stem for path in SAMPLES_DIR.glob("*.zip")}
    assert del_sitio == en_disco


def test_cada_tarjeta_tiene_su_miniatura():
    faltan = [one["slug"] for one in site_samples()
              if not (PICTURES_DIR / f"{one['slug']}.webp").exists()]
    assert not faltan, (f"Faltan miniaturas: {faltan}. "
                        "Corre: python landing/samples.py")


@pytest.mark.parametrize("one", site_samples(), ids=lambda one: one["slug"])
def test_cada_muestra_mide_800_y_lleva_dos_fotos_como_mucho(one):
    """Todas del mismo alto, para que la miniatura (3:4 de 600) las enseñe
    enteras; y pocas fotos, que cuentan contra el tope de quien la abre."""
    import json
    import zipfile

    with zipfile.ZipFile(SAMPLES_DIR / f"{one['slug']}.zip") as pack:
        board = json.loads(pack.read("lienzo.json"))
    fotos = {item["name"] for item in board["items"] if item["t"] == "image"}
    assert board["h"] == 800
    assert len(fotos) <= 2
    assert one["group"] in ("promo", "api")


@pytest.mark.parametrize("slug", [one["slug"] for one in site_samples()])
def test_cada_muestra_abre_su_lienzo(client, database, outbox, slug):
    browser = inside(client)
    account = database.accounts.find_one({"email": "ana@ejemplo.com"})

    answer = browser.get(f"/templates/sample/{slug}")

    assert answer.status_code == 302
    assert "/templates/canvas/" in answer.headers["Location"]
    guardadas = designs.for_account(database, account["_id"])
    assert len(guardadas) == 1 and guardadas[0]["source"] == designs.CANVAS


def test_cada_pulsacion_es_otra_copia(client, database, outbox):
    browser = inside(client)
    account = database.accounts.find_one({"email": "ana@ejemplo.com"})
    browser.get("/templates/sample/restaurant")
    browser.get("/templates/sample/restaurant")
    assert len(designs.for_account(database, account["_id"])) == 2


def test_una_inventada_no_existe(client, database, outbox):
    browser = inside(client)
    for slug in ("no-existe", "..%2Fsecreto", "RESTAURANT"):
        assert browser.get(f"/templates/sample/{slug}").status_code == 404


def test_sin_sesion_entra_y_sigue_hasta_ella(client, database, outbox):
    register(client)
    visitor = other(client)

    first = visitor.get("/templates/sample/restaurant")
    assert first.headers["Location"].endswith("/login?sample=restaurant")

    visitor.get("/login?sample=restaurant")
    with visitor.session_transaction() as sess:
        csrf = sess["_csrf"]
    after = visitor.post("/login?sample=restaurant", data={
        "csrf_token": csrf, "email": "ana@ejemplo.com",
        "password": "Contrasena-Larga1"})
    assert after.headers["Location"].endswith("/templates/sample/restaurant")


def test_una_precarga_no_crea_nada(client, database, outbox):
    browser = inside(client)
    account = database.accounts.find_one({"email": "ana@ejemplo.com"})
    answer = browser.get("/templates/sample/restaurant",
                         headers={"Sec-Purpose": "prefetch"})
    assert answer.status_code == 204
    assert designs.for_account(database, account["_id"]) == []


def test_un_administrador_no_puede(client, database, outbox):
    admin, _ = make_admin(client, database)
    answer = admin.get("/templates/sample/restaurant")
    assert answer.headers["Location"].endswith("/admin/")
    assert database.designs.count_documents({}) == 0
