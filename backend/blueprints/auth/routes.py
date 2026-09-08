"""Registration, email confirmation and session.

Four rules run through the whole file:

  * The screen never reveals whether an address has an account. Registering and
    resending answer identically either way; the owner of an existing address is
    told by email instead. This is what shapes the confirmation screen: every
    wrong code gets the same answer, whether or not a code was ever issued.
  * A confirmation code is only ever compared as a hash, and it is spent once.
  * If the email cannot be sent, a registration is undone. An account that
    exists but can never be confirmed is worse than no account at all.
  * Every attempt is recorded in auth_events, with what really happened. The log
    knows more than the screen says, and that is the point: it is the audit
    trail, read only by the admin.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import ip_address

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
from models import session as sessions
from models import token as tokens
from services import mailer
from services.security import (csrf_ok, hash_password, now as security_now,
                               password_problem, rate_limit, verify_password)

bp = Blueprint("auth", __name__)

# Per address and per IP, so one noisy visitor cannot spend someone else's
# budget. Cloudflare filters in front; this is the second layer.
REGISTER_PER_IP = (10, 3600)
RESEND_PER_EMAIL = (5, 3600)
RESEND_PER_IP = (15, 3600)
LOGIN_PER_IP = (20, 900)
CONFIRM_PER_IP = (30, 900)
PASSWORD_PER_IP = (10, 900)
RECOVER_PER_IP = (10, 3600)
RECOVER_PER_EMAIL = (5, 3600)
# Registering with someone else's address sends them a notice. Without a budget
# per address, that is a way to fill a stranger's inbox from many machines, so
# the notice has one of its own, separate from the per-IP budget.
REGISTER_PER_EMAIL = (5, 3600)

# What to tell someone about their password. The rules themselves live in
# services/security.py; this only names them in Spanish.
PASSWORD_MESSAGES = {
    "too_short": "error_password_short",
    "too_long": "error_password_long",
    "no_upper": "error_password_upper",
    "no_digit": "error_password_digit",
    "no_symbol": "error_password_symbol",
}

# The account waiting for a code, and how many times this browser has got it
# wrong. The counter lives in the session as well as on the code document
# because the screen has to answer the same way when there is no code at all.
PENDING_KEY = "pending_account_id"
ATTEMPTS_KEY = "confirm_attempts"
DEADLINE_KEY = "code_expires_at"
# Recovering a password walks the same three steps as confirming an address, so
# it keeps its own copies of them: whose code it is, how many tries are left,
# until when, and —once the code is right— that this browser proved it.
RESET_KEY = "reset_account_id"
RESET_ATTEMPTS = "reset_attempts"
RESET_DEADLINE = "reset_expires_at"
RESET_VERIFIED = "reset_verified_for"
# Lo único que identifica una sesión: el resto vive en la colección sessions.
SESSION_KEY = "sid"


def current_session():
    """The live session document behind this request's cookie, or None.

    The cookie carries an identifier and nothing else. Everything worth knowing
    —which account, since when, from which device, and whether it was closed
    from another one— lives in the sessions collection, which is what makes it
    possible to shut one device without touching the rest.
    """
    return sessions.find(get_db(), session.get(SESSION_KEY))


def session_account_id():
    """The signed-in account's id, or None."""
    doc = current_session()
    return doc["account_id"] if doc else None


def as_object_id(raw):
    if not raw:
        return None
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def current_account() -> dict | None:
    """The signed-in account, or None.

    A cookie whose session was closed from another device, or that outlived it,
    is cleared here: it will never be good again and keeping it only delays the
    sign-in screen.
    """
    doc = current_session()
    if doc is None:
        if session.get(SESSION_KEY):
            session.clear()
        return None
    account = accounts.by_id(get_db(), doc["account_id"])
    if account is None:
        session.clear()
        return None
    sessions.touch(get_db(), doc)
    return account


