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

from datetime import datetime
from functools import wraps

from bson.errors import InvalidId
from bson import ObjectId
from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template, request, url_for)

from blueprints.auth.routes import current_account, same_name
from db import get_db
from i18n import t
from models import account as accounts
from models import admin_event as decisions
from models import auth_event as events
from models import campaign_run as sendings
from models import contact as contacts
from models import import_job as imports
from models import invoice as invoices
from models import mail_log
from models import payment as payments
from models import session as sessions
from models import suppression as suppressions
from models import verification_doc as verification_docs
from services import activity as happening
from services import erase
from services import notices
from services import plans
from services import reputation
from services import sender
from services import stats
from services.security import csrf_ok

bp = Blueprint("admin", __name__, url_prefix="/admin")

PER_PAGE = 100

# El valor que toma el filtro de estado cuando lo que se quiere ver es la cola
# de las que pidieron la demostración. No es un estado de la cuenta, así que no
# puede estar en STATUSES; es una vista más de la misma lista.
DEMO_FILTER = "demo"
# Lo mismo para las que subieron un documento y esperan que alguien lo mire.
REVIEW_FILTER = "review"


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
# dirección —en inglés, como el resto de los filtros— y el valor es el tipo
# que dibuja la plantilla.
KINDS = {
    "logins": "auth",
    "payments": "payment",
    "emails": "campaign",
    "imports": "import",
    "decisions": "decision",
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

    Es la misma plantilla y el mismo `services/stats.py` que usa `/dashboard`: la
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

    wanted = as_id(request.args.get("account"))
    whose = next((one for one in clients if one["_id"] == wanted), clients[0])
    return render_template(
        "admin/stats.html", admin=account, account=account, pick=clients,
        **stats.screen(db, whose,
                       period=request.args.get("period", ""),
                       tag=request.args.get("tag", ""),
                       campaign=request.args.get("campaign", "")))


# ---------------------------------------------------------------- las cuentas

@bp.route("/emails")
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


@bp.route("/accounts")
@only_admins
def accounts_list(account):
    db = get_db()
    status = request.args.get("status", "").strip()
    text = request.args.get("q", "").strip()[:120]
    try:
        skip = max(0, int(request.args.get("since", "0")))
    except ValueError:
        skip = 0

    # La cola de las demostraciones es un filtro más y no una pantalla aparte:
    # sigue siendo la lista de lo que pide acción, pero vive donde están todas.
    demo = request.args.get("status") == DEMO_FILTER
    review = request.args.get("status") == REVIEW_FILTER
    rows, total = accounts.search(db, status=status, text=text, demo=demo,
                                  review=review, limit=PER_PAGE, skip=skip)
    return render_template("admin/accounts.html", section="cuentas",
                           admin=account, rows=rows, total=total,
                           status=(DEMO_FILTER if demo else
                                   REVIEW_FILTER if review else status),
                           search=text, skip=skip, per_page=PER_PAGE,
                           statuses=accounts.STATUSES,
                           demo_filter=DEMO_FILTER, review_filter=REVIEW_FILTER)


# ------------------------------------------------------------- los clientes

# Hasta cuántas empresas lee la tabla de Clientes. Se calcula y se ordena entera
# en memoria: con unos cientos de clientes es nada, y ordenar por un porcentaje
# que no está guardado no se puede pedir a la base.
CLIENTS_MAX = 2000

# Cómo se ordena cada columna. El estado va de lo más grave a lo menos.
CLIENT_SORTS = {
    "company": lambda one: (one["account"].get("company_name") or "").lower(),
    "plan": lambda one: one["account"].get("plan") or "",
    "sent": lambda one: one["sent"],
    "delivered": lambda one: one["delivered_rate"],
    "bounces": lambda one: one["bounce"],
    "complaints": lambda one: one["complaint"],
    "opens": lambda one: one["open_rate"],
    "contacts": lambda one: one["contacts"],
    "last": lambda one: one["last_sent"].timestamp() if one["last_sent"] else 0,
    "state": lambda one: reputation.STATES.index(one["state"]),
}
# Lo que se lee primero sin elegir nada: lo más grave arriba, y entre iguales
# el que más envía.
CLIENT_DEFAULT_SORT = "state"


@bp.route("/clients")
@only_admins
def clients_list(account):
    """Vigilar a los clientes: cuánto envía cada uno y cómo le va.

    Cuentas es para hacer cosas (aprobar, abrir, limitar); esta pantalla es
    para mirar. Arriba, la salud de la cuenta entera ante Amazon, que es la
    cifra que mira él; debajo, una fila por empresa con los últimos 30 días, en
    ámbar cuando se acerca al umbral de la pausa automática y en rojo cuando lo
    pasa. Cifras, nunca direcciones de contactos.
    """
    db = get_db()
    text = request.args.get("q", "").strip()[:120]
    plan = request.args.get("plan", "")
    state = request.args.get("state", "")
    sort = request.args.get("sort", "")
    sort = sort if sort in CLIENT_SORTS else CLIENT_DEFAULT_SORT
    # Lo de mayor a menor es lo que se quiere ver primero en las cifras; el
    # nombre y el estado se leen de arriba abajo.
    ascending_first = sort in ("company", "plan", "state")
    raw_dir = request.args.get("dir", "")
    ascending = raw_dir == "asc" if raw_dir in ("asc", "desc") else ascending_first

    rows, _ = accounts.search(db, text=text, limit=CLIENTS_MAX)
    if plan in plans.PLANS:
        rows = [row for row in rows if row.get("plan") == plan]
    table = reputation.table(db, rows)
    if state in reputation.STATES:
        table = [one for one in table if one["state"] == state]
    table.sort(key=lambda one: one["sent"], reverse=True)
    table.sort(key=CLIENT_SORTS[sort], reverse=not ascending)

    return render_template(
        "admin/clients.html", section="clientes", admin=account, rows=table,
        search=text, plan=plan, state=state, sort=sort, ascending=ascending,
        plan_names=list(plans.PLANS), states=reputation.STATES,
        plan_name=lambda name: plans.PLANS.get(name or "", {}).get("name", ""),
        day=reputation.overall(db, days=1),
        month=reputation.overall(db),
        window=reputation.WINDOW_DAYS, percent=reputation.percent,
        bounce_min=reputation.BOUNCE_MIN_SENT,
        complaint_min=reputation.COMPLAINT_MIN_SENT)


# ------------------------------------------------------------- los eventos

def activity_filters():
    """El filtro de tipo y la empresa que pide la dirección, ya limpios."""
    wanted = request.args.get("type", "")
    if wanted not in happening.FILTERS:
        wanted = happening.DEFAULT_FILTER
    # Sin empresa, ninguna: `ObjectId(None)` no falla, inventa un id nuevo.
    raw = request.args.get("account", "")
    return wanted, as_id(raw) if raw else None


@bp.route("/events")
@only_admins
def activity_page(account):
    """Lo que está pasando: lo que cuenta Amazon de cada correo y lo que pasa en
    las cuentas, del más nuevo al más viejo.

    Se dibuja entera con lo de los últimos días, y `static/js/admin-events.js`
    le pide a `activity_feed` lo nuevo cada pocos segundos. Sin JavaScript
    funciona igual, recargando. Del destinatario, solo el dominio.
    """
    db = get_db()
    wanted, whose = activity_filters()
    rows = happening.latest(db, wanted=wanted, account_id=whose)
    companies, _ = accounts.search(db, limit=CLIENTS_MAX)
    newest = rows[0]["at"] if rows else happening.now()
    return render_template(
        "admin/events.html", section="eventos", admin=account, rows=rows,
        wanted=wanted, whose=whose, filters=list(happening.FILTERS),
        companies=companies, newest=newest.isoformat(),
        moment=happening.moment, level=happening.level)


@bp.route("/events/feed")
@only_admins
def activity_feed(account):
    """Lo nuevo desde `after`, para la pantalla abierta: las filas ya armadas
    (la misma plantilla que la página) y la hora de la más nueva."""
    wanted, whose = activity_filters()
    try:
        after = happening.aware(datetime.fromisoformat(request.args.get("after", "")))
    except ValueError:
        after = None
    rows = happening.latest(get_db(), wanted=wanted, account_id=whose, after=after)
    newest = max([row["at"] for row in rows] + ([after] if after else [])
                 or [happening.now()])
    response = jsonify({
        "html": render_template("admin/_event_rows.html", rows=rows,
                                moment=happening.moment, level=happening.level),
        "newest": newest.isoformat()})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/accounts/<raw>")
@only_admins
def account_page(account, raw):
    db = get_db()
    client = wanted(raw)
    # Un tipo que no existe se mira como si no se hubiera pedido nada: la
    # dirección la escribe cualquiera, y una página vacía por una letra de más
    # parecería que la cuenta no ha hecho nada.
    shown = request.args.get("activity", "")
    shown = shown if shown in KINDS else ""
    return render_template(
        "admin/account.html", section="cuentas", admin=account, client=client,
        statuses=accounts.STATUSES, plans=sorted(accounts.PLAN_CONTACTS),
        cycles=plans.CYCLES, is_open=accounts.is_open(client),
        whatsapp=accounts.whatsapp_url(client.get("phone")),
        tax_id=accounts.tax_id_of(client),
        client_from=sender.sender_email(client), client_reply=sender.reply_to(client),
        client_sender=accounts.sender_of(client),
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
        invoice_mb=invoices.MAX_BYTES // (1024 * 1024),
        company_whatsapp=[(one, accounts.whatsapp_url(one))
                          for one in client.get("company_phones") or []],
        verifications={kind: accounts.verification_of(client, kind)
                       for kind in accounts.VERIFY_KINDS},
        verify_kinds=accounts.VERIFY_KINDS,
        documents=verification_docs.present(db, client["_id"]),
        limited=accounts.limited_of(client),
        limit_reasons=accounts.LIMIT_REASONS)


@bp.route("/accounts/<raw>/update", methods=["POST"])
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
    cycle = request.form.get("cycle", plans.MONTHLY)
    suspend = bool(request.form.get("suspendida"))
    reason = request.form.get("reason", "").strip()

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
        return redirect(url_for("admin.account_page", raw=raw, missing="reason"))

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

    return redirect(url_for("admin.account_page", raw=raw, done=1))


@bp.route("/accounts/<raw>/open", methods=["POST"])
@only_admins
def open_account(account, raw):
    """Abrir la cuenta después de la demostración.

    Es la única puerta con una persona detrás, y la otra forma de pasarla es
    pagar. Se abre al empezar la llamada, para importar la lista y armar la
    primera plantilla juntos. Antes se mira que la empresa exista, con el RUC o
    la cédula que dejó al pedirla; el motivo queda escrito en `admin_events`.
    """
    db = get_db()
    client = wanted(raw)
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("admin.account_page", raw=raw))

    reason = request.form.get("reason", "").strip()
    if not reason:
        return redirect(url_for("admin.account_page", raw=raw, missing="reason"))

    if accounts.open_account(db, client["_id"], account["_id"]):
        # Es la única espera que se le pide a un cliente, así que enterarse de
        # que terminó no puede depender de que vuelva a entrar a mirar.
        notices.opened(client)
        decisions.record(db, kind=decisions.OPEN, admin_id=account["_id"],
                         account_id=client["_id"], before=None, after="opened",
                         reason=reason)
    return redirect(url_for("admin.account_page", raw=raw, done=1))


