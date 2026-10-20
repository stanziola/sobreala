"""La rama «API» del Dashboard (octubre de 2026): las llaves, los avisos a su
sistema, los correos que mandó y el registro.

**Solo el dueño.** Una llave habla con los datos de la empresa sin sesión, así
que crearla es como dar una copia de la contraseña: un usuario de la empresa no
ve esta rama, y un administrador no tiene Dashboard.

**Crear pide demostrar quién es**, como eliminar la cuenta: la contraseña (o un
código al correo para quien entró con Google o GitHub) y el código de la app si
tiene segundo factor. La prueba vale `PROOF_MINUTES` y queda atada a **esta
cuenta y esta sesión**: con varias cuentas abiertas en el navegador
(`/switch-account` solo cambia la sesión activa), probar la contraseña de una
no sirve para la otra.

**La llave se enseña una sola vez, en la respuesta del POST que la crea**: no
pasa por la sesión (la galleta va firmada, no cifrada), ni por la dirección, ni
por un aviso. El formulario lleva un número de un solo uso, así recargar la
página que la enseña no crea otra.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, Response, redirect, render_template, request,
                   session, url_for)

from blueprints.auth.routes import (PASSWORD_PER_IP, SESSION_KEY, client_ip,
                                    current_account, log_auth, needs,
                                    not_for_admins, owner_only)
from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import api_key as api_keys
from models import api_log
from models import auth_event as events
from models import event as mail_events
from models import message as messages
from models import webhook as hooks
from models import token as tokens
from services import api_auth, notices, safe_http, totp, webhooks
from services.security import csrf_ok, rate_limit, verify_password

bp = Blueprint("developers", __name__, url_prefix="/developers")

PROOF_KEY = "api_proof"
PROOF_MINUTES = 10
PROOF_PER_ACCOUNT = (5, 900)
# El número de un solo uso del formulario de crear.
FORM_KEY = "api_key_form"


@bp.before_request
def keep_out():
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    return (not_for_admins(account) or owner_only(account)
            or needs(account, accounts.CONTACTS))


def now() -> datetime:
    return datetime.now(timezone.utc)


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def docs_url() -> str:
    return f"{Config.PUBLIC_SITE_URL}/api/"


# ------------------------------------------------------------ la prueba

def proved(account) -> bool:
    """Si esta cuenta, en esta sesión, demostró hace poco quién es."""
    found = session.get(PROOF_KEY) or {}
    if (found.get("account") != str(account["_id"])
            or found.get("sid") != session.get(SESSION_KEY)):
        return False
    try:
        return datetime.fromisoformat(found.get("until", "")) > now()
    except (TypeError, ValueError):
        return False


def prove(account) -> None:
    session[PROOF_KEY] = {"account": str(account["_id"]),
                          "sid": session.get(SESSION_KEY),
                          "until": (now() + timedelta(minutes=PROOF_MINUTES)).isoformat()}


def check_proof(db, account, form) -> dict[str, str]:
    """Comprobar la contraseña (o el código del correo) y el de la app.
    Devuelve los errores; vacío es que quedó demostrado."""
    errors: dict[str, str] = {}
    if (not rate_limit(db, f"apiproof:{account['_id']}", *PROOF_PER_ACCOUNT)
            or not rate_limit(db, f"apiproof:ip:{client_ip()}", *PASSWORD_PER_IP)):
        return {"form": t("error_too_many")}
    spent = None
    if account.get("password_hash"):
        if not verify_password(form.get("password", ""), account.get("password_hash")):
            errors["password"] = t("erase_error_password")
    else:
        reason, doc = tokens.check(db, account["_id"], form.get("email_code", "").strip(),
                                   tokens.API_ACCESS)
        if reason != tokens.VALID:
            errors["email_code"] = t("erase_error_code")
        else:
            spent = doc
    if accounts.two_factor_on(account) and not errors:
        typed = form.get("app_code", "").strip()
        counter = (totp.counter_for(account["two_factor"]["secret"], typed)
                   if typed else None)
        if counter is None or not accounts.use_counter(db, account["_id"], counter):
            errors["app_code"] = t("error_code_invalid")
    if not errors and spent is not None and not tokens.spend(db, spent):
        # Otra petición lo gastó primero: no vale dos veces.
        errors["email_code"] = t("erase_error_code")
    if not errors:
        prove(account)
    return errors


def proof_context(account) -> dict:
    return {"needs_proof": not proved(account),
            "with_password": bool(account.get("password_hash")),
            "two_step": accounts.two_factor_on(account)}


# ------------------------------------------------------------ las llaves

def shown(found) -> dict:
    """Una llave para la lista: si sigue abriendo, y cómo se reconoce."""
    return {**found, "live": api_keys.is_live(found),
            "expired": (not found.get("revoked_at") and not api_keys.is_live(found))}


@bp.route("/keys")
def keys():
    account = current_account()
    db = get_db()
    mine = [shown(one) for one in api_keys.for_account(db, account["_id"])]
    return render_template(
        "developers/keys.html", keys=mine, docs=docs_url(),
        active=sum(1 for one in mine if one["live"]), limit=api_keys.KEY_LIMIT,
        done=request.args.get("done", ""))


def key_form_values(form) -> dict:
    mode = form.get("mode", api_keys.LIVE)
    if mode not in api_keys.MODES:
        mode = api_keys.LIVE
    preset = form.get("preset", "")
    wanted = (api_keys.PRESETS[preset] if preset in api_keys.PRESETS
              else form.getlist("scope"))
    try:
        days = int(form.get("days", "0"))
    except ValueError:
        days = -1
    return {"name": api_keys.clean_name(form.get("name", "")), "mode": mode,
            "scopes": api_keys.clean_scopes(wanted, mode), "days": days,
            "ips_raw": form.get("ips", "")[:2000]}


@bp.route("/keys/new", methods=["GET", "POST"])
def new_key():
    """Crear una llave: el formulario, la prueba si hace falta, y la página que
    la enseña una vez."""
    account = current_account()
    db = get_db()
    errors: dict[str, str] = {}
    sent = False
    values = key_form_values(request.form) if request.method == "POST" else {
        "name": "", "mode": api_keys.LIVE, "scopes": [api_keys.EMAILS_SEND],
        "days": 0, "ips_raw": ""}

    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif request.form.get("action") == "code":
            # Sin contraseña: el código va a su correo.
            if not account.get("password_hash") and rate_limit(
                    db, f"apiproof:code:{account['_id']}", 5, 3600):
                code = tokens.issue(db, account["_id"], tokens.API_ACCESS)
                sent = notices.api_access_code(account, code)
        elif api_keys.active_count(db, account["_id"]) >= api_keys.KEY_LIMIT:
            errors["form"] = t("api_keys_full", n=api_keys.KEY_LIMIT)
        elif (not request.form.get("once")
              or request.form.get("once") != session.get(FORM_KEY)):
            # La página se recargó o se mandó dos veces: no se crea otra.
            return redirect(url_for("developers.keys"))
        else:
            if not proved(account):
                errors.update(check_proof(db, account, request.form))
            ips, bad = api_auth.clean_ips(values["ips_raw"].replace(",", "\n").splitlines())
            if not values["name"]:
                errors["name"] = t("error_required")
            if not values["scopes"]:
                errors["scope"] = t("api_keys_scope_required")
            if values["days"] not in api_keys.EXPIRY_DAYS:
                errors["days"] = t("error_required")
            if bad:
                errors["ips"] = t("api_keys_ips_bad", what=", ".join(bad[:3]))
            elif len(ips) > api_keys.IPS_MAX:
                errors["ips"] = t("api_keys_ips_full", n=api_keys.IPS_MAX)
            if not errors:
                session.pop(FORM_KEY, None)
                raw, made = api_keys.create(
                    db, account["_id"], name=values["name"], mode=values["mode"],
                    scopes=values["scopes"], ips=ips, days=values["days"], ip=client_ip())
                log_auth(db, events.API_KEY, events.CREATED, email=account["email"],
                         account_id=account["_id"])
                notices.api_key_created(account, found=made, ip=client_ip())
                response = Response(render_template(
                    "developers/key-created.html", raw=raw, made=made,
                    base=f"{Config.APP_BASE_URL}/api/v1", docs=docs_url()))
                response.headers["Cache-Control"] = "no-store"
                return response

    session[FORM_KEY] = secrets.token_urlsafe(16)
    return render_template(
        "developers/key-new.html", values=values, errors=errors, sent=sent,
        once=session[FORM_KEY], scopes=api_keys.SCOPES, test_scopes=api_keys.TEST_SCOPES,
        expiry=api_keys.EXPIRY_DAYS, docs=docs_url(), **proof_context(account))


@bp.route("/keys/<raw>/revoke", methods=["GET", "POST"])
def revoke_key(raw):
    """Revocar una llave: la pantalla que pregunta, y el POST que revoca."""
    account = current_account()
    db = get_db()
    found = api_keys.by_id(db, account["_id"], as_id(raw))
    if found is None or found.get("revoked_at"):
        return redirect(url_for("developers.keys"))
    if request.method == "POST" and csrf_ok(request.form.get("csrf_token")):
        if api_keys.revoke(db, account["_id"], found["_id"], by=account["_id"],
                           reason=t("api_key_revoked_by_owner")):
            log_auth(db, events.API_KEY, events.REVOKED, email=account["email"],
                     account_id=account["_id"])
            notices.api_key_revoked(account, name=found.get("name", ""))
        return redirect(url_for("developers.keys", done="revoked"))
    return render_template("developers/key-revoke.html", found=found)


# ------------------------------------------------------------ el registro

@bp.route("/log")
def log():
    """Lo que falló en los últimos días, de todas las llaves o de una."""
    account = current_account()
    db = get_db()
    mine = api_keys.for_account(db, account["_id"])
    wanted = as_id(request.args.get("llave"))
    chosen = wanted if any(one["_id"] == wanted for one in mine) else None
    names = {one["_id"]: one.get("name", "") for one in mine}
    return render_template(
        "developers/log.html", rows=api_log.recent(db, account["_id"], key_id=chosen),
        keys=mine, chosen=chosen, names=names, days=api_log.KEEP_DAYS, docs=docs_url())


# ------------------------------------------------------------ los correos

EMAILS_PER_PAGE = 50
# Lo que más dice de cada correo, de lo peor a lo mejor: lo primero que tenga.
OUTCOMES = (mail_events.COMPLAINT, mail_events.BOUNCE, mail_events.CLICK,
            mail_events.OPEN, mail_events.DELIVERED)


@bp.route("/emails")
def emails():
    """Los correos que mandó la API (octubre de 2026), 50 por página, con lo
    que pasó con cada uno. El asunto sale como se escribió: los datos de cada
    correo no se guardan."""
    account = current_account()
    db = get_db()
    query: dict = {"account_id": account["_id"]}
    before = as_id(request.args.get("antes"))
    if before is not None:
        query["_id"] = {"$lt": before}
    rows = list(db.messages.find(query).sort("_id", -1).limit(EMAILS_PER_PAGE + 1))
    more = len(rows) > EMAILS_PER_PAGE
    rows = rows[:EMAILS_PER_PAGE]
    counted = mail_events.counts_by_run(db, account["_id"], [one["_id"] for one in rows])
    for one in rows:
        seen = counted.get(one["_id"], {})
        one["outcome"] = next((kind for kind in OUTCOMES if seen.get(kind)), one["status"])
    return render_template(
        "developers/emails.html", rows=rows, docs=docs_url(),
        days=messages.KEEP_DAYS, next_page=rows[-1]["_id"] if more else None,
        older=before is not None)


# ------------------------------------------------------------ los avisos a su sistema
#
# Los webhooks (octubre de 2026): a dónde manda la cuenta lo que pasa con sus
# correos. Crear uno, cambiarle la dirección o el secreto pide la misma prueba
# que crear una llave: un aviso manda datos de la cuenta a un servidor, y quien
# encontró una sesión abierta no puede poner el suyo. El secreto se enseña una
# vez, en la respuesta que lo crea.

TESTS_PER_HOUR = 10


def code_asked(db, account) -> bool:
    """El código al correo, para quien no tiene contraseña. True si salió."""
    if account.get("password_hash") or not rate_limit(
            db, f"apiproof:code:{account['_id']}", 5, 3600):
        return False
    return notices.api_access_code(account, tokens.issue(db, account["_id"],
                                                         tokens.API_ACCESS))


def hook_form_values(form) -> dict:
    return {"url": form.get("url", "").strip()[:safe_http.URL_MAX + 1],
            "description": " ".join(form.get("description", "").split())[
                :hooks.DESCRIPTION_MAX],
            "events": [one for one in hooks.EVENTS if one in form.getlist("event")]}


def hook_errors(values: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        safe_http.check_url(values["url"])
    except safe_http.Refused as exc:
        errors["url"] = t("webhooks_url_" + str(exc))
    if not values["events"]:
        errors["event"] = t("webhooks_events_required")
    return errors


def secret_page(found, *, created: bool):
    """La única vez que se ve el secreto."""
    response = Response(render_template(
        "developers/webhook-secret.html", found=found, created=created,
        secret=webhooks.secret_of(found), docs=docs_url()))
    response.headers["Cache-Control"] = "no-store"
    return response


def own_hook(db, account, raw):
    return hooks.by_id(db, account["_id"], as_id(raw))


@bp.route("/webhooks")
def webhooks_list():
    account = current_account()
    db = get_db()
    return render_template(
        "developers/webhooks.html", hooks=hooks.for_account(db, account["_id"]),
        limit=hooks.LIMIT, docs=docs_url(), done=request.args.get("done", ""))


@bp.route("/webhooks/new", methods=["GET", "POST"])
@bp.route("/webhooks/<raw>/edit", methods=["GET", "POST"])
def webhook_form(raw=None):
    """Crear un aviso, o cambiarle la dirección, la descripción y los eventos.
    La prueba se pide al crear y al cambiar la dirección."""
    account = current_account()
    db = get_db()
    found = own_hook(db, account, raw) if raw else None
    if raw and found is None:
        return redirect(url_for("developers.webhooks_list"))
    errors: dict[str, str] = {}
    sent = False
    values = (hook_form_values(request.form) if request.method == "POST" else
              {"url": (found or {}).get("url", ""),
               "description": (found or {}).get("description", ""),
               "events": list((found or {}).get("events") or hooks.EVENTS)})
    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif request.form.get("action") == "code":
            sent = code_asked(db, account)
        elif found is None and len(hooks.for_account(db, account["_id"])) >= hooks.LIMIT:
            errors["form"] = t("webhooks_full", n=hooks.LIMIT)
        else:
            errors.update(hook_errors(values))
            moved = found is None or values["url"] != found.get("url")
            if moved and not proved(account) and not errors:
                errors.update(check_proof(db, account, request.form))
            if not errors:
                host = safe_http.check_url(values["url"])[0]
                if found is None:
                    new_id = hooks.create(db, account["_id"], url=values["url"], host=host,
                                          events=values["events"],
                                          description=values["description"])
                    notices.webhook_added(account, host=host, ip=client_ip())
                    return secret_page(hooks.by_id(db, account["_id"], new_id), created=True)
                hooks.update(db, account["_id"], found["_id"], url=values["url"], host=host,
                             events=values["events"], description=values["description"])
                if moved:
                    notices.webhook_added(account, host=host, ip=client_ip())
                return redirect(url_for("developers.webhook", raw=found["_id"], done="saved"))
    # La prueba se pide al guardar si la dirección cambió; cambiar los eventos
    # o la descripción no la pide.
    context = proof_context(account)
    return render_template(
        "developers/webhook-form.html", found=found, values=values, errors=errors,
        sent=sent, events=hooks.EVENTS, docs=docs_url(), **context)


@bp.route("/webhooks/<raw>")
def webhook(raw):
    """Un aviso: su estado, sus botones y las últimas 50 entregas."""
    account = current_account()
    db = get_db()
    found = own_hook(db, account, raw)
    if found is None:
        return redirect(url_for("developers.webhooks_list"))
    return render_template(
        "developers/webhook.html", found=found, docs=docs_url(),
        deliveries=hooks.recent(db, account["_id"], found["_id"]),
        done=request.args.get("done", ""), tested=request.args.get("prueba", ""),
        tested_status=request.args.get("estado", "")[:3],
        tested_ms=request.args.get("ms", "")[:6],
        tested_error=request.args.get("error", "")[:60])


@bp.route("/webhooks/<raw>/switch", methods=["POST"])
def webhook_switch(raw):
    account = current_account()
    db = get_db()
    found = own_hook(db, account, raw)
    if found is not None and csrf_ok(request.form.get("csrf_token")):
        on = not found.get("enabled")
        changes = {"enabled": on, "disabled_reason": None}
        if on:
            changes.update(failing_since=None, next_try_at=None)
        hooks.update(db, account["_id"], found["_id"], **changes)
        return redirect(url_for("developers.webhook", raw=found["_id"],
                                done="on" if on else "off"))
    return redirect(url_for("developers.webhooks_list"))


@bp.route("/webhooks/<raw>/test", methods=["POST"])
def webhook_test(raw):
    """Un aviso de prueba, en el momento: dice qué respondió y cuánto tardó."""
    account = current_account()
    db = get_db()
    found = own_hook(db, account, raw)
    if found is None or not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("developers.webhooks_list"))
    if not rate_limit(db, f"webhooktest:{account['_id']}", TESTS_PER_HOUR, 3600):
        return redirect(url_for("developers.webhook", raw=found["_id"], prueba="many"))
    answer = webhooks.attempt(found, webhooks.test_payload())
    return redirect(url_for("developers.webhook", raw=found["_id"],
                            prueba="ok" if answer.ok else "bad",
                            estado=answer.status or "", ms=answer.ms,
                            error=answer.error[:60]))


@bp.route("/webhooks/<raw>/secret", methods=["GET", "POST"])
def webhook_secret(raw):
    """Cambiar el secreto (el de antes deja de servir) y verlo una vez."""
    account = current_account()
    db = get_db()
    found = own_hook(db, account, raw)
    if found is None:
        return redirect(url_for("developers.webhooks_list"))
    errors: dict[str, str] = {}
    sent = False
    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif request.form.get("action") == "code":
            sent = code_asked(db, account)
        else:
            if not proved(account):
                errors.update(check_proof(db, account, request.form))
            if not errors:
                hooks.rotate(db, account["_id"], found["_id"])
                return secret_page(hooks.by_id(db, account["_id"], found["_id"]),
                                   created=False)
    return render_template("developers/webhook-ask.html", found=found, errors=errors,
                           sent=sent, what="secret", **proof_context(account))


@bp.route("/webhooks/<raw>/delete", methods=["GET", "POST"])
def webhook_delete(raw):
    account = current_account()
    db = get_db()
    found = own_hook(db, account, raw)
    if found is None:
        return redirect(url_for("developers.webhooks_list"))
    if request.method == "POST" and csrf_ok(request.form.get("csrf_token")):
        hooks.remove(db, account["_id"], found["_id"])
        return redirect(url_for("developers.webhooks_list", done="deleted"))
    return render_template("developers/webhook-ask.html", found=found, errors={},
                           sent=False, what="delete", needs_proof=False,
                           with_password=False, two_step=False)
