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
from i18n import t
from models import account as accounts
from models import admin_event as decisions
from models import auth_event as events
from models import campaign_run as sendings
from models import contact as contacts
from models import design as designs
from models import import_job as imports
from models import invoice as invoices
from models import mail_log
from models import payment as payments
from models import session as sessions
from models import suppression as suppressions
from services import notices
from services import plans
from services import stats
from services.security import csrf_ok

bp = Blueprint("admin", __name__, url_prefix="/admin")

PER_PAGE = 100

# El valor que toma el filtro de estado cuando lo que se quiere ver es la cola
# de habilitación. No es un estado de la cuenta, así que no puede estar en
# STATUSES; es una vista más de la misma lista.
PENDING_FILTER = "sin-habilitar"


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


# Las cinco fuentes de la línea de tiempo. La clave es lo que viaja en la
# dirección —en español, como el resto de los filtros— y el valor es el tipo
# que dibuja la plantilla.
KINDS = {
    "entradas": "auth",
    "pagos": "payment",
    "correos": "campaign",
    "contactos": "import",
    "decisiones": "decision",
}

# Cuántas líneas se enseñan.
TIMELINE = 60


def activity(db, client, *, only: str = "") -> list[dict]:
    """Lo que hizo la cuenta y lo que se decidió sobre ella, en una sola línea
    de tiempo.

    Cinco colecciones que ya existían y que por separado no cuentan nada:
    entradas, importaciones, pagos, campañas y decisiones. Se juntan aquí y no
    en la plantilla porque lo que ordena es la fecha, no de dónde salió cada
    cosa.

    **Filtrar es preguntar de nuevo, no esconder filas.** De la mezcla se
    guardan las sesenta más recientes, así que quedarse después con los pagos
    enseñaría los pocos que sobrevivieron a ella; pidiendo una sola fuente, esa
    fuente se lleva el sitio entero.

    Las direcciones de sus contactos siguen sin aparecer: se enseña que importó
    un archivo y cuántos entraron, o que mandó una campaña y cuántos salieron,
    nunca a quiénes.
    """
    account_id = client["_id"]
    want = KINDS.get(only, "")

    def room(default: int) -> int:
        return TIMELINE if want else default

    rows: list[dict] = []
    if want in ("", "auth"):
        for row in events.for_account(db, account_id, kinds=SHOWN,
                                      limit=room(40)):
            rows.append({"at": row["created_at"], "type": "auth", "row": row})
    if want in ("", "import"):
        for job in imports.for_account(db, account_id, limit=room(20)):
            rows.append({"at": job["created_at"], "type": "import", "row": job})
    if want in ("", "payment"):
        for paid in payments.for_account(db, account_id, limit=room(20)):
            rows.append({"at": paid["created_at"], "type": "payment",
                         "row": paid})
    if want in ("", "campaign"):
        # Una línea por envío y no por campaña: la que se manda cada mes no es
        # una cosa que pasó una vez.
        for one in sendings.for_account(db, account_id, limit=room(20)):
            rows.append({"at": one["finished_at"], "type": "campaign",
                         "row": one})
    if want in ("", "decision"):
        for taken in decisions.for_account(db, account_id, limit=room(50)):
            rows.append({"at": taken["created_at"], "type": "decision",
                         "row": taken})

    rows.sort(key=lambda entry: entry["at"], reverse=True)
    return rows[:TIMELINE]


# ---------------------------------------------------------- las estadísticas

@bp.route("/")
@only_admins
def home(account):
    """Lo mismo que ve un cliente en su pantalla, de la cuenta que elijas.

    Es la misma plantilla y el mismo `services/stats.py` que usa `/panel`: la
    gracia de esta pantalla es enseñar lo que ve él, y dos copias acabarían
    enseñando cosas distintas.

    Hubo una portada antes que esta, con el conteo por estado y las últimas
    decisiones. Se quitó: lo que pedía acción se mira ahora desde el filtro de
    Cuentas, y lo que se decidió sobre una cuenta está en su propia ficha.
    """
    db = get_db()
    # Solo clientes: una cuenta de administrador no envía nada, así que no hay
    # estadística suya que mirar.
    clients, _ = accounts.search(db, limit=200)
    if not clients:
        return render_template("admin/no-clients.html", admin=account)

    wanted = as_id(request.args.get("cuenta"))
    whose = next((one for one in clients if one["_id"] == wanted), clients[0])
    return render_template(
        "admin/stats.html", admin=account, account=account, pick=clients,
        **stats.screen(db, whose,
                       period=request.args.get("periodo", ""),
                       tag=request.args.get("etiqueta", ""),
                       campaign=request.args.get("campana", "")))


# ---------------------------------------------------------------- las cuentas

