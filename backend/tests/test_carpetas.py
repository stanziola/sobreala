"""Las carpetas de Mis plantillas, y «Crear», que pasó a llamarse «Lienzo»
(octubre de 2026).

Lo que fijan estas pruebas: que una carpeta se crea, cambia de nombre y de
color, y se elimina sin borrar sus plantillas; que una plantilla solo se mueve a
una carpeta de su cuenta; que al pasar el ratón asoman las tres más recientes,
cada una con el enlace a su editor, y que el cristal entra a la carpeta; que la
carpeta de otra cuenta no se abre; que sin JavaScript cada bandeja llega
abierta; y que Mis plantillas ya no tiene arriba Crear, Cargar ni las notas,
que están en el Lienzo.
"""

from __future__ import annotations

import json
from datetime import timedelta

from bson import ObjectId

from test_canvas import con_texto, guardar, lienzo, texto
from test_dashboard import tree_of
from test_designs import cargada, csrf, inside, pieza_de_antes

from models import account as accounts
from models import design as designs
from services import canvas


def cuenta(database, email="ana@ejemplo.com"):
    return accounts.by_email(database, email)


def nueva(browser, nombre="Boletines", color="blue"):
    return browser.post("/templates/folders", data={
        "csrf_token": csrf(browser), "action": "new", "nombre": nombre, "color": color})


def cambiar(browser, carpeta, action, **data):
    return browser.post("/templates/folders", data={
        "csrf_token": csrf(browser), "action": action, "folder": str(carpeta), **data})


def la_carpeta(database, nombre="Boletines", email="ana@ejemplo.com"):
    return next(one for one in designs.folders_of(cuenta(database, email))
                if one["name"] == nombre)


def hoja(database, nombre, email="ana@ejemplo.com", **extra):
    """Una plantilla del lienzo, guardada directo."""
    hecha = designs.save_canvas(database, cuenta(database, email)["_id"], name=nombre,
                                doc=canvas.blank(), backgrounds=[], shades=[])
    if extra:
        database.designs.update_one({"_id": hecha}, {"$set": extra})
    return hecha


def mover(browser, plantilla, carpeta, back=""):
    return browser.post("/templates/move", data={
        "csrf_token": csrf(browser), "id": str(plantilla),
        "folder": str(carpeta) if carpeta else "", "back": str(back) if back else ""})


# ----------------------------------------------------------------- las carpetas

def test_se_crea_cambia_y_se_elimina_sin_borrar_sus_plantillas(client, database, outbox):
    browser = inside(client)
    respuesta = nueva(browser)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/templates?carpeta_hecha=nueva")
    hecha = la_carpeta(database)
    assert hecha["color"] == "blue"
    pantalla = browser.get("/templates?carpeta_hecha=nueva").get_data(as_text=True)
    assert 'class="folder folder--blue"' in pantalla
    assert "Listo, ya tienes la carpeta." in pantalla

    # El nombre: el mismo no escribe nada, y uno nuevo vuelve con su aviso.
    assert "same=1" in cambiar(browser, hecha["id"], "rename",
                               nombre="Boletines").headers["Location"]
    assert cambiar(browser, hecha["id"], "rename", nombre="Avisos").status_code == 302
    assert la_carpeta(database, "Avisos")["id"] == hecha["id"]

    # El color: solo los de la paleta.
    mal = cambiar(browser, hecha["id"], "color", color="black")
    assert mal.status_code == 200 and "Elige uno de los colores." in mal.get_data(as_text=True)
    cambiar(browser, hecha["id"], "color", color="teal")
    assert la_carpeta(database, "Avisos")["color"] == "teal"

    # Eliminarla deja sus plantillas, sin carpeta.
    dentro = hoja(database, "Junio", folder_id=hecha["id"])
    respuesta = cambiar(browser, hecha["id"], "delete")
    assert respuesta.headers["Location"].endswith("/templates?carpeta_hecha=eliminada")
    assert designs.folders_of(cuenta(database)) == []
    sigue = database.designs.find_one({"_id": dentro})
    assert sigue is not None and "folder_id" not in sigue