def sign_in(account: dict, *, remember: bool = True) -> None:
    """Open a session for this device.

    `remember` decides two lifetimes at once: the cookie's —permanent, or gone
    when the browser closes— and the document's. The document is the one that
    counts, because a browser is free to keep a cookie longer than it was told.
    """
    session.clear()
    session[SESSION_KEY] = sessions.start(
        get_db(), account["_id"], ip=client_ip(),
        user_agent=request.headers.get("User-Agent", ""), remember=remember)
    session.permanent = remember


def await_code(account_id=None) -> None:
    """Start the wait for a code: which account it belongs to, if any, and the
    deadline the screen counts down to.

    The deadline is written even when no code was issued —an address that was
    already taken, a resend for one that does not exist— because the screen has
    to look the same in every case. A countdown that only appeared when a code
    was really sent would answer, without saying it, the one question rule 7
    forbids: whether that address has an account.

    What it shows is not what decides: the code's real expiry is in
    account_tokens, and the server checks that one.
    """
    if account_id is not None:
        session[PENDING_KEY] = str(account_id)
    session[ATTEMPTS_KEY] = 0
    session[DEADLINE_KEY] = (security_now() + timedelta(
        minutes=Config.CONFIRMATION_CODE_MINUTES)).isoformat()


def await_reset(account_id=None) -> None:
    """The same wait as await_code(), for the recovery code."""
    if account_id is not None:
        session[RESET_KEY] = str(account_id)
    session[RESET_ATTEMPTS] = 0
    session[RESET_DEADLINE] = (security_now() + timedelta(
        minutes=Config.CONFIRMATION_CODE_MINUTES)).isoformat()


def seconds_left(key: str = DEADLINE_KEY) -> int:
    """How long the screen says is left. Never negative."""
    raw = session.get(key)
    if not raw:
        return 0
    try:
        deadline = datetime.fromisoformat(raw)
    except ValueError:
        return 0
    return max(0, int((deadline - security_now()).total_seconds()))


def client_ip() -> str:
    """The visitor's address, for the rate limit counters.

    Cloudflare sits in front in production and puts the real address in
    CF-Connecting-IP; without it every visitor would arrive as the proxy and
    share one budget. The header is checked for being an actual IP before it is
    used, because it arrives from outside: anything else would let a caller
    write whatever it liked into the keys of the rate_limits collection.
    """
    claimed = request.headers.get("CF-Connecting-IP", "")[:64].strip()
    if claimed:
        try:
            return str(ip_address(claimed))
        except ValueError:
            pass  # not an address: fall back to the connection itself
    return request.remote_addr or "unknown"


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
    code = tokens.issue(db, account["_id"])
    minutes = Config.CONFIRMATION_CODE_MINUTES
    mailer.send(
        to=account["email"],
        # The code goes in the subject too: on a phone it is readable from the
        # notification, without opening anything.
        subject=t("mail_confirm_subject", code=code),
        html=render_template("email/confirm.html", code=code, minutes=minutes),
        text=render_template("email/confirm.txt", code=code, minutes=minutes),
        purpose=mail_log.CONFIRM,
        account_id=account["_id"],
    )


def send_welcome(db, account: dict) -> None:
    """The message that closes a registration.

    Says the two things nobody guesses: that the account now exists, and that
    sending is still off until it is approved by hand.
    """
    panel = f"{Config.APP_BASE_URL}{url_for('auth.panel')}"
    mailer.send(
        to=account["email"],
        subject=t("mail_welcome_subject"),
        html=render_template("email/welcome.html", name=account["contact_name"],
                             panel=panel),
        text=render_template("email/welcome.txt", name=account["contact_name"],
                             panel=panel),
        purpose=mail_log.WELCOME,
        account_id=account["_id"],
    )


def send_recovery(db, account: dict) -> None:
    code = tokens.issue(db, account["_id"], purpose=tokens.PASSWORD_RESET)
    minutes = Config.CONFIRMATION_CODE_MINUTES
    mailer.send(
        to=account["email"],
        subject=t("mail_recover_subject", code=code),
        html=render_template("email/recover.html", code=code, minutes=minutes),
        text=render_template("email/recover.txt", code=code, minutes=minutes),
        purpose=mail_log.RECOVER,
        account_id=account["_id"],
    )


