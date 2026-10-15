"""El logo de la empresa (octubre de 2026).

Lo sube el dueño en Configuración → Cuenta y se ve en la barra del panel y del
sitio, en la lista de cuentas abiertas, en administración, en las páginas que
abre un contacto, en el PDF de Estadísticas y, como copia, en el lienzo. Lo que
se fija aquí: que entre solo un PNG, un JPG o un WebP de hasta 5 MB; que
cambiarlo o quitarlo no deje basura ni rompa una plantilla; que no cuente
contra el tope de fotos ni lo barra la limpieza de las fotos sueltas; y que un
usuario de la empresa lo vea y no lo cambie.
"""

from __future__ import annotations

import io

from PIL import Image

from conftest import login
from test_admin import make_admin
from test_campaigns import ready
from test_users import as_member

from config import Config
from models import account as accounts
from models import contact as contacts
from models import image as images
from services import unsubscribe


def png(width=60, height=30, color=(49, 102, 167, 255)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (width, height), color).save(out, format="PNG")
    return out.getvalue()


def csrf(browser, url="/settings/account"):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def upload(browser, data: bytes, name="logo.png"):
    return browser.post("/settings/logo", data={
        "csrf_token": csrf(browser), "logo": (io.BytesIO(data), name)},
        content_type="multipart/form-data")


def remove(browser):
    return browser.post("/settings/logo", data={
        "csrf_token": csrf(browser), "action": "remove"})


def logo_of(database, cuenta) -> str:
    return accounts.logo_of(accounts.by_id(database, cuenta["_id"]))


def test_subir_cambiar_y_quitar(client, database, outbox, monkeypatch):
    monkeypatch.setattr(Config, "PUBLIC_SITE_URL", "http://localhost")
    browser, cuenta, _ = ready(client, database)

    subido = upload(browser, png())
    assert subido.headers["Location"].endswith("/settings/account?logo=saved#logo")
    primero = logo_of(database, cuenta)
    guardado = database.images.find_one({"name": primero})
    assert guardado["kind"] == images.LOGO
    # Se ve en la barra, en Configuración, y viaja en la migaja para el sitio.
    pantalla = browser.get("/settings/account").get_data(as_text=True)
    assert f'class="menu__avatar" src="/img/{primero}"' in pantalla
    assert f'class="logo-preview" src="/img/{primero}"' in pantalla
    assert browser.get_cookie("sa_in").value.endswith(f":{primero}")
    # No cuenta contra el tope de fotos.
    assert images.count(database, cuenta["_id"]) == 0

    upload(browser, png(color=(200, 0, 0, 255)))
    segundo = logo_of(database, cuenta)
    assert segundo and segundo != primero
    # El de antes nunca salió en un correo: se borra.
    assert database.images.find_one({"name": primero}) is None

    quitado = remove(browser)
    assert quitado.headers["Location"].endswith("logo=removed#logo")
    assert logo_of(database, cuenta) == ""
    assert database.images.find_one({"name": segundo}) is None
    # Quitar sin logo no cambia nada, y lo dice.
    assert "same=1" in remove(browser).headers["Location"]
    assert "menu__avatar" not in browser.get("/settings/account").get_data(as_text=True)


def test_solo_entra_una_imagen_buena(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    assert "logo_error=required" in browser.post("/settings/logo", data={
        "csrf_token": csrf(browser)}).headers["Location"]
    assert "logo_error=kind" in upload(browser, b"%PDF-1.4 no", "logo.pdf").headers["Location"]
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    assert "logo_error=kind" in upload(browser, gif.getvalue(), "logo.gif").headers["Location"]
    pesado = png() + b"0" * (5 * 1024 * 1024)
    assert "logo_error=heavy" in upload(browser, pesado).headers["Location"]
    assert logo_of(database, cuenta) == ""
    assert "Elige una imagen para subir." in browser.get(
        "/settings/account?logo_error=required").get_data(as_text=True)


def test_la_limpieza_y_las_plantillas_no_tocan_el_logo(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    upload(browser, png())
    logo = logo_of(database, cuenta)
    from datetime import datetime, timedelta, timezone
    luego = datetime.now(timezone.utc) + timedelta(days=30)
    assert logo not in images.uploaded_before(database, cuenta["_id"], luego)
    images.remove(database, cuenta["_id"], [logo])
    assert database.images.find_one({"name": logo}) is not None


def test_un_usuario_lo_ve_y_no_lo_cambia(client, database, outbox):
    dueno, empresa, suyo = as_member(client, database, outbox=outbox)
    upload(dueno, png())
    logo = logo_of(database, empresa)
    pantalla = suyo.get("/contacts").get_data(as_text=True)
    assert f'class="menu__avatar" src="/img/{logo}"' in pantalla
    with suyo.session_transaction() as sess:
        token = sess.get("_csrf", "")
    respuesta = suyo.post("/settings/logo", data={"csrf_token": token, "action": "remove"})
    assert respuesta.status_code == 302 and "/settings/security" in respuesta.headers["Location"]
    assert logo_of(database, empresa) == logo


def test_sale_en_las_paginas_del_contacto_y_en_administracion(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    upload(browser, png())
    logo = logo_of(database, cuenta)

    quien = contacts.page(database, cuenta["_id"])[0][0]
    baja = client.application.test_client().get(f"/unsubscribe/{unsubscribe.sign(quien['_id'])}")
    assert f'class="sender-head__logo" src="/img/{logo}"' in baja.get_data(as_text=True)

    abiertas = browser.get("/switch-account").get_data(as_text=True)
    assert f'class="switcher__logo" src="/img/{logo}"' in abiertas

    admin, _ = make_admin(client, database)
    assert f'src="/img/{logo}"' in admin.get("/admin/clients").get_data(as_text=True)
    assert f'src="/img/{logo}"' in admin.get("/admin/accounts").get_data(as_text=True)
    assert f'src="/img/{logo}"' in admin.get(
        f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)


def test_el_pdf_lleva_el_logo(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    sin = browser.get("/dashboard/export.pdf").get_data()
    upload(browser, png())
    con = browser.get("/dashboard/export.pdf").get_data()
    assert con.startswith(b"%PDF")
    assert b"/Subtype /Image" in con and b"/Subtype /Image" not in sin


def test_mi_logo_en_el_lienzo_pone_una_copia(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    assert 'data-add="logo"' not in browser.get("/templates/create").get_data(as_text=True)
    sin_logo = browser.post("/templates/canvas/logo", data={"csrf_token": csrf(browser, "/templates/create")})
    assert sin_logo.status_code == 400

    upload(browser, png())
    logo = logo_of(database, cuenta)
    assert 'data-add="logo"' in browser.get("/templates/create").get_data(as_text=True)
    copia = browser.post("/templates/canvas/logo", data={
        "csrf_token": csrf(browser, "/templates/create")}).get_json()
    assert copia["name"] != logo and copia["width"] == 60 and copia["height"] == 30
    # La copia es una foto más: cuenta contra el tope, y el logo no.
    assert images.count(database, cuenta["_id"]) == 1
    assert database.images.find_one({"name": copia["name"]}).get("kind") is None
