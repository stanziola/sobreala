"""Contacts: the list, the importer and the suppressions.

Three rules from CLAUDE.md run through the whole file:

  * Nobody is duplicated. Every write is an upsert against {account_id,
    email_normalized}, and the unique index is what enforces it.
  * Deleting a contact does not delete its suppression, and importing the
    address again does not bring it back.
  * Every screen is scoped to the signed-in account. An id from somebody else's
    account matches nothing, because the account is part of every query rather
    than something checked beforehand.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, Response, abort, redirect, render_template,
                   request, url_for)

from blueprints.auth.routes import (current_account, current_workspace,
                                    log_auth, needs, not_for_admins)
from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import auth_event as events
from models import contact as contacts
from models import import_job as imports
from models import lock as locks
from models import suppression as suppressions
from services import address_check
from services import fields as columns
from services import importer
from services import plans
from services.security import csrf_ok

bp = Blueprint("contacts", __name__)

@bp.before_request
def keep_out():
    """Quién no entra aquí: un administrador, que no tiene contactos que mirar,
    y un usuario de una cuenta sin ese permiso.

    Va aquí y no en un decorador por ruta: esta pantalla tiene varias y una
    nueva heredaría la puerta sin que nadie se acuerde de ponérsela.
    """
    account = current_account()
    return not_for_admins(account) or needs(account, accounts.CONTACTS)


# How many rows one screen of the list shows.
PER_PAGE = 50

# Lo que dice el desplegable del mapeo cuando esa columna del archivo todavía
# no existe en la cuenta y hay que crearla.
NEW_COLUMN = "nueva"

# Los títulos que el importador ya reconoce solo. La pantalla no los pregunta,
# y la lista viaja de aquí y no copiada al guion: es la misma.
KNOWN_HEADERS = ",".join(importer.EMAIL_HEADERS + importer.NAME_HEADERS)


def signed_in():
    """**La cuenta de la empresa**, o None. Every route starts here.

    Para un usuario que la empresa creó es la de su dueño: los contactos son de
    ella, no de quien los mira (`current_workspace()`).
    """
    return current_workspace()


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def values_written(account, errors: dict[str, str]) -> dict[str, str]:
    """Lo que el formulario escribió en cada columna de la cuenta.

    Se recorren las columnas que existen, no lo que llegó: un campo con un
    nombre inventado no escribe nada.

    **Todas son obligatorias**, y lo que no encaja en su tipo cuenta como que
    falta: un contacto sin sus datos no entra, y si ya estaba, no recibe nada.
    """
    written: dict[str, str] = {}
    for one in accounts.fields_of(account):
        raw = request.form.get(f"col-{one['key']}", "")
        value = columns.parse(raw, one.get("type", columns.TEXT))
        if value:
            written[one["key"]] = value
        else:
            errors[f"col-{one['key']}"] = (
                t("error_field_value") if raw.strip() else t("error_required"))
    return written


def tags_chosen(account) -> list[str]:
    """Las etiquetas marcadas en el formulario, filtradas por las que existen.

    Nada se crea desde aquí. Lo que llegue y no esté en el registro de la
    cuenta se descarta: la pantalla solo enseña casillas, y el servidor no se
    fía de eso, porque un formulario se puede escribir a mano.
    """
    marcadas = set(request.form.getlist("tags"))
    return [tag for tag in accounts.tags_of(account) if tag in marcadas]


def shared(db, account, **extra):
    """What every contacts screen needs: the counter and the tabs."""
    # Dos números distintos a propósito: los que hay, y los que ocupan sitio.
    # Un anulado no puede recibir nada, así que no cuenta contra el límite.
    total = contacts.count(db, account["_id"])
    active = contacts.active_count(db, account["_id"])
    limit = accounts.contact_limit(account)
    return {
        "account": account, "total": total, "active": active, "limit": limit,
        "blocked_total": total - active,
        "left": max(0, limit - active),
        "suppressed_total": suppressions.count(db, account["_id"]),
        # Las de un dominio que no recibe correo: se ven en la lista y se
        # borran de una vez (`services/address_check.py`).
        "invalid_total": contacts.invalid_count(db, account["_id"]),
        # Los que no tienen todas sus columnas llenas. No reciben correos, así
        # que la cifra va donde se cuentan los contactos y no escondida.
        "incomplete_total": contacts.incomplete_count(
            db, account["_id"], accounts.fields_of(account)),
        # Cuántas columnas más caben en el plan. Con cero, el botón de agregar
        # sale apagado.
        "field_room": (accounts.field_limit(account)
                       - len(accounts.fields_of(account))),
        # Del registro de la cuenta y no de los contactos: así una etiqueta
        # recién creada aparece desde ese momento, aunque no tenga a nadie.
        "tags": accounts.tags_of(account),
        # Lo mismo con las columnas propias: se crean antes de usarse.
        "fields": accounts.fields_of(account),
        # Para dibujar cada valor como se escribe y saber a quién le falta uno.
        "show": columns.show,
        "values_of": columns.values_of,
        "missing": columns.missing,
        # El tope del plan lo miran dos pantallas: la de columnas y la de
        # importar, que es donde se pueden crear de golpe.
        "field_limit": accounts.field_limit(account),
        **extra,
    }


# ------------------------------------------------------------------- the list

@bp.route("/contacts")
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    search = request.args.get("q", "").strip()[:120]
    tag = request.args.get("tag", "").strip()[:40]
    invalid_only = request.args.get("estado") == "invalidas"
    try:
        skip = max(0, int(request.args.get("since", "0")))
    except ValueError:
        skip = 0

    # Los anulados no salen: la consulta los deja fuera, así que esta pantalla
    # ya no tiene que preguntar cuáles lo están.
    found, matching = contacts.page(db, account["_id"], search=search, tag=tag,
                                    limit=PER_PAGE, skip=skip,
                                    invalid_only=invalid_only)

    return render_template(
        "contacts/list.html", section="lista",
        **shared(db, account, rows=found, matching=matching,
                 search=search, tag=tag, skip=skip, per_page=PER_PAGE,
                 invalid_only=invalid_only))


@bp.route("/contacts/new", methods=["GET", "POST"])
def add_one():
    """Agregar un contacto a mano, en su propia pantalla.

    Vive aparte de la lista porque desde la lista se llega con un botón, y
    porque un formulario colgando del final de una tabla de cincuenta filas no
    lo encuentra nadie.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}

    if request.method == "POST":
        address = importer.clean(request.form.get("email", ""))
        source = request.form.get("source", "")

        written = values_written(account, errors)

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not address:
            errors["email"] = t("error_contact_email")
        elif not address_check.domain_receives(address_check.domain_of(address)):
            errors["email"] = t("contacts_undeliverable",
                                domain=address_check.domain_of(address))
        elif source not in contacts.SOURCES:
            errors["source"] = t("error_required")
        elif contacts.active_count(db, account["_id"]) >= accounts.contact_limit(account):
            errors["form"] = t("error_contacts_full")
        elif errors:
            # Le falta alguna columna. Cada una dice lo suyo debajo del campo.
            errors["form"] = t("error_fields_required")
        else:
            contacts.create(
                db, account["_id"], email=address,
                name=request.form.get("name", "").strip(),
                tags=tags_chosen(account),
                values=written,
                consent=contacts.consent_of(source,
                                            request.form.get("note", "")))
            # Si esa dirección está anulada, se guarda igual pero no va a
            # recibir nada: mejor decirlo ahora que dejarlo descubrir.
            if suppressions.has(db, account["_id"], address):
                return redirect(url_for("contacts.index", suppressed=1))
            return redirect(url_for("contacts.index", saved=1))

    return render_template("contacts/new.html", section="lista", errors=errors,
                           **shared(db, account, sources=contacts.SOURCES))