def send_new_login(db, account: dict, session_doc: dict) -> None:
    """Tell the owner that somebody signed in from a device never used before.

    The one message that matters when it was not them, so it carries what they
    need to recognise it —device, address, when— and a way out that does not
    require remembering the password, which is precisely what cannot be assumed
    here.
    """
    raw = tokens.issue_link(db, account["_id"], tokens.SESSION_REVOKE,
                            {"session_id": str(session_doc["_id"])})
    link = f"{Config.APP_BASE_URL}{url_for('auth.close_from_email', token=raw)}"
    recover = f"{Config.APP_BASE_URL}{url_for('auth.recover')}"
    who = sessions.describe(session_doc.get("user_agent"))
    device = (t("device_on", browser=who["browser"], system=who["system"])
              if who["browser"] and who["system"]
              else (who["browser"] or who["system"] or t("device_unknown")))
    mailer.send(
        to=account["email"],
        subject=t("mail_login_subject"),
        html=render_template("email/new-login.html", device=device,
                             ip=session_doc.get("ip", ""), link=link,
                             recover=recover),
        text=render_template("email/new-login.txt", device=device,
                             ip=session_doc.get("ip", ""), link=link,
                             recover=recover),
        purpose=mail_log.NEW_LOGIN,
        account_id=account["_id"],
    )


def send_password_changed(db, account: dict) -> None:
    """Tell the owner that the password just changed.

    The one message that matters when it was not them: it is the only warning
    someone gets that another person is inside their account.
    """
    panel = f"{Config.APP_BASE_URL}{url_for('auth.panel')}"
    mailer.send(
        to=account["email"],
        subject=t("mail_password_subject"),
        html=render_template("email/password-changed.html",
                             name=account["contact_name"], panel=panel),
        text=render_template("email/password-changed.txt",
                             name=account["contact_name"], panel=panel),
        purpose=mail_log.PASSWORD_CHANGED,
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


def deliver(db, send, account: dict, *, kind: str) -> bool:
    """Send a system email. True if it went out.

    The caller decides what a failure means — the registration undoes itself,
    the resend only says so — but neither may let the exception escape: an
    unreachable provider used to reach the visitor as a bare 502. mail_log keeps
    the row with the real error; this adds one auth_event so the failure shows up
    beside the attempt it belongs to.
    """
    try:
        send(db, account)
        return True
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [mailer] no se pudo enviar el correo a {account.get('email')}: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)
        log_auth(db, kind, events.MAIL_FAILED, email=account.get("email", ""),
                 account_id=account.get("_id"))
        return False


# ------------------------------------------------------------------- register

@bp.route("/registro", methods=["GET", "POST"])
def register():
    if current_session():
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
            if problem:
                errors["password"] = t(PASSWORD_MESSAGES[problem])

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
                    if not deliver(db, send_confirmation, created,
                                   kind=events.REGISTER):
                        # Undo it. The address is free again and whoever tried
                        # can register once the mail provider answers.
                        tokens.discard(db, created["_id"])
                        accounts.delete(db, created["_id"])
                        errors["form"] = t("error_mail_failed")
                        return render_template("register.html", form=form,
                                               errors=errors)
                    await_code(created["_id"])
                else:
                    # The address is taken, and the screen says so. Rule 7 in
                    # CLAUDE.md no longer covers this form: hiding it here left
                    # people staring at a code that was never coming. Signing in
                    # and recovering still give nothing away.
                    existing = accounts.by_email(db, email)
                    log_auth(db, events.REGISTER, events.ALREADY_REGISTERED,
                             email=email,
                             account_id=existing["_id"] if existing else None)
                    if existing and rate_limit(
                            db, f"register:mail:{accounts.normalize_email(email)}",
                            *REGISTER_PER_EMAIL):
                        # The notice keeps its own budget per address: telling
                        # the owner is one thing, letting a stranger fill their
                        # inbox from this form is another.
                        deliver(db, send_already_registered, existing,
                                kind=events.REGISTER)
                    errors["email"] = t("error_email_taken")
                    return render_template("register.html", form=form,
                                           errors=errors)
                return redirect(url_for("auth.confirm"))

    return render_template("register.html", form=form, errors=errors)


