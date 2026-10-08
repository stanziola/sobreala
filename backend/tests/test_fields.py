"""Las columnas propias del contacto: crearlas, llenarlas y escribirlas.

Lo que se fija aquí es lo que hace que esto sirva y no haga daño. Que el tope
del plan lo ponga `docs/pricing.md` y no una lista copiada. Que un archivo con
columnas de más se pueda importar igual, porque lo que cuenta es lo que el
cliente marca. Que lo que escribió otro salga **escapado** dentro de un correo
nuestro. Y que un contacto sin todos sus datos no entre, y si ya estaba, no
reciba nada hasta completarlo.
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


def csrf(client, url="/contacts/columns"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def crear(browser, nombre, tipo="text"):
    return browser.post("/contacts/columns/new", data={
        "csrf_token": csrf(browser, "/contacts/columns/new"),
        "nombre": nombre, "type": tipo})


def guardar_contacto(browser, email, **columnas):
    """Agregar uno a mano, como lo manda la pantalla."""
    data = {"csrf_token": csrf(browser, "/contacts/new"),
            "email": email, "source": "members"}
    data.update({f"col-{key}": value for key, value in columnas.items()})
    return browser.post("/contacts/new", data=data)


def subir(browser, texto, **extra):
    data = {"csrf_token": csrf(browser, "/contacts/import"),
            "source": "members", "note": "",
            "archivo": (io.BytesIO(texto.encode("utf-8")), "socios.csv")}
    data.update(extra)
    return browser.post("/contacts/import", data=data,
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
    columnas = [{"key": "CIUDAD", "label": "Ciudad", "type": "text"}]
    quien = {"fields": {"CIUDAD": "<b>Santiago</b> & Co"}}

    salida = fields.fill("Hola *|CIUDAD|*", quien, columnas)

    assert "<b>" not in salida
    assert "&lt;b&gt;Santiago&lt;/b&gt; &amp; Co" in salida


def test_en_el_asunto_no_se_escapa_porque_es_texto():
    columnas = [{"key": "EMPRESA", "label": "Empresa", "type": "text"}]
    quien = {"fields": {"EMPRESA": "Pérez & Cía"}}

    assert fields.fill("Para *|EMPRESA|*", quien, columnas,
                       html=False) == "Para Pérez & Cía"


def test_sin_dato_la_marca_se_queda_en_blanco():
    """No hay respaldo: a quien le falta un dato no le llega el correo, así que
    el caso no debería darse. Si se da, no se inventa nada."""
    columnas = [{"key": "CIUDAD", "label": "Ciudad", "type": "text"}]

    assert fields.fill("Hola *|CIUDAD|*", {}, columnas) == "Hola "


def test_la_vista_previa_dibuja_el_nombre_de_la_columna():
    columnas = [{"key": "CIUDAD", "label": "Ciudad", "type": "text"}]

    assert fields.fill("Hola *|CIUDAD|*", fields.sample(columnas),
                       columnas) == "Hola Ciudad"


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
    crear(browser, "Ciudad")
    contacts.create(database, cuenta["_id"], email="socio@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS),
                    values={"CIUDAD": "Santiago"})

    browser.post("/contacts/columns/delete", data={
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
    """A uno que ya existe se le actualiza lo que traiga el archivo, columna a
    columna: traer la ciudad no le borra el monto."""
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad")
    crear(browser, "Monto", tipo="number")

    subir(browser, "correo,ciudad,monto\nana@coop.com,Santiago,300\n")
    subir(browser, "correo,ciudad\nana@coop.com,David\n")

    quien = contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    assert fields.values_of(quien) == {"CIUDAD": "David", "MONTO": "300"}


def test_un_contacto_nuevo_sin_todas_sus_columnas_no_entra(client, database,
                                                           outbox):
    """Sin sus datos no podría recibir nada, así que entrar sería entrar de
    peso muerto. El resultado dice cuántos se quedaron fuera."""
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad")
    crear(browser, "Monto", tipo="number")

    respuesta = subir(browser, "correo,ciudad\nana@coop.com,Santiago\n"
                               "bea@coop.com,David\n")

    assert contacts.count(database, cuenta["_id"]) == 0
    assert "Sin todos sus datos" in respuesta.get_data(as_text=True)


def test_a_mano_tampoco_entra_sin_todas_sus_columnas(client, database, outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad")

    respuesta = guardar_contacto(browser, "ana@coop.com")
    assert contacts.count(database, cuenta["_id"]) == 0
    assert "Todas las columnas son obligatorias" in respuesta.get_data(as_text=True)

    guardar_contacto(browser, "ana@coop.com", CIUDAD="Santiago")
    assert contacts.count(database, cuenta["_id"]) == 1


def test_un_valor_que_no_es_de_su_tipo_cuenta_como_que_falta(client, database,
                                                             outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Vence", tipo="date")

    respuesta = guardar_contacto(browser, "ana@coop.com", VENCE="cuando sea")

    assert contacts.count(database, cuenta["_id"]) == 0
    assert "no es del tipo de la columna" in respuesta.get_data(as_text=True)


def test_cambiar_el_tipo_no_pisa_los_valores_que_no_encajan(client, database,
                                                            outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Ciudad")
    guardar_contacto(browser, "ana@coop.com", CIUDAD="Santiago")

    respuesta = browser.post("/contacts/columns/type", data={
        "csrf_token": csrf(browser, "/contacts/columns"),
        "columna": "CIUDAD", "type": "number"}, follow_redirects=True)

    fresca = accounts.by_id(database, cuenta["_id"])
    assert accounts.fields_of(fresca)[0]["type"] == "text"
    assert "No cambié el tipo" in respuesta.get_data(as_text=True)


def test_el_tipo_se_cambia_cuando_todo_encaja(client, database, outbox):
    browser, cuenta = inside(client, database)
    crear(browser, "Monto")
    guardar_contacto(browser, "ana@coop.com", MONTO="300")

    browser.post("/contacts/columns/type", data={
        "csrf_token": csrf(browser, "/contacts/columns"),
        "columna": "MONTO", "type": "number"})

    fresca = accounts.by_id(database, cuenta["_id"])
    assert accounts.fields_of(fresca)[0]["type"] == "number"


def test_con_el_plan_lleno_la_ruta_no_crea_ninguna(client, database, outbox):
    """Apagar el botón no es un permiso: el formulario se puede escribir a
    mano."""
    browser, cuenta = inside(client, database, plan="basico")
    crear(browser, "Ciudad")

    crear(browser, "Monto")

    fresca = accounts.by_id(database, cuenta["_id"])
    assert [one["key"] for one in accounts.fields_of(fresca)] == ["CIUDAD"]


# ---------------------------------------------------------------- el envío

def test_cada_uno_recibe_lo_suyo_y_el_incompleto_no_recibe(
        client, database, outbox, monkeypatch):
    """Lo de cada quien en su correo. Y al que le falta el dato no le llega
    nada: ni con un hueco ni con un texto inventado."""
    salidos: list = []
    monkeypatch.setattr(sender, "deliver",
                        lambda message: salidos.append(message) or "de-mentira")
    browser, cuenta = inside(client, database)
    accounts.clear_sending(database, cuenta["_id"], cuenta["_id"])
    # La dirección del pie, que sin ella no se envía.
    accounts.set_postal(database, cuenta["_id"], "Apartado 0816-00001, Santiago")
    # Y su usuario de envío, que sin él tampoco.
    accounts.set_handle(database, cuenta["_id"], "cooperativa")
    crear(browser, "Ciudad")
    contacts.create(database, cuenta["_id"], email="socio0@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS),
                    values={"CIUDAD": "Santiago"})
    contacts.create(database, cuenta["_id"], email="socio1@ejemplo.com",
                    consent=contacts.consent_of(contacts.MEMBERS))
    pieza = designs.save_filled(
        database, cuenta["_id"], name="Aviso", template="aviso",
        filled={"titulo": "Asamblea en *|CIUDAD|*", "texto": "El martes"})

    browser.post("/campaigns", data={
        "csrf_token": csrf(browser, "/campaigns"), "asunto": "Hola *|CIUDAD|*",
        "pieza": str(pieza), "lista": "", "cuando": "ahora"})
    una = database.campaigns.find_one({"account_id": cuenta["_id"]})
    # Y la pantalla que pregunta cuenta lo mismo que va a salir.
    pregunta = browser.get(f"/campaigns/{una['_id']}/send").get_data(as_text=True)
    assert "Un contacto" in pregunta
    browser.post(f"/campaigns/{una['_id']}/send",
                 data={"csrf_token": csrf(browser, "/campaigns")})

    assert [one["To"] for one in salidos] == ["socio0@ejemplo.com"]
    assert salidos[0]["Subject"] == "Hola Santiago"
    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "Asamblea en Santiago" in cuerpo
    assert "*|CIUDAD|*" not in cuerpo