@bp.route("/contacts/edit/<raw>", methods=["GET", "POST"])
def edit(raw):
    """Cambiar la dirección, el nombre y las etiquetas de un contacto.

    Existe para lo que antes obligaba a borrar y volver a crear: un nombre mal
    escrito, una dirección a la que le falta una letra. Borrarlo y rehacerlo
    perdía cuándo entró, por dónde y qué origen se declaró.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    contact_id = as_id(raw)
    row = contacts.by_id(db, account["_id"], contact_id) if contact_id else None
    if row is None:
        abort(404)

    errors: dict[str, str] = {}
    if request.method == "POST":
        address = importer.clean(request.form.get("email", ""))
        written = values_written(account, errors)

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not address:
            errors["email"] = t("error_contact_email")
        elif errors:
            errors["form"] = t("error_fields_required")
        elif not contacts.update(db, account["_id"], contact_id, email=address,
                                 name=request.form.get("name", ""),
                                 tags=tags_chosen(account),
                                 values=written):
            # Lo dice el índice único, no una consulta previa.
            errors["email"] = t("error_contact_taken")
        else:
            return redirect(url_for("contacts.index", saved=1))
        row = contacts.by_id(db, account["_id"], contact_id)

    return render_template("contacts/edit.html", section="lista", errors=errors,
                           row=row, chosen=row.get("tags") or [],
                           written=columns.values_of(row),
                           **shared(db, account))


@bp.route("/contacts/delete/<raw>")
def remove_ask(raw):
    """Antes de borrar uno, la pantalla que pregunta. No borra nada: el que
    borra es el POST. Es fácil pulsar Eliminar sin querer en una lista larga."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    contact_id = as_id(raw)
    row = contacts.by_id(db, account["_id"], contact_id) if contact_id else None
    if row is None:
        abort(404)
    return render_template("contacts/remove.html", section="lista", going=1,
                           rows=[row], action=url_for("contacts.remove"),
                           back=request.referrer or url_for("contacts.index"),
                           **shared(db, account))


