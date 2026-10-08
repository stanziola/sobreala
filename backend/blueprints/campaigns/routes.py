"""Enviar correos: a quién, con qué pieza, y cuándo.

La pantalla que junta lo que ya había suelto —las listas de `/contacts` y las
piezas de `/templates`— y lo manda. Es la única del panel desde la que sale
correo a un contacto de un cliente.

**Un administrador no la ve ni entra**: su cuenta no tiene contactos a los que
escribirle, así que la fila no le sale en el menú y la ruta lo devuelve a
`/admin`. Esconder una fila no es un permiso.

El envío de verdad vive en `services/sender.py`. Aquí solo se elige, se agenda,
y se le pide que mande una tanda.

**Una campaña se guarda y se manda las veces que haga falta.** La pantalla
tiene por eso dos listas: las campañas guardadas, que se pueden corregir y
volver a mandar, y los envíos, uno por vez que salió. Y mandar pasa siempre por
una pantalla que pregunta, como exportar contactos: el GET no manda nada y el
POST sí.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, abort, redirect, render_template, request,
                   session, url_for)

from blueprints.auth.routes import (CONFIRM_PER_IP, REGISTER_PER_EMAIL,
                                    clean_email, client_ip, current_account,
                                    current_workspace, needs, not_for_admins,
                                    seconds_left)
from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from models import design as designs
from models import event as events
from models import token as tokens
from services import notices, render, sender, ses_identity
from services import clock
from services.security import csrf_ok, rate_limit

bp = Blueprint("campaigns", __name__)

# Cómo viaja la fecha en el formulario: lo que escribe <input type="datetime-local">.
WHEN_FORMAT = "%Y-%m-%dT%H:%M"


@bp.before_request
def keep_out():
    """Un administrador no tiene a quién escribirle, y un usuario entra solo si
    la empresa le dio al menos ver las campañas. Mandar pide su propio permiso,
    y eso se comprueba en las dos rutas que mandan."""
    account = current_account()
    return not_for_admins(account) or needs(account, accounts.CAMPAIGNS)


def signed_in():
    """La cuenta de la empresa: las campañas, los contactos y la cuota son
    suyos, también cuando los mira un usuario que ella creó."""
    return current_workspace()


def may_send():
    """Un redirect si quien mira puede ver las campañas pero no mandarlas."""
    return needs(current_account(), accounts.SEND)


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def read_when(raw: str) -> datetime | None:
    """La fecha que se escribió, en UTC.

    El navegador manda la hora del reloj de quien la escribió y sin zona. Se
    entiende en la zona de su dispositivo (`services/clock.py`) y se guarda en
    UTC: «a las 3 de la tarde» desde Panamá son las 20:00 UTC.
    """
    try:
        return clock.to_utc(datetime.strptime(raw, WHEN_FORMAT))
    except (ValueError, TypeError):
        return None


def pieces(db, account_id) -> list[dict]:
    """Las piezas guardadas, con el nombre que les puso el cliente."""
    return designs.for_account(db, account_id)


def lists_of(db, account) -> list[dict]:
    """Las etiquetas a las que se le puede escribir, con cuántos hay en cada una.

    Marcar varias es escribirle a quien lleve **cualquiera** de ellas, y no
    marcar ninguna es escribirle a toda la lista: una cuenta que nunca creó una
    etiqueta tiene igualmente a quién escribirle.
    """
    # Con las columnas de la cuenta: quien no las tenga llenas no va a recibir
    # nada, así que contarlo aquí sería prometer un número que no sale.
    counted = contacts.count_by_tag(db, account["_id"],
                                    accounts.fields_of(account))
    return [{"tag": name, "name": name, "howmany": counted.get(name, 0)}
            for name in accounts.tags_of(account)]


def lists_chosen(account) -> list[str]:
    """Las etiquetas marcadas, filtradas por las que existen.

    Se recorren las de la cuenta y no lo que llegó: un nombre inventado se
    descarta en vez de filtrar por él, que es lo mismo que hace la pantalla de
    contactos. Vacío es toda la lista.
    """
    marked = set(request.form.getlist("lista"))
    return [name for name in accounts.tags_of(account) if name in marked]


def shared(db, account, **extra):
    sent_runs = runs.for_account(db, account["_id"])
    return {
        "account": account,
        "lists": lists_of(db, account),
        "pieces": pieces(db, account["_id"]),
        "named": {one["key"]: one["label"]
                  for one in render.TEMPLATE_LIST.values()},
        "campaigns": campaigns.for_account(db, account["_id"]),
        "tags_of": campaigns.tags_of,
        "everyone": t("send_all_contacts"),
        # Una fila por vez que salió algo, que es otra cosa que una fila por
        # campaña: la mandada seis veces son seis envíos.
        "runs": sent_runs,
        # Lo que contó SES de cada envío: entregados, rebotes, abiertos, con
        # clic y quejas, en personas. Una consulta para toda la lista.
        "run_counts": events.counts_by_run(
            db, account["_id"], [one["_id"] for one in sent_runs]),
        "times": runs.times_by_campaign(db, account["_id"]),
        # Qué le falta a la cuenta para que un envío salga de verdad. Se enseña
        # siempre, no al final: enterarse de que no se puede después de armarlo
        # todo es la peor forma de enterarse.
        "blocked": sender.blocked(account),
        "from_email": sender.sender_email(account),
        "reply": sender.reply_to(account),
        "quota": accounts.quota_left(account),
        "editable": campaigns.editable,
        "due": campaigns.due,
        # Un usuario puede tener solo «ver las campañas»: entonces la pantalla
        # se lee entera y no enseña botones que su cuenta no puede pulsar.
        "can_send": accounts.can(current_account(), accounts.SEND),
        **extra,
    }


@bp.route("/campaigns", methods=["GET", "POST"])
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}

    if request.method == "POST":
        answer = may_send()
        if answer:
            return answer
        errors = save(db, account, None)
        if not errors:
            return redirect(url_for("campaigns.index", saved=1))

    return render_template(
        "campaigns/index.html", section="envios",
        **shared(db, account, errors=errors, form=request.form,
                 saved=bool(request.args.get("saved")),
                 done=request.args.get("done", ""),
                 removed=bool(request.args.get("deleted"))))


def save(db, account, campaign) -> dict[str, str]:
    """Guardar lo que dice el formulario, para una nueva o para una que se edita."""
    errors: dict[str, str] = {}
    subject = campaigns.clean_subject(request.form.get("asunto", ""))
    design_id = as_id(request.form.get("pieza"))
    tags = lists_chosen(account)
    now_wanted = request.form.get("cuando") == "ahora"
    when = accounts.now() if now_wanted else read_when(
        request.form.get("fecha", ""))

    if not csrf_ok(request.form.get("csrf_token")):
        return {"form": t("error_csrf")}
    if not subject:
        errors["asunto"] = t("error_required")
    if design_id is None or designs.by_id(db, account["_id"], design_id) is None:
        errors["pieza"] = t("send_pick_piece")
    if when is None:
        errors["fecha"] = t("send_pick_when")
    elif not now_wanted and when <= accounts.now():
        # Programar para una hora que ya pasó es pedir que salga ahora mismo, y
        # eso tiene su propio botón.
        errors["fecha"] = t("send_when_past")
    if errors:
        return errors

    if campaign is None:
        campaigns.create(db, account["_id"], subject=subject,
                         design_id=design_id, tags=tags, scheduled_at=when)
    elif not campaigns.update(db, account["_id"], campaign["_id"],
                              subject=subject, design_id=design_id, tags=tags,
                              scheduled_at=when):
        return {"form": t("send_already_out")}
    return {}


@bp.route("/campaigns/<raw>", methods=["GET", "POST"])
def edit(raw):
    """Cambiar una campaña que todavía no ha empezado a salir."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    campaign_id = as_id(raw)
    found = (campaigns.by_id(db, account["_id"], campaign_id)
             if campaign_id else None)
    if found is None:
        return redirect(url_for("campaigns.index"))
    if not campaigns.editable(found):
        return redirect(url_for("campaigns.index", done="late"))

    errors: dict[str, str] = {}
    if request.method == "POST":
        answer = may_send()
        if answer:
            return answer
        errors = save(db, account, found)
        if not errors:
            return redirect(url_for("campaigns.index", saved=1))

    return render_template(
        "campaigns/edit.html", section="envios",
        **shared(db, account, errors=errors, form=request.form,
                 campaign=found,
                 # Vuelve a salir en la hora de quien la mira.
                 when=clock.local(found["scheduled_at"]).strftime(WHEN_FORMAT)))


