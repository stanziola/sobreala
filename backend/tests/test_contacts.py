"""Contactos: el importador, las etiquetas y las supresiones.

Lo que fijan estas pruebas es lo que no se puede deshacer si sale mal. Un
contacto duplicado se cobra dos veces y recibe dos correos. Una supresión que se
levanta sola le escribe a quien pidió que no. Y una lista importada sin origen
se queda sin origen para siempre, porque eso no se rellena hacia atrás.
"""

from __future__ import annotations

import io

from conftest import login, register

from models import account as accounts
from models import contact as contacts
from models import import_job as imports
from models import suppression as suppressions
from services import importer

PASSWORD = "Contrasena-Larga1"


def other(client):
    return client.application.test_client()


def inside(client, email="ana@ejemplo.com"):
    """Una cuenta creada y con sesión abierta."""
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser


def csrf(client, url="/contactos"):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def make_tag(client, name):
    """Crear una etiqueta como lo hace la pantalla. Existen antes de usarse."""
    return client.post("/contactos/etiquetas/nueva", data={
        "csrf_token": csrf(client, "/contactos/etiquetas"), "etiqueta": name})


def upload(client, text, *, source="members", tags=(), filename="lista.csv"):
    """Subir un archivo. Las etiquetas van marcadas, como casillas."""
    token = csrf(client, "/contactos/importar")
    data = {"csrf_token": token, "source": source, "note": "",
            "archivo": (io.BytesIO(text.encode("utf-8")), filename)}
    if tags:
        data["tags"] = list(tags)
    return client.post("/contactos/importar", data=data,
                       content_type="multipart/form-data")


def account_of(database, email="ana@ejemplo.com"):
    return accounts.by_email(database, email)


LISTA = ("correo,nombre\n"
         "ana@coop.com,Ana\n"
         "BEA@Coop.com ,Bea\n"
         "carlos@coop.com,Carlos\n")


# ------------------------------------------------------------ el importador

def test_una_lista_entra_entera(client, database, outbox):
    browser = inside(client)
    make_tag(browser, "socios")
    upload(browser, LISTA, tags=["socios"])

    cuenta = account_of(database)
    assert contacts.count(database, cuenta["_id"]) == 3
    # La normalización es la misma de siempre: sin espacios y en minúsculas.
    guardado = contacts.by_email(database, cuenta["_id"], "bea@coop.com")
    assert guardado is not None
    assert guardado["tags"] == ["socios"]


def test_subir_el_mismo_archivo_dos_veces_no_duplica_a_nadie(client, database, outbox):
    browser = inside(client)
    make_tag(browser, "socios")
    make_tag(browser, "junta")
    upload(browser, LISTA, tags=["socios"])
    upload(browser, LISTA, tags=["junta"])

    cuenta = account_of(database)
    assert contacts.count(database, cuenta["_id"]) == 3
    # Y la segunda etiqueta se suma a la primera en vez de reemplazarla: una
    # persona puede estar en dos listas y sigue siendo un solo documento.
    guardado = contacts.by_email(database, cuenta["_id"], "ana@coop.com")
    assert sorted(guardado["tags"]) == ["junta", "socios"]


def test_una_fila_sin_correo_se_cuenta_y_no_detiene_el_archivo(client, database, outbox):
    browser = inside(client)
    upload(browser, "correo\nana@coop.com\nesto no es un correo\nbea@coop.com\n")

    cuenta = account_of(database)
    assert contacts.count(database, cuenta["_id"]) == 2
    trabajo = imports.for_account(database, cuenta["_id"])[0]
    assert trabajo["invalid"] == 1
    assert trabajo["added"] == 2


def test_el_archivo_de_excel_en_espanol_tambien_entra(client, database, outbox):
    """Excel en español exporta con punto y coma, no con coma."""
    browser = inside(client)
    upload(browser, "correo;nombre\nana@coop.com;Ana\nbea@coop.com;Bea\n")

    assert contacts.count(database, account_of(database)["_id"]) == 2


def test_una_sola_columna_sin_encabezado_tambien_entra(client, database, outbox):
    """Lo que sale de pegar una columna: ni títulos ni nombres."""
    browser = inside(client)
    upload(browser, "ana@coop.com\nbea@coop.com\ncarlos@coop.com\n")

    assert contacts.count(database, account_of(database)["_id"]) == 3


def test_el_origen_queda_escrito_en_cada_contacto(client, database, outbox):
    """No se puede rellenar después: o entra ahora, o esa lista no tiene."""
    browser = inside(client)
    upload(browser, LISTA, source=contacts.MEMBERS)

    cuenta = account_of(database)
    for documento in database.contacts.find({"account_id": cuenta["_id"]}):
        assert documento["consent"]["source"] == contacts.MEMBERS
        assert documento["consent"]["recorded_at"] is not None