@bp.route("/contacts/delete", methods=["POST"])
def remove():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        # Its suppression, if it has one, is not touched. That is rule 2, and
        # it is what stops "delete and re-upload" from being a way around a
        # baja somebody asked for.
        contacts.delete(get_db(), account["_id"], request.form.get("email", ""))
    return redirect(request.form.get("volver") or url_for("contacts.index"))


@bp.route("/contacts/invalid/delete", methods=["GET", "POST"])
def remove_invalid():
    """Borrar de una vez los contactos con una dirección inválida (de un dominio
    que no recibe correo). El GET dice cuántos y pregunta; el POST borra."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    if request.method == "GET":
        db = get_db()
        context = shared(db, account)
        return render_template(
            "contacts/remove.html", section="lista",
            going=context["invalid_total"], rows=[], blocked=False,
            action=url_for("contacts.remove_invalid"),
            back=url_for("contacts.index", estado="invalidas"), **context)

    if csrf_ok(request.form.get("csrf_token")):
        contacts.delete_invalid(get_db(), account["_id"])
    return redirect(url_for("contacts.index", saved=1))


@bp.route("/contacts/suppressed/delete", methods=["GET", "POST"])
def remove_suppressed():
    """Borrar los contactos anulados. Las supresiones se quedan.

    El GET es la pantalla que dice cuántos se van y pregunta; el POST borra.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    if request.method == "GET":
        db = get_db()
        context = shared(db, account)
        return render_template(
            "contacts/remove.html", section="supresiones",
            going=context["blocked_total"], rows=[], blocked=True,
            action=url_for("contacts.remove_suppressed"),
            back=url_for("contacts.blocked"), **context)

    if csrf_ok(request.form.get("csrf_token")):
        contacts.delete_suppressed(get_db(), account["_id"])
    return redirect(url_for("contacts.index"))


