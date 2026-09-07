"""Registration, email confirmation and session.

Two rules run through the whole file:

  * The screen never reveals whether an address has an account. Registering and
    resending answer identically either way; the owner of an existing address is
    told by email instead.
  * The token in a link is only ever compared as a hash, and it is spent once.
"""

from __future__ import annotations

from email_validator import EmailNotValidError, validate_email
from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)

from config import Config
from db import get_db
from i18n import t
from models import account as accounts
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


def current_account() -> dict | None:
    """The signed-in account, or None. Also drops a session whose account was
    deleted, or whose password changed after it was issued."""
    account_id = session.get("account_id")
    if not account_id:
        return None
    from bson import ObjectId
    try:
        account = accounts.by_id(get_db(), ObjectId(account_id))
    except Exception:
        account = None
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


def send_confirmation(db, account: dict) -> None:
    raw = tokens.issue(db, account["_id"])
    link = f"{Config.APP_BASE_URL}{url_for('auth.confirm', token=raw)}"
    hours = Config.CONFIRMATION_TOKEN_HOURS
    mailer.send(
        to=account["email"],
        subject=t("mail_confirm_subject"),
        html=render_template("email/confirm.html", link=link, hours=hours),
        text=render_template("email/confirm.txt", link=link, hours=hours),
    )


def send_already_registered(db, account: dict) -> None:
    """Tell the owner, because the screen cannot."""
    link = f"{Config.APP_BASE_URL}{url_for('auth.login')}"
    mailer.send(
        to=account["email"],
        subject=t("mail_exists_subject"),
        html=render_template("email/exists.html", link=link),
        text=render_template("email/exists.txt", link=link),
    )


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
        elif not rate_limit(db, f"register:ip:{client_ip()}", *REGISTER_PER_IP):
            errors["form"] = t("error_too_many")
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

            if not errors:
                created = accounts.create(
                    db,
                    company_name=form["company_name"],
                    contact_name=form["contact_name"],
                    email=email,
                    password=password,
                    phone=form["phone"],
                )
                if created:
                    send_confirmation(db, created)
                else:
                    # Address already registered. Same screen either way.
                    existing = accounts.by_email(db, email)
                    if existing:
                        send_already_registered(db, existing)
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

    if reason == tokens.VALID:
        if not tokens.spend(db, doc):
            # Someone used the same link a moment ago.
            return render_template("confirm.html", state="already")
        account = accounts.by_id(db, doc["account_id"])
        confirmed_now = accounts.confirm_email(db, doc["account_id"]) if account else False
        return render_template("confirm.html", state="ok" if confirmed_now else "already")

    if reason == tokens.USED:
        account = accounts.by_id(db, doc["account_id"])
        if accounts.is_confirmed(account):
            return render_template("confirm.html", state="already")
        return render_template("confirm.html", state="unknown")

    if reason == tokens.EXPIRED:
        return render_template("confirm.html", state="expired",
                               hours=Config.CONFIRMATION_TOKEN_HOURS)

    return render_template("confirm.html", state="unknown")


@bp.route("/reenviar-confirmacion", methods=["GET", "POST"])
def resend():
    errors: dict[str, str] = {}
    email_value = ""

    if request.method == "POST":
        db = get_db()
        email_value = request.form.get("email", "").strip()

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not rate_limit(db, f"resend:ip:{client_ip()}", *RESEND_PER_IP):
            errors["form"] = t("error_too_many")
        else:
            email = clean_email(email_value) if email_value else None
            if not email:
                errors["email"] = t("error_email_invalid")
            else:
                # Silently skipped when over budget: the answer must not depend
                # on whether this address exists or how often it was asked for.
                if rate_limit(db, f"resend:mail:{accounts.normalize_email(email)}",
                              *RESEND_PER_EMAIL):
                    existing = accounts.by_email(db, email)
                    if existing and not accounts.is_confirmed(existing):
                        send_confirmation(db, existing)
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
        elif not rate_limit(db, f"login:ip:{client_ip()}", *LOGIN_PER_IP):
            errors["form"] = t("error_too_many")
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
                return redirect(url_for("auth.panel"))
            errors["form"] = t("error_login_failed")

    return render_template("login.html", errors=errors, email=email_value)


@bp.route("/salir", methods=["POST"])
def logout():
    if csrf_ok(request.form.get("csrf_token")):
        session.clear()
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------- panel

@bp.route("/panel")
def panel():
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    return render_template("panel.html", account=account,
                           confirmed=accounts.is_confirmed(account))