# Cuántas personas por página en el detalle de un envío.
PER_PAGE = 50


@bp.route("/campaigns/sent/<raw>")
def run_detail(raw):
    """A quién le salió un envío y qué pasó con cada uno: si le llegó, si lo
    abrió, si pulsó. Una fila por persona, con la primera vez de cada cosa.

    El filtro por etiqueta y el buscador se resuelven primero en Contactos: se
    busca quién cumple y solo se miran los eventos de esas personas. Las
    etiquetas y el nombre son los de hoy; quien ya no está en Contactos sale con
    su dirección y lo dice.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    run_id = as_id(raw)
    found = runs.by_id(db, account["_id"], run_id) if run_id else None
    if found is None:
        abort(404)

    known = accounts.tags_of(account)
    tag = request.args.get("tag", "")
    tag = tag if tag in known else ""
    search = " ".join(request.args.get("q", "").split())[:100]
    outcome = request.args.get("status", "")
    outcome = outcome if outcome in events.OUTCOMES else ""
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    emails = None
    if tag or search:
        emails = contacts.emails_matching(db, account["_id"], tag=tag, text=search)
    total, people = events.recipients(db, account["_id"], found["_id"], emails=emails,
                                      outcome=outcome, skip=(page - 1) * PER_PAGE,
                                      limit=PER_PAGE)
    # Nombre y etiquetas de la página, en una consulta (regla 10).
    here = contacts.by_emails(db, account["_id"], [one["email"] for one in people])
    for one in people:
        one["contact"] = here.get(one["email"])

    return render_template(
        "campaigns/run.html", section="envios", account=account, run=found,
        people=people, total=total, page=page,
        pages=max(1, -(-total // PER_PAGE)), tag=tag, tags=known, search=search,
        outcome=outcome, outcomes=list(events.OUTCOMES),
        seen=events.counts_by_run(db, account["_id"], [found["_id"]]).get(found["_id"]),
        everyone=t("send_all_contacts"))


@bp.route("/campaigns/<raw>/delete", methods=["POST"])
def remove(raw):
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    answer = may_send()
    if answer:
        return answer
    if csrf_ok(request.form.get("csrf_token")):
        campaign_id = as_id(raw)
        if campaign_id:
            campaigns.remove(get_db(), account["_id"], campaign_id)
    return redirect(url_for("campaigns.index", deleted=1))


@bp.route("/campaigns/<raw>/send", methods=["GET", "POST"])
def send(raw):
    """Preguntar primero, y después mandar una tanda de esta campaña.

    **El GET no manda nada**: dibuja a quién le va a salir y cuántos son, y
    pregunta. Es el mismo reparto que exportar contactos, y aquí importa más,
    porque lo que hace el POST no se puede deshacer: un correo que salió, salió.

    Una tanda y no la campaña entera: esto corre dentro de la petición y una
    lista larga la cortaría el servidor a la mitad. La pantalla dice cuántos
    van y ofrece seguir, que es lo que hará el proceso en segundo plano el día
    que exista, sin que nada de esto cambie.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = may_send()
    if answer:
        return answer

    db = get_db()
    campaign_id = as_id(raw)
    found = (campaigns.by_id(db, account["_id"], campaign_id)
             if campaign_id else None)
    if found is None:
        return redirect(url_for("campaigns.index"))

    if request.method == "GET":
        return render_template(
            "campaigns/confirm.html", section="envios",
            **shared(db, account, campaign=found,
                     piece=designs.by_id(db, account["_id"],
                                         found.get("design_id")),
                     going=contacts.matching_count(
                         db, account["_id"],
                         tags=campaigns.tags_of(found),
                         complete=accounts.fields_of(account)),
                     already=runs.times(db, account["_id"], found["_id"])))

    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("campaigns.index"))

    # Volver a mandar una que ya salió empieza por devolver a cero los
    # contadores de la vuelta. Si otra pestaña se adelantó, la consulta no
    # encuentra nada y aquí no se manda dos veces lo mismo.
    if found["status"] == campaigns.SENT:
        if not campaigns.restart(db, account["_id"], found["_id"],
                                 when=accounts.now()):
            return redirect(url_for("campaigns.index", done="late"))
        found = campaigns.by_id(db, account["_id"], found["_id"])

    result = sender.run(db, account, found)
    if result["blocked"]:
        return redirect(url_for("campaigns.index", done="blocked"))
    return redirect(url_for("campaigns.index",
                            done="partial" if result["left"] else "all"))