def csv_lines(account, rows, blocked):
    """Los contactos como CSV, fila por fila: punto y coma y marca de orden de
    bytes, que es lo que abre Excel en español y lo que nuestro importador
    lee. Lo usa Exportar."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

    def flush():
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    # Las columnas propias salen al final y con su nombre: así el
    # archivo que baja se puede volver a subir y el importador las reconoce
    # por el título, que es lo que hace que exportar sirva de copia.
    mine = accounts.fields_of(account)

    yield "\ufeff"
    writer.writerow([t("contacts_col_email"), t("contacts_col_name"),
                     t("contacts_col_tags"), t("contacts_col_how"),
                     t("contacts_col_added"), t("contacts_col_status")]
                    + [one["label"] for one in mine])
    yield flush()
    for row in rows:
        how = row.get("added_by")
        writer.writerow([
            row.get("email", ""),
            row.get("name", ""),
            ", ".join(row.get("tags") or []),
            t("contacts_how_" + how) if how else "",
            (row.get("created_at").date().isoformat()
             if row.get("created_at") else ""),
            t("contacts_status_blocked")
            if row["email_normalized"] in blocked
            else t("contacts_status_active"),
            *[columns.show(columns.values_of(row).get(one["key"], ""),
                           one.get("type", columns.TEXT))
              for one in mine],
        ])
        yield flush()


@bp.route("/contacts/export", methods=["GET", "POST"])
def export():
    """Bajar lo que enseña la tabla, respetando el buscador y el filtro.

    El GET no descarga nada: enseña cuántos van a salir y con qué filtro, y el
    POST es el que escribe el archivo. Antes bajaba de golpe y no había forma de
    saber, mirando el archivo, si el filtro que uno creía puesto lo estaba.

    Punto y coma y marca de orden de bytes: es lo que abre Excel en español sin
    meter todo en una columna, y es lo que nuestro propio importador lee. Y se
    escribe fila por fila, no armando el archivo entero en memoria.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    # El filtro viaja igual por los dos lados: en la dirección al llegar, y en
    # campos escondidos al confirmar.
    source = request.form if request.method == "POST" else request.args
    search = source.get("q", "").strip()[:120]
    tag = source.get("tag", "").strip()[:accounts.TAG_LENGTH]

    if request.method == "GET" or not csrf_ok(request.form.get("csrf_token")):
        return render_template(
            "contacts/export.html", section="lista",
            **shared(db, account, search=search, tag=tag,
                     going=contacts.matching_count(db, account["_id"],
                                                   search=search, tag=tag)))

    rows = contacts.all_of(db, account["_id"], search=search, tag=tag)
    blocked = {d["email_normalized"] for d in
               db.suppressions.find({"account_id": account["_id"]},
                                    {"email_normalized": 1})}

    name = f"contactos-{date.today().isoformat()}.csv"
    # mimetype y no content_type: Flask le añade el charset, y ponerlo aquí
    # además lo dejaba escrito dos veces en la cabecera.
    return Response(csv_lines(account, rows, blocked), mimetype="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="{name}"'})


# ------------------------------------------------------------- las etiquetas

@bp.route("/contacts/tags")
def tags():
    """Las etiquetas de la cuenta, con cuántos contactos lleva cada una.

    Existen aquí y no dentro de los contactos: por eso una recién creada ya se
    puede elegir, aunque todavía no tenga a nadie.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    return render_template(
        "contacts/tags.html", section="etiquetas",
        **shared(db, account, counts=contacts.count_by_tag(db, account["_id"]),
                 room=accounts.tag_limit(account) - len(accounts.tags_of(account)),
                 tag_limit=accounts.tag_limit(account),
                 tags_free=accounts.tag_limit(account) >= plans.UNLIMITED))


@bp.route("/contacts/tags/new", methods=["POST"])
def add_tag():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        if not accounts.add_tag(get_db(), account["_id"],
                                request.form.get("tag", "")):
            return redirect(url_for("contacts.tags", error="tag"))
    return redirect(url_for("contacts.tags", saved=1))


@bp.route("/contacts/tags/delete", methods=["POST"])
def drop_tag():
    """Borrar una etiqueta: sale del registro y de los contactos que la
    llevaban. Los contactos se quedan."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        db = get_db()
        tag = request.form.get("tag", "").strip()[:accounts.TAG_LENGTH]
        accounts.remove_tag(db, account["_id"], tag)
        contacts.drop_tag(db, account["_id"], tag)
    return redirect(url_for("contacts.tags"))


# ------------------------------------------- las columnas propias del contacto

@bp.route("/contacts/columns")
def fields():
    """Las columnas que esta cuenta guarda de cada contacto.

    Existen aquí y no deducidas de los contactos, como las etiquetas: una
    recién creada ya se puede usar en una pieza aunque nadie tenga ese dato
    escrito todavía.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    limit = accounts.field_limit(account)
    return render_template(
        "contacts/fields.html", section="columnas",
        **shared(db, account, types=columns.TYPES,
                 room=limit - len(accounts.fields_of(account)),
                 fields_free=limit >= plans.UNLIMITED,
                 counts=contacts.count_by_field(
                     db, account["_id"], accounts.fields_of(account))))


@bp.route("/contacts/columns/new", methods=["GET", "POST"])
def add_field():
    """Crear una columna, en su propia pantalla.

    Se llega desde la lista de contactos, que es donde se está cuando hace
    falta una columna más. Antes se creaba desde la pestaña de columnas, que es
    a donde se va a corregir lo que ya existe, no a empezar algo.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}
    limit = accounts.field_limit(account)
    room = limit - len(accounts.fields_of(account))

    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif room <= 0:
            # Se comprueba aquí y no solo en el botón: apagar un botón no es un
            # permiso.
            errors["form"] = t("fields_full")
        elif not accounts.add_field(db, account["_id"],
                                    label=request.form.get("nombre", ""),
                                    kind=request.form.get("type", "")):
            errors["nombre"] = t("error_field")
        else:
            return redirect(url_for("contacts.fields", saved=1))

    return render_template(
        "contacts/field-new.html", section="columnas", errors=errors,
        **shared(db, account, types=columns.TYPES, room=room,
                 field_limit=limit,
                 fields_free=limit >= plans.UNLIMITED))


