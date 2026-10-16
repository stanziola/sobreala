"""El Dashboard (octubre de 2026).

Estadísticas, Correos y Contactos en un árbol a la izquierda y la pantalla a la
derecha, con la búsqueda en la barra de arriba y solo aquí (y en
Administración). Lo que fijan estas pruebas: que el árbol sea el de los
permisos de quien mira y marque la pantalla en la que se está, que vaya pegado
a la izquierda, que Estadísticas se mire por secciones sin perder los filtros,
que Enviados escriba las cifras de una campaña sobre los que salieron y las de
un individual con marcas, y que el pie de los correos del sistema lleve las
mismas redes que el del sitio.
"""

from __future__ import annotations

import ast
from pathlib import Path

from bson import ObjectId

from test_admin import make_admin, make_client_account
from test_campaigns import ready
from test_users import as_member

from models import event as events
from services import mailer

ROOT = Path(__file__).resolve().parent.parent.parent


def tree_of(page: str) -> str:
    return page.split('data-dash-nav')[1].split('class="dash__pane"')[0]


# ------------------------------------------------------------------ el árbol

def test_el_arbol_tiene_sus_ramas_y_marca_donde_se_esta(client, database, outbox):
    browser, _, _ = ready(client, database)
    for url, current in (("/dashboard", "Resumen"), ("/campaigns", "Masivo"),
                         ("/campaigns/write", "Redactar"), ("/templates", "Mis plantillas"),
                         ("/campaigns/sent", "Enviados"), ("/campaigns/sender", "Remitente"),
                         ("/contacts", "Lista"), ("/contacts/suppressions", "Supresiones"),
                         # Importar, Etiquetas y Columnas viven bajo la lista.
                         ("/contacts/import", "Lista"), ("/contacts/tags", "Lista"),
                         ("/contacts/columns", "Lista"),
                         # Configuración, rama del Dashboard (octubre de 2026).
                         ("/settings/account", "Cuenta"), ("/settings/security", "Seguridad"),
                         ("/settings/notifications", "Notificaciones"),
                         ("/settings/billing", "Facturación")):
        page = browser.get(url)
        assert page.status_code == 200, url
        arbol = tree_of(page.get_data(as_text=True))
        assert f'aria-current="page">{current}<' in arbol, url
        for rama in ("Estadísticas", "Correos", "Enviar", "Plantillas", "Contactos",
                     "Configuración"):
            assert f">{rama}</span>" in arbol, (url, rama)
    arbol = tree_of(browser.get("/contacts").get_data(as_text=True))
    assert ">Etiquetas<" not in arbol and ">Columnas<" not in arbol
    assert ">Importar<" not in arbol
    # Remitente está en Configuración, y Plantillas ya no es una fila de Enviar.
    configuracion = arbol.split(">Configuración</span>")[1]
    assert ">Remitente<" in configuracion
    enviar = arbol.split(">Enviar</span>")[1].split(">Plantillas</span>")[0]
    assert ">Remitente<" not in enviar and ">Mis plantillas<" not in enviar


def test_la_busqueda_vive_solo_en_el_dashboard(client, database, outbox):
    browser, _, _ = ready(client, database)
    assert "data-search" in browser.get("/dashboard").get_data(as_text=True)
    assert "data-search" in browser.get("/contacts").get_data(as_text=True)
    # Configuración también es del Dashboard (octubre de 2026).
    assert "data-search" in browser.get("/settings/account").get_data(as_text=True)
    assert "data-search" not in browser.get("/switch-account").get_data(as_text=True)


def test_pegado_a_la_izquierda(client, database, outbox):
    """El menú de secciones arranca donde arranca el ala (octubre de 2026), y lo
    de la derecha se lleva el resto: el Dashboard y Administración. Configuración
    arranca igual, para que el menú no salte, con su ancho de siempre."""
    browser, _, _ = ready(client, database)
    for url, clase in (("/dashboard", "wrap wrap--wide wrap--left"),
                       ("/campaigns/write", "wrap wrap--wide wrap--left"),
                       ("/contacts", "wrap wrap--table wrap--left"),
                       ("/settings/account", "wrap wrap--wide wrap--left")):
        assert f'<main class="{clase}">' in browser.get(url).get_data(as_text=True), url
    assert "wrap--left" not in client.get("/login").get_data(as_text=True)
    # Configuración, dentro del Dashboard, va en medio de su espacio.
    assert '<div class="dash__pane dash__pane--center">' in browser.get(
        "/settings/account").get_data(as_text=True)
    admin, _ = make_admin(client, database)
    # La Configuración del administrador sigue aparte, con su ancho de siempre.
    assert '<main class="wrap wrap--wide wrap--left wrap--rows">' in admin.get(
        "/settings/security").get_data(as_text=True)
    assert '<main class="wrap wrap--wide wrap--left">' in admin.get(
        "/admin/accounts").get_data(as_text=True)
    css = (ROOT / "backend/static/css/_panel.src.css").read_text(encoding="utf-8")
    assert ".wrap--left {" in css and ".wrap--rows { max-width: 1400px; }" in css