# -------------------------------------------------------------------- confirm

@bp.route("/confirmar", methods=["GET", "POST"])
def confirm():
    """Ask for the six digit code and check it.

    Every refusal reads the same — a wrong code, an expired one, and an account
    that never had one all get one message — because the difference between them
    is exactly what rule 7 forbids showing. The real reason goes to auth_events.
    """
    errors: dict[str, str] = {}
    account_id = as_object_id(session.get(PENDING_KEY))

    if request.method == "POST":
        db = get_db()
        # Six boxes share the name, so the code arrives in pieces. A single
        # field still works: getlist() returns a list of one.
        typed = "".join(request.form.getlist("code"))

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.CONFIRM, events.CSRF_FAILED, account_id=account_id)
        elif not rate_limit(db, f"confirm:ip:{client_ip()}", *CONFIRM_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.CONFIRM, events.RATE_LIMITED, account_id=account_id)
        else:
            attempts = session.get(ATTEMPTS_KEY, 0) + 1
            session[ATTEMPTS_KEY] = attempts

            if account_id is None:
                reason, doc = tokens.UNKNOWN, None
            else:
                reason, doc = tokens.check(db, account_id, typed)

            # With no code on file the document cannot run out of tries, so the
            # session counter stands in for it. Otherwise an address that has a
            # code and one that does not would start answering differently.
            if reason in (tokens.UNKNOWN, tokens.INVALID) and attempts >= tokens.MAX_ATTEMPTS:
                reason = tokens.TOO_MANY

            if reason == tokens.VALID:
                account = accounts.by_id(db, account_id)
                if account is None:
                    reason = tokens.UNKNOWN
                elif not tokens.spend(db, doc):
                    # Someone typed the same code a moment ago.
                    reason = tokens.USED
                else:
                    accounts.confirm_email(db, account_id)
                    log_auth(db, events.CONFIRM, events.OK,
                             email=account["email"], account_id=account_id)
                    # The opposite of registration: a failure here undoes
                    # nothing and locks nobody out. The account is confirmed
                    # already and the session opens either way; the failure is
                    # written down and that is all.
                    deliver(db, send_welcome, account, kind=events.CONFIRM)
                    sign_in(account)
                    return redirect(url_for("auth.panel"))

            if reason == tokens.USED:
                errors["form"] = t("error_code_used")
            elif reason == tokens.TOO_MANY:
                errors["form"] = t("error_code_too_many")
            else:
                errors["form"] = t("error_code_invalid")
            log_auth(db, events.CONFIRM, events.CONFIRM_OUTCOMES[reason],
                     account_id=account_id)

    return render_template("confirm.html", errors=errors,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left())