@bp.route("/contacts/columns/type", methods=["POST"])
def field_type():
    """Cambiarle el tipo a una columna que ya existe.

    Lo único que se puede corregir: el nombre es lo que se escribe dentro de
    las piezas, y cambiarlo dejaría a las que la nombran escribiendo en blanco.

    **No se cambia si hay valores que no encajan** en el tipo nuevo —«Santiago»
    en una que pasa a número—: se dice cuántos son y no se toca nada, porque
    guardar un valor que después no se puede enseñar es perderlo en silencio.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("contacts.fields"))

    db = get_db()
    key = request.form.get("columna", "").strip()[:columns.KEY_MAX]
    kind = columns.clean_kind(request.form.get("type", ""))
    one = accounts.field_by_key(account, key)
    if one is None:
        return redirect(url_for("contacts.fields"))

    wrong = contacts.values_not_of_type(db, account["_id"], key, kind)
    if wrong:
        return redirect(url_for("contacts.fields", error="type", n=wrong))
    accounts.set_field_type(db, account["_id"], key, kind)
    return redirect(url_for("contacts.fields", saved=1))


@bp.route("/contacts/columns/delete", methods=["POST"])
def drop_field():
    """Borrar una columna: sale del registro y de los contactos que la tenían
    escrita. Los contactos se quedan, y las piezas que la nombraban dejan de
    escribir nada en ese sitio."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        db = get_db()
        key = request.form.get("columna", "").strip()[:columns.KEY_MAX]
        accounts.remove_field(db, account["_id"], key)
        contacts.drop_field(db, account["_id"], key)
    return redirect(url_for("contacts.fields"))


# ------------------------------------------------------------- the importer

def chosen_columns(db, account, head: list[str]):
    """Qué columna del archivo se guarda en qué columna de la cuenta.

    **El archivo no manda.** Uno de quince columnas se acepta igual; lo que
    cuenta contra el plan es lo que el cliente marque, y eso es lo que se
    comprueba aquí. Devuelve (mapa, error).

    Sin JavaScript la pantalla no dibuja el mapeo y no llega ninguna elección:
    entonces se hace por título, contra las columnas que esa cuenta ya tiene.
    Nada se crea así, porque crear una columna es una decisión y no un efecto
    secundario de subir un archivo.
    """
    marked = {index: request.form.get(f"columna-{index}", "").strip()
              for index in range(len(head))}
    marked = {i: what for i, what in marked.items() if what}
    if not marked:
        return importer.matching(head, accounts.fields_of(account)), None

    existing = accounts.fields_of(account)
    limit = accounts.field_limit(account)
    fresh = [i for i, what in marked.items() if what == NEW_COLUMN]
    if len(existing) + len(fresh) > limit:
        return {}, t("error_fields_full", n=limit)

    for index in fresh:
        # El título del archivo es el nombre de la columna. El tipo lo eligió
        # la pantalla al lado.
        if not accounts.add_field(db, account["_id"], label=head[index],
                                  kind=request.form.get(f"tipo-{index}", "")):
            return {}, t("error_field")

    account = accounts.by_id(db, account["_id"])
    known = {one["key"]: one for one in accounts.fields_of(account)}
    take: dict[int, dict] = {}
    for index, what in marked.items():
        key = (columns.key_from(head[index]) if what == NEW_COLUMN else what)
        one = known.get(key)
        # Una clave que no existe se ignora en vez de romper la importación:
        # el formulario se puede escribir a mano.
        if one is not None:
            take[index] = one
    return take, None