def test_sin_decir_de_donde_salio_no_se_importa_nada(client, database, outbox):
    browser = inside(client)
    respuesta = upload(browser, LISTA, source="")

    assert contacts.count(database, account_of(database)["_id"]) == 0
    assert "Completa este campo" in respuesta.get_data(as_text=True)


# ------------------------------------------------------------- los límites

def test_al_llegar_al_tope_se_detiene_y_lo_que_entro_se_queda(client, database,
                                                              outbox, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, "CONTACTS_FREE_LIMIT", 2)

    browser = inside(client)
    upload(browser, LISTA)

    cuenta = account_of(database)
    assert contacts.count(database, cuenta["_id"]) == 2
    trabajo = imports.for_account(database, cuenta["_id"])[0]
    assert trabajo["status"] == imports.STOPPED
    # Los que ya estaban dentro no se borran: lo dice docs/pricing.md.
    assert trabajo["added"] == 2


def test_la_importacion_once_del_dia_se_rechaza(client, database, outbox):
    browser = inside(client)
    cuenta = account_of(database)
    for _ in range(10):
        imports.finish(database,
                       imports.start(database, cuenta["_id"], filename="x.csv",
                                     tags=[], consent=contacts.consent_of("members")),
                       status=imports.DONE, counts={})

    respuesta = upload(browser, LISTA)

    assert contacts.count(database, cuenta["_id"]) == 0
    assert "importaciones de hoy" in respuesta.get_data(as_text=True)


def test_dos_importaciones_a_la_vez_no(client, database, outbox):
    browser = inside(client)
    cuenta = account_of(database)
    imports.start(database, cuenta["_id"], filename="a medias.csv", tags=[],
                  consent=contacts.consent_of("members"))

    respuesta = upload(browser, LISTA)

    assert contacts.count(database, cuenta["_id"]) == 0
    assert "en curso" in respuesta.get_data(as_text=True)


def test_un_archivo_enorme_se_rechaza_sin_leerlo(client, database, outbox):
    """El corte lo hace Flask mientras el archivo llega, no el importador."""
    from config import Config

    browser = inside(client)
    grande = "a" * (Config.IMPORT_MAX_BYTES + 200 * 1024)
    token = csrf(browser, "/contactos/importar")
    respuesta = browser.post("/contactos/importar", data={
        "csrf_token": token, "source": "members", "note": "",
        "archivo": (io.BytesIO(grande.encode("ascii")), "enorme.csv"),
    }, content_type="multipart/form-data")

    assert respuesta.status_code == 413
    assert contacts.count(database, account_of(database)["_id"]) == 0


# --------------------------------------------------- una consulta por lote

def test_las_supresiones_se_preguntan_en_lote(client, database, outbox, monkeypatch):
    """Regla 10: nunca una consulta por contacto.

    Doscientas filas tienen que costar una sola pregunta por las supresiones y
    una sola escritura, no doscientas de cada.
    """
    llamadas = {"among": 0, "bulk": 0}
    original_among = suppressions.among
    original_bulk = contacts.upsert_many

    def contar_among(*a, **k):
        llamadas["among"] += 1
        return original_among(*a, **k)

    def contar_bulk(*a, **k):
        llamadas["bulk"] += 1
        return original_bulk(*a, **k)

    monkeypatch.setattr(suppressions, "among", contar_among)
    monkeypatch.setattr(contacts, "upsert_many", contar_bulk)

    browser = inside(client)
    filas = "correo\n" + "".join(f"socio{n}@coop.com\n" for n in range(200))
    upload(browser, filas)

    assert contacts.count(database, account_of(database)["_id"]) == 200
    assert llamadas["among"] == 1
    assert llamadas["bulk"] == 1


# ------------------------------------------------------------ supresiones

def test_un_suprimido_se_guarda_marcado_y_sigue_marcado(client, database, outbox):
    browser = inside(client)
    cuenta = account_of(database)
    suppressions.add(database, cuenta["_id"], "bea@coop.com",
                     reason=suppressions.COMPLAINT)

    upload(browser, LISTA)

    # Entra como los demás: el envío es el que lo salta, no la importación.
    assert contacts.by_email(database, cuenta["_id"], "bea@coop.com") is not None
    assert suppressions.has(database, cuenta["_id"], "bea@coop.com")
    pantalla = browser.get("/contactos").get_data(as_text=True)
    assert "Anulado" in pantalla


def test_borrar_un_contacto_no_levanta_su_supresion(client, database, outbox):
    """Regla 2: borrar y volver a subir no es una forma de saltarse una baja."""
    browser = inside(client)
    cuenta = account_of(database)
    upload(browser, LISTA)
    suppressions.add(database, cuenta["_id"], "bea@coop.com",
                     reason=suppressions.UNSUBSCRIBE)

    browser.post("/contactos/borrar", data={
        "csrf_token": csrf(browser), "email": "bea@coop.com"})
    assert contacts.by_email(database, cuenta["_id"], "bea@coop.com") is None
    assert suppressions.has(database, cuenta["_id"], "bea@coop.com")

    upload(browser, LISTA)
    assert suppressions.has(database, cuenta["_id"], "bea@coop.com")