@bp.route("/confirmar/corregir", methods=["GET", "POST"])
def correct_email():
    """Fix the address of an account that has not been confirmed yet.

    Typing the address wrong used to be a dead end: the account exists under the
    address with the mistake, so asking for another code with the right one
    finds nothing and says nothing —rule 7 forbids it— and the code goes on
    arriving at a mailbox that is not yours.

    Only for the account this browser is waiting on, and only while it is
    unconfirmed. Changing the address of a finished account is another matter
    and deserves its own screen.
    """
    db = get_db()
    account_id = as_object_id(session.get(PENDING_KEY))
    account = accounts.by_id(db, account_id) if account_id else None
    if account is None or accounts.is_confirmed(account):
        return redirect(url_for("auth.confirm"))

    errors: dict[str, str] = {}
    email_value = account["email"]

    if request.method == "POST":
        email_value = request.form.get("email", "").strip()

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.CORRECT_EMAIL, events.CSRF_FAILED,
                     account_id=account_id)
        elif not rate_limit(db, f"correct:ip:{client_ip()}", *REGISTER_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.CORRECT_EMAIL, events.RATE_LIMITED,
                     account_id=account_id)
        else:
            email = clean_email(email_value) if email_value else None
            if not email:
                errors["email"] = t("error_email_invalid")
                log_auth(db, events.CORRECT_EMAIL, events.INVALID,
                         email=email_value, account_id=account_id)
            elif accounts.by_email(db, email) and \
                    accounts.normalize_email(email) != account["email_normalized"]:
                errors["email"] = t("error_email_taken")
                log_auth(db, events.CORRECT_EMAIL, events.TAKEN, email=email,
                         account_id=account_id)
            elif not rate_limit(db, f"register:mail:{accounts.normalize_email(email)}",
                                *REGISTER_PER_EMAIL):
                # This screen sends mail to an address typed by hand, exactly
                # like the registration form, so it shares its budget: nobody
                # gets to fill a stranger's inbox by correcting the address over
                # and over.
                log_auth(db, events.CORRECT_EMAIL, events.RATE_LIMITED,
                         email=email, account_id=account_id)
                await_code(account_id)
                return redirect(url_for("auth.confirm"))
            elif not accounts.change_email(db, account_id, email):
                errors["email"] = t("error_email_taken")
                log_auth(db, events.CORRECT_EMAIL, events.TAKEN, email=email,
                         account_id=account_id)
            else:
                # issue() throws the old code away, so the one that went to the
                # wrong address stops working at this moment.
                account = accounts.by_id(db, account_id)
                deliver(db, send_confirmation, account, kind=events.CORRECT_EMAIL)
                log_auth(db, events.CORRECT_EMAIL, events.OK, email=email,
                         account_id=account_id)
                await_code(account_id)
                return redirect(url_for("auth.confirm"))

    return render_template("correct-email.html", errors=errors, email=email_value)


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
                    await_code()
                else:
                    existing = accounts.by_email(db, email)
                    if existing is None:
                        log_auth(db, events.RESEND, events.NO_ACCOUNT, email=email)
                        # Whatever the session was waiting for, it is not this
                        # address. Dropping the pointer changes nothing on
                        # screen —the three cases look the same— and stops the
                        # session from holding an account nobody asked about.
                        session.pop(PENDING_KEY, None)
                        await_code()
                    elif accounts.is_confirmed(existing):
                        log_auth(db, events.RESEND, events.ALREADY_CONFIRMED,
                                 email=email, account_id=existing["_id"])
                        session.pop(PENDING_KEY, None)
                        await_code()
                    else:
                        # A failure here is not shown: for an address with no
                        # account nothing is sent either, so an error message
                        # would be the difference between the two cases. It goes
                        # to mail_log, where it belongs.
                        deliver(db, send_confirmation, existing,
                                kind=events.RESEND)
                        log_auth(db, events.RESEND, events.SENT, email=email,
                                 account_id=existing["_id"])
                        await_code(existing["_id"])
                return redirect(url_for("auth.confirm"))

    return render_template("resend.html", errors=errors, email=email_value)


# ---------------------------------------------------------------------- login