# --------------------------------------------------------------- remitente
#
# De quién sale cada campaña y a dónde llegan las respuestas. Vale para todas
# las campañas de la cuenta. La ve quien puede ver las campañas, y la cambia
# solo el dueño, como la dirección postal: es la firma de la empresa.

REPLY_ATTEMPTS = "reply_to_attempts"
REPLY_DEADLINE = "reply_to_expires_at"
# Cuántas veces al día se puede pedir un dominio, comprobarlo o quitarlo: cada
# una es una llamada a Amazon.
DOMAIN_PER_ACCOUNT = (20, 86400)


def sender_screen(db, account, **extra):
    mine = accounts.sender_of(account)
    return render_template(
        "campaigns/sender.html", section="envios", account=account, mine=mine,
        sending_domain=Config.SENDING_DOMAIN,
        from_email=sender.sender_email(account),
        reply=sender.reply_to(account),
        suggestion=mine.get("handle") or accounts.suggest_handle(
            db, account.get("company_name", "")),
        records=ses_identity.records(mine["domain"], mine.get("dkim_tokens") or [])
        if mine.get("domain") else [],
        can_edit=not accounts.is_member(current_account()),
        **extra)


@bp.route("/campaigns/sender", methods=["GET", "POST"])
def sender_page():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    mine = accounts.sender_of(account)
    errors: dict[str, str] = {}

    if request.method == "GET":
        # Un dominio que espera sus registros se mira al abrir la pantalla: no
        # hay quién lo mire a las tres de la mañana.
        if mine.get("domain") and mine.get("domain_status") != accounts.DOMAIN_VERIFIED:
            try:
                accounts.set_domain_status(db, account["_id"],
                                           ses_identity.status(mine["domain"]))
                # Leída otra vez de la base: la de la sesión es de antes.
                account = accounts.by_id(db, account["_id"])
            except ses_identity.IdentityError as exc:
                print(f"  [remitente] {mine['domain']}: {exc}", flush=True)
        return sender_screen(db, account, errors=errors, form={},
                             done=request.args.get("done", ""))

    if accounts.is_member(current_account()) or not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("campaigns.sender_page"))

    action = request.form.get("action", "")
    if action == "handle":
        handle = accounts.clean_handle(request.form.get("handle", ""))
        if handle is None:
            errors["handle"] = t("sender_handle_bad", min=accounts.HANDLE_MIN,
                                 max=accounts.HANDLE_MAX)
        elif not accounts.set_handle(db, account["_id"], handle):
            errors["handle"] = t("sender_handle_taken")
        else:
            return redirect(url_for("campaigns.sender_page", done="handle"))

    elif action == "reply":
        typed = request.form.get("reply_to", "").strip()
        address = clean_email(typed) if typed else None
        domain = mine.get("domain") if accounts.domain_ready(account) else ""
        if not address:
            errors["reply"] = t("error_email_invalid")
        elif address.lower() == sender.reply_to(account).lower():
            errors["reply"] = t("sender_reply_same")
        elif domain and address.lower().endswith("@" + domain):
            # Una dirección de su propio dominio ya está probada: el dominio
            # entero se probó suyo con sus registros DNS.
            accounts.set_reply_to(db, account["_id"], address)
            return redirect(url_for("campaigns.sender_page", done="reply"))
        elif not rate_limit(db, f"reply:mail:{accounts.normalize_email(address)}",
                            *REGISTER_PER_EMAIL) \
                or not rate_limit(db, f"reply:account:{account['_id']}",
                                  *REGISTER_PER_EMAIL):
            # Cada intento le manda un correo a una dirección escrita a mano:
            # con tope, nadie llena el buzón de un tercero desde aquí.
            errors["reply"] = t("error_too_many")
        else:
            accounts.start_reply_to(db, account["_id"], address)
            code = tokens.issue(db, account["_id"], tokens.REPLY_TO)
            notices.reply_to_code(account, code=code, to=address,
                                  minutes=Config.CONFIRMATION_CODE_MINUTES)
            session[REPLY_ATTEMPTS] = 0
            session[REPLY_DEADLINE] = (accounts.now() + timedelta(
                minutes=Config.CONFIRMATION_CODE_MINUTES)).isoformat()
            return redirect(url_for("campaigns.reply_code"))

    elif action in ("domain", "check", "remove"):
        if not rate_limit(db, f"domain:account:{account['_id']}", *DOMAIN_PER_ACCOUNT):
            errors["domain"] = t("error_too_many")
        elif action == "domain":
            domain = accounts.clean_domain(request.form.get("domain", ""))
            if mine.get("domain"):
                errors["domain"] = t("sender_domain_already")
            elif domain is None:
                errors["domain"] = t("sender_domain_bad")
            elif db.accounts.find_one({"sender.domain": domain}, {"_id": 1}):
                # Antes de hablar con Amazon: el dominio de otra cuenta no se
                # crea ni se toca desde aquí.
                errors["domain"] = t("sender_domain_taken")
            else:
                try:
                    found = ses_identity.create(domain)
                except ses_identity.IdentityError as exc:
                    print(f"  [remitente] {domain}: {exc}", flush=True)
                    errors["domain"] = t("sender_domain_failed")
                else:
                    if accounts.set_domain(db, account["_id"], domain, found):
                        return redirect(url_for("campaigns.sender_page",
                                                done="domain") + "#domain")
                    errors["domain"] = t("sender_domain_taken")
        elif not mine.get("domain"):
            return redirect(url_for("campaigns.sender_page"))
        elif action == "check":
            try:
                accounts.set_domain_status(db, account["_id"],
                                           ses_identity.status(mine["domain"]))
                return redirect(url_for("campaigns.sender_page", done="check")
                                + "#domain")
            except ses_identity.IdentityError as exc:
                print(f"  [remitente] {mine['domain']}: {exc}", flush=True)
                errors["domain"] = t("sender_domain_failed")
        else:
            try:
                ses_identity.delete(mine["domain"])
            except ses_identity.IdentityError as exc:
                print(f"  [remitente] {mine['domain']}: {exc}", flush=True)
                errors["domain"] = t("sender_domain_failed")
            else:
                accounts.clear_domain(db, account["_id"])
                # Un «Responder a» de ese dominio ya no lo prueba nada.
                if sender.reply_to(account).lower().endswith("@" + mine["domain"]):
                    accounts.clear_reply_to(db, account["_id"])
                return redirect(url_for("campaigns.sender_page", done="removed"))

    elif action == "local":
        if mine.get("domain_status") != accounts.DOMAIN_VERIFIED:
            return redirect(url_for("campaigns.sender_page"))
        local = accounts.clean_local(request.form.get("local", ""))
        if local is None:
            errors["local"] = t("sender_local_bad")
        else:
            accounts.set_domain_local(db, account["_id"], local)
            return redirect(url_for("campaigns.sender_page", done="local") + "#domain")

    return sender_screen(db, account, errors=errors, done="", form=request.form)


