"""La búsqueda (octubre de 2026), en la barra de arriba del Dashboard.

Para moverse por el Dashboard sin saber dónde está cada cosa. Mientras se
escribe sugiere dos clases de resultados:

  * **las pantallas del Dashboard, sacadas de su árbol** (`dashboard.tree()`),
    **cada una con su sitio** al lado: «Lista · Estadísticas» y «Lista ·
    Contactos», «Remitente · Configuración de envío» (16 de octubre de 2026: antes
    salían de una lista aparte, sin decir dónde estaban). El árbol ya trae
    los permisos de quien mira. Además, lo que se hace desde una pantalla sin
    ser fila (importar, agregar un contacto, etiquetas, columnas). La
    configuración de la cuenta no sale: es aparte del Dashboard, y se llega
    por el menú de arriba. Se buscan por su nombre, el de
    su rama y palabras con que la gente las pide («csv», «bajas»). Un
    administrador busca en lo suyo;
  * **lo suyo por nombre**: campañas, envíos, plantillas y etiquetas de su
    cuenta, con un tope cada uno.

Sin acentos y sin mayúsculas: «facturacion» encuentra «Facturación». Las
sugerencias las pide `panel.js` a `/search/suggest` (JSON); sin JavaScript, el
campo manda a `/search`, que enseña lo mismo en una página. Sin sesión, las dos
responden 404: no hay nada que buscar.

Solo vive en el panel: el sitio público no tiene sesión, y sin ella no hay qué
buscar (es la excepción a «lo que existe en los dos sitios», `CLAUDE.md`).
"""

from __future__ import annotations

import re
from typing import Any

from flask import Blueprint, abort, jsonify, render_template, request, url_for

from blueprints.auth.routes import current_account, current_workspace
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import design as designs
from services import dashboard
from services.importer import fold

bp = Blueprint("search", __name__)

# Cuántas sugerencias salen de cada clase, y en total.
PER_KIND = 5
SUGGEST_MAX = 8
QUERY_MAX = 80

# Las palabras con que se pide cada fila del árbol del Dashboard, además de su
# nombre y el de su rama (octubre de 2026: el buscador sale del árbol).
SEARCH_WORDS = {
    "stats-summary": "estadisticas cifras resumen panel dashboard graficas",
    "stats-opens": "aperturas clics abiertos",
    "stats-campaigns": "campanas cifras por campana",
    "stats-timing": "hora dia horario cuando abren",
    "stats-growth": "crecimiento contactos nuevos",
    "stats-quota": "cuota correos del mes limite plan",
    "compose": "escribir correo individual una persona adjunto archivo",
    "bulk": "enviar campanas correos programar mandar",
    "sent": "envios salieron historial abiertos clics",
    "sender": "dominio propio responder a direccion de salida",
    "templates": "disenos piezas carpetas",
    # Se llamó «Crear» hasta octubre de 2026: así se sigue encontrando.
    "templates-new": "plantilla nueva crear disenar",
    "contacts": "personas socios clientes",
    "suppressions": "bajas anulados rebotes quejas",
    "settings-test": "demostracion correos verificados prueba",
}
# Lo que se hace desde una pantalla y no es fila del árbol: (texto, ruta,
# permiso, la fila donde vive, palabras con que se pide).
CLIENT_ACTIONS = (
    ("search_page_import", "contacts.upload", accounts.CONTACTS, "contacts",
     "importar subir csv excel archivo lista"),
    ("search_page_add_contact", "contacts.add_one", accounts.CONTACTS, "contacts",
     "agregar contacto nuevo a mano"),
    ("search_page_tags", "contacts.tags", accounts.CONTACTS, "contacts",
     "etiquetas listas grupos"),
    ("search_page_fields", "contacts.fields", accounts.CONTACTS, "contacts",
     "columnas campos datos propios"),
)
ADMIN_PAGES = (
    ("search_page_admin_stats", "admin.home", "estadisticas cifras"),
    ("search_page_admin_accounts", "admin.accounts_list",
     "cuentas aprobar abrir limitar demostracion verificar eliminar"),
    ("search_page_admin_clients", "admin.clients_list",
     "clientes vigilar rebotes quejas amazon salud"),
    ("search_page_admin_events", "admin.activity_page", "eventos en vivo lo que pasa avisos"),
    ("search_page_admin_mail", "admin.system_mail", "correos del sistema no le llego codigo"),
)
PATH = " › "


def words(text: str) -> list[str]:
    return [one for one in re.split(r"\s+", fold(text)) if one]


def matches(query: list[str], *texts: str) -> bool:
    """Si cada palabra buscada está, al principio de alguna palabra del texto."""
    found = words(" ".join(texts))
    return all(any(one.startswith(part) for one in found) for part in query)