@bp.route("/contacts/import", methods=["GET", "POST"])
def upload():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}
    result = None

    if request.method == "POST":
        archivo = request.files.get("archivo")
        source = request.form.get("source", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif (imports.running(db, account["_id"])
              or locks.held(db, f"contacts:{account['_id']}")):
            # One at a time per account: two files landing at once would race
            # each other for the same room under the limit. Also a load from
            # the API (octubre de 2026), which takes the same lock.
            errors["form"] = t("error_import_running")
        elif imports.today(db, account["_id"]) >= Config.IMPORTS_PER_DAY:
            errors["form"] = t("error_import_too_many", n=Config.IMPORTS_PER_DAY)
        elif not archivo or not archivo.filename:
            errors["archivo"] = t("error_required")
        elif source not in contacts.SOURCES:
            # Asked before anything is written, because it cannot be filled in
            # afterwards: a list imported without an origin has none, ever.
            errors["source"] = t("error_required")
        else:
            consent = contacts.consent_of(source, request.form.get("note", ""))
            tags = tags_chosen(account)
            # El archivo se lee dos veces: la primera solo los títulos, para
            # saber qué columna es cuál, y la segunda es la que escribe.
            head = importer.header_of(archivo.stream)
            archivo.stream.seek(0)
            take, wrong = chosen_columns(db, account, head)

            if wrong:
                errors["form"] = wrong
                return render_template(
                    "contacts/import.html", section="importar", errors=errors,
                    result=None,
                    **shared(db, account, sources=contacts.SOURCES,
                             history=imports.for_account(db, account["_id"]),
                             per_day=Config.IMPORTS_PER_DAY,
                             new_column=NEW_COLUMN, types=columns.TYPES,
                             known_headers=KNOWN_HEADERS,
                             max_mb=Config.IMPORT_MAX_BYTES // (1024 * 1024)))

            job = imports.start(db, account["_id"], filename=archivo.filename,
                                tags=tags, consent=consent)
            try:
                counts, stopped = importer.run(
                    db, account["_id"], archivo.stream, tags=tags,
                    consent=consent, limit=accounts.contact_limit(account),
                    take=take, required=accounts.fields_of(account))
            except Exception as exc:  # noqa: BLE001 - written down, not hidden
                imports.finish(db, job, status=imports.FAILED, counts={},
                               error=f"{type(exc).__name__}: {exc}")
                log_auth(db, events.IMPORT, events.FAILED,
                         email=account["email"], account_id=account["_id"])
                errors["form"] = t("error_import_unreadable")
            else:
                imports.finish(db, job,
                               status=imports.STOPPED if stopped else imports.DONE,
                               counts=counts)
                log_auth(db, events.IMPORT, events.OK, email=account["email"],
                         account_id=account["_id"])
                result = {"counts": counts, "stopped": stopped}

    return render_template(
        "contacts/import.html", section="importar", errors=errors, result=result,
        **shared(db, account, sources=contacts.SOURCES,
                 history=imports.for_account(db, account["_id"]),
                 per_day=Config.IMPORTS_PER_DAY,
                 new_column=NEW_COLUMN, types=columns.TYPES,
                 known_headers=KNOWN_HEADERS,
                 max_mb=Config.IMPORT_MAX_BYTES // (1024 * 1024)))


# ---------------------------------------------------------- the suppressions

@bp.route("/contacts/suppressions")
def blocked():
    """Las direcciones a las que esta cuenta ya no le escribe, y por qué.

    Solo para mirar (octubre de 2026): aquí entran solas, por la baja, el
    rebote permanente o la queja, y no se ponen ni se quitan a mano. Para
    dejar de escribirle a alguien se borra el contacto.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    return render_template(
        "contacts/suppressions.html", section="supresiones",
        **shared(db, account, rows=suppressions.for_account(db, account["_id"])))