@bp.route("/correos")
@only_admins
def system_mail(account):
    """Los correos del sistema que se le mandaron a una dirección, y qué dijo
    Amazon de cada uno.

    Es la pantalla del «no me llegó el código», que casi siempre es de alguien
    que todavía no tiene cuenta: por eso se busca por dirección y no desde una
    ficha. No dibuja el cuerpo de ningún correo; solo cuándo salió, qué era y
    qué pasó después.
    """
    wanted = request.args.get("q", "").strip()[:200]
    return render_template(
        "admin/mail.html", section="correos", admin=account, search=wanted,
        rows=mail_log.for_address(get_db(), wanted) if wanted else [])


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

    # La cola de habilitación es un filtro más y no una pantalla aparte: sigue
    # siendo la lista de lo que pide acción, pero vive donde están todas.
    pending = request.args.get("estado") == PENDING_FILTER
    rows, total = accounts.search(db, status=status, text=text, pending=pending,
                                  limit=PER_PAGE, skip=skip)
    return render_template("admin/accounts.html", section="cuentas",
                           admin=account, rows=rows, total=total,
                           status=PENDING_FILTER if pending else status,
                           search=text, skip=skip, per_page=PER_PAGE,
                           statuses=accounts.STATUSES,
                           pending_filter=PENDING_FILTER)


@bp.route("/cuentas/<raw>")
@only_admins
def account_page(account, raw):
    db = get_db()
    client = wanted(raw)
    # Un tipo que no existe se mira como si no se hubiera pedido nada: la
    # dirección la escribe cualquiera, y una página vacía por una letra de más
    # parecería que la cuenta no ha hecho nada.
    shown = request.args.get("actividad", "")
    shown = shown if shown in KINDS else ""
    return render_template(
        "admin/account.html", section="cuentas", admin=account, client=client,
        statuses=accounts.STATUSES, plans=sorted(accounts.PLAN_CONTACTS),
        cycles=plans.CYCLES, can_send=accounts.can_send(client),
        limit=accounts.contact_limit(client),
        # Cifras y orígenes. Las direcciones de sus contactos no se listan.
        contacts_total=contacts.count(db, client["_id"]),
        suppressed_total=suppressions.count(db, client["_id"]),
        tags=accounts.tags_of(client),
        history=imports.for_account(db, client["_id"], limit=20),
        devices=sessions.for_account(db, client["_id"]),
        activity=activity(db, client, only=shown),
        activity_kinds=list(KINDS),
        activity_only=shown,
        describe=sessions.describe,
        sources=contacts.SOURCES,
        # Los cobrados, para subirles la factura que se emitió a mano.
        paid=payments.for_account(db, client["_id"], only_paid=True, limit=50),
        invoices=invoices.paid_with_invoice(db, client["_id"]),
        invoices_shown=invoices.SHOWN,
        invoice_mb=invoices.MAX_BYTES // (1024 * 1024))


@bp.route("/cuentas/<raw>/actualizar", methods=["POST"])
@only_admins
def update(account, raw):
    """El plan y la suspensión en un solo envío, con el motivo escrito.

    Ya no hay una casilla para aprobar ni para activar: **estar activa es el
    efecto de un pago cobrado, no una decisión**. Lo que queda aquí es lo que
    una persona sí tiene que poder decidir:

      * ponerle el plan a quien pagó por fuera de la web —Yappy, transferencia—,
        que llama al mismo `activate_plan()` que usa PayPal, así que la cuenta
        queda activa y **con fecha de vencimiento**, no con un plan que no vence
        nunca;
      * suspenderla y levantarle la suspensión.

    `admin_events` guarda una línea por cosa cambiada, con el mismo motivo si
    cambian las dos: es lo que las hace legibles meses después. Y el motivo no
    es papeleo: la única respuesta honesta a «por qué me suspendieron» es lo que
    se escribió el día que se hizo.
    """
    db = get_db()
    client = wanted(raw)
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("admin.account_page", raw=raw))

    plan = request.form.get("plan", "") or None
    cycle = request.form.get("ciclo", plans.MONTHLY)
    suspend = bool(request.form.get("suspendida"))
    reason = request.form.get("motivo", "").strip()

    # Un plan que no existe no cambia nada y tampoco deja una decisión escrita:
    # anotar «pasó a xyz» sería mentir el registro.
    if plan is not None and plan not in accounts.PLAN_CONTACTS:
        return redirect(url_for("admin.account_page", raw=raw))
    if cycle not in plans.CYCLES:
        cycle = plans.MONTHLY

    was_suspended = accounts.is_suspended(client)
    new_plan = plan != (client.get("plan") or None)
    if not new_plan and suspend == was_suspended:
        return redirect(url_for("admin.account_page", raw=raw))
    if not reason:
        return redirect(url_for("admin.account_page", raw=raw, falta="motivo"))

    if new_plan:
        before = client.get("plan") or None
        if plan is None:
            accounts.set_plan(db, client["_id"], None)
        else:
            running = accounts.plan_until(client)
            renewed = (before == plan and running is not None
                       and running > accounts.now())
            until = payments.until(
                cycle, since=accounts.renews_from(client, plan))
            accounts.activate_plan(db, client["_id"], plan, until)
            # Quien pagó por Yappy o por transferencia recibe el mismo correo
            # que quien pagó por PayPal: para el cliente es el mismo hecho.
            notices.paid(client, plan=plan, until=until, renewed=renewed)
        decisions.record(db, kind=decisions.PLAN, admin_id=account["_id"],
                         account_id=client["_id"], before=before, after=plan,
                         reason=reason)

    # Después del plan, porque poner uno deja la cuenta activa y suspenderla
    # tiene que ganarle a eso.
    if suspend != was_suspended:
        fresh = accounts.by_id(db, client["_id"])
        wanted_status = accounts.SUSPENDED if suspend else (
            accounts.ACTIVE if (fresh or {}).get("plan") else accounts.REGISTERED)
        before = accounts.set_status(db, client["_id"], wanted_status)
        if before is not None:
            decisions.record(db, kind=decisions.STATUS, admin_id=account["_id"],
                             account_id=client["_id"], before=before,
                             after=wanted_status, reason=reason)
            # El correo no lleva el motivo: eso se escribe para el registro y
            # puede ser corto y duro. Lo que necesita quien lo recibe es saber
            # qué significa y a dónde escribir.
            if suspend:
                notices.suspended(client)
            else:
                notices.reinstated(client)
        # Suspender cierra lo que esté abierto: si no, quien ya estaba dentro
        # sigue dentro hasta que se le ocurra salir.
        if suspend:
            sessions.revoke_others(db, client["_id"])

    return redirect(url_for("admin.account_page", raw=raw, hecho=1))


