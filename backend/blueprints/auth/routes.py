"""Registration, email confirmation and session.

Three rules run through the whole file:

  * The screen never reveals whether an address has an account. Registering and
    resending answer identically either way; the owner of an existing address is
    told by email instead.
  * The token in a link is only ever compared as a hash, and it is spent once.
  * Every attempt is recorded in auth_events, with what really happened. The log
    knows more than the screen says, and that is the point: it is the audit
    trail, read only by the admin.
"""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from email_validator import EmailNotValidError, validate_email
from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)

from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import auth_event as events
from models import mail_log
from models import token as tokens
from services import mailer
from services.security import (csrf_ok, password_problem, rate_limit,
                               verify_password)

bp = Blueprint("auth", __name__)

# Per address and per IP, so one noisy visitor cannot spend someone else's
# budget. Cloudflare filters in front; this is the second layer.
REGISTER_PER_IP = (10, 3600)
RESEND_PER_EMAIL = (5, 3600)
RESEND_PER_IP = (15, 3600)
LOGIN_PER_IP = (20, 900)


def session_account_id():
    """The signed-in account's id as an ObjectId, or None.

    The session cookie can only hold JSON, so the id lives there as text while
    every collection stores the real ObjectId. Converting in one place keeps the
    two types from getting mixed in the same field.
    """
    raw = session.get("account_id")
    if not raw:
        return None
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def current_account() -> dict | None:
    """The signed-in account, or None. Also drops a session whose account was
    deleted, or whose password changed after it was issued."""
    account_id = session_account_id()
    if account_id is None:
        return None
    account = accounts.by_id(get_db(), account_id)
    if account is None or account.get("session_version", 1) != session.get("session_version"):
        session.clear()
        return None
    return account


def client_ip() -> str:
    # Cloudflare sits in front in production and sets this header.
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"


def clean_email(raw: str) -> str | None:
    try:
        return validate_email(raw, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def log_auth(db, kind: str, outcome: str, *, email: str = "",
             account_id=None) -> None:
    """Record one attempt.

    Never raises. The audit trail is worth having, but not at the price of
    turning a request that otherwise worked into an error page.
    """
    try:
        events.record(db, kind=kind, outcome=outcome, email=email,
                      account_id=account_id, ip=client_ip(),
                      user_agent=request.headers.get("User-Agent", ""))
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [auth_events] no se pudo registrar el intento: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)


def send_confirmation(db, account: dict) -> None:
    raw = tokens.issue(db, account["_id"])
    link = f"{Config.APP_BASE_URL}{url_for('auth.confirm', token=raw)}"
    hours = Config.CONFIRMATION_TOKEN_HOURS
    mailer.send(
        to=account["email"],
        subject=t("mail_confirm_subject"),
        html=render_template("email/confirm.html", link=link, hours=hours),
        text=render_template("email/confirm.txt", link=link, hours=hours),
        purpose=mail_log.CONFIRM,
        account_id=account["_id"],
    )


def send_already_registered(db, account: dict) -> None:
    """Tell the owner, because the screen cannot."""
    link = f"{Config.APP_BASE_URL}{url_for('auth.login')}"
    mailer.send(
        to=account["email"],
        subject=t("mail_exists_subject"),
        html=render_template("email/exists.html", link=link),
        text=render_template("email/exists.txt", link=link),
        purpose=mail_log.EXISTS,
        account_id=account["_id"],
    )


def deliver(db, send, account: dict, *, kind: str) -> None:
    """Send a system email without letting a failure break the request.

    The account already exists by the time this runs, and an unreachable mail
    provider cannot undo it — nor change what the visitor is told, since rule 7
    requires the same screen either way. mail_log keeps the row with the real
    error; this adds one auth_event so the failure shows up beside the attempt
    it belongs to.
    """
    try:
        send(db, account)
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [mailer] no se pudo enviar el correo a {account.get('email')}: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)
        log_auth(db, kind, events.MAIL_FAILED, email=account.get("email", ""),
                 account_id=account.get("_id"))


# ------------------------------------------------------------------- register

@bp.route("/registro", methods=["GET", "POST"])
def register():
    if session.get("account_id"):
        return redirect(url_for("auth.panel"))

    form = {"company_name": "", "contact_name": "", "email": "", "phone": ""}
    errors: dict[str, str] = {}

    if request.method == "POST":
        db = get_db()
        form = {k: request.form.get(k, "").strip() for k in form}
        password = request.form.get("password", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.REGISTER, events.CSRF_FAILED, email=form["email"])
        elif not rate_limit(db, f"register:ip:{client_ip()}", *REGISTER_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.REGISTER, events.RATE_LIMITED, email=form["email"])
        else:
            if not form["company_name"]:
                errors["company_name"] = t("error_required")
            if not form["contact_name"]:
                errors["contact_name"] = t("error_required")

            email = clean_email(form["email"]) if form["email"] else None
            if not form["email"]:
                errors["email"] = t("error_required")
            elif not email:
                errors["email"] = t("error_email_invalid")

            problem = password_problem(password)
            if problem == "too_short":
                errors["password"] = t("error_password_short")
            elif problem == "too_long":
                errors["password"] = t("error_password_long")

            if errors:
                log_auth(db, events.REGISTER, events.INVALID, email=form["email"])
            else:
                created = accounts.create(
                    db,
                    company_name=form["company_name"],
                    contact_name=form["contact_name"],
                    email=email,
                    password=password,
                    phone=form["phone"],
                )
                if created:
                    log_auth(db, events.REGISTER, events.CREATED, email=email,
                             account_id=created["_id"])
                    deliver(db, send_confirmation, created, kind=events.REGISTER)
                else:
                    # Address already registered. Same screen either way; only
                    # the log and the owner's inbox know the difference.
                    existing = accounts.by_email(db, email)
                    log_auth(db, events.REGISTER, events.ALREADY_REGISTERED,
                             email=email,
                             account_id=existing["_id"] if existing else None)
                    if existing:
                        deliver(db, send_already_registered, existing,
                                kind=events.REGISTER)
                return redirect(url_for("auth.sent"))

    return render_template("register.html", form=form, errors=errors)