@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_session():
        return redirect(url_for("auth.panel"))

    errors: dict[str, str] = {}
    email_value = ""
    # Ticked by default the first time; after a failure, whatever was left.
    remember = True

    if request.method == "POST":
        db = get_db()
        email_value = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

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
                # Asked before opening the session: once it exists, this device
                # is one this account has used.
                first_time = not sessions.is_known_device(
                    db, account["_id"], request.headers.get("User-Agent", ""))
                sign_in(account, remember=bool(request.form.get("remember")))
                accounts.touch_login(db, account["_id"])
                log_auth(db, events.LOGIN, events.OK, email=email_value,
                         account_id=account["_id"])
                if first_time:
                    # A failure here cannot keep anyone out of their own
                    # account: it is a warning, not a gate.
                    here = current_session()
                    if here:
                        deliver(db, lambda d, a: send_new_login(d, a, here),
                                account, kind=events.LOGIN)
                return redirect(url_for("auth.panel"))
            errors["form"] = t("error_login_failed")
            # One outcome for both halves of the failure, because the visitor is
            # told one thing. The account_id is still filled in when the address
            # does exist: that distinction belongs in the audit trail, which only
            # the admin reads, and it is what makes a brute-force attempt against
            # a real account visible.
            log_auth(db, events.LOGIN, events.BAD_CREDENTIALS, email=email_value,
                     account_id=account["_id"] if account else None)

    return render_template("login.html", errors=errors, email=email_value,
                           remember=remember)


@bp.route("/salir", methods=["POST"])
def logout():
    db = get_db()
    doc = current_session()
    account_id = doc["account_id"] if doc else None
    if csrf_ok(request.form.get("csrf_token")):
        # Close it for real instead of just forgetting the cookie: whoever
        # copied its value no longer holds anything.
        if doc:
            sessions.revoke(db, account_id, doc["_id"])
        session.clear()
        log_auth(db, events.LOGOUT, events.OK, account_id=account_id)
    else:
        log_auth(db, events.LOGOUT, events.CSRF_FAILED, account_id=account_id)
    return redirect(url_for("auth.login"))


# -------------------------------------------------------------- recover

@bp.route("/recuperar", methods=["GET", "POST"])
def recover():
    """Ask for the address a code should go to.

    Answers the same whether or not the address has an account. Rule 7 no
    longer covers the registration form, but it very much covers this one: a
    recovery screen that said "no such account" would be the customer finder
    that hiding it was meant to prevent, without even the excuse of helping
    whoever is typing.

    Signed in, the address is already known and the form does not ask for it:
    this is also the way to change a password without remembering the old one.
    """
    account = current_account()
    errors: dict[str, str] = {}
    email_value = account["email"] if account else ""

    if request.method == "POST":
        db = get_db()
        if account is None:
            email_value = request.form.get("email", "").strip()

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.RECOVER, events.CSRF_FAILED, email=email_value)
        elif not rate_limit(db, f"recover:ip:{client_ip()}", *RECOVER_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.RECOVER, events.RATE_LIMITED, email=email_value)
        else:
            email = clean_email(email_value) if email_value else None
            if not email:
                errors["email"] = t("error_email_invalid")
                log_auth(db, events.RECOVER, events.INVALID, email=email_value)
            else:
                if not rate_limit(db, f"recover:mail:{accounts.normalize_email(email)}",
                                  *RECOVER_PER_EMAIL):
                    # Silently over budget, so the answer cannot depend on how
                    # often this address has been asked for.
                    log_auth(db, events.RECOVER, events.RATE_LIMITED, email=email)
                    await_reset()
                else:
                    existing = accounts.by_email(db, email)
                    if existing is None:
                        log_auth(db, events.RECOVER, events.NO_ACCOUNT, email=email)
                        await_reset()
                    else:
                        # A failure is not shown for the same reason: for an
                        # address with no account nothing is sent either.
                        deliver(db, send_recovery, existing, kind=events.RECOVER)
                        log_auth(db, events.RECOVER, events.SENT, email=email,
                                 account_id=existing["_id"])
                        await_reset(existing["_id"])
                return redirect(url_for("auth.recover_code"))

    return render_template("recover.html", errors=errors, email=email_value,
                           known=account is not None)