@bp.route("/cuentas/<raw>/habilitar-envio", methods=["POST"])
@only_admins
def clear_sending(account, raw):
    """Habilitar a una cuenta para que salga su primera campaña.

    Es la única puerta que queda con una persona detrás. Todos los clientes
    envían desde el mismo dominio, así que comparten una sola reputación: una
    lista comprada la quema para todos. Se mira una vez —de dónde dijo que salió
    cada lista, y la pieza que va a mandar— y después la cuenta queda
    habilitada.
    """
    db = get_db()
    client = wanted(raw)
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("admin.account_page", raw=raw))

    reason = request.form.get("motivo", "").strip()
    if not reason:
        return redirect(url_for("admin.account_page", raw=raw, falta="motivo"))

    if accounts.clear_sending(db, client["_id"], account["_id"]):
        # Es la única espera que se le pide a un cliente, así que enterarse de
        # que terminó no puede depender de que vuelva a entrar a mirar.
        notices.sending_cleared(client)
        decisions.record(db, kind=decisions.SENDING, admin_id=account["_id"],
                         account_id=client["_id"], before=None, after="cleared",
                         reason=reason)
    return redirect(url_for("admin.account_page", raw=raw, hecho=1))


@bp.route("/cuentas/<raw>/factura", methods=["POST"])
@only_admins
def upload_invoice(account, raw):
    """Subir el PDF de la factura de un pago cobrado de esa cuenta.

    Solo PDF de verdad (se mira cómo empieza, no cómo se llama) y hasta 2 MB.
    Subir otra al mismo pago la reemplaza. La primera vez se le avisa al
    cliente; al reemplazarla no, que ya sabe que la tiene.
    """
    if not invoices.SHOWN:
        abort(404)
    db = get_db()
    client = wanted(raw)
    back = url_for("admin.account_page", raw=raw) + "#facturas"
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    try:
        payment_id = ObjectId(request.form.get("pago", ""))
    except (InvalidId, TypeError):
        return redirect(back)
    paid = db.payments.find_one({"_id": payment_id, "account_id": client["_id"],
                                 "status": payments.COMPLETED})
    if paid is None:
        return redirect(back)

    archivo = request.files.get("archivo")
    raw_pdf = archivo.read(invoices.MAX_BYTES + 1) if archivo else b""
    if not raw_pdf or len(raw_pdf) > invoices.MAX_BYTES or not invoices.is_pdf(raw_pdf):
        return redirect(url_for("admin.account_page", raw=raw,
                                factura="mala") + "#facturas")

    first = invoices.save(db, client["_id"], payment_id, data=raw_pdf,
                          uploaded_by=account["_id"])
    decisions.record(db, kind=decisions.INVOICE, admin_id=account["_id"],
                     account_id=client["_id"], before=None if first else "factura",
                     after=str(payment_id),
                     reason=t("admin_invoice_reason_first" if first
                              else "admin_invoice_reason_again"))
    if first:
        notices.invoice_ready(client, paid_at=paid.get("completed_at"))
    return redirect(url_for("admin.account_page", raw=raw, factura="ok") + "#facturas")


# ---------------------------------------------------- las plantillas subidas

@bp.route("/plantillas")
@only_admins
def designs_queue(account):
    """El HTML que han subido los clientes.

    Ya no es una cola: lo peligroso —`<script>`, un atributo de evento, más de
    102 KB— lo rechaza solo el validador en el momento de subirlo, y la única
    mirada humana que queda está en habilitar el envío de la cuenta. Esto es
    para poder abrir una pieza cuando haga falta.
    """
    db = get_db()
    rows = designs.latest(db)
    return render_template(
        "admin/designs.html", section="plantillas", admin=account, rows=rows,
        named=accounts.names_of(db, [row["account_id"] for row in rows]))


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