@bp.route("/accounts/<raw>/invoice", methods=["POST"])
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
    back = url_for("admin.account_page", raw=raw) + "#invoices"
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
                                invoice="bad") + "#invoices")

    first = invoices.save(db, client["_id"], payment_id, data=raw_pdf,
                          uploaded_by=account["_id"])
    decisions.record(db, kind=decisions.INVOICE, admin_id=account["_id"],
                     account_id=client["_id"], before=None if first else "factura",
                     after=str(payment_id),
                     reason=t("admin_invoice_reason_first" if first
                              else "admin_invoice_reason_again"))
    if first:
        notices.invoice_ready(client, paid_at=paid.get("completed_at"))
    return redirect(url_for("admin.account_page", raw=raw, invoice="ok") + "#invoices")


# ------------------------------------------------------- las verificaciones

@bp.route("/accounts/<raw>/document/<kind>")
@only_admins
def document_file(account, raw, kind):
    """Bajar el documento que subió el cliente para una verificación.

    Se descarga, nunca se dibuja dentro del panel: es el documento de otro, y la
    sesión abierta es la de administración. Con su tipo de verdad (el que se
    leyó al subirlo) y sin que el navegador adivine otro.
    """
    client = wanted(raw)
    if kind not in accounts.VERIFY_KINDS:
        abort(404)
    found = verification_docs.of(get_db(), client["_id"], kind)
    if found is None:
        abort(404)
    name = "%s-%s.%s" % (kind, client["_id"], found.get("ext", "bin"))
    return Response(
        bytes(found["data"]),
        mimetype=found.get("mime", "application/octet-stream"),
        headers={"Content-Disposition": 'attachment; filename="%s"' % name,
                 "X-Content-Type-Options": "nosniff",
                 "Cache-Control": "no-store"})


