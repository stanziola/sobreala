"""La búsqueda (octubre de 2026), arriba de la barra lateral del Dashboard.

Para moverse por el panel sin saber dónde está cada cosa. Mientras se escribe
sugiere dos clases de resultados:

  * **pantallas y acciones** («Importar contactos», «Cambiar la contraseña»,
    «Facturación», «Redactar»), **las que esa cuenta puede abrir**:
    un usuario de la empresa ve solo las de sus permisos, y un administrador
    las suyas. Se buscan por su nombre y por palabras que la gente usa para
    pedirlas («csv», «bajas», «dos pasos»);
  * **lo suyo por nombre**: campañas, envíos, plantillas y etiquetas de su
    cuenta, con un tope cada uno.

Sin acentos y sin mayúsculas: «facturacion» encuentra «Facturación». Las
sugerencias las pide `panel.js` a `/search/suggest` (JSON); sin JavaScript, el
campo manda a `/search`, que enseña lo mismo en una página. Sin sesión, las dos
responden 404: no hay nada que buscar.

Solo vive en el panel, y dentro de él en la barra lateral del Dashboard (la del
administrador, en la de Administración): el sitio público no tiene sesión, y
sin ella no hay qué buscar (es la excepción a «lo que existe en los dos
sitios», `CLAUDE.md`).
"""

from __future__ import annotations

import re
from typing import Any

from flask import Blueprint, abort, jsonify, render_template, request, url_for

from blueprints.auth.routes import (WHOLE, current_account, current_workspace,
                                    parts_for, sections_for)
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import design as designs
from services.importer import fold

bp = Blueprint("search", __name__)

# Cuántas sugerencias salen de cada clase, y en total.
PER_KIND = 5
SUGGEST_MAX = 8
QUERY_MAX = 80

# Las pantallas de un cliente: (texto, ruta, permiso, palabras con que se piden).
# Configuración se agrega aparte, con sus subsecciones (`settings_pages`).
CLIENT_PAGES = (
    ("search_page_stats", "auth.panel", accounts.STATS,
     "estadisticas cifras aperturas clics rebotes graficas panel dashboard resumen"),
    ("search_page_send", "campaigns.index", accounts.CAMPAIGNS,
     "enviar campanas correos programar mandar masivo"),
    ("search_page_sent", "campaigns.sent_list", accounts.CAMPAIGNS,
     "enviados envios salieron historial abiertos clics"),
    ("search_page_write", "campaigns.write", accounts.SEND,
     "escribir correo individual una persona adjunto archivo redactar"),
    ("search_page_sender", "campaigns.sender_page", accounts.SEND,
     "remitente dominio propio responder a direccion de salida"),
    ("search_page_contacts", "contacts.index", accounts.CONTACTS,
     "contactos lista personas socios clientes"),
    ("search_page_import", "contacts.upload", accounts.CONTACTS,
     "importar subir csv excel archivo lista"),
    ("search_page_add_contact", "contacts.add_one", accounts.CONTACTS,
     "agregar contacto nuevo a mano"),
    ("search_page_tags", "contacts.tags", accounts.CONTACTS,
     "etiquetas listas grupos"),
    ("search_page_fields", "contacts.fields", accounts.CONTACTS,
     "columnas campos datos propios"),
    ("search_page_suppressions", "contacts.blocked", accounts.CONTACTS,
     "bajas supresiones anulados rebotes quejas"),
    ("search_page_designs", "designs.index", accounts.DESIGNS,
     "plantillas disenos piezas"),
    ("search_page_new_design", "designs.create", accounts.DESIGNS,
     "crear plantilla nueva lienzo disenar"),
)
ADMIN_PAGES = (
    ("search_page_admin_stats", "admin.home", None, "estadisticas cifras"),
    ("search_page_admin_accounts", "admin.accounts_list", None,
     "cuentas aprobar abrir limitar demostracion verificar"),
    ("search_page_admin_clients", "admin.clients_list", None,
     "clientes vigilar rebotes quejas amazon salud"),
    ("search_page_admin_events", "admin.activity_page", None,
     "eventos en vivo lo que pasa avisos"),
    ("search_page_admin_mail", "admin.system_mail", None,
     "correos del sistema no le llego codigo"),
)
# Palabras con que se piden las subsecciones de Configuración, además de su
# nombre y el de su sección.
SETTINGS_WORDS = {
    ("account", "profile"): "nombre empresa correo cambiar correo",
    ("account", "contact"): "direccion postal telefonos",
    ("account", "verification"): "verificar documentos identificacion cedula",
    ("account", "plan"): "plan contratado",
    ("security", "two-step"): "dos pasos doble factor mfa codigo autenticador",
    ("security", "password"): "cambiar contrasena clave google",
    ("security", "users"): "usuarios equipo invitar permisos",
    ("security", "sessions"): "sesiones dispositivos cerrar sesion",
    ("notifications", "plan"): "avisos correos facturacion vencimiento",
    ("notifications", "security"): "avisos dispositivo nuevo seguridad",
    ("notifications", "clients"): "avisos pagos registros pausas",
    ("billing", "plan"): "plan vence pagar",
    ("billing", "methods"): "metodos de pago paypal tarjeta agregar",
    ("billing", "auto-renewal"): "renovacion automatica suscripcion cobro",
    ("billing", "history"): "historial compras facturas pagos recibos",
    ("test", "addresses"): "direcciones de prueba demostracion",
}
SECTION_LABELS = {"account": "settings_section_account",
                  "security": "settings_section_security",
                  "notifications": "settings_section_notifications",
                  "billing": "settings_section_payments",
                  "test": "settings_section_test"}


def words(text: str) -> list[str]:
    return [one for one in re.split(r"\s+", fold(text)) if one]


def matches(query: list[str], *texts: str) -> bool:
    """Si cada palabra buscada está, al principio de alguna palabra del texto."""
    found = words(" ".join(texts))
    return all(any(one.startswith(part) for one in found) for part in query)


def pages_for(account: dict) -> list[dict[str, Any]]:
    """Las pantallas que esta cuenta puede abrir, con lo que las encuentra."""
    out = []
    listed = ADMIN_PAGES if accounts.is_admin(account) else CLIENT_PAGES
    for key, endpoint, permission, extra in listed:
        if permission and not accounts.can(account, permission):
            continue
        out.append({"label": t(key), "url": url_for(endpoint), "kind": "page",
                    "hint": "", "words": extra})
    for section in sections_for(account):
        section_label = t(SECTION_LABELS[section])
        # Cuenta y Facturación se leen enteras: la sección, y sus partes como
        # anclas.
        whole = WHOLE.get(section, ())
        if whole:
            out.append({"label": section_label, "kind": "page",
                        "hint": t("search_in", where=t("menu_settings")),
                        "url": url_for("auth.settings", section=section),
                        "words": "configuracion " + " ".join(
                            SETTINGS_WORDS.get((section, part), "") for part in whole)})
        for part in parts_for(account, section) or whole:
            label = t(f"settings_part_{section}_{part.replace('-', '_')}")
            url = (url_for("auth.settings", section=section) + "#" + part if part in whole
                   else url_for("auth.settings", section=section, part=part))
            out.append({"label": label, "kind": "page",
                        "hint": t("search_in", where=section_label),
                        "url": url,
                        "words": f"configuracion {section_label} "
                                 + SETTINGS_WORDS.get((section, part), "")})
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