def leaves(rows: list[dict], path: list[str]):
    """Cada fila del árbol que abre una pantalla, con el camino de ramas que
    lleva a ella."""
    for row in rows:
        if row.get("rows"):
            yield from leaves(row["rows"], path + [t(row["label"])])
        else:
            yield row, path


def pages_for(account: dict) -> list[dict[str, Any]]:
    """Las pantallas que esta cuenta puede abrir, cada una con su sitio.

    Salen del árbol del Dashboard (`services/dashboard.tree()`), que ya trae los
    permisos de quien mira: lo que cambie en el árbol cambia solo aquí. La pista
    es el camino de ramas, así «Lista» de Estadísticas y «Lista» de Contactos
    no se confunden.
    """
    out: list[dict[str, Any]] = []

    def add(label, url, path, extra=""):
        out.append({"label": label, "url": url, "kind": "page",
                    "hint": PATH.join(path), "words": " ".join(path) + " " + extra})

    if accounts.is_admin(account):
        for key, endpoint, extra in ADMIN_PAGES:
            add(t(key), url_for(endpoint), [t("admin_title")], extra)
        return out

    places = {}
    for row, path in leaves(dashboard.tree(account), []):
        add(t(row["label"]), row["url"], path, SEARCH_WORDS.get(row["key"], ""))
        places[row["key"]] = path + [t(row["label"])]
    for key, endpoint, permission, where, extra in CLIENT_ACTIONS:
        if accounts.can(account, permission) and where in places:
            add(t(key), url_for(endpoint), places[where][:-1], extra)
    return out


def things_for(db, account: dict, workspace: dict, query: list[str]) -> list[dict[str, Any]]:
    """Lo suyo por nombre: campañas, envíos, plantillas y etiquetas."""
    if accounts.is_admin(account) or not workspace:
        return []
    out: list[dict[str, Any]] = []
    owner = workspace["_id"]
    if accounts.can(account, accounts.CAMPAIGNS):
        found = [one for one in campaigns.for_account(db, owner, limit=200)
                 if one.get("kind") != campaigns.SINGLE
                 and matches(query, one.get("subject", ""))][:PER_KIND]
        for one in found:
            out.append({"label": one.get("subject", ""), "kind": "campaign",
                        "hint": t("search_kind_campaign"),
                        "url": url_for("campaigns.edit", raw=one["_id"])})
        sent = [one for one in runs.for_account(db, owner, limit=200)
                if matches(query, one.get("subject", ""), one.get("to", ""))][:PER_KIND]
        for one in sent:
            out.append({"label": one.get("subject", ""), "kind": "run",
                        "hint": t("search_kind_run"),
                        "url": url_for("campaigns.run_detail", raw=one["_id"])})
    if accounts.can(account, accounts.DESIGNS):
        found = [one for one in designs.for_account(db, owner, limit=200)
                 if matches(query, one.get("name", ""))][:PER_KIND]
        for one in found:
            if one.get("source") == designs.CANVAS:
                url = url_for("designs.edit_canvas", raw=one["_id"])
            elif one.get("source") == designs.UPLOAD:
                url = url_for("designs.edit_html", raw=one["_id"])
            else:
                url = url_for("designs.piece", raw=one["_id"])
            out.append({"label": one.get("name", ""), "kind": "design",
                        "hint": t("search_kind_design"), "url": url})
    if accounts.can(account, accounts.CONTACTS):
        for name in [one for one in accounts.tags_of(workspace)
                     if matches(query, one)][:PER_KIND]:
            out.append({"label": name, "kind": "tag", "hint": t("search_kind_tag"),
                        "url": url_for("contacts.index", tag=name)})
    return out


def results(raw: str) -> list[dict[str, Any]]:
    """Todo lo que coincide: primero las pantallas, después lo suyo."""
    account = current_account()
    if account is None:
        abort(404)
    query = words(raw[:QUERY_MAX])
    if not query:
        return []
    pages = [one for one in pages_for(account)
             if matches(query, one["label"], one["words"])]
    return pages + things_for(get_db(), account, current_workspace(), query)


@bp.route("/search")
def page():
    """La página de resultados: lo que hace el campo sin JavaScript."""
    raw = " ".join(request.args.get("q", "").split())[:QUERY_MAX]
    found = results(raw)
    return render_template("search.html", query=raw, found=found)


@bp.route("/search/suggest")
def suggest():
    """Las sugerencias mientras se escribe, para `panel.js`."""
    found = results(request.args.get("q", ""))[:SUGGEST_MAX]
    response = jsonify({"items": [{key: one[key] for key in ("label", "hint", "url", "kind")}
                                  for one in found]})
    response.headers["Cache-Control"] = "no-store"
    return response