@bp.route("/accounts/<raw>/verify/<kind>", methods=["POST"])
@only_admins
def verify(account, raw, kind):
    """Verificar o rechazar la identificación o la dirección de una cuenta.

    Las dos cosas **borran el documento**: de la cédula de alguien o de su
    recibo no hace falta guardar más que el resultado. Rechazar pide un motivo,
    que el cliente lee en el formulario y en el correo, porque es lo que le dice
    qué subir. **Ninguna de las dos manda correo**: eso lo decide el
    administrador con «Enviar correo al cliente» (`notify`).

    Rechazar **limita la cuenta sola**, si no lo estaba: sin el documento no se
    puede comprobar quién envía. Si la cuenta estaba limitada por falta de
    verificación y con esta quedan las dos verificadas, el límite se levanta
    solo.
    """
    db = get_db()
    client = wanted(raw)
    back = url_for("admin.account_page", raw=raw) + "#verificaciones"
    if kind not in accounts.VERIFY_KINDS or not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    decision = request.form.get("decision", "")
    reason = request.form.get("reason", "").strip()
    if decision not in ("verified", "rejected"):
        return redirect(back)
    if decision == "rejected" and not reason:
        return redirect(url_for("admin.account_page", raw=raw, missing="reason")
                        + "#verificaciones")
    before = accounts.verification_of(client, kind)["status"]
    status = accounts.VERIFIED if decision == "verified" else accounts.REJECTED
    if before == status:
        # Ya estaba así: no se anota otra decisión igual, y se dice. El
        # documento, si quedó uno, se borra igual: de él no hace falta nada.
        verification_docs.remove(db, client["_id"], kind)
        return redirect(url_for("admin.account_page", raw=raw, same=1)
                        + "#verificaciones")
    accounts.set_verification(db, client["_id"], kind, status, by=account["_id"],
                              reason=reason if status == accounts.REJECTED else "")
    verification_docs.remove(db, client["_id"], kind)
    decisions.record(db, kind=decisions.VERIFY, admin_id=account["_id"],
                     account_id=client["_id"], before="%s:%s" % (kind, before),
                     after="%s:%s" % (kind, status),
                     reason=reason or t("admin_verify_reason_ok"))
    if status == accounts.REJECTED:
        fresh = accounts.by_id(db, client["_id"])
        if (not accounts.limited_of(fresh)
                and accounts.limit(db, client["_id"], reason=accounts.LIMIT_VERIFICATION,
                                   admin_id=account["_id"],
                                   note=t("admin_limit_note_rejected"))):
            decisions.record(db, kind=decisions.LIMIT, admin_id=account["_id"],
                             account_id=client["_id"], before=None,
                             after=accounts.LIMIT_VERIFICATION,
                             reason=t("admin_limit_note_rejected"))
    else:
        fresh = accounts.by_id(db, client["_id"])
        shown = accounts.limited_of(fresh)
        if (shown and shown.get("reason") == accounts.LIMIT_VERIFICATION
                and accounts.all_verified(fresh)
                and accounts.unlimit(db, client["_id"])):
            decisions.record(db, kind=decisions.LIMIT, admin_id=account["_id"],
                             account_id=client["_id"], before=shown.get("reason"),
                             after=None, reason=t("admin_limit_lifted_auto"))
    return redirect(url_for("admin.account_page", raw=raw, done=1)
                    + "#verificaciones")