@bp.route("/recuperar/codigo", methods=["GET", "POST"])
def recover_code():
    """The same six boxes as the confirmation, for the recovery code."""
    errors: dict[str, str] = {}
    account_id = as_object_id(session.get(RESET_KEY))

    if request.method == "POST":
        db = get_db()
        typed = "".join(request.form.getlist("code"))

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.RECOVER, events.CSRF_FAILED, account_id=account_id)
        elif not rate_limit(db, f"recover:code:{client_ip()}", *CONFIRM_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.RECOVER, events.RATE_LIMITED, account_id=account_id)
        else:
            attempts = session.get(RESET_ATTEMPTS, 0) + 1
            session[RESET_ATTEMPTS] = attempts

            if account_id is None:
                reason, doc = tokens.UNKNOWN, None
            else:
                reason, doc = tokens.check(db, account_id, typed,
                                           purpose=tokens.PASSWORD_RESET)

            # Same trick as the confirmation: with no code on file the document
            # cannot run out of tries, so the session counter stands in for it.
            if reason in (tokens.UNKNOWN, tokens.INVALID) and attempts >= tokens.MAX_ATTEMPTS:
                reason = tokens.TOO_MANY

            if reason == tokens.VALID and tokens.spend(db, doc):
                # Proved control of the inbox. That is what the next screen
                # stands on, and it is spent: this cannot be replayed.
                session[RESET_VERIFIED] = str(account_id)
                log_auth(db, events.RECOVER, events.OK, account_id=account_id)
                return redirect(url_for("auth.recover_new"))

            if reason == tokens.USED:
                errors["form"] = t("error_code_used")
            elif reason == tokens.TOO_MANY:
                errors["form"] = t("error_code_too_many")
            else:
                errors["form"] = t("error_code_invalid")
            log_auth(db, events.RECOVER, events.CONFIRM_OUTCOMES[reason],
                     account_id=account_id)

    return render_template("recover-code.html", errors=errors,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left(RESET_DEADLINE))


@bp.route("/recuperar/nueva", methods=["GET", "POST"])
def recover_new():
    """The new password, once the code proved who is asking."""
    account_id = as_object_id(session.get(RESET_VERIFIED))
    db = get_db()
    account = accounts.by_id(db, account_id) if account_id else None
    if account is None:
        return redirect(url_for("auth.recover"))

    errors: dict[str, str] = {}
    if request.method == "POST":
        fresh = request.form.get("password", "")
        repeated = request.form.get("repeat", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.RECOVER, events.CSRF_FAILED,
                     email=account["email"], account_id=account_id)
        else:
            problem = password_problem(fresh)
            if problem:
                errors["password"] = t(PASSWORD_MESSAGES[problem])
            elif fresh != repeated:
                errors["repeat"] = t("error_password_repeat")
            elif accounts.password_was_used(account, fresh):
                # Recovering with the same password puts the account back where
                # it was: whoever knew it, knows it still.
                errors["password"] = t("error_password_used")

            if errors:
                log_auth(db, events.RECOVER, events.INVALID,
                         email=account["email"], account_id=account_id)
            else:
                accounts.set_password(db, account_id, hash_password(fresh))
                # Every session goes, including any the person cannot see: if
                # the password was recovered because somebody else knew it,
                # this is what puts them out.
                sessions.revoke_others(db, account_id)
                log_auth(db, events.PASSWORD_CHANGE, events.OK,
                         email=account["email"], account_id=account_id)
                sign_in(account)
                deliver(db, send_password_changed, account,
                        kind=events.PASSWORD_CHANGE)
                return redirect(url_for("auth.panel", cambiada=1))

    return render_template("recover-new.html", errors=errors)


# ---------------------------------------------------------------------- panel

@bp.route("/panel")
def panel():
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    here = current_session()
    return render_template(
        "panel.html", account=account,
        confirmed=accounts.is_confirmed(account),
        devices=sessions.for_account(get_db(), account["_id"]),
        here=here["_id"] if here else None,
        describe=sessions.describe,
    )


# ---------------------------------------------------------------- devices