@bp.route("/campaigns/sender/code", methods=["GET", "POST"])
def reply_code():
    """El código que llegó al «Responder a» nuevo. Hasta que entra, las
    respuestas siguen llegando a la dirección de antes."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    waiting = accounts.sender_of(account).get("reply_to_pending")
    if accounts.is_member(current_account()) or not waiting:
        return redirect(url_for("campaigns.sender_page"))

    db = get_db()
    errors: dict[str, str] = {}
    if request.method == "POST":
        typed = "".join(request.form.getlist("code"))
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not rate_limit(db, f"reply:ip:{client_ip()}", *CONFIRM_PER_IP):
            errors["form"] = t("error_too_many")
        else:
            attempts = session.get(REPLY_ATTEMPTS, 0) + 1
            session[REPLY_ATTEMPTS] = attempts
            reason, doc = tokens.check(db, account["_id"], typed, tokens.REPLY_TO)
            if reason in (tokens.UNKNOWN, tokens.INVALID) \
                    and attempts >= tokens.MAX_ATTEMPTS:
                reason = tokens.TOO_MANY
            if reason == tokens.VALID and not tokens.spend(db, doc):
                reason = tokens.USED
            if reason == tokens.VALID:
                accounts.set_reply_to(db, account["_id"], waiting)
                return redirect(url_for("campaigns.sender_page", done="reply"))
            errors["form"] = t({tokens.USED: "error_code_used",
                                tokens.TOO_MANY: "error_code_too_many"}.get(
                                    reason, "error_code_invalid"))

    return render_template("campaigns/sender-code.html", section="envios",
                           errors=errors, waiting=waiting,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left(REPLY_DEADLINE))
