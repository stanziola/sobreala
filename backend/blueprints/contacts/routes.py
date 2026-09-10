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

from blueprints.auth.routes import current_account, log_auth
from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import auth_event as events
from models import contact as contacts
from models import import_job as imports
from models import suppression as suppressions
from services import importer
from services import plans
from services.security import csrf_ok

bp = Blueprint("contacts", __name__)

# How many rows one screen of the list shows.
PER_PAGE = 50


def signed_in():
    """The account behind this request, or None. Every route starts here."""
    return current_account()


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


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
        # Del registro de la cuenta y no de los contactos: así una etiqueta
        # recién creada aparece desde ese momento, aunque no tenga a nadie.
        "tags": accounts.tags_of(account),
        **extra,
    }


# ------------------------------------------------------------------- the list

@bp.route("/contactos")
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    search = request.args.get("q", "").strip()[:120]
    tag = request.args.get("etiqueta", "").strip()[:40]
    try:
        skip = max(0, int(request.args.get("desde", "0")))
    except ValueError:
        skip = 0

    found, matching = contacts.page(db, account["_id"], search=search, tag=tag,
                                    limit=PER_PAGE, skip=skip)
    # One question for the whole page, never one per row: rule 10.
    blocked = suppressions.among(db, account["_id"],
                                 [c["email_normalized"] for c in found])

    return render_template(
        "contacts/list.html", section="lista",
        **shared(db, account, rows=found, matching=matching, blocked=blocked,
                 search=search, tag=tag, skip=skip, per_page=PER_PAGE))


@bp.route("/contactos/nuevo", methods=["GET", "POST"])
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

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not address:
            errors["email"] = t("error_contact_email")
        elif source not in contacts.SOURCES:
            errors["source"] = t("error_required")
        elif contacts.active_count(db, account["_id"]) >= accounts.contact_limit(account):
            errors["form"] = t("error_contacts_full")
        else:
            contacts.create(
                db, account["_id"], email=address,
                name=request.form.get("name", "").strip(),
                tags=tags_chosen(account),
                consent=contacts.consent_of(source,
                                            request.form.get("note", "")))
            # Si esa dirección está anulada, se guarda igual pero no va a
            # recibir nada: mejor decirlo ahora que dejarlo descubrir.
            if suppressions.has(db, account["_id"], address):
                return redirect(url_for("contacts.index", anulado=1))
            return redirect(url_for("contacts.index", guardado=1))

    return render_template("contacts/new.html", section="lista", errors=errors,
                           **shared(db, account, sources=contacts.SOURCES))


@bp.route("/contactos/editar/<raw>", methods=["GET", "POST"])
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

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not address:
            errors["email"] = t("error_contact_email")
        elif not contacts.update(db, account["_id"], contact_id, email=address,
                                 name=request.form.get("name", ""),
                                 tags=tags_chosen(account)):
            # Lo dice el índice único, no una consulta previa.
            errors["email"] = t("error_contact_taken")
        else:
            return redirect(url_for("contacts.index", guardado=1))
        row = contacts.by_id(db, account["_id"], contact_id)

    return render_template("contacts/edit.html", section="lista", errors=errors,
                           row=row, chosen=row.get("tags") or [],
                           **shared(db, account))


@bp.route("/contactos/borrar", methods=["POST"])
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


@bp.route("/contactos/anulados/eliminar", methods=["POST"])
def remove_suppressed():
    """Borrar los contactos anulados. Las supresiones se quedan."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        contacts.delete_suppressed(get_db(), account["_id"])
    return redirect(url_for("contacts.index"))


@bp.route("/contactos/exportar", methods=["GET", "POST"])
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
    tag = source.get("etiqueta", "").strip()[:accounts.TAG_LENGTH]

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

    def lines():
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

        def flush():
            value = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return value

        yield "\ufeff"
        writer.writerow([t("contacts_col_email"), t("contacts_col_name"),
                         t("contacts_col_tags"), t("contacts_col_how"),
                         t("contacts_col_added"), t("contacts_col_status")])
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
            ])
            yield flush()

    name = f"contactos-{date.today().isoformat()}.csv"
    # mimetype y no content_type: Flask le añade el charset, y ponerlo aquí
    # además lo dejaba escrito dos veces en la cabecera.
    return Response(lines(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="{name}"'})


# ------------------------------------------------------------- las etiquetas

@bp.route("/contactos/etiquetas")
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


@bp.route("/contactos/etiquetas/nueva", methods=["POST"])
def add_tag():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        if not accounts.add_tag(get_db(), account["_id"],
                                request.form.get("etiqueta", "")):
            return redirect(url_for("contacts.tags", error="etiqueta"))
    return redirect(url_for("contacts.tags", guardado=1))


@bp.route("/contactos/etiquetas/borrar", methods=["POST"])
def drop_tag():
    """Borrar una etiqueta: sale del registro y de los contactos que la
    llevaban. Los contactos se quedan."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        db = get_db()
        tag = request.form.get("etiqueta", "").strip()[:accounts.TAG_LENGTH]
        accounts.remove_tag(db, account["_id"], tag)
        contacts.drop_tag(db, account["_id"], tag)
    return redirect(url_for("contacts.tags"))


# ------------------------------------------------------------- the importer

@bp.route("/contactos/importar", methods=["GET", "POST"])
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
        elif imports.running(db, account["_id"]):
            # One at a time per account: two files landing at once would race
            # each other for the same room under the limit.
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
            job = imports.start(db, account["_id"], filename=archivo.filename,
                                tags=tags, consent=consent)
            try:
                counts, stopped = importer.run(
                    db, account["_id"], archivo.stream, tags=tags,
                    consent=consent, limit=accounts.contact_limit(account))
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
                 max_mb=Config.IMPORT_MAX_BYTES // (1024 * 1024)))


# ---------------------------------------------------------- the suppressions

@bp.route("/contactos/supresiones")
def blocked():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    return render_template(
        "contacts/suppressions.html", section="supresiones",
        **shared(db, account, rows=suppressions.for_account(db, account["_id"]),
                 liftable=suppressions.LIFTABLE))


@bp.route("/contactos/supresiones/anadir", methods=["POST"])
def block():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        address = importer.clean(request.form.get("email", ""))
        if not address:
            return redirect(url_for("contacts.blocked", error="correo"))
        suppressions.add(get_db(), account["_id"], address,
                         reason=suppressions.MANUAL, source="panel")
    return redirect(url_for("contacts.blocked", guardado=1))


@bp.route("/contactos/supresiones/quitar", methods=["POST"])
def unblock():
    """Only what the client put there by hand comes off.

    A bounce or a complaint is a fact about the address, not a preference, and
    models/suppression.py refuses the others rather than trusting this form.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        suppressions.lift(get_db(), account["_id"],
                          request.form.get("email", ""))
    return redirect(url_for("contacts.blocked"))
