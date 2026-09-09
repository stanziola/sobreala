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

from flask import Blueprint, redirect, render_template, request, url_for

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
from services.security import csrf_ok

bp = Blueprint("contacts", __name__)

# How many rows one screen of the list shows.
PER_PAGE = 50


def signed_in():
    """The account behind this request, or None. Every route starts here."""
    return current_account()


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
    total = contacts.count(db, account["_id"])
    limit = accounts.contact_limit(account)
    return {
        "account": account, "total": total, "limit": limit,
        "left": max(0, limit - total),
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
        elif contacts.count(db, account["_id"]) >= accounts.contact_limit(account):
            errors["form"] = t("error_contacts_full")
        else:
            contacts.create(
                db, account["_id"], email=address,
                name=request.form.get("name", "").strip(),
                tags=tags_chosen(account),
                consent=contacts.consent_of(source,
                                            request.form.get("note", "")))
            return redirect(url_for("contacts.index", guardado=1))

    return render_template("contacts/new.html", section="lista", errors=errors,
                           **shared(db, account, sources=contacts.SOURCES))


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
                 room=accounts.TAGS_MAX - len(accounts.tags_of(account))))


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