@bp.route("/sesion/cerrar/<token>", methods=["GET", "POST"])
def close_from_email(token: str):
    """Close a session from the link in the notice, with no password.

    GET only draws the page. The closing happens on POST, and that is not a
    detail: antivirus and mail scanners open the links of the messages they
    inspect, and a session that closed on GET would be closed by a scanner
    before its owner ever read the mail.
    """
    db = get_db()
    doc = tokens.find_link(db, token, tokens.SESSION_REVOKE)
    if doc is None:
        return render_template("close-session.html", state="unknown"), 410

    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            return render_template("close-session.html", state="unknown"), 400
        session_id = as_object_id((doc.get("data") or {}).get("session_id"))
        if session_id:
            sessions.revoke(db, doc["account_id"], session_id)
        tokens.spend(db, doc)
        log_auth(db, events.SESSION_CLOSED, events.OK,
                 account_id=doc["account_id"])
        return render_template("close-session.html", state="done")

    return render_template("close-session.html", state="ready")


@bp.route("/dispositivos/cerrar", methods=["POST"])
def close_device():
    """Close one session, or every one but this.

    The id comes from a form, so models/session.py scopes the update to the
    signed-in account: an id from somebody else's account matches nothing.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    if not csrf_ok(request.form.get("csrf_token")):
        log_auth(db, events.SESSION_CLOSED, events.CSRF_FAILED,
                 email=account["email"], account_id=account["_id"])
        return redirect(url_for("auth.panel"))

    here = current_session()
    wanted = request.form.get("session_id", "")
    if wanted == "otras":
        closed = sessions.revoke_others(db, account["_id"], here["_id"] if here else None)
        log_auth(db, events.SESSION_CLOSED, f"others:{closed}",
                 email=account["email"], account_id=account["_id"])
    else:
        target = as_object_id(wanted)
        if target and sessions.revoke(db, account["_id"], target):
            log_auth(db, events.SESSION_CLOSED, events.OK,
                     email=account["email"], account_id=account["_id"])
        # Closing the one in use is signing out, so the cookie goes with it.
        if here and target == here["_id"]:
            session.clear()
            return redirect(url_for("auth.login"))
    return redirect(url_for("auth.panel"))


# --------------------------------------------------------------- password

@bp.route("/cambiar-contrasena", methods=["GET", "POST"])
def change_password():
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))

    errors: dict[str, str] = {}
    if request.method == "POST":
        db = get_db()
        current = request.form.get("current", "")
        fresh = request.form.get("password", "")
        repeated = request.form.get("repeat", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.PASSWORD_CHANGE, events.CSRF_FAILED,
                     email=account["email"], account_id=account["_id"])
        elif not rate_limit(db, f"password:ip:{client_ip()}", *PASSWORD_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.PASSWORD_CHANGE, events.RATE_LIMITED,
                     email=account["email"], account_id=account["_id"])
        elif not verify_password(current, account.get("password_hash")):
            errors["current"] = t("error_password_wrong")
            log_auth(db, events.PASSWORD_CHANGE, events.BAD_CURRENT,
                     email=account["email"], account_id=account["_id"])
        else:
            problem = password_problem(fresh)
            if problem:
                errors["password"] = t(PASSWORD_MESSAGES[problem])
            elif fresh != repeated:
                errors["repeat"] = t("error_password_repeat")
            elif accounts.password_was_used(account, fresh):
                # Covers "the same as the current one" too, and every other one
                # this account ever had.
                errors["password"] = t("error_password_used")

            if errors:
                log_auth(db, events.PASSWORD_CHANGE, events.INVALID,
                         email=account["email"], account_id=account["_id"])
            else:
                accounts.set_password(db, account["_id"], hash_password(fresh))
                # Whoever knew the old password stops being inside. This session
                # survives because it is the one that proved it knew it.
                here = current_session()
                sessions.revoke_others(db, account["_id"], here["_id"] if here else None)
                log_auth(db, events.PASSWORD_CHANGE, events.OK,
                         email=account["email"], account_id=account["_id"])
                # A failed notice cannot undo a password that already changed.
                deliver(db, send_password_changed, account,
                        kind=events.PASSWORD_CHANGE)
                return redirect(url_for("auth.panel", cambiada=1))

    return render_template("password.html", errors=errors)
