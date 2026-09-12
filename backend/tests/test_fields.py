"""Las columnas propias del contacto: crearlas, llenarlas y escribirlas.

Lo que se fija aquí es lo que hace que esto sirva y no haga daño. Que el tope
del plan lo ponga `docs/pricing.md` y no una lista copiada. Que un archivo con
columnas de más se pueda importar igual, porque lo que cuenta es lo que el
cliente marca. Que lo que escribió otro salga **escapado** dentro de un correo
nuestro. Y que a quien le falte un dato le llegue el respaldo y no un hueco en
medio de la frase.
"""

from __future__ import annotations

import io

from conftest import login, register

from models import account as accounts
from models import contact as contacts
from models import design as designs
from services import fields, importer, plans, sender

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def inside(client, database, email="ana@ejemplo.com", plan="negocio"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    cuenta = accounts.by_email(database, email)
    if plan:
        accounts.set_plan(database, cuenta["_id"], plan)
    return browser, accounts.by_id(database, cuenta["_id"])


def csrf(client, url="/contactos/columnas"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def crear(browser, nombre, tipo="text", respaldo=""):
    return browser.post("/contactos/columnas/nueva", data={
        "csrf_token": csrf(browser), "nombre": nombre, "tipo": tipo,
        "respaldo": respaldo})


def subir(browser, texto, **extra):
    data = {"csrf_token": csrf(browser, "/contactos/importar"),
            "source": "members", "note": "",
            "archivo": (io.BytesIO(texto.encode("utf-8")), "socios.csv")}
    data.update(extra)
    return browser.post("/contactos/importar", data=data,
                        content_type="multipart/form-data")


# --------------------------------------------------------------- los tipos

def test_cada_tipo_se_guarda_parejo_venga_como_venga():
    """El archivo de cada cliente viene como viene; lo guardado sale igual."""
    assert fields.parse("1,234.50", fields.NUMBER) == "1234.5"
    assert fields.parse("B/. 300", fields.NUMBER) == "300"
    assert fields.parse("el martes", fields.NUMBER) is None
    assert fields.parse("15/03/2026", fields.DATE) == "2026-03-15"
    assert fields.parse("2026-03-15", fields.DATE) == "2026-03-15"
    assert fields.parse("cuando sea", fields.DATE) is None
    assert fields.parse("Sí", fields.YESNO) == "si"
    assert fields.parse("0", fields.YESNO) == "no"


def test_una_fecha_se_escribe_como_la_escribiria_una_persona():
    assert fields.show("2026-03-15", fields.DATE) == "15 de marzo de 2026"
    assert fields.show("si", fields.YESNO) == "sí"


def test_el_nombre_de_la_columna_da_su_marca():
    assert fields.key_from("Número de socio") == "NUMERO_DE_SOCIO"
    assert fields.mark("CIUDAD") == "*|CIUDAD|*"


# ------------------------------------------------------------- el escapado

def test_lo_que_escribio_otro_sale_escapado_dentro_del_correo():
    """El HTML de alrededor es nuestro y el dato es de otro: una etiqueta
    dentro de una celda no puede convertirse en etiqueta al enviar."""
    columnas = [{"key": "CIUDAD", "label": "Ciudad", "type": "text",
                 "default": "tu ciudad"}]
    quien = {"fields": {"CIUDAD": "<b>Santiago</b> & Co"}}

    salida = fields.fill("Hola *|CIUDAD|*", quien, columnas)

    assert "<b>" not in salida
    assert "&lt;b&gt;Santiago&lt;/b&gt; &amp; Co" in salida


def test_en_el_asunto_no_se_escapa_porque_es_texto():
    columnas = [{"key": "EMPRESA", "label": "Empresa", "type": "text",
                 "default": ""}]
    quien = {"fields": {"EMPRESA": "Pérez & Cía"}}

    assert fields.fill("Para *|EMPRESA|*", quien, columnas,
                       html=False) == "Para Pérez & Cía"


def test_a_quien_le_falta_el_dato_le_llega_el_respaldo():
    columnas = [{"key": "CIUDAD", "label": "Ciudad", "type": "text",
                 "default": "tu ciudad"}]

    assert fields.fill("Hola *|CIUDAD|*", {}, columnas) == "Hola tu ciudad"


def test_una_columna_borrada_no_deja_la_marca_a_la_vista():
    """Si no, se le manda «*|CIUDAD|*» a mil personas."""
    assert fields.fill("Hola *|CIUDAD|*", {}, []) == "Hola "


# ------------------------------------------------------------- el límite

def test_el_tope_lo_pone_el_documento_de_precios():
    assert plans.field_limit("basico") == 1
    assert plans.field_limit("negocio") == 5
    assert plans.field_limit(None) == plans.FREE_FIELDS


def test_no_se_crean_mas_de_las_que_caben(client, database, outbox):
    browser, cuenta = inside(client, database, plan="basico")

    crear(browser, "Ciudad")
    crear(browser, "Monto", tipo="number")

    fresca = accounts.by_id(database, cuenta["_id"])
    assert [one["key"] for one in accounts.fields_of(fresca)] == ["CIUDAD"]


def test_dos_columnas_con_el_mismo_nombre_no_se_repiten(client, database,
                                                        outbox):
    browser, cuenta = inside(client, database)

    crear(browser, "Ciudad")
    crear(browser, "ciudad")

    fresca = accounts.by_id(database, cuenta["_id"])
    assert len(accounts.fields_of(fresca)) == 1


def test_borrar_la_columna_borra_lo_que_tenian_escrito(client, database,
                                                       outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad", respaldo="tu ciudad")
    contacts.create(database, cuenta["_id"], email="socio@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS),
                    values={"CIUDAD": "Santiago"})

    browser.post("/contactos/columnas/borrar", data={
        "csrf_token": csrf(browser), "columna": "CIUDAD"})

    fresca = accounts.by_id(database, cuenta["_id"])
    assert accounts.fields_of(fresca) == []
    quien = contacts.by_email(database, cuenta["_id"], "socio@ejemplo.com")
    # El contacto se queda; lo que tenía escrito en esa columna, no.
    assert quien is not None and fields.values_of(quien) == {}


# ------------------------------------------------------------ el importador

def test_se_elige_que_columna_del_archivo_se_guarda(client, database, outbox):
    """Un archivo con columnas de más se importa igual: lo que cuenta contra el
    plan es lo que se marca, no lo que trae el archivo."""
    browser, cuenta = inside(client, database, plan="basico")

    subir(browser,
          "correo,nombre,ciudad,monto,notas\n"
          "ana@coop.com,Ana,Santiago,300,lo que sea\n",
          **{"columna-2": "nueva", "tipo-2": "text"})

    fresca = accounts.by_id(database, cuenta["_id"])
    assert [one["key"] for one in accounts.fields_of(fresca)] == ["CIUDAD"]
    quien = contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    assert fields.values_of(quien) == {"CIUDAD": "Santiago"}


def test_marcar_mas_columnas_de_las_que_caben_no_importa_nada(client, database,
                                                              outbox):
    browser, cuenta = inside(client, database, plan="basico")

    respuesta = subir(browser,
                      "correo,ciudad,monto\nana@coop.com,Santiago,300\n",
                      **{"columna-1": "nueva", "tipo-1": "text",
                         "columna-2": "nueva", "tipo-2": "number"})

    assert "más columnas de las que caben" in respuesta.get_data(as_text=True)
    fresca = accounts.by_id(database, cuenta["_id"])
    assert accounts.fields_of(fresca) == []
    assert contacts.count(database, cuenta["_id"]) == 0


def test_sin_elegir_nada_se_casan_los_titulos_con_las_que_ya_existen(
        client, database, outbox):
    """Es lo que pasa sin JavaScript: nada se crea, pero lo que ya existe se
    llena."""
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad")

    subir(browser, "correo,ciudad,monto\nana@coop.com,Santiago,300\n")

    quien = contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    assert fields.values_of(quien) == {"CIUDAD": "Santiago"}
    fresca = accounts.by_id(database, cuenta["_id"])
    # Y «monto» no se creó sola: crear una columna es una decisión.
    assert len(accounts.fields_of(fresca)) == 1


def test_lo_que_no_es_de_ese_tipo_no_se_guarda(client, database, outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Vence", tipo="date")

    subir(browser, "correo,vence\nana@coop.com,cuando sea\n"
                   "bea@coop.com,15/03/2026\n")

    mala = contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    buena = contacts.by_email(database, cuenta["_id"], "bea@coop.com")
    assert fields.values_of(mala) == {}
    assert fields.values_of(buena) == {"VENCE": "2026-03-15"}


def test_reimportar_otra_columna_no_borra_la_anterior(client, database, outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad")
    crear(browser, "Monto", tipo="number")

    subir(browser, "correo,ciudad\nana@coop.com,Santiago\n")
    subir(browser, "correo,monto\nana@coop.com,300\n")

    quien = contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    assert fields.values_of(quien) == {"CIUDAD": "Santiago", "MONTO": "300"}


# ---------------------------------------------------------------- el envío

def test_cada_uno_recibe_lo_suyo(client, database, outbox, monkeypatch):
    salidos: list = []
    monkeypatch.setattr(sender, "deliver",
                        lambda message: salidos.append(message) or "de-mentira")
    browser, cuenta = inside(client, database)
    accounts.clear_sending(database, cuenta["_id"], cuenta["_id"])
    crear(browser, "Ciudad", respaldo="tu ciudad")
    contacts.create(database, cuenta["_id"], email="socio0@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS),
                    values={"CIUDAD": "Santiago"})
    contacts.create(database, cuenta["_id"], email="socio1@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS))
    pieza = designs.save_filled(
        database, cuenta["_id"], name="Aviso", template="aviso",
        filled={"titulo": "Asamblea en *|CIUDAD|*", "texto": "El martes"})

    browser.post("/envios", data={
        "csrf_token": csrf(browser, "/envios"), "asunto": "Hola *|CIUDAD|*",
        "pieza": str(pieza), "lista": "", "cuando": "ahora"})
    una = database.campaigns.find_one({"account_id": cuenta["_id"]})
    browser.post(f"/envios/{una['_id']}/mandar",
                 data={"csrf_token": csrf(browser, "/envios")})

    assert len(salidos) == 2
    escrito = {one["To"]: one for one in salidos}
    # El que tiene el dato, y el que no: al segundo le llega el respaldo.
    assert escrito["socio0@ejemplo.com"]["Subject"] == "Hola Santiago"
    assert escrito["socio1@ejemplo.com"]["Subject"] == "Hola tu ciudad"
    cuerpo = escrito["socio0@ejemplo.com"].get_body(("html",)).get_content()
    assert "Asamblea en Santiago" in cuerpo
    assert "*|CIUDAD|*" not in cuerpo
