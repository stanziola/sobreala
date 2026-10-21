"""El registro desde octubre de 2026: nombres que son nombres, teléfonos de
Panamá con sus reglas, la dirección por partes, la casilla de los términos y la
de las novedades de Sobreala."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from conftest import ADDRESS, SIGNUP_EXTRA, login, register

from models import account as accounts

ROOT = Path(__file__).resolve().parent.parent.parent
EMAIL = "nueva@ejemplo.com"


def other(client):
    return client.application.test_client()


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def signup(browser, **changes):
    """Registrarse como lo hace la pantalla, con lo que se quiera cambiar."""
    data = {"csrf_token": csrf(browser, "/signup"), "company_name": "Coop Sur, S.A.",
            "contact_name": "María-José O'Neill", "email": EMAIL,
            "phone_country": "PA", "phone": "6000-1111", **SIGNUP_EXTRA,
            "password": "Contrasena-Larga1"}
    data.update(changes)
    return browser.post("/signup", data=data)


# ----------------------------------------------------------------- los nombres

def test_un_nombre_de_empresa_tiene_que_ser_un_nombre():
    for bueno in ("Coop Sur", "Ferretería 2000, S.A.", "Pérez & Hijos", "3M", "7-Eleven",
                  "Cía. (Panamá) S/A"):
        assert accounts.clean_company_name(bueno), bueno
    for malo in (".", "..", "123", "A", "-", "x" * 81, '{"$ne": null}', "Coop_Sur",
                 "Coop <b>"):
        assert accounts.clean_company_name(malo) is None, malo
    # Los espacios de más se quitan.
    assert accounts.clean_company_name("  Coop    Sur ") == "Coop Sur"


def test_un_nombre_de_persona_tiene_que_ser_un_nombre():
    for bueno in ("Ana", "María-José O'Neill", "J. Pérez", "Ñandú Güell"):
        assert accounts.clean_person_name(bueno), bueno
    for malo in (".", "A", "Ana2", "123", "x" * 61, "Ana@", "--"):
        assert accounts.clean_person_name(malo) is None, malo


def test_el_registro_rechaza_un_punto_por_nombre(client, database, outbox):
    pantalla = signup(other(client), company_name=".", contact_name=".").get_data(
        as_text=True)
    assert "Escribe el nombre de tu negocio" in pantalla
    assert "Escribe un nombre de persona" in pantalla
    assert accounts.by_email(database, EMAIL) is None
    # Y el formulario no deja escribir de más.
    registro = client.get("/signup").get_data(as_text=True)
    assert 'maxlength="80"' in registro and 'maxlength="60"' in registro


# ------------------------------------------------------------------ teléfonos

def test_en_panama_el_personal_es_un_celular():
    personal = accounts.PERSONAL_PHONE
    assert accounts.check_phone("6000-1111", "PA", personal) == ("+50760001111", "")
    assert accounts.check_phone("+507 6000-1111", "US", personal) == ("+50760001111", "")
    # Siete dígitos es un fijo, y uno de ocho tiene que empezar con 6.
    assert accounts.check_phone("998-1234", "PA", personal) == (
        None, "error_phone_pa_mobile")
    assert accounts.check_phone("7000-1111", "PA", personal) == (
        None, "error_phone_pa_mobile")
    # Los de la empresa pueden ser un fijo de siete, no uno de seis ni de nueve.
    empresa = accounts.COMPANY_PHONE
    assert accounts.check_phone("998-1234", "PA", empresa) == ("+5079981234", "")
    assert accounts.check_phone("600-1111", "PA", empresa) == (
        None, "error_phone_pa_number")
    assert accounts.check_phone("99-8123", "PA", empresa) == (
        None, "error_phone_pa_number")
    assert accounts.check_phone("6000-11112", "PA", empresa) == (
        None, "error_phone_pa_number")
    # Fuera de Panamá, la regla de siempre.
    assert accounts.check_phone("8888 1234", "CR", personal) == ("+50688881234", "")


def test_el_registro_dice_por_que_no_vale_el_telefono(client, database, outbox):
    pantalla = signup(other(client), phone="998-1234").get_data(as_text=True)
    assert "tiene que ser un celular de Panamá" in pantalla
    assert accounts.by_email(database, EMAIL) is None

    pantalla = signup(other(client), company_phone_country=["PA"],
                      company_phone=["600-111"]).get_data(as_text=True)
    assert "Un número de Panamá tiene 8 dígitos" in pantalla
    assert accounts.by_email(database, EMAIL) is None


# ---------------------------------------------------------------- la dirección

def test_la_direccion_por_partes_y_armada_sin_repetir():
    partes, errores = accounts.clean_address({
        "line1": "  Calle 10  ", "line2": "", "city": "Santiago de Veraguas",
        "region": "Veraguas", "postal_code": "", "country": "pa"})
    assert errores == {}
    assert partes["line1"] == "Calle 10" and partes["country"] == "PA"
    # «Veraguas» ya va en la ciudad: no se repite (así salía antes).
    assert accounts.compose_postal(partes) == "Calle 10, Santiago de Veraguas, Panamá"
    otra = {**partes, "line2": "Local 3", "city": "David", "region": "Chiriquí",
            "postal_code": "0426"}
    assert accounts.compose_postal(otra) == "Calle 10, Local 3, David, Chiriquí, 0426, Panamá"

    _, errores = accounts.clean_address({"line1": "C1", "city": "", "region": "",
                                         "postal_code": "@@", "country": "ZZ"})
    assert set(errores) == {"line1", "city", "region", "postal_code", "country"}


def test_una_cuenta_de_antes_tiene_su_direccion_en_la_linea_1():
    antes = {"postal_address": "Apartado 0816-00001, Santiago"}
    assert accounts.address_of(antes)["line1"] == "Apartado 0816-00001, Santiago"
    assert accounts.address_of(antes)["city"] == "" and accounts.address_of(antes)["country"] == "PA"


def test_el_registro_guarda_la_direccion_por_partes(client, database, outbox):
    pantalla = client.get("/signup").get_data(as_text=True)
    for campo in ("address_line1", "address_line2", "address_city", "address_region",
                  "address_postal_code", "address_country"):
        assert f'name="{campo}"' in pantalla
    # Las provincias de Panamá se sugieren, sin JavaScript.
    assert '<option value="Veraguas"></option>' in pantalla

    signup(other(client), address_line2="Edificio Uno", address_postal_code="0901")
    cuenta = accounts.by_email(database, EMAIL)
    assert cuenta["address"] == {"line1": "Calle 10", "line2": "Edificio Uno",
                                 "city": "Santiago de Veraguas", "region": "Veraguas",
                                 "postal_code": "0901", "country": "PA"}
    assert cuenta["postal_address"] == ("Calle 10, Edificio Uno, Santiago de Veraguas, "
                                        "0901, Panamá")


# ------------------------------------------------- los términos y las novedades

def test_sin_aceptar_los_terminos_no_hay_cuenta(client, database, outbox):
    pantalla = signup(other(client), terms="").get_data(as_text=True)
    assert "acepta los términos y condiciones" in pantalla
    assert accounts.by_email(database, EMAIL) is None


def test_se_anota_la_version_de_los_terminos_y_las_novedades_nacen_en_no(
        client, database, outbox):
    signup(other(client))
    cuenta = accounts.by_email(database, EMAIL)
    assert cuenta["terms_version"] == accounts.TERMS_VERSION and cuenta["terms_accepted_at"]
    assert cuenta["news_opt_in"] is False and not accounts.wants_news(cuenta)

    signup(other(client), email="otra@ejemplo.com", news="1")
    otra = accounts.by_email(database, "otra@ejemplo.com")
    assert otra["news_opt_in"] is True and otra["news_opt_in_at"]


def test_la_version_es_la_de_los_terminos_del_sitio():
    """El backend no lee landing/ al correr: guarda una copia de la fecha."""
    spec = importlib.util.spec_from_file_location("site_content",
                                                  ROOT / "landing" / "content.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert accounts.TERMS_VERSION == module.TERMS_UPDATED


def test_las_novedades_se_cambian_en_notificaciones(client, database, outbox):
    register(client)
    browser = other(client)
    login(browser)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert not accounts.wants_news(cuenta)
    pantalla = browser.get("/settings/notifications").get_data(as_text=True)
    assert 'id="news"' in pantalla and 'name="news"' in pantalla

    # Lo que ya tenía, más las novedades: se guardan.
    marcados = {name: "on" for name in accounts.notices_for(cuenta)
                if accounts.wants(cuenta, name)}
    respuesta = browser.post("/settings/notifications", data={
        "csrf_token": csrf(browser, "/settings/notifications"), **marcados, "news": "on"})
    assert "saved=1" in respuesta.headers["Location"]
    assert accounts.wants_news(accounts.by_email(database, "ana@ejemplo.com"))

    # Lo mismo otra vez no escribe nada.
    igual = browser.post("/settings/notifications", data={
        "csrf_token": csrf(browser, "/settings/notifications"), **marcados, "news": "on"})
    assert "same=1" in igual.headers["Location"]


def test_la_direccion_se_edita_por_partes(client, database, outbox):
    register(client)
    browser = other(client)
    login(browser)
    respuesta = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings/account"), **ADDRESS,
        "address_line1": "Avenida Central", "address_city": "David",
        "address_region": "Chiriquí"})
    assert respuesta.headers["Location"].endswith("address=1#address")
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    assert cuenta["postal_address"] == "Avenida Central, David, Chiriquí, Panamá"
