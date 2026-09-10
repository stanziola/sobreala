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
from flask import (Blueprint, Response, abort, redirect, render_template,
                   request, url_for)

from blueprints.auth.routes import current_account
from db import get_db
from models import account as accounts
from models import admin_event as decisions
from models import auth_event as events
from models import contact as contacts
from models import design as designs
from models import import_job as imports
from models import payment as payments
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


# Lo que se enseña de auth_events en la actividad de una cuenta. Fuera quedan
# los reenvíos y los ajustes: llenan la línea de tiempo sin contar nada de lo
# que uno viene a mirar.
SHOWN = (events.LOGIN, events.LOGOUT, events.REGISTER, events.CONFIRM,
         events.PASSWORD_CHANGE, events.RECOVER, events.CORRECT_EMAIL,
         events.TWO_FACTOR, events.SESSION_CLOSED)


def activity(db, client) -> list[dict]:
    """Lo que hizo la cuenta y lo que se decidió sobre ella, en una sola línea
    de tiempo.

    Cuatro colecciones que ya existían y que hasta ahora se miraban por
    separado: entradas, importaciones, pagos y decisiones. Se juntan aquí y no
    en la plantilla porque lo que ordena es la fecha, no de dónde salió cada
    cosa.

    Las direcciones de sus contactos siguen sin aparecer: se enseña que importó
    un archivo y cuántos entraron, no quiénes.
    """
    rows: list[dict] = []

    for row in events.for_account(db, client["_id"], kinds=SHOWN, limit=40):
        rows.append({"at": row["created_at"], "type": "auth", "row": row})
    for job in imports.for_account(db, client["_id"], limit=20):
        rows.append({"at": job["created_at"], "type": "import", "row": job})
    for paid in payments.for_account(db, client["_id"], limit=20):
        rows.append({"at": paid["created_at"], "type": "payment", "row": paid})
    for taken in decisions.for_account(db, client["_id"]):
        rows.append({"at": taken["created_at"], "type": "decision", "row": taken})

    rows.sort(key=lambda entry: entry["at"], reverse=True)
    return rows[:60]


# --------------------------------------------------------------- la portada

@bp.route("/")
@only_admins
def home(account):
    db = get_db()
    counted = accounts.by_status(db)
    # Lo primero de la pantalla es lo único que pide acción: quien espera
    # aprobación desde hace más tiempo, primero.
    waiting, _ = accounts.search(db, status=accounts.REGISTERED, limit=10)
    latest = decisions.latest(db, limit=10)
    return render_template("admin/home.html", section="portada", admin=account,
                           counted=counted, waiting=waiting,
                           statuses=accounts.STATUSES, decisions=latest,
                           # De qué cuenta es cada decisión. Sin esto hay que
                           # abrirlas una a una para saberlo, y se resuelven en
                           # una sola consulta, no una por fila.
                           named=accounts.names_of(
                               db, [row["account_id"] for row in latest]))


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
        tags=accounts.tags_of(client),
        history=imports.for_account(db, client["_id"], limit=20),
        devices=sessions.for_account(db, client["_id"]),
        activity=activity(db, client),
        describe=sessions.describe,
        sources=contacts.SOURCES)


@bp.route("/cuentas/<raw>/actualizar", methods=["POST"])
@only_admins
def update(account, raw):
    """Estado y plan en un solo envío, con el motivo escrito.

    Eran dos formularios con dos botones, y quien aprobaba una cuenta y le
    ponía el plan tenía que escribir el mismo motivo dos veces. Ahora es una
    decisión —«qué hago con esta cuenta»— y `admin_events` sigue guardando una
    línea por cosa cambiada, que es lo que la hace legible meses después.

    El motivo no es papeleo: la única respuesta honesta a «por qué me
    suspendieron» es lo que se escribió el día que se hizo.
    """
    db = get_db()
    client = wanted(raw)
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("admin.account_page", raw=raw))

    status = request.form.get("estado", "")
    plan = request.form.get("plan", "") or None
    reason = request.form.get("motivo", "").strip()

    # Lo que no es un estado o un plan de verdad no cambia nada y tampoco deja
    # una decisión escrita: escribir «pasó a xyz» sería mentir el registro.
    if status not in accounts.STATUSES:
        return redirect(url_for("admin.account_page", raw=raw))
    if plan is not None and plan not in accounts.PLAN_CONTACTS:
        return redirect(url_for("admin.account_page", raw=raw))

    new_status = status != client.get("status")
    new_plan = plan != (client.get("plan") or None)
    if not new_status and not new_plan:
        return redirect(url_for("admin.account_page", raw=raw))
    if not reason:
        return redirect(url_for("admin.account_page", raw=raw, falta="motivo"))

    if new_status:
        before = accounts.set_status(db, client["_id"], status)
        decisions.record(db, kind=decisions.STATUS, admin_id=account["_id"],
                         account_id=client["_id"], before=before, after=status,
                         reason=reason)
        # Suspender cierra lo que esté abierto: si no, quien ya estaba dentro
        # sigue dentro hasta que se le ocurra salir.
        if status == accounts.SUSPENDED:
            sessions.revoke_others(db, client["_id"])

    if new_plan:
        before = accounts.set_plan(db, client["_id"], plan)
        decisions.record(db, kind=decisions.PLAN, admin_id=account["_id"],
                         account_id=client["_id"], before=before, after=plan,
                         reason=reason)

    return redirect(url_for("admin.account_page", raw=raw, hecho=1))


# ---------------------------------------------------- las plantillas subidas

@bp.route("/plantillas")
@only_admins
def designs_queue(account):
    """Lo que espera revisión: la primera pieza de cada cliente.

    Después de esa, el cliente queda habilitado y las siguientes entran solas.
    Lo que se revisa la primera vez no es el archivo, es si esa organización
    sabe lo que está mandando.
    """
    db = get_db()
    rows = designs.waiting(db)
    return render_template(
        "admin/designs.html", section="plantillas", admin=account, rows=rows,
        named=accounts.names_of(db, [row["account_id"] for row in rows]))


@bp.route("/plantillas/<raw>/revisar", methods=["POST"])
@only_admins
def review_design(account, raw):
    """Aprobar o rechazar una. Rechazar pide motivo, igual que suspender."""
    design_id = as_id(raw)
    if not csrf_ok(request.form.get("csrf_token")) or design_id is None:
        return redirect(url_for("admin.designs_queue"))

    db = get_db()
    decision = request.form.get("decision", "")
    reason = request.form.get("motivo", "").strip()
    if decision == designs.REJECTED and not reason:
        return redirect(url_for("admin.designs_queue", falta="motivo"))

    designs.review(db, design_id, status=decision, reason=reason)
    return redirect(url_for("admin.designs_queue"))


@bp.route("/plantillas/<raw>/archivo")
@only_admins
def design_file(account, raw):
    """Bajar el HTML tal como lo subió el cliente, para poder mirarlo.

    Se descarga, no se dibuja: enseñarlo dentro del panel sería meter el
    documento de otro en una página nuestra con la sesión de administrador
    abierta. Y se sirve como texto plano, para que ni el navegador lo ejecute
    si alguien abre el archivo desde ahí.
    """
    design_id = as_id(raw)
    found = get_db().designs.find_one({"_id": design_id}) if design_id else None
    if found is None:
        abort(404)
    return Response(found["html"], mimetype="text/plain",
                    headers={"Content-Disposition":
                             f'attachment; filename="plantilla-{raw}.html"'})