def test_solo_se_quita_lo_que_se_puso_a_mano(client, database, outbox):
    browser = inside(client)
    cuenta = account_of(database)
    suppressions.add(database, cuenta["_id"], "queja@coop.com",
                     reason=suppressions.COMPLAINT)
    suppressions.add(database, cuenta["_id"], "mia@coop.com",
                     reason=suppressions.MANUAL)

    for direccion in ("queja@coop.com", "mia@coop.com"):
        browser.post("/contactos/supresiones/quitar", data={
            "csrf_token": csrf(browser, "/contactos/supresiones"),
            "email": direccion})

    # Un rebote o una queja son un hecho de la dirección, no una preferencia.
    assert suppressions.has(database, cuenta["_id"], "queja@coop.com")
    assert not suppressions.has(database, cuenta["_id"], "mia@coop.com")


def test_suprimir_a_mano_desde_la_pantalla(client, database, outbox):
    browser = inside(client)
    browser.post("/contactos/supresiones/anadir", data={
        "csrf_token": csrf(browser, "/contactos/supresiones"),
        "email": "quiensea@coop.com"})

    assert suppressions.has(database, account_of(database)["_id"],
                            "quiensea@coop.com")


# ------------------------------------------------------- cada cuenta la suya

def test_una_cuenta_no_ve_ni_toca_los_contactos_de_otra(client, database, outbox):
    una = inside(client)
    upload(una, LISTA)
    mia = account_of(database)

    otra = inside(other(client), email="otra@ejemplo.com")
    ajena = account_of(database, "otra@ejemplo.com")

    assert contacts.count(database, ajena["_id"]) == 0
    assert "ana@coop.com" not in otra.get("/contactos").get_data(as_text=True)

    # Y borrando por dirección tampoco alcanza los de la otra cuenta.
    otra.post("/contactos/borrar", data={
        "csrf_token": csrf(otra), "email": "ana@coop.com"})
    assert contacts.by_email(database, mia["_id"], "ana@coop.com") is not None


def test_las_supresiones_no_son_globales(client, database, outbox):
    """Una baja en una cuenta no dice nada de las demás."""
    inside(client)
    mia = account_of(database)
    suppressions.add(database, mia["_id"], "bea@coop.com")

    inside(other(client), email="otra@ejemplo.com")
    ajena = account_of(database, "otra@ejemplo.com")

    assert not suppressions.has(database, ajena["_id"], "bea@coop.com")


# ------------------------------------------------------------- etiquetas

def test_quitar_una_etiqueta_deja_los_contactos(client, database, outbox):
    browser = inside(client)
    make_tag(browser, "socios")
    upload(browser, LISTA, tags=["socios"])
    cuenta = account_of(database)

    browser.post("/contactos/etiquetas/borrar", data={
        "csrf_token": csrf(browser, "/contactos/etiquetas"), "etiqueta": "socios"})

    # Los contactos se quedan; la etiqueta sale del registro y de ellos.
    assert contacts.count(database, cuenta["_id"]) == 3
    assert accounts.tags_of(account_of(database)) == []
    assert contacts.tags_in_use(database, cuenta["_id"]) == []


def test_filtrar_por_etiqueta(client, database, outbox):
    browser = inside(client)
    make_tag(browser, "junta")
    make_tag(browser, "socios")
    upload(browser, "correo\nana@coop.com\n", tags=["junta"])
    upload(browser, "correo\nbea@coop.com\n", tags=["socios"])

    pantalla = browser.get("/contactos?etiqueta=junta").get_data(as_text=True)
    assert "ana@coop.com" in pantalla
    assert "bea@coop.com" not in pantalla


# --------------------------------------------------------------- la pantalla

# --------------------------------------------------------------- etiquetas

def test_una_etiqueta_recien_creada_ya_se_puede_elegir(client, database, outbox):
    """El problema que tenían: sin contactos dentro, no aparecía en ningún lado."""
    browser = inside(client)
    make_tag(browser, "junta")

    assert accounts.tags_of(account_of(database)) == ["junta"]
    # En el filtro de la lista y en las dos pantallas que asignan.
    for url in ("/contactos", "/contactos/nuevo", "/contactos/importar"):
        assert "junta" in browser.get(url).get_data(as_text=True), url


def test_una_etiqueta_repetida_no_entra_dos_veces(client, database, outbox):
    """Ni escrita igual ni con otras mayúsculas: era justo lo que pasaba."""
    browser = inside(client)
    make_tag(browser, "Socios")
    make_tag(browser, "socios")
    make_tag(browser, "  Socios  ")

    assert accounts.tags_of(account_of(database)) == ["Socios"]


