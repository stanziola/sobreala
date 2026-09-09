"""El panel de administración: aprobar cuentas y mirar cómo va cada cliente.

Un blueprint con verificación de rol dentro de la misma aplicación, no un
programa aparte: comparte los modelos, el inicio de sesión y el doble factor con
todo lo demás. Una aplicación separada sería una segunda puerta a la misma base
de datos, con su propia autenticación que proteger.

Dos decisiones que se notan en todo el archivo:

  * **Quien no es administrador recibe un 404**, no un «no tienes permiso». Un
    403 le confirma a un curioso que la dirección existe; un 404 no le dice
    nada.
  * **La ficha de un cliente enseña cifras y orígenes, nunca la lista de
    direcciones de sus contactos.** Esa lista es de él y de las personas que
    están en ella; se mira por un motivo concreto, no hojeando.
"""

from __future__ import annotations

from functools import wraps

from bson.errors import InvalidId
from bson import ObjectId
from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for)

from blueprints.auth.routes import current_account
from db import get_db
from models import account as accounts
from models import admin_event as decisions
from models import auth_event as events
from models import contact as contacts
from models import import_job as imports
from models import session as sessions
from models import suppression as suppressions
from services.security import csrf_ok

bp = Blueprint("admin", __name__, url_prefix="/admin")

PER_PAGE = 100


def only_admins(view):
    """La puerta. Todas las rutas de aquí pasan por ella.

    Sin sesión se va a entrar, como en cualquier otra pantalla. Con sesión pero
    sin rol, 404. Y con rol pero sin doble factor, a activarlo primero: es la
    cuenta que puede aprobar, suspender y leer las cifras de todos los
    clientes, y una contraseña sola es poco para eso.
    """
    @wraps(view)
    def guarded(*args, **kwargs):
        account = current_account()
        if account is None:
            return redirect(url_for("auth.login"))
        if not accounts.is_admin(account):
            abort(404)
        if not accounts.two_factor_on(account):
            return redirect(url_for("auth.two_factor", admin=1))
        return view(*args, account=account, **kwargs)
    return guarded


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def wanted(raw):
    """La cuenta que pide la dirección, o 404 si no existe."""
    account_id = as_id(raw)
    found = accounts.by_id(get_db(), account_id) if account_id else None
    if found is None:
        abort(404)
    return found


# --------------------------------------------------------------- la portada

@bp.route("/")
@only_admins
def home(account):
    db = get_db()
    counted = accounts.by_status(db)
    # Lo primero de la pantalla es lo único que pide acción: quien espera
    # aprobación desde hace más tiempo, primero.
    waiting, _ = accounts.search(db, status=accounts.REGISTERED, limit=10)
    return render_template("admin/home.html", section="portada", admin=account,
                           counted=counted, waiting=waiting,
                           statuses=accounts.STATUSES,
                           decisions=decisions.latest(db, limit=10))


# ---------------------------------------------------------------- las cuentas

@bp.route("/cuentas")
@only_admins
def accounts_list(account):
    db = get_db()
    status = request.args.get("estado", "").strip()
    text = request.args.get("q", "").strip()[:120]
    try:
        skip = max(0, int(request.args.get("desde", "0")))
    except ValueError:
        skip = 0

    rows, total = accounts.search(db, status=status, text=text,
                                  limit=PER_PAGE, skip=skip)
    return render_template("admin/accounts.html", section="cuentas",
                           admin=account, rows=rows, total=total, status=status,
                           search=text, skip=skip, per_page=PER_PAGE,
                           statuses=accounts.STATUSES)


@bp.route("/cuentas/<raw>")
@only_admins
def account_page(account, raw):
    db = get_db()
    client = wanted(raw)
    return render_template(
        "admin/account.html", section="cuentas", admin=account, client=client,
        statuses=accounts.STATUSES, plans=sorted(accounts.PLAN_CONTACTS),
        limit=accounts.contact_limit(client),
        # Cifras y orígenes. Las direcciones de sus contactos no se listan.
        contacts_total=contacts.count(db, client["_id"]),
        suppressed_total=suppressions.count(db, client["_id"]),
        tags=contacts.tags_of(db, client["_id"]),
        history=imports.for_account(db, client["_id"], limit=20),
        devices=sessions.for_account(db, client["_id"]),
        decisions=decisions.for_account(db, client["_id"]),
        describe=sessions.describe,
        sources=contacts.SOURCES)


@bp.route("/cuentas/<raw>/estado", methods=["POST"])
@only_admins
def change_status(account, raw):
    """Mover una cuenta de estado, con el motivo escrito.

    El motivo no es papeleo: meses después, la única respuesta honesta a «por
    qué me suspendieron» es lo que se escribió el día que se hizo.
    """
    db = get_db()
    client = wanted(raw)
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("admin.account_page", raw=raw))

    status = request.form.get("estado", "")
    reason = request.form.get("motivo", "").strip()
    if not reason:
        return redirect(url_for("admin.account_page", raw=raw, falta="motivo"))

    before = accounts.set_status(db, client["_id"], status)
    if before is None:
        return redirect(url_for("admin.account_page", raw=raw))

    decisions.record(db, kind=decisions.STATUS, admin_id=account["_id"],
                     account_id=client["_id"], before=before, after=status,
                     reason=reason)
    # Suspender cierra lo que esté abierto: si no, quien ya estaba dentro
    # sigue dentro hasta que se le ocurra salir.
    if status == accounts.SUSPENDED:
        sessions.revoke_others(db, client["_id"])
    return redirect(url_for("admin.account_page", raw=raw, hecho=1))


@bp.route("/cuentas/<raw>/plan", methods=["POST"])
@only_admins
def change_plan(account, raw):
    """Poner o quitar el plan. Es lo que enciende el límite de contactos."""
    db = get_db()
    client = wanted(raw)
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("admin.account_page", raw=raw))

    plan = request.form.get("plan", "") or None
    reason = request.form.get("motivo", "").strip()
    if not reason:
        return redirect(url_for("admin.account_page", raw=raw, falta="motivo"))

    before = accounts.set_plan(db, client["_id"], plan)
    if before is None and (client.get("plan") or None) == plan:
        return redirect(url_for("admin.account_page", raw=raw))

    decisions.record(db, kind=decisions.PLAN, admin_id=account["_id"],
                     account_id=client["_id"], before=before, after=plan,
                     reason=reason)
    return redirect(url_for("admin.account_page", raw=raw, hecho=1))