@bp.route("/revisa-tu-correo")
def sent():
    return render_template("sent.html", hours=Config.CONFIRMATION_TOKEN_HOURS)


# -------------------------------------------------------------------- confirm

@bp.route("/confirmar/<token>")
def confirm(token: str):
    db = get_db()
    reason, doc = tokens.check(db, token)

    def done(state: str, account: dict | None = None, **extra):
        """Record the outcome, then draw it. The log stores the same four
        states the visitor is shown, so the two never disagree."""
        log_auth(db, events.CONFIRM, state,
                 email=(account or {}).get("email", ""),
                 account_id=(account or {}).get("_id"))
        return render_template("confirm.html", state=state, **extra)

    if reason == tokens.VALID:
        if not tokens.spend(db, doc):
            # Someone used the same link a moment ago.
            return done("already")
        account = accounts.by_id(db, doc["account_id"])
        confirmed_now = accounts.confirm_email(db, doc["account_id"]) if account else False
        return done("ok" if confirmed_now else "already", account)

    if reason == tokens.USED:
        account = accounts.by_id(db, doc["account_id"])
        if accounts.is_confirmed(account):
            return done("already", account)
        return done("unknown", account)

    if reason == tokens.EXPIRED:
        return done("expired", hours=Config.CONFIRMATION_TOKEN_HOURS)

    return done("unknown")


@bp.route("/reenviar-confirmacion", methods=["GET", "POST"])
def resend():
    errors: dict[str, str] = {}
    email_value = ""

    if request.method == "POST":
        db = get_db()
        email_value = request.form.get("email", "").strip()

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.RESEND, events.CSRF_FAILED, email=email_value)
        elif not rate_limit(db, f"resend:ip:{client_ip()}", *RESEND_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.RESEND, events.RATE_LIMITED, email=email_value)
        else:
            email = clean_email(email_value) if email_value else None
            if not email:
                errors["email"] = t("error_email_invalid")
                log_auth(db, events.RESEND, events.INVALID, email=email_value)
            else:
                # Silently skipped when over budget: the answer must not depend
                # on whether this address exists or how often it was asked for.
                if not rate_limit(db, f"resend:mail:{accounts.normalize_email(email)}",
                                  *RESEND_PER_EMAIL):
                    log_auth(db, events.RESEND, events.RATE_LIMITED, email=email)
                else:
                    existing = accounts.by_email(db, email)
                    if existing is None:
                        log_auth(db, events.RESEND, events.NO_ACCOUNT, email=email)
                    elif accounts.is_confirmed(existing):
                        log_auth(db, events.RESEND, events.ALREADY_CONFIRMED,
                                 email=email, account_id=existing["_id"])
                    else:
                        log_auth(db, events.RESEND, events.SENT, email=email,
                                 account_id=existing["_id"])
                        deliver(db, send_confirmation, existing,
                                kind=events.RESEND)
                return redirect(url_for("auth.sent"))

    return render_template("resend.html", errors=errors, email=email_value)


# ---------------------------------------------------------------------- login

@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if session.get("account_id"):
        return redirect(url_for("auth.panel"))

    errors: dict[str, str] = {}
    email_value = ""

    if request.method == "POST":
        db = get_db()
        email_value = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.LOGIN, events.CSRF_FAILED, email=email_value)
        elif not rate_limit(db, f"login:ip:{client_ip()}", *LOGIN_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.LOGIN, events.RATE_LIMITED, email=email_value)
        else:
            account = accounts.by_email(db, email_value) if email_value else None
            # Called even when there is no account, so a wrong address and a
            # wrong password take a similar amount of time.
            if verify_password(password, account and account.get("password_hash")):
                session.clear()
                session["account_id"] = str(account["_id"])
                session["session_version"] = account.get("session_version", 1)
                session.permanent = True
                accounts.touch_login(db, account["_id"])
                log_auth(db, events.LOGIN, events.OK, email=email_value,
                         account_id=account["_id"])
                return redirect(url_for("auth.panel"))
            errors["form"] = t("error_login_failed")
            # One outcome for both halves of the failure, because the visitor is
            # told one thing. The account_id is still filled in when the address
            # does exist: that distinction belongs in the audit trail, which only
            # the admin reads, and it is what makes a brute-force attempt against
            # a real account visible.
            log_auth(db, events.LOGIN, events.BAD_CREDENTIALS, email=email_value,
                     account_id=account["_id"] if account else None)

    return render_template("login.html", errors=errors, email=email_value)


@bp.route("/salir", methods=["POST"])
def logout():
    # The session holds the id as text; the log stores ObjectId everywhere else,
    # so convert rather than mix the two types in one field.
    account_id = session_account_id()
    if csrf_ok(request.form.get("csrf_token")):
        session.clear()
        log_auth(get_db(), events.LOGOUT, events.OK, account_id=account_id)
    else:
        log_auth(get_db(), events.LOGOUT, events.CSRF_FAILED, account_id=account_id)
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------- panel

@bp.route("/panel")
def panel():
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    return render_template("panel.html", account=account,
                           confirmed=accounts.is_confirmed(account))