@bp.route("/accounts/<raw>/notify", methods=["POST"])
@only_admins
def notify_result(account, raw):
    """Mandarle al cliente el resultado de sus verificaciones.

    Lo pulsa el administrador cuando quiere (octubre de 2026): verificar y
    rechazar solo anotan el resultado. El correo dice qué quedó verificado y qué
    se rechazó, con el motivo, y si hay un rechazo pide volver a enviar ese
    documento para poder seguir enviando campañas. Sin ningún resultado no hay
    nada que contar, y no sale nada.
    """
    db = get_db()
    client = wanted(raw)
    back = url_for("admin.account_page", raw=raw) + "#verificaciones"
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    results = {kind: accounts.verification_of(client, kind)
               for kind in accounts.VERIFY_KINDS}
    if not any(one["status"] in (accounts.VERIFIED, accounts.REJECTED)
               for one in results.values()):
        return redirect(back)
    notices.verification_result(client, results=results)
    decisions.record(db, kind=decisions.NOTIFY, admin_id=account["_id"],
                     account_id=client["_id"], before=None,
                     after=",".join("%s:%s" % (k, v["status"]) for k, v in results.items()),
                     reason=t("admin_notify_reason"))
    return redirect(url_for("admin.account_page", raw=raw, notified=1)
                    + "#verificaciones")