def test_una_etiqueta_que_no_existe_no_se_puede_asignar(client, database, outbox):
    """La pantalla solo enseña casillas, pero un formulario se escribe a mano."""
    browser = inside(client)
    upload(browser, LISTA, tags=["inventada"])

    cuenta = account_of(database)
    assert contacts.count(database, cuenta["_id"]) == 3
    assert contacts.tags_in_use(database, cuenta["_id"]) == []


def test_las_etiquetas_que_ya_estaban_pasan_al_registro(client, database, outbox):
    """El relleno de una vez, para las cuentas de antes del registro."""
    from db import ensure_indexes

    browser = inside(client)
    make_tag(browser, "socios")
    upload(browser, LISTA, tags=["socios"])
    cuenta = account_of(database)

    # Una cuenta como las de antes: con etiquetas puestas y sin registro.
    database.accounts.update_one({"_id": cuenta["_id"]},
                                 {"$unset": {"contact_tags": ""}})
    ensure_indexes(database)

    assert accounts.tags_of(account_of(database)) == ["socios"]


# ------------------------------------------------------ como entro cada uno

def test_se_guarda_por_donde_entro_cada_contacto(client, database, outbox):
    browser = inside(client)
    upload(browser, "correo\nana@coop.com\n")
    browser.post("/contactos/nuevo", data={
        "csrf_token": csrf(browser, "/contactos/nuevo"),
        "email": "bea@coop.com", "source": "customers"})

    cuenta = account_of(database)
    assert contacts.by_email(database, cuenta["_id"],
                             "ana@coop.com")["added_by"] == contacts.IMPORT
    assert contacts.by_email(database, cuenta["_id"],
                             "bea@coop.com")["added_by"] == contacts.MANUAL

    pantalla = browser.get("/contactos").get_data(as_text=True)
    assert "Importado" in pantalla
    assert "A mano" in pantalla


def test_la_columna_de_estado_dice_activo_o_anulado(client, database, outbox):
    browser = inside(client)
    upload(browser, LISTA)
    cuenta = account_of(database)
    suppressions.add(database, cuenta["_id"], "bea@coop.com")

    pantalla = browser.get("/contactos").get_data(as_text=True)
    assert "Activo" in pantalla
    assert "Anulado" in pantalla


def test_contactos_pide_sesion(client, database):
    for url in ("/contactos", "/contactos/nuevo", "/contactos/importar",
                "/contactos/etiquetas", "/contactos/supresiones"):
        assert client.get(url).status_code == 302


def test_agregar_uno_a_mano(client, database, outbox):
    browser = inside(client)
    make_tag(browser, "junta")
    make_tag(browser, "socios")
    browser.post("/contactos/nuevo", data={
        "csrf_token": csrf(browser, "/contactos/nuevo"), "email": "nuevo@coop.com",
        "name": "Nuevo", "tags": ["junta", "socios"], "source": "customers"})

    guardado = contacts.by_email(database, account_of(database)["_id"],
                                 "nuevo@coop.com")
    assert guardado["name"] == "Nuevo"
    assert sorted(guardado["tags"]) == ["junta", "socios"]
    assert guardado["consent"]["source"] == contacts.CUSTOMERS


def test_el_buscador_no_deja_pasar_una_expresion_regular(client, database, outbox):
    """Lo que se escribe en la caja es texto, no sintaxis de búsqueda."""
    browser = inside(client)
    upload(browser, LISTA)

    pantalla = browser.get("/contactos?q=.*").get_data(as_text=True)
    assert "ana@coop.com" not in pantalla


def test_el_limite_se_ve_en_pantalla(client, database, outbox):
    browser = inside(client)
    assert "de 500 contactos" in browser.get("/contactos").get_data(as_text=True)


# ---------------------------------------------------------- las columnas

def test_el_lector_encuentra_las_columnas_por_su_nombre(client, database, outbox):
    assert importer.columns(["Nombre", "Correo electrónico"]) == (1, 0)
    assert importer.columns(["e-mail", "otra cosa"]) == (0, None)
    assert importer.columns(["algo", "otra"]) == (None, None)


def test_el_lector_no_carga_el_archivo_entero(client, database, outbox):
    """rows() es un generador: pedir la primera fila no lee el resto."""
    filas = "correo\n" + "".join(f"socio{n}@coop.com\n" for n in range(1000))
    flujo = io.BytesIO(filas.encode("utf-8"))
    generador = importer.rows(flujo)

    primera = next(generador)
    assert primera[0] == "socio0@coop.com"
    # Todavía queda archivo sin leer detrás del búfer.
    assert flujo.tell() < len(filas.encode("utf-8"))