def test_el_nombre_no_queda_vacio_ni_se_repite_y_hay_tope(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Boletines")
    assert "Completa este campo." in nueva(browser, "   ").get_data(as_text=True)
    # Sin mayúsculas, como las etiquetas.
    assert "Ya tienes una carpeta con ese nombre." in nueva(
        browser, "boletines").get_data(as_text=True)
    assert len(designs.folders_of(cuenta(database))) == 1

    database.accounts.update_one({"_id": cuenta(database)["_id"]}, {"$set": {
        "design_folders": [{"id": ObjectId(), "name": f"Carpeta {n}", "color": "gray"}
                           for n in range(designs.FOLDER_LIMIT)]}})
    llena = nueva(browser, "Una más").get_data(as_text=True)
    assert f"Ya tienes {designs.FOLDER_LIMIT} carpetas" in llena
    # Ya no se ofrece crear otra.
    assert "Nueva carpeta</span>" not in browser.get("/templates").get_data(as_text=True)


def test_se_mueve_solo_a_una_carpeta_de_su_cuenta(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Cobros")
    suya = la_carpeta(database, "Cobros")
    plantilla = hoja(database, "Recordatorio")

    respuesta = mover(browser, plantilla, suya["id"])
    assert respuesta.headers["Location"].endswith("/templates?movida=1")
    assert database.designs.find_one({"_id": plantilla})["folder_id"] == suya["id"]

    # Una carpeta de otra cuenta no es ninguna.
    bea = inside(client, "bea@ejemplo.com")
    nueva(bea, "Ajena")
    ajena = la_carpeta(database, "Ajena", "bea@ejemplo.com")
    mover(browser, plantilla, ajena["id"])
    assert database.designs.find_one({"_id": plantilla})["folder_id"] == suya["id"]
    # Ni se mueve la plantilla de otra.
    mover(bea, plantilla, ajena["id"])
    assert database.designs.find_one({"_id": plantilla})["folder_id"] == suya["id"]

    # «Sin carpeta» la saca, y se vuelve a la carpeta desde donde se pulsó.
    respuesta = mover(browser, plantilla, None, back=suya["id"])
    assert respuesta.headers["Location"].endswith(f"/templates/folders/{suya['id']}?movida=1")
    assert "folder_id" not in database.designs.find_one({"_id": plantilla})


def test_se_mueven_varias_de_una_vez(client, database, outbox):
    """Las que se arrastran juntas (octubre de 2026): llegan en un solo envío,
    con una `id` por plantilla. La de otra cuenta se ignora."""
    browser = inside(client)
    nueva(browser, "Cobros")
    suya = la_carpeta(database, "Cobros")
    una, otra = hoja(database, "Cuota de enero"), hoja(database, "Cuota de febrero")
    inside(client, "bea@ejemplo.com")
    ajena = hoja(database, "De Bea", email="bea@ejemplo.com")

    respuesta = browser.post("/templates/move", data={
        "csrf_token": csrf(browser), "folder": str(suya["id"]), "back": "",
        "id": [str(una), str(otra), str(ajena)]})
    assert respuesta.headers["Location"].endswith("/templates?movida=2")
    for uno in (una, otra):
        assert database.designs.find_one({"_id": uno})["folder_id"] == suya["id"]
    assert "folder_id" not in database.designs.find_one({"_id": ajena})
    assert "Listo, se movieron 2 plantillas." in browser.get(
        "/templates?movida=2").get_data(as_text=True)


def test_se_arrastra_desde_las_tarjetas_y_las_hojas(client, database, outbox):
    """Lo que el arrastre necesita en la página (octubre de 2026): qué se
    arrastra, dónde se suelta y el formulario que se manda al soltar."""
    browser = inside(client)
    nueva(browser, "Eventos")
    suya = la_carpeta(database, "Eventos")
    dentro = hoja(database, "Asamblea", folder_id=suya["id"])
    suelta = hoja(database, "Suelta")

    lista = browser.get("/templates").get_data(as_text=True)
    assert f'data-drag-template="{suelta}"' in lista
    assert f'data-drag-template="{dentro}"' in lista  # su hoja, que asoma
    assert f'data-drop-folder="{suya["id"]}"' in lista
    assert 'class="shelf__loose" data-drop-folder=""' in lista
    assert 'data-drag-form' in lista and 'data-move-to="Mover a «{name}»"' in lista

    # Con todas en carpetas, «Sin carpeta» sigue ahí para soltar, y lo dice.
    database.designs.update_one({"_id": suelta}, {"$set": {"folder_id": suya["id"]}})
    lista = browser.get("/templates").get_data(as_text=True)
    assert "Todas tus plantillas están en carpetas." in lista

    # Dentro de la carpeta, «← Mis plantillas» saca lo que se le suelta.
    carpeta = browser.get(f"/templates/folders/{suya['id']}").get_data(as_text=True)
    assert 'data-drop-folder="" data-drop-name=""' in carpeta.split('class="crumb"')[1]
    assert f'data-drag-folder="{suya["id"]}"' in carpeta
    assert 'name="back" value="{}"'.format(suya["id"]) in carpeta.split("data-drag-form")[1]


def test_el_sobre_puede_ser_blanco(client, database, outbox):
    browser = inside(client)
    assert nueva(browser, "Avisos", "white").status_code == 302
    assert la_carpeta(database, "Avisos")["color"] == "white"
    pantalla = browser.get("/templates").get_data(as_text=True)
    assert 'class="folder folder--white"' in pantalla
    assert 'value="white"' in pantalla and "Blanco" in pantalla


def test_duplicar_la_deja_en_la_misma_carpeta(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Eventos")
    suya = la_carpeta(database, "Eventos")
    plantilla = hoja(database, "Asamblea", folder_id=suya["id"])
    respuesta = browser.post("/templates/duplicate", data={
        "csrf_token": csrf(browser), "id": str(plantilla), "back": str(suya["id"])})
    assert respuesta.headers["Location"].endswith(f"/templates/folders/{suya['id']}?copy=1")
    copia = database.designs.find_one({"name": "Copia de Asamblea"})
    assert copia["folder_id"] == suya["id"]


def test_la_carpeta_trae_todas_y_la_de_otra_cuenta_no_se_abre(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Boletines")
    suya = la_carpeta(database)
    for n in range(6):
        hoja(database, f"Boletín {n}", folder_id=suya["id"])
    hoja(database, "Suelta")

    pantalla = browser.get(f"/templates/folders/{suya['id']}").get_data(as_text=True)
    for n in range(6):
        assert f"<b>Boletín {n}</b>" in pantalla
    assert "<b>Suelta</b>" not in pantalla
    assert 'href="/templates"' in pantalla  # «← Mis plantillas»
    assert 'aria-current="page">Mis plantillas<' in tree_of(pantalla)

    # La suelta sigue en Mis plantillas, y las de la carpeta no.
    lista = browser.get("/templates").get_data(as_text=True)
    assert "<b>Suelta</b>" in lista and "<b>Boletín 0</b>" not in lista

    bea = inside(client, "bea@ejemplo.com")
    assert bea.get(f"/templates/folders/{suya['id']}").status_code == 404
    assert bea.get(f"/templates/folders/{ObjectId()}").status_code == 404
    assert bea.get("/templates/folders/no-es-un-id").status_code == 404


def test_una_carpeta_vacia_lo_dice(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Vacía")
    suya = la_carpeta(database, "Vacía")
    pantalla = browser.get(f"/templates/folders/{suya['id']}").get_data(as_text=True)
    assert "Esta carpeta está vacía." in pantalla
    assert "Vacía</span>" in browser.get("/templates").get_data(as_text=True)


def test_asoman_las_tres_mas_recientes_y_cada_una_abre_su_editor(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Boletines")
    suya = la_carpeta(database)
    base = designs.now()
    ids = {}
    for n in range(6):
        ids[n] = hoja(database, f"Boletín {n}", folder_id=suya["id"],
                      updated_at=base + timedelta(minutes=n))
    # Una cargada antes y una prediseñada de antes, que se editan en otro sitio.
    html = cargada(database, name="Cargada")
    database.designs.update_one({"_id": html}, {"$set": {
        "folder_id": suya["id"], "updated_at": base + timedelta(minutes=10)}})
    vieja = pieza_de_antes(client, "aviso")
    database.designs.update_one({"_id": vieja}, {"$set": {
        "folder_id": suya["id"], "updated_at": base + timedelta(minutes=9)}})

    pantalla = browser.get("/templates").get_data(as_text=True)
    carpeta = pantalla.split('class="folder folder--blue"')[1].split("</details>")[0]
    hojas = carpeta.split('class="folder__files folder__files--3"')[1].split("</ul>")[0]
    # Tres (pedido así: para entrar rápido a una), de la más vieja a la más
    # nueva: la última queda delante del cristal.
    nombres = [one.split('"')[0] for one in hojas.split('data-drag-name="')[1:]]
    assert nombres == ["Boletín 5", "De antes", "Cargada"]
    assert f'href="/templates/canvas/{ids[5]}"' in hojas
    assert f'href="/templates/piece/{vieja}"' in hojas
    assert f'href="/templates/html/{html}"' in hojas
    assert f'href="/templates/canvas/{ids[4]}"' not in hojas
    # Cada hoja es su plantilla: su vista, que se pide al pasar el ratón
    # (`data-src`), fuera del enlace, y se puede arrastrar a otra carpeta.
    for uno in (ids[5], vieja, html):
        assert f'data-src="/templates/{uno}/preview"' in hojas
        assert f'data-drag-template="{uno}"' in hojas
    enlace = hojas.split('class="folder__sheet-link"')[1].split("</a>")[0]
    assert "<iframe" not in enlace
    # Sin su nombre a la vista: se lee dentro de la carpeta. Lo oye quien no
    # ve la hoja.
    assert 'class="visually-hidden">Boletín 5</span>' in enlace
    assert "hace " not in hojas
    # El cristal entra a la carpeta, y dice cuántas tiene.
    assert f'class="folder__front" href="/templates/folders/{suya["id"]}"' in carpeta
    assert "8 plantillas" in carpeta


def test_sin_javascript_cada_bandeja_llega_abierta(client, database, outbox):
    browser = inside(client)
    nueva(browser, "Cobros", "amber")
    suya = la_carpeta(database, "Cobros")
    pantalla = browser.get(f"/templates?carpeta={suya['id']}&editar=nombre").get_data(as_text=True)
    bandeja = pantalla.split('id="carpeta-bandeja"')[1].split("</section>")[0]
    assert 'name="action" value="rename"' in bandeja
    assert 'value="Cobros"' in bandeja
    color = browser.get(f"/templates?carpeta={suya['id']}&editar=color").get_data(as_text=True)
    assert 'value="amber" data-fill="color" checked' in color.split(
        'id="carpeta-bandeja"')[1].split("</section>")[0]
    assert 'id="carpeta-bandeja"' in browser.get("/templates?nueva=1").get_data(as_text=True)
    # Lo que no es una bandeja, o la carpeta de nadie, no abre nada.
    assert 'id="carpeta-bandeja"' not in browser.get(
        f"/templates?carpeta={suya['id']}&editar=otra").get_data(as_text=True)
    assert 'id="carpeta-bandeja"' not in browser.get(
        f"/templates?carpeta={ObjectId()}&editar=nombre").get_data(as_text=True)
    # Con JavaScript, el mismo enlace abre su diálogo, lleno con la carpeta.
    assert 'data-folder-tray="rename" data-folder-id="{}"'.format(suya["id"]) in pantalla
    assert 'data-folder-dialog="delete"' in pantalla


def test_un_usuario_sin_el_permiso_y_el_administrador_no_entran(client, database, outbox):
    from test_admin import make_admin
    from test_users import as_member

    dueno, empresa, suyo = as_member(client, database, permisos=("contacts",), outbox=outbox)
    nueva(dueno, "Boletines")
    carpeta = la_carpeta(database, "Boletines", empresa["email"])
    assert suyo.get(f"/templates/folders/{carpeta['id']}").status_code != 200
    suyo.post("/templates/folders", data={"action": "delete", "folder": str(carpeta["id"])})
    assert len(designs.folders_of(cuenta(database, empresa["email"]))) == 1

    # Al administrador, como en todas las plantillas, lo manda a lo suyo.
    admin, _ = make_admin(client, database)
    respuesta = admin.get(f"/templates/folders/{carpeta['id']}")
    assert respuesta.status_code == 302 and respuesta.headers["Location"].endswith("/admin/")


# ---------------------------------------------- Mis plantillas y el Lienzo

def test_mis_plantillas_ya_no_tiene_crear_cargar_ni_las_notas(client, database, outbox):
    browser = inside(client)
    pantalla = browser.get("/templates").get_data(as_text=True)
    assert "Crear plantilla" not in pantalla
    assert "Cargar plantilla (ZIP)" not in pantalla
    assert "*|NOMBRE|*" not in pantalla and "102 KB" not in pantalla
    assert "Nueva carpeta" in pantalla
    # En el árbol, «Crear» se llama «Lienzo».
    arbol = tree_of(pantalla)
    assert ">Lienzo<" in arbol and ">Crear<" not in arbol

    lienzo_ = browser.get("/templates/create").get_data(as_text=True)
    assert "Cargar plantilla (ZIP)" in lienzo_
    assert 'href="/templates/upload"' in lienzo_
    assert 'accept=".zip,application/zip"' in lienzo_
    # Su campo de nombre no choca con el de la plantilla.
    assert lienzo_.count('id="nombre"') == 1 and 'id="cargar-nombre"' in lienzo_


def test_el_lienzo_guarda_la_carpeta_y_vuelve_a_ella(client, database, outbox):
    browser = inside(client)
    # Sin carpetas, no hay lista que elegir.
    assert 'name="carpeta"' not in browser.get("/templates/create").get_data(as_text=True)
    nueva(browser, "Eventos")
    suya = la_carpeta(database, "Eventos")
    assert f'<option value="{suya["id"]}">Eventos</option>' in browser.get(
        "/templates/create").get_data(as_text=True)

    respuesta = browser.post("/templates/create", data={
        "csrf_token": csrf(browser, "/templates/create"), "nombre": "Asamblea",
        "carpeta": str(suya["id"]),
        "lienzo": json.dumps(con_texto(lienzo(texto(40, 40, text="Asamblea anual"))))})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith(f"/templates/folders/{suya['id']}?saved=1")
    hecha = database.designs.find_one({"name": "Asamblea"})
    assert hecha["folder_id"] == suya["id"]

    # Al editarla, la lista trae su carpeta; «Sin carpeta» la saca.
    url = f"/templates/canvas/{hecha['_id']}"
    assert f'<option value="{suya["id"]}" selected>' in browser.get(url).get_data(as_text=True)
    browser.post(url, data={"csrf_token": csrf(browser, url), "nombre": "Asamblea",
                            "carpeta": "", "lienzo": json.dumps(hecha["canvas"])})
    assert "folder_id" not in database.designs.find_one({"_id": hecha["_id"]})

    # La carpeta de otra cuenta es ninguna.
    bea = inside(client, "bea@ejemplo.com")
    guardar(bea, lienzo(texto(40, 40, text="Ajena")), nombre="De Bea")
    de_bea = database.designs.find_one({"name": "De Bea"})
    url = f"/templates/canvas/{de_bea['_id']}"
    bea.post(url, data={"csrf_token": csrf(bea, url), "nombre": "De Bea",
                        "carpeta": str(suya["id"]), "lienzo": json.dumps(de_bea["canvas"])})
    assert "folder_id" not in database.designs.find_one({"_id": de_bea["_id"]})