@bp.route("/accounts/<raw>/limit", methods=["POST"])
@only_admins
def limit_account(account, raw):
    """Limitar la cuenta, o quitarle el límite.

    Limitar no es suspender: entra, prepara todo y paga, y lo único que no
    puede es enviar (`sender.blocked()` dice `limited`). Se elige el motivo de
    una lista, que es lo que lee el cliente, y se deja una nota, que es para el
    registro. Al limitarla le llega un correo con el enlace a sus documentos.
    """
    db = get_db()
    client = wanted(raw)
    back = url_for("admin.account_page", raw=raw) + "#limite"
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    shown = accounts.limited_of(client)
    note = request.form.get("note", "").strip()
    if request.form.get("lift"):
        if shown and accounts.unlimit(db, client["_id"]):
            decisions.record(db, kind=decisions.LIMIT, admin_id=account["_id"],
                             account_id=client["_id"], before=shown.get("reason"),
                             after=None, reason=note or t("admin_limit_lifted"))
        return redirect(url_for("admin.account_page", raw=raw, done=1) + "#limite")
    reason = request.form.get("reason", "")
    if shown or reason not in accounts.LIMIT_REASONS:
        return redirect(back)
    if accounts.limit(db, client["_id"], reason=reason, admin_id=account["_id"],
                      note=note):
        decisions.record(db, kind=decisions.LIMIT, admin_id=account["_id"],
                         account_id=client["_id"], before=None, after=reason,
                         reason=note or t("admin_limit_reason_" + reason))
        notices.limited(client, reason=reason)
    return redirect(url_for("admin.account_page", raw=raw, done=1) + "#limite")


@bp.route("/accounts/<raw>/erase", methods=["POST"])
@only_admins
def erase_account(account, raw):
    """Eliminar esta cuenta y sus datos, con su motivo (octubre de 2026). Lo que
    antes se hacía a mano en la base; la misma `erase()` que usa el dueño. Se
    confirma escribiendo el nombre de la empresa."""
    db = get_db()
    client = wanted(raw)
    back = url_for("admin.account_page", raw=raw) + "#eliminar"
    reason = request.form.get("reason", "").strip()
    if (not csrf_ok(request.form.get("csrf_token")) or not reason
            or not same_name(request.form.get("company", ""), client.get("company_name", ""))):
        return redirect(url_for("admin.account_page", raw=raw, erase_error=1) + "#eliminar")
    gone = dict(client)
    erase.erase(db, client["_id"], by=account["_id"], reason=reason)
    notices.erased(gone)
    return redirect(url_for("admin.accounts_list", erased=1))