def test_un_usuario_ve_solo_sus_ramas(client, database, outbox):
    _, _, suyo = as_member(client, database, permisos=("contacts",), outbox=outbox)
    # Sin Estadísticas, /dashboard lo lleva a lo primero que sí tiene.
    assert suyo.get("/dashboard").headers["Location"].endswith("/contacts")
    arbol = tree_of(suyo.get("/contacts").get_data(as_text=True))
    assert ">Contactos</span>" in arbol
    assert ">Estadísticas</span>" not in arbol and ">Correos</span>" not in arbol
    # El menú de arriba tiene la fila, que es la entrada.
    assert ">Dashboard</span>" in suyo.get("/contacts").get_data(as_text=True)


# --------------------------------------------------------- las estadísticas

def test_estadisticas_por_secciones_con_los_filtros(client, database, outbox):
    browser, _, _ = ready(client, database)
    for section, title in (("", "Cómo le fue"), ("opens", "Aperturas y clics"),
                           ("campaigns", "Tus mejores campañas"),
                           ("timing", "Cuándo abren tus correos"),
                           ("growth", "Crecimiento de la lista"),
                           ("quota", "Correos de este mes")):
        page = browser.get(f"/dashboard/{section}?period=7d" if section else "/dashboard?period=7d")
        assert page.status_code == 200, section
        text = page.get_data(as_text=True)
        assert f">{title}</h2>" in text, section
        # El árbol se lleva el filtro puesto a las otras secciones.
        assert 'href="/dashboard/opens?period=7d"' in text
    resumen = browser.get("/dashboard").get_data(as_text=True)
    assert ">Aperturas y clics</h2>" not in resumen
    assert browser.get("/dashboard/inventada").status_code == 404
    assert browser.get("/dashboard/summary").status_code == 404


def test_el_administrador_ve_todas_las_secciones_seguidas(client, database, outbox):
    make_client_account(client, database)
    admin, _ = make_admin(client, database)
    text = admin.get("/admin/").get_data(as_text=True)
    for title in ("Cómo le fue", "Aperturas y clics", "Tus mejores campañas",
                  "Correos de este mes"):
        assert f">{title}</h2>" in text


# ----------------------------------------------------------------- enviados

def add_run(database, account, *, to="", sent=3, kinds=(), with_file=False):
    campaign = database.campaigns.insert_one({
        "account_id": account["_id"], "kind": "single" if to else "campaign",
        "subject": "Prueba", "status": "sent",
        **({"download_id": ObjectId()} if with_file else {})}).inserted_id
    run = ObjectId()
    database.campaign_runs.insert_one({
        "_id": run, "account_id": account["_id"], "campaign_id": campaign,
        "subject": "Prueba de " + (to or "campaña"), "tags": [], "to": to,
        "sent": sent, "skipped": 0, "failed": 0, "finished_at": events.now()})
    for kind, who in kinds:
        events.record(database, account["_id"], kind=kind, campaign_id=campaign,
                      run_id=run, email=who)
    return run


def row_of(page: str, subject: str) -> str:
    return page.split(subject)[1].split("</tr>")[0]


def test_enviados_cifras_de_campana_y_marcas_de_individual(client, database, outbox):
    browser, account, _ = ready(client, database)
    add_run(database, account, sent=3, kinds=[
        (events.DELIVERED, "a@x.com"), (events.DELIVERED, "b@x.com"),
        (events.DELIVERED, "c@x.com"), (events.OPEN, "a@x.com"),
        (events.OPEN, "b@x.com"), (events.OPEN, "b@x.com")])
    add_run(database, account, to="uno@x.com", sent=1, with_file=True, kinds=[
        (events.DELIVERED, "uno@x.com"), (events.OPEN, "uno@x.com"),
        (events.DOWNLOAD, "uno@x.com")])
    add_run(database, account, to="dos@x.com", sent=1)

    page = browser.get("/campaigns/sent").get_data(as_text=True)
    campana = row_of(page, "Prueba de campaña")
    assert "3/3" in campana and "2/3" in campana and "0/3" in campana
    uno = row_of(page, "Prueba de uno@x.com")
    assert uno.count("✓") == 2 and "Descargó el archivo" in uno
    # Sin avisos de Amazon todavía lo dice, en vez de una fila de ceros.
    assert "Esperando lo que cuente Amazon" in row_of(page, "Prueba de dos@x.com")
    # Masivo ya no enseña lo que salió.
    assert "Prueba de campaña" not in browser.get("/campaigns").get_data(as_text=True)


# --------------------------------------------------------- el pie del correo

def test_el_pie_del_correo_tiene_las_redes_del_sitio(client, database, outbox):
    source = (ROOT / "landing" / "content.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    contact = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign)
                   and getattr(node.targets[0], "id", "") == "CONTACT")
    assert mailer.INSTAGRAM_URL == contact["instagram_url"]
    assert mailer.WHATSAPP_NUMBER == contact["whatsapp_number"]

    ready(client, database)
    mail = sorted(outbox.glob("*.html"))[0].read_text(encoding="utf-8")
    assert contact["instagram_url"] in mail
    assert f"https://wa.me/{contact['whatsapp_number']}" in mail
    assert "Santiago de Veraguas" in mail and "/static/img/mail/instagram.png" in mail
