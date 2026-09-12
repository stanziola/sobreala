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
from flask import (Blueprint, current_app, g, has_request_context, redirect,
                   render_template, request, session, url_for)
from markupsafe import Markup

from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import auth_event as events
from models import mail_log
from models import payment as payments
from models import session as sessions
from models import token as tokens
from services import mailer
from services import notices
from services import paypal
from services import plans
from services import stats
from services import totp
from services.security import (csrf_ok, hash_password, now as security_now,
                               password_problem, rate_limit, verify_password)

bp = Blueprint("auth", __name__)

# Per address and per IP, so one noisy visitor cannot spend someone else's
# budget. Cloudflare filters in front; this is the second layer.
REGISTER_PER_IP = (10, 3600)
RESEND_PER_EMAIL = (5, 3600)
RESEND_PER_IP = (15, 3600)
LOGIN_PER_IP = (20, 900)
TWO_FACTOR_PER_IP = (20, 900)
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
# Between the password and the second step there is a moment where the password
# was right and the session is not open yet. That waiting room lives here.
PENDING_2FA = "pending_two_factor"
PENDING_REMEMBER = "pending_remember"
# The secret while it is being set up, before any code proved it works.
SETUP_KEY = "two_factor_setup"
# La contraseña se pide en la primera pantalla y el QR está en la segunda, así
# que hace falta recordar entre las dos que quien mira ya demostró quién es.
# Con vencimiento, como el código de recuperación: una pestaña olvidada abierta
# no puede seguir sirviendo de puerta media hora después.
TWO_FACTOR_OK = "two_factor_verified"
TWO_FACTOR_MINUTES = 10
# Lo único que identifica una sesión: el resto vive en la colección sessions.
SESSION_KEY = "sid"
# Y las que este navegador tiene abiertas a la vez, la activa incluida. Son
# testigos como el de arriba, así que valen lo mismo que él y viven donde él:
# en la galleta firmada, que ya es HttpOnly y no sale de aquí.
OPEN_KEY = "sids"
# Cuántas caben. El tope existe porque esto viaja en una galleta y porque cuatro
# es más de lo que nadie necesita abrir en un mismo navegador.
MAX_ACCOUNTS = 4
# Marca de que la pantalla de entrar se abrió para **agregar** una cuenta y no
# para reemplazar la que hay. Vive en la sesión y no en la dirección porque el
# segundo paso pasa por otra pantalla y perdería el parámetro.
ADDING = "adding_account"


def open_tokens() -> list[str]:
    """Los testigos guardados, con el activo dentro aunque no estuviera.

    Una galleta escrita antes de que esta lista existiera trae solo el activo;
    se lee igual, así que un despliegue no saca a nadie de su cuenta.
    """
    raws = list(session.get(OPEN_KEY) or [])
    active = session.get(SESSION_KEY)
    if active and active not in raws:
        raws.insert(0, active)
    return raws


def open_accounts() -> list[dict]:
    """Las cuentas que este navegador tiene abiertas ahora mismo.

    Cada testigo se comprueba contra la colección y se descarta el que ya no
    vale —cerrado desde otro dispositivo, vencido, o de una cuenta suspendida—,
    y la lista se deja limpia. Así la pantalla no ofrece una puerta que no abre,
    y cerrar un dispositivo desde Seguridad sigue significando lo que dice.
    """
    db = get_db()
    active = session.get(SESSION_KEY)
    found: list[dict] = []
    keep: list[str] = []
    seen = set()
    for raw in open_tokens():
        doc = sessions.find(db, raw)
        if doc is None:
            continue
        account = accounts.by_id(db, doc["account_id"])
        if account is None or accounts.is_suspended(account):
            continue
        # La misma cuenta dos veces serían dos puertas al mismo sitio.
        if doc["account_id"] in seen:
            continue
        seen.add(doc["account_id"])
        keep.append(raw)
        found.append({"raw": raw, "doc": doc, "account": account,
                      "active": raw == active})
    if keep != list(session.get(OPEN_KEY) or []):
        session[OPEN_KEY] = keep
    return found


def forget_active() -> None:
    """Olvidar la sesión activa sin tocar las demás.

    Hace falta cuando la que estaba en uso deja de valer —la cerraron desde otro
    dispositivo, o suspendieron esa cuenta— y en el navegador quedan otras
    abiertas: hay que sacar a esa, no a todas.
    """
    dead = session.get(SESSION_KEY)
    others = [raw for raw in open_tokens() if raw != dead]
    session.clear()
    if others:
        session[OPEN_KEY] = others


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

    The answer is kept for the rest of the request. The bar at the top of every
    page asks for it too, and without this each page would read the account
    twice and write last_seen_at twice for one visit.
    """
    if hasattr(g, "_account"):
        return g._account
    g._account = _load_account()
    return g._account


def _load_account() -> dict | None:
    doc = current_session()
    if doc is None:
        if session.get(SESSION_KEY):
            forget_active()
        return None
    account = accounts.by_id(get_db(), doc["account_id"])
    if account is None:
        forget_active()
        return None
    # Suspender a alguien que ya estaba dentro tiene que sacarlo, no esperar a
    # que se le ocurra salir.
    if accounts.is_suspended(account):
        forget_active()
        return None
    sessions.touch(get_db(), doc)
    return account


@bp.app_context_processor
def bar_account():
    """Who the bar at the top of the page belongs to, if anyone.

    Every template extends base.html, and base.html draws either the menu of a
    signed-in account or the one with just the theme and the language. Passing
    it from each route would mean remembering to, on every screen there is.

    It never raises: the error page extends the same base, and a database that
    is down must not turn a readable error into a blank one.
    """
    if not has_request_context():
        return {}
    try:
        account = current_account()
        return {"bar_account": account, "bar_admin": accounts.is_admin(account)}
    except Exception:  # noqa: BLE001 - the page is worth more than the menu
        return {"bar_account": None, "bar_admin": False}


def landing(account: dict | None) -> str:
    """A dónde va alguien que acaba de entrar o que salta de cuenta.

    **Al sitio público, sea quien sea.** Es la portada: desde ahí se elige a
    dónde ir con el menú de siempre, que para una cuenta de administrador
    enseña Administración de primera fila. Antes un cliente caía en
    Estadísticas y un administrador en `/admin`, que son dos pantallas
    concretas y dos reglas distintas para el mismo momento; se nota al probar
    con varias cuentas abiertas, donde saltar a una te dejaba en un sitio y
    saltar a otra en otro.

    No se confunda con `inside()`, que es a dónde se vuelve **desde dentro** del
    panel, ni con `not_for_admins()`, que es la puerta que devuelve a `/admin` a
    quien abre una pantalla de cliente que su cuenta no tiene.

    Devuelve una dirección entera y no una ruta, porque el sitio está en otro
    dominio. Eso obliga a una cosa más, en `app.py`: la cabecera `form-action`
    tiene que permitirlo, porque gobierna también la redirección que sigue al
    envío de un formulario, y entrar es un formulario.
    """
    return Config.PUBLIC_SITE_URL


# El plan que alguien venía a contratar cuando se le pidió entrar. Se guarda su
# nombre —«basico»— y nunca una dirección: así no hay ninguna vuelta que validar
# y esa vuelta no puede servir para mandar a nadie a otro sitio.
WANTED_PLAN = "wanted_plan"


def remember_plan(raw: str | None) -> None:
    """Anotar el plan que se quería, si es uno de los de docs/pricing.md.

    Solo escribe; no borra lo que ya hubiera. Recargar la pantalla de entrar
    —o pedirla otra vez por cualquier motivo— llega sin el parámetro, y eso no
    puede significar «ya no quería contratar nada». Lo gasta `after_sign_in()`
    al abrir sesión, y salir limpia la sesión entera.
    """
    if raw and raw in plans.PLANS:
        session[WANTED_PLAN] = raw


def after_sign_in(account: dict | None) -> str:
    """A dónde va quien acaba de abrir sesión.

    Si llegó desde el botón de un plan, sigue a contratarlo en vez de aterrizar
    en su panel y tener que buscarlo otra vez. Un administrador nunca: su cuenta
    no compra.
    """
    wanted = session.pop(WANTED_PLAN, None)
    if wanted and wanted in plans.PLANS and not accounts.is_admin(account):
        return url_for("auth.checkout", plan=wanted)
    return landing(account)


def inside(account: dict | None) -> str:
    """La pantalla de dentro que le toca a esta cuenta.

    No es lo mismo que `landing()`: aquella es a dónde se aterriza al entrar, y
    esta es a dónde se vuelve desde una pantalla del panel, que tiene que ser
    otra del panel y no el sitio público.
    """
    if accounts.is_admin(account):
        return url_for("admin.home")
    return url_for("auth.panel")


def not_for_admins(account: dict | None):
    """Un redirect a administración si esta cuenta es de administrador.

    El panel de envíos, los contactos y las plantillas son de quien tiene
    clientes a los que escribirle. Una cuenta de administrador no los tiene, así
    que esas pantallas le salen vacías y lo único que hacen es estorbar.

    Devuelve None cuando no hay nada que hacer, para poder escribir
    `answer = not_for_admins(account) ...` sin envolver cada vista en un
    decorador. Se comprueba aquí además de esconder las filas del menú: esconder
    un botón no es un permiso.
    """
    if accounts.is_admin(account):
        return redirect(url_for("admin.home"))
    return None


def sign_in(account: dict, *, remember: bool = True, keep: bool = False) -> None:
    """Open a session for this device, and make it the one in use.

    `remember` decides two lifetimes at once: the cookie's —permanent, or gone
    when the browser closes— and the document's. The document is the one that
    counts, because a browser is free to keep a cookie longer than it was told.

    La sesión se vacía a propósito antes de abrir la nueva: nada de lo que
    hubiera antes de identificarse tiene por qué sobrevivir a identificarse. Lo
    único que cruza es el plan que se venía a contratar, porque es justamente
    para después de entrar, y es un nombre de plan comprobado contra
    docs/pricing.md, no una dirección.

    `keep` es lo que distingue **agregar** una cuenta de **entrar**: con él
    sobreviven los testigos de las que ya estaban abiertas. Entrar sin él sigue
    dejando una sola, que es lo que esta función siempre hizo.
    """
    wanted = session.get(WANTED_PLAN)

    # Se lee antes de vaciar la sesión, porque después ya no habría lista.
    everything = open_accounts()
    kept: list[dict] = []
    replaced: list[dict] = []
    dropped: list[dict] = []
    if keep:
        for one in everything:
            if one["account"]["_id"] == account["_id"]:
                replaced.append(one)
            else:
                kept.append(one)
        # Pasado el tope se van las más viejas.
        dropped = kept[:max(0, len(kept) - (MAX_ACCOUNTS - 1))]
        kept = kept[len(dropped):]
    else:
        # Entrar sin más cierra lo que este navegador tuviera abierto. Se
        # cierran de verdad y no solo se olvidan: una sesión viva cuyo testigo
        # nadie tiene ya es una puerta suelta que además aparecería en la
        # pantalla de dispositivos de su dueño.
        dropped = everything

    session.clear()
    db = get_db()
    for one in replaced + dropped:
        sessions.revoke(db, one["doc"]["account_id"], one["doc"]["_id"])

    if wanted:
        session[WANTED_PLAN] = wanted
    token = sessions.start(
        db, account["_id"], ip=client_ip(),
        user_agent=request.headers.get("User-Agent", ""), remember=remember)
    session[SESSION_KEY] = token
    session[OPEN_KEY] = [one["raw"] for one in kept] + [token]
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


def password_proved() -> bool:
    """Si la contraseña se comprobó hace poco, en el primer paso.

    Es lo único que abre la pantalla del QR. Sin esto, cualquiera que encuentre
    una sesión abierta escribe la dirección a mano y se pone su propio teléfono
    como segundo paso, que es exactamente lo que la contraseña evita.
    """
    raw = session.get(TWO_FACTOR_OK)
    if not raw:
        return False
    try:
        return datetime.fromisoformat(raw) > security_now()
    except (TypeError, ValueError):
        return False


def prove_password() -> None:
    session[TWO_FACTOR_OK] = (
        security_now() + timedelta(minutes=TWO_FACTOR_MINUTES)).isoformat()


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

    Says the two things nobody guesses: that the account exists and can already
    buy a plan, and that the first campaign is looked at before it goes out.
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


def send_two_factor_changed(db, account: dict, *, on: bool) -> None:
    """Tell the owner that two-step was turned on, or off.

    Both directions matter and for opposite reasons: turned on by somebody
    else, it locks the owner out of their own account with a phone that is not
    theirs; turned off, it is the first thing anyone does after getting in.
    """
    panel = f"{Config.APP_BASE_URL}{url_for('auth.panel')}"
    mailer.send(
        to=account["email"],
        subject=t("mail_two_step_on_subject" if on else "mail_two_step_off_subject"),
        html=render_template("email/two-factor.html", on=on, panel=panel),
        text=render_template("email/two-factor.txt", on=on, panel=panel),
        purpose=mail_log.TWO_FACTOR,
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
    # Con «agregar» la pantalla se dibuja aunque ya haya una sesión: es crear
    # **otra** cuenta sin cerrar la que está abierta, el mismo camino que ya
    # tiene entrar. Sin la marca, quien ya está dentro no tiene nada que hacer
    # aquí y vuelve a la portada, como siempre.
    adding = bool(request.args.get("agregar"))
    if current_session() and not adding:
        return redirect(landing(current_account()))
    if request.method == "GET":
        # Vive en la sesión porque el camino pasa por la pantalla del código,
        # que llega sin parámetros. La gasta `confirm()` al abrir la sesión.
        if adding:
            session[ADDING] = True
        else:
            session.pop(ADDING, None)

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
                                               errors=errors, adding=adding)
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
                                           errors=errors, adding=adding)
                return redirect(url_for("auth.confirm"))

    return render_template("register.html", form=form, errors=errors,
                           adding=adding)


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
                    # Si la cuenta se creó desde otra, aquella sigue abierta:
                    # crear una segunda no es motivo para cerrar la primera.
                    sign_in(account, keep=bool(session.pop(ADDING, False)))
                    return redirect(url_for("auth.welcome"))

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
    # Con «agregar» la pantalla se dibuja aunque ya haya una sesión abierta: es
    # la única forma de sumar una segunda cuenta, y pasa por aquí entera —con su
    # contraseña y su segundo paso— como cualquier otra.
    adding = bool(request.args.get("agregar"))
    if current_session() and not adding:
        return redirect(landing(current_account()))

    # Quien llegó desde el botón de un plan sigue hasta él al abrir sesión. Se
    # anota al dibujar la pantalla, para que sobreviva al segundo paso.
    if request.method == "GET":
        remember_plan(request.args.get("plan"))
        # La marca vive en la sesión porque el segundo paso pasa por otra
        # dirección y perdería el parámetro. Y se borra al abrir esta pantalla
        # sin él, para que una marca vieja no deje abierta una cuenta de más.
        if adding:
            session[ADDING] = True
        else:
            session.pop(ADDING, None)

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
                # Suspendida es suspendida: hasta ahora el estado se enseñaba y
                # no impedía nada. Se comprueba después de la contraseña, para
                # no decirle a un desconocido qué cuentas están suspendidas.
                if accounts.is_suspended(account):
                    errors["form"] = t("error_suspended")
                    log_auth(db, events.LOGIN, events.SUSPENDED,
                             email=email_value, account_id=account["_id"])
                    return render_template("login.html", errors=errors,
                                           email=email_value, remember=remember)
                remember = bool(request.form.get("remember"))
                # The password was right, and with two-step on that is not
                # enough: nothing is opened until the code from the app is
                # typed. Every time, on every device — un dispositivo que deja
                # de preguntar durante un mes es un segundo candado abierto
                # durante un mes.
                if accounts.two_factor_on(account):
                    session[PENDING_2FA] = str(account["_id"])
                    session[PENDING_REMEMBER] = remember
                    log_auth(db, events.LOGIN, events.SECOND_STEP,
                             email=email_value, account_id=account["_id"])
                    return redirect(url_for("auth.login_code"))

                # Asked before opening the session: once it exists, this device
                # is one this account has used.
                first_time = not sessions.is_known_device(
                    db, account["_id"], request.headers.get("User-Agent", ""))
                sign_in(account, remember=remember,
                        keep=bool(session.pop(ADDING, False)))
                accounts.touch_login(db, account["_id"])
                log_auth(db, events.LOGIN, events.OK, email=email_value,
                         account_id=account["_id"])
                if first_time and accounts.wants(account, accounts.NEW_LOGIN):
                    # The one notice of the four security ones that can be
                    # turned off, from Configuración → Notificaciones. A failure
                    # here cannot keep anyone out of their own account: it is a
                    # warning, not a gate.
                    here = current_session()
                    if here:
                        deliver(db, lambda d, a: send_new_login(d, a, here),
                                account, kind=events.LOGIN)
                return redirect(after_sign_in(account))
            errors["form"] = t("error_login_failed")
            # One outcome for both halves of the failure, because the visitor is
            # told one thing. The account_id is still filled in when the address
            # does exist: that distinction belongs in the audit trail, which only
            # the admin reads, and it is what makes a brute-force attempt against
            # a real account visible.
            log_auth(db, events.LOGIN, events.BAD_CREDENTIALS, email=email_value,
                     account_id=account["_id"] if account else None)

    return render_template("login.html", errors=errors, email=email_value,
                           remember=remember, adding=adding,
                           # Solo cuando no hay nada que corregir: un error de
                           # contraseña importa más que de dónde se venía.
                           switched=bool(request.args.get("cambiar"))
                           and not errors)


@bp.route("/entrar/codigo", methods=["GET", "POST"])
def login_code():
    """The second step: the code from the app, or one of the recovery codes.

    Nothing is open while this screen is up. The password alone got the visitor
    this far and no further, which is the whole point of the second factor.
    """
    db = get_db()
    account_id = as_object_id(session.get(PENDING_2FA))
    account = accounts.by_id(db, account_id) if account_id else None
    if account is None or not accounts.two_factor_on(account):
        return redirect(url_for("auth.login"))

    errors: dict[str, str] = {}
    if request.method == "POST":
        typed = "".join(request.form.getlist("code"))
        backup = request.form.get("recovery", "").strip()

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.LOGIN, events.CSRF_FAILED, account_id=account_id)
        elif not rate_limit(db, f"2fa:ip:{client_ip()}", *TWO_FACTOR_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.LOGIN, events.RATE_LIMITED, account_id=account_id)
        else:
            secret = account["two_factor"]["secret"]
            counter = totp.counter_for(secret, typed) if typed else None
            used_backup = False

            if backup:
                used_backup = accounts.use_recovery_code(
                    db, account_id, totp.hash_recovery(backup))
            elif counter is not None:
                # Spending the window is what stops the same six digits from
                # working twice, for anyone who saw them.
                counter = counter if accounts.use_counter(db, account_id, counter) else None

            if used_backup or counter is not None:
                session.pop(PENDING_2FA, None)
                remember = bool(session.pop(PENDING_REMEMBER, True))
                first_time = not sessions.is_known_device(
                    db, account["_id"], request.headers.get("User-Agent", ""))
                sign_in(account, remember=remember,
                        keep=bool(session.pop(ADDING, False)))
                accounts.touch_login(db, account["_id"])
                log_auth(db, events.LOGIN,
                         events.RECOVERY_USED if used_backup else events.OK,
                         email=account["email"], account_id=account_id)

                answer = redirect(after_sign_in(account))
                if first_time:
                    # After the second step, never before: warning about a
                    # sign-in that had not happened yet is noise in the one
                    # message that has to be read.
                    here = current_session()
                    if here:
                        deliver(db, lambda d, a: send_new_login(d, a, here),
                                account, kind=events.LOGIN)
                return answer

            errors["form"] = t("error_code_invalid")
            log_auth(db, events.LOGIN, events.BAD_CREDENTIALS,
                     email=account["email"], account_id=account_id)

    return render_template("login-code.html", errors=errors,
                           recovery_left=len(account["two_factor"].get("recovery", [])))


# Cómo dicen los navegadores que una petición la pidieron ellos y no la persona.
# Se miran las tres porque conviven: la nueva de Chrome, la vieja de Chrome y la
# de Firefox.
PREFETCH_HEADERS = (("Sec-Purpose", "prefetch"), ("Purpose", "prefetch"),
                    ("X-Moz", "prefetch"))


def is_prefetch() -> bool:
    """Si esta petición la está adelantando el navegador por su cuenta."""
    return any(value in request.headers.get(name, "").lower()
               for name, value in PREFETCH_HEADERS)


@bp.route("/salir", methods=["GET", "POST"])
def logout():
    """Close this device's session, by either method.

    The public site sits on another host and carries none of our tokens, so its
    "Cerrar sesión" cannot be a form: it is a link, and a link is a GET. Salir
    tiene que costar lo mismo desde los dos sitios —un clic— así que el GET
    también cierra.

    Lo único que no cierra es una petición que el propio navegador dice estar
    adelantando: sin eso, un navegador que precarga enlaces sacaría a alguien de
    su cuenta sin que hubiera pulsado nada. Se cierra por omisión y se calla solo
    ante esa cabecera; si un intermediario se la comiera, lo que se pierde es la
    protección y no el salir, que es el lado bueno de equivocarse.

    Cerrar las sesiones de los otros dispositivos no se pregunta aquí: eso vive
    en Configuración → Seguridad, que es su sitio.
    """
    if request.method == "GET":
        if not current_session():
            return redirect(url_for("auth.login"))
        if is_prefetch():
            # Nadie la va a ver: la pidió el navegador, no la persona.
            return render_template("logout.html")

    close_session()
    return redirect(url_for("auth.login"))


@bp.route("/cambiar-cuenta", methods=["GET", "POST"])
def switch_account():
    """Las cuentas que este navegador tiene abiertas, para saltar entre ellas.

    **Son sesiones de verdad, abiertas a la vez.** Cada una tiene su documento
    en `sessions`, con su dispositivo y su vencimiento, y aparece en Seguridad
    como cualquier otra; lo único que comparten es la galleta que guarda sus
    testigos. Saltar de una a otra es cambiar cuál está activa: no se vuelve a
    escribir ninguna contraseña y no se cierra nada.

    Agregar una siempre pasa por la pantalla de entrar completa, con su
    contraseña y su segundo paso si lo tiene. Aquí no se abre ninguna puerta que
    no estuviera ya abierta.
    """
    db = get_db()

    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            return redirect(url_for("auth.switch_account"))
        # Se elige por el identificador de la cuenta y nunca por el testigo: un
        # testigo dibujado en la página sería la sesión escrita en el HTML.
        wanted = as_object_id(request.form.get("cuenta"))
        chosen = next((one for one in open_accounts()
                       if one["account"]["_id"] == wanted), None)
        if chosen is None:
            return redirect(url_for("auth.switch_account"))

        if request.form.get("accion") == "quitar":
            sessions.revoke(db, chosen["doc"]["account_id"],
                            chosen["doc"]["_id"])
            log_auth(db, events.LOGOUT, events.OK,
                     account_id=chosen["account"]["_id"])
            if chosen["active"]:
                forget_active()
            else:
                session[OPEN_KEY] = [raw for raw in open_tokens()
                                     if raw != chosen["raw"]]
            return redirect(url_for("auth.switch_account"))

        session[SESSION_KEY] = chosen["raw"]
        return redirect(landing(chosen["account"]))

    mine = open_accounts()
    if not mine:
        return redirect(url_for("auth.login"))
    here = next((one for one in mine if one["active"]), None)
    return render_template(
        "accounts.html", accounts=mine, max_accounts=MAX_ACCOUNTS,
        back=inside(here["account"]) if here else url_for("auth.login"))


def close_session() -> bool:
    """Cerrar **todas** las sesiones de este dispositivo. True si se cerraron.

    Todas y no solo la activa: «Cerrar sesión» en una computadora prestada tiene
    que significar que no queda ninguna cuenta abierta. Para dejar solo una hay
    un botón por cuenta en la pantalla de cambiar de cuenta.

    El testigo se le pide al formulario del panel, que lo tiene. Al enlace del
    sitio público no, porque vive en otro dominio y no puede llevarlo; lo que
    protege a ese lado es no obedecer a una precarga.
    """
    db = get_db()
    mine = open_accounts()
    account_id = session_account_id()
    if request.method == "GET" or csrf_ok(request.form.get("csrf_token")):
        # Close them for real instead of just forgetting the cookie: whoever
        # copied a value no longer holds anything.
        for one in mine:
            sessions.revoke(db, one["doc"]["account_id"], one["doc"]["_id"])
            log_auth(db, events.LOGOUT, events.OK,
                     account_id=one["account"]["_id"])
        session.clear()
        if not mine:
            log_auth(db, events.LOGOUT, events.OK, account_id=account_id)
        return True
    log_auth(db, events.LOGOUT, events.CSRF_FAILED, account_id=account_id)
    return False


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

    **Salvo cuando se está agregando una cuenta**, que es el caso contrario:
    ahí hay una sesión abierta, pero la contraseña que se olvidó es la de la
    **otra** dirección, la que se venía a sumar. Sin esta distinción el código
    salía al buzón de la cuenta en la que ya estaba dentro, que es justo donde
    no hace falta.
    """
    account = current_account()
    # La marca la pone /entrar?agregar=1 y vive hasta que se abre la sesión
    # nueva, así que sigue puesta al pasar por aquí.
    adding = bool(session.get(ADDING))
    known = account is not None and not adding
    errors: dict[str, str] = {}
    email_value = account["email"] if known else ""

    if request.method == "POST":
        db = get_db()
        if not known:
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
                           known=known)


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
                # Si se venía agregando una cuenta, las que ya estaban
                # abiertas siguen abiertas: recuperar la contraseña de la
                # segunda no es motivo para cerrar la primera.
                sign_in(account, keep=bool(session.pop(ADDING, False)))
                deliver(db, send_password_changed, account,
                        kind=events.PASSWORD_CHANGE)
                return redirect(url_for("auth.panel", cambiada=1))

    return render_template("recover-new.html", errors=errors)


# ---------------------------------------------------------------------- panel

@bp.route("/bienvenida")
def welcome():
    """Lo primero que ve quien acaba de crear su cuenta.

    Antes se caía directo en Estadísticas, que sin plan contratado y sin envíos
    es un cuadro vacío diciendo que todavía no ha pasado nada: la peor primera
    pantalla posible. Esta dice lo único que importa en ese momento —que la
    cuenta está lista— y hacia dónde ir.

    Los dos guardas de abajo no son para el día del registro, donde no pueden
    darse: son para después, porque esta dirección queda en el historial y se
    puede escribir a mano. A quien ya contrató no tiene nada que decirle, y un
    administrador vuelve a `/admin` como en cualquier pantalla de cliente.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account)
    if answer:
        return answer
    if accounts.plan_of(account):
        return redirect(url_for("auth.panel"))

    return render_template("welcome.html", account=account)


@bp.route("/panel")
def panel():
    """Las estadísticas de la cuenta: sus cifras y las gráficas de sus envíos.

    La dirección sigue siendo /panel aunque la pantalla se llame Estadísticas:
    cambiarla rompería los enlaces guardados y el correo de bienvenida a cambio
    de nada.

    La llena `services/stats.py`, el mismo que llena la del administrador, para
    que las dos no puedan separarse.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account)
    if answer:
        return answer

    db = get_db()
    # Sin proceso en segundo plano, entrar al panel es el único momento en que
    # alguien puede enterarse de que su plan está por vencerse o ya venció.
    notices.plan_watch(db, account)

    return render_template(
        "stats.html", account=account, pick=None,
        **stats.screen(db, account,
                       period=request.args.get("periodo", ""),
                       tag=request.args.get("etiqueta", "")))


# --------------------------------------------------------------- settings

# The four sections, in the order the sidebar lists them.
SECTIONS = ("cuenta", "seguridad", "notificaciones", "pagos")

# Del administrador solo una. Estado y plan no significan nada en una cuenta
# que no compra, y los avisos de campañas e importaciones son de cosas que no
# hace. Lo que sí le aplica es cuidar la cuenta que puede aprobar y suspender a
# todas las demás: contraseña, dos pasos y dispositivos.
ADMIN_SECTIONS = ("seguridad",)


def sections_for(account: dict | None) -> tuple[str, ...]:
    """Las secciones que esa cuenta puede abrir. La primera es la de entrada."""
    return ADMIN_SECTIONS if accounts.is_admin(account) else SECTIONS


@bp.route("/configuracion", methods=["GET", "POST"])
@bp.route("/configuracion/<section>", methods=["GET", "POST"])
def settings(section: str = "cuenta"):
    """The account's own settings: one view, one template, its sections.

    They differ in what they draw, not in what they need — each one wants the
    same account beside the same sidebar — so splitting them into four views
    would only spread the same six lines over four places.

    Cuáles son depende de quién mira: un cliente tiene cuatro y un
    administrador solo Seguridad.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    sections = sections_for(account)
    if section not in sections:
        # Una que no le toca —o una inventada— lo deja en la primera suya, no
        # en una pantalla en blanco.
        return redirect(url_for("auth.settings", section=sections[0]))

    db = get_db()
    if request.method == "POST":
        if section != "notificaciones":
            return redirect(url_for("auth.settings", section=section))
        if csrf_ok(request.form.get("csrf_token")):
            # Only the names models/account.py knows are read. A field naming a
            # security notice is dropped here rather than written, so no form
            # —or anything pretending to be one— can turn the alarm off.
            accounts.set_notifications(db, account["_id"], {
                name: bool(request.form.get(name)) for name in accounts.NOTICES})
            log_auth(db, events.SETTINGS, events.OK, email=account["email"],
                     account_id=account["_id"])
        else:
            log_auth(db, events.SETTINGS, events.CSRF_FAILED,
                     email=account["email"], account_id=account["_id"])
        return redirect(url_for("auth.settings", section="notificaciones",
                                guardado=1))

    here = current_session()
    return render_template(
        "settings.html", section=section, sections=sections, account=account,
        plans=plans.PLANS, cycles=plans.CYCLES, currency=plans.CURRENCY,
        paypal_ready=paypal.configured(),
        plan_until=accounts.plan_until(account),
        payments=payments.for_account(db, account["_id"]),
        confirmed=accounts.is_confirmed(account),
        plan=accounts.plan_of(account),
        two_step=accounts.two_factor_on(account),
        notifications={name: accounts.wants(account, name)
                       for name in accounts.NOTICES},
        devices=sessions.for_account(db, account["_id"]),
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
        return redirect(url_for("auth.settings", section="seguridad"))

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
    return redirect(url_for("auth.settings", section="seguridad"))


# ------------------------------------------------------------------- pagos

@bp.route("/contratar/<plan>")
def checkout(plan: str):
    """La pantalla de un plan: lo que cuesta y el botón de pagarlo.

    Es a donde llevan los botones de /planes. El sitio público es estático y
    vive en otro dominio, así que no puede iniciar un cobro por su cuenta: eso
    es un formulario con testigo y tiene que salir de aquí.

    No cobra nada. El botón hace POST a `start_payment()`, que es y sigue siendo
    el único que habla con PayPal.
    """
    account = current_account()
    if account is None:
        # El plan viaja por su nombre para que, al entrar, siga hasta aquí.
        return redirect(url_for("auth.login", plan=plan))
    answer = not_for_admins(account)
    if answer:
        return answer

    # Corporativo va sin precio público: comprarlo por la web pondría un precio
    # donde docs/pricing.md dice que no hay ninguno.
    if not plans.buyable(plan):
        return redirect(url_for("auth.settings", section="pagos", error="plan"))

    return render_template(
        "checkout.html", plan=plan, one=plans.PLANS[plan],
        # Bajar de plan no se hace por la web: lo que ya se pagó no se
        # devuelve, así que quitarle sitio a una cuenta a cambio de nada tiene
        # que pasar por una conversación. Renovar el mismo sí, que es sumarle
        # tiempo al que ya tiene.
        downgrade=plans.is_downgrade(accounts.plan_of(account), plan),
        currency=plans.CURRENCY,
        can_buy=accounts.can_buy(account),
        suspended=accounts.is_suspended(account),
        paypal_ready=paypal.configured(),
        current=accounts.plan_of(account),
        plan_until=accounts.plan_until(account))


@bp.route("/configuracion/pagos/contratar", methods=["POST"])
def start_payment():
    """Crear la orden en PayPal y mandar al cliente a pagarla.

    Nada se activa aquí. Lo único que hace esta ruta es anotar el intento y
    abrir el checkout; quien decide si alguien pagó es la vuelta, comparando lo
    que responda PayPal contra lo que ese plan cuesta.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    # Una cuenta de administrador no compra planes: no tiene a quién escribirle.
    answer = not_for_admins(account)
    if answer:
        return answer

    db = get_db()
    back = url_for("auth.settings", section="pagos")
    plan = request.form.get("plan", "")
    cycle = request.form.get("cycle", "")

    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    # Correo confirmado y cuenta no suspendida, nada más. Se comprueba aquí y
    # no solo en la pantalla, porque un formulario se escribe a mano.
    if not accounts.can_buy(account):
        return redirect(url_for("auth.settings", section="pagos", error="estado"))
    # Corporativo va sin precio público: comprarlo por la web pondría un precio
    # donde docs/pricing.md dice que no hay ninguno.
    amount = plans.amount(plan, cycle) if plans.buyable(plan) else None
    if amount is None:
        return redirect(url_for("auth.settings", section="pagos", error="plan"))
    # Se comprueba aquí y no solo en la pantalla, porque un formulario se
    # escribe a mano y el botón gris del sitio es solo un aviso.
    if plans.is_downgrade(accounts.plan_of(account), plan):
        return redirect(url_for("auth.checkout", plan=plan))
    if not paypal.configured():
        return redirect(url_for("auth.settings", section="pagos", error="paypal"))

    attempt = payments.start(db, account["_id"], plan=plan, cycle=cycle,
                             amount=amount, currency=plans.CURRENCY)
    try:
        order_id, approve = paypal.create(
            amount=amount, currency=plans.CURRENCY,
            description=f"Panamails {plans.PLANS[plan]['name']}",
            reference=str(attempt),
            return_url=f"{Config.APP_BASE_URL}{url_for('auth.finish_payment')}",
            cancel_url=f"{Config.APP_BASE_URL}{back}?error=cancelado")
    except paypal.PayPalError as exc:
        payments.fail(db, attempt, str(exc))
        return redirect(url_for("auth.settings", section="pagos", error="paypal"))

    payments.attach_order(db, attempt, order_id)
    log_auth(db, events.PAYMENT, events.CREATED, email=account["email"],
             account_id=account["_id"])
    return redirect(approve)


@bp.route("/configuracion/pagos/volver")
def finish_payment():
    """La vuelta de PayPal: cobrar de verdad y, solo entonces, activar.

    Lo que trae el navegador aquí es un identificador de orden y nada más. No
    prueba que se haya pagado: lo que prueba es lo que responde PayPal cuando
    el servidor le pide cobrarla, y por eso se compara el monto y la moneda
    contra lo que ese plan cuesta antes de tocar la cuenta.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    back = url_for("auth.settings", section="pagos")
    order_id = request.args.get("token", "")[:64]
    attempt = payments.by_order(db, account["_id"], order_id) if order_id else None
    if attempt is None:
        return redirect(f"{back}?error=orden")
    # Recargar esta página entra por aquí otra vez. El intento ya está cobrado,
    # así que no se cobra ni se alarga nada: solo se dice que ya está.
    if attempt["status"] != payments.CREATED:
        return redirect(f"{back}?hecho=1")

    try:
        result = paypal.capture(order_id)
    except paypal.PayPalError as exc:
        payments.fail(db, attempt["_id"], str(exc))
        return redirect(f"{back}?error=paypal")

    esperado = plans.amount(attempt["plan"], attempt["cycle"])
    if result["status"] != "COMPLETED":
        payments.fail(db, attempt["_id"], f"estado {result['status']}")
        return redirect(f"{back}?error=cobro")
    if result["amount"] != esperado or result["currency"] != attempt["currency"]:
        # Cobró algo distinto de lo que vale el plan: no se activa nada y queda
        # escrito, que es lo que hace falta para reclamarlo.
        payments.fail(db, attempt["_id"],
                      f"cobró {result['amount']} {result['currency']}, "
                      f"esperaba {esperado} {attempt['currency']}")
        log_auth(db, events.PAYMENT, events.INVALID, email=account["email"],
                 account_id=account["_id"])
        return redirect(f"{back}?error=monto")

    if not payments.complete(db, attempt["_id"]):
        return redirect(f"{back}?hecho=1")

    # Renovar es pagar el mismo plan que todavía corre; cambiarlo o volver
    # después de que venciera es contratar. Se mira antes de activar, que es
    # cuando la cuenta todavía dice lo que decía.
    running = accounts.plan_until(account)
    renewed = (accounts.plan_of(account) == attempt["plan"]
               and running is not None and running > accounts.now())
    until = payments.until(
        attempt["cycle"],
        since=accounts.renews_from(account, attempt["plan"]))
    accounts.activate_plan(db, account["_id"], attempt["plan"], until)
    log_auth(db, events.PAYMENT, events.OK, email=account["email"],
             account_id=account["_id"])

    # Los dos correos van después de todo lo que decide algo: si el correo no
    # sale, el pago sigue cobrado y el plan activo.
    notices.paid(account, plan=attempt["plan"], until=until, renewed=renewed)
    notices.payment_to_admins(db, account, plan=attempt["plan"])
    return redirect(f"{back}?hecho=1")


# --------------------------------------------------------- cambiar el correo

# Lo que la segunda pantalla necesita recordar de la primera. No hace falta
# guardar de quién es el código: quien lo escribe está dentro de su cuenta.
MAIL_ATTEMPTS = "email_change_attempts"
MAIL_DEADLINE = "email_change_expires_at"


def await_email_change() -> None:
    """Empezar la espera del código, como `await_code()` con la suya."""
    session[MAIL_ATTEMPTS] = 0
    session[MAIL_DEADLINE] = (security_now() + timedelta(
        minutes=Config.CONFIRMATION_CODE_MINUTES)).isoformat()


@bp.route("/cuenta/correo", methods=["GET", "POST"])
def change_email():
    """Mover la cuenta a otra dirección: la contraseña, y después el código.

    Corregir el correo (`/confirmar/corregir`) es otra cosa y es de antes: sirve
    mientras la cuenta no está confirmada y nadie ha probado nada todavía. Esta
    pantalla es la de después, y por eso pide las dos pruebas:

      * **la contraseña**, como para cambiarla o para tocar los dos pasos. Sin
        ella, quien encuentre una sesión abierta se lleva la cuenta a su propio
        buzón y desde ahí pide recuperar la contraseña;
      * **un código a la dirección nueva**, que es lo que prueba que existe y
        que es suya. Un error de dedo dejaría la cuenta apuntando al buzón de
        nadie, y aquí eso significa perderla: la recuperación va por correo.

    Un administrador puede usarla, igual que puede cambiar su contraseña: esto
    es la identidad con la que entra, no una pantalla de cliente. Lo que no
    tiene es el botón, porque su Configuración no enseña la sección Cuenta.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}
    email_value = ""

    if request.method == "POST":
        email_value = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.EMAIL_CHANGE, events.CSRF_FAILED,
                     email=account["email"], account_id=account["_id"])
        elif not rate_limit(db, f"email:ip:{client_ip()}", *PASSWORD_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.EMAIL_CHANGE, events.RATE_LIMITED,
                     email=account["email"], account_id=account["_id"])
        elif not verify_password(password, account.get("password_hash")):
            errors["password"] = t("error_password_wrong")
            log_auth(db, events.EMAIL_CHANGE, events.BAD_CURRENT,
                     email=account["email"], account_id=account["_id"])
        else:
            email = clean_email(email_value) if email_value else None
            if not email:
                errors["email"] = t("error_email_invalid")
                log_auth(db, events.EMAIL_CHANGE, events.INVALID,
                         email=email_value, account_id=account["_id"])
            elif accounts.normalize_email(email) == account["email_normalized"]:
                errors["email"] = t("error_email_same")
            elif accounts.by_email(db, email):
                # Se dice, como en el registro y en corregir: callarlo deja a
                # alguien esperando un código que no va a llegar nunca.
                errors["email"] = t("error_email_taken")
                log_auth(db, events.EMAIL_CHANGE, events.TAKEN, email=email,
                         account_id=account["_id"])
            elif not rate_limit(db, f"register:mail:{accounts.normalize_email(email)}",
                                *REGISTER_PER_EMAIL):
                # Esta pantalla manda correo a una dirección escrita a mano, así
                # que comparte el presupuesto del registro: nadie llena el buzón
                # de un tercero pidiendo el cambio una y otra vez.
                errors["form"] = t("error_too_many")
                log_auth(db, events.EMAIL_CHANGE, events.RATE_LIMITED,
                         email=email, account_id=account["_id"])
            else:
                # La dirección nueva se anota aparte: la cuenta sigue entrando y
                # recibiendo por la de siempre hasta que el código llegue.
                accounts.start_email_change(db, account["_id"], email)
                code = tokens.issue(db, account["_id"], tokens.EMAIL_CHANGE)
                notices.email_change_code(
                    account, code=code, to=email,
                    minutes=Config.CONFIRMATION_CODE_MINUTES)
                log_auth(db, events.EMAIL_CHANGE, events.SENT, email=email,
                         account_id=account["_id"])
                await_email_change()
                return redirect(url_for("auth.change_email_code"))

    return render_template("email-change.html", errors=errors,
                           email=email_value, account=account)


@bp.route("/cuenta/correo/codigo", methods=["GET", "POST"])
def change_email_code():
    """El código que llegó a la dirección nueva.

    Hasta que entra aquí no se ha movido nada. Cuando entra, se escribe la
    dirección nueva y **se avisa a la vieja**: es la alarma que entera al dueño
    si quien hizo esto no era él.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    waiting = accounts.pending_email(account)
    if not waiting:
        return redirect(url_for("auth.change_email"))

    db = get_db()
    errors: dict[str, str] = {}

    if request.method == "POST":
        typed = "".join(request.form.getlist("code"))

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.EMAIL_CHANGE, events.CSRF_FAILED,
                     account_id=account["_id"])
        elif not rate_limit(db, f"email:ip:{client_ip()}", *CONFIRM_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.EMAIL_CHANGE, events.RATE_LIMITED,
                     account_id=account["_id"])
        else:
            attempts = session.get(MAIL_ATTEMPTS, 0) + 1
            session[MAIL_ATTEMPTS] = attempts
            reason, doc = tokens.check(db, account["_id"], typed,
                                       tokens.EMAIL_CHANGE)
            if reason in (tokens.UNKNOWN, tokens.INVALID) \
                    and attempts >= tokens.MAX_ATTEMPTS:
                reason = tokens.TOO_MANY

            if reason == tokens.VALID and not tokens.spend(db, doc):
                # Alguien escribió el mismo código hace un instante.
                reason = tokens.USED

            if reason == tokens.VALID:
                old = account["email"]
                if accounts.finish_email_change(db, account["_id"], waiting):
                    # Si la cuenta estaba sin confirmar, acaba de confirmarse:
                    # lo que prueba una confirmación es justo lo que acaba de
                    # probar el código. Ya confirmada, no hace nada.
                    accounts.confirm_email(db, account["_id"])
                    notices.email_changed(account, old=old, new=waiting)
                    log_auth(db, events.EMAIL_CHANGE, events.OK, email=waiting,
                             account_id=account["_id"])
                    return redirect(url_for("auth.settings", section="cuenta",
                                            correo=1))
                # Se la llevó otra cuenta entre que se pidió el código y se
                # escribió. El índice único es quien lo dice.
                accounts.cancel_email_change(db, account["_id"])
                log_auth(db, events.EMAIL_CHANGE, events.TAKEN, email=waiting,
                         account_id=account["_id"])
                return redirect(url_for("auth.change_email", tomada=1))

            if reason == tokens.USED:
                errors["form"] = t("error_code_used")
            elif reason == tokens.TOO_MANY:
                errors["form"] = t("error_code_too_many")
            else:
                errors["form"] = t("error_code_invalid")
            log_auth(db, events.EMAIL_CHANGE, events.CONFIRM_OUTCOMES[reason],
                     account_id=account["_id"])

    return render_template("email-change-code.html", errors=errors,
                           waiting=waiting,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left(MAIL_DEADLINE))


# --------------------------------------------------------------- password


# Las dos acciones que se pueden hacer sobre una verificación ya encendida.
TWO_FACTOR_ACTIONS = ("regenerate", "disable")


@bp.route("/cuenta/dos-pasos", methods=["GET", "POST"])
def two_factor():
    """La primera pantalla, que es siempre la de la contraseña.

    Apagada, pide la contraseña y manda a escanear. Encendida, enseña las dos
    cosas que se pueden hacer y, cuando se elige una, pide la contraseña para
    esa: así se confirma una decisión y no un botón cualquiera.

    La contraseña va en los dos caminos y no es papeleo. Sin ella, quien
    encuentre una sesión abierta activa la verificación con *su* teléfono y deja
    al dueño fuera de su propia cuenta para siempre, o la desactiva y se queda
    con la puerta abierta.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    on = accounts.two_factor_on(account)
    errors: dict[str, str] = {}
    # Qué se está confirmando. Viaja en la dirección para dibujar la pantalla y
    # en el formulario para hacerla: lo que decide es el POST.
    action = (request.form.get("action") if request.method == "POST"
              else request.args.get("accion", "")) or ""
    if action not in TWO_FACTOR_ACTIONS:
        action = ""

    if request.method == "POST":
        password = request.form.get("password", "")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.TWO_FACTOR, events.CSRF_FAILED,
                     email=account["email"], account_id=account["_id"])
        elif not rate_limit(db, f"2fa:setup:{client_ip()}", *PASSWORD_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.TWO_FACTOR, events.RATE_LIMITED,
                     email=account["email"], account_id=account["_id"])
        elif not verify_password(password, account.get("password_hash")):
            errors["password"] = t("error_password_wrong")
            log_auth(db, events.TWO_FACTOR, events.BAD_CURRENT,
                     email=account["email"], account_id=account["_id"])

        elif not on:
            # La contraseña quedó demostrada; el QR está en la otra pantalla.
            prove_password()
            session.pop(SETUP_KEY, None)
            return redirect(url_for("auth.two_factor_scan"))

        elif action == "disable":
            accounts.disable_two_factor(db, account["_id"])
            session.pop(SETUP_KEY, None)
            session.pop(TWO_FACTOR_OK, None)
            log_auth(db, events.TWO_FACTOR, events.DISABLED,
                     email=account["email"], account_id=account["_id"])
            # A notice that fails to go out cannot undo a change already made.
            deliver(db, lambda d, a: send_two_factor_changed(d, a, on=False),
                    account, kind=events.TWO_FACTOR)
            return redirect(url_for("auth.settings", section="seguridad",
                                    dospasos="off"))

        elif action == "regenerate":
            codes = totp.new_recovery_codes()
            accounts.set_recovery_codes(db, account["_id"], totp.hash_all(codes))
            log_auth(db, events.TWO_FACTOR, events.REGENERATED,
                     email=account["email"], account_id=account["_id"])
            return render_template("two-factor-codes.html", codes=codes)

    # Tres pantallas, un archivo: pedir la contraseña, elegir qué hacer, o
    # confirmar lo elegido.
    step = "password" if not on else ("confirm" if action else "choose")
    return render_template(
        "two-factor.html", errors=errors, on=on, step=step, action=action,
        recovery_left=len((account.get("two_factor") or {}).get("recovery", [])))


@bp.route("/cuenta/dos-pasos/activar", methods=["GET", "POST"])
def two_factor_scan():
    """La segunda pantalla: el QR y el código que prueba que la app lo tiene.

    No se llega escribiendo la dirección: hace falta haber pasado por la
    anterior hace menos de diez minutos.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    if accounts.two_factor_on(account):
        return redirect(url_for("auth.two_factor"))
    if not password_proved():
        return redirect(url_for("auth.two_factor", vencido=1))

    db = get_db()
    errors: dict[str, str] = {}
    # El secreto vive en la galleta mientras se prepara: todavía no es de nadie,
    # y solo pasa a ser de la cuenta cuando un código prueba que la app lo tiene.
    secret = session.get(SETUP_KEY) or totp.new_secret()

    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
            log_auth(db, events.TWO_FACTOR, events.CSRF_FAILED,
                     email=account["email"], account_id=account["_id"])
        elif not rate_limit(db, f"2fa:setup:{client_ip()}", *PASSWORD_PER_IP):
            errors["form"] = t("error_too_many")
            log_auth(db, events.TWO_FACTOR, events.RATE_LIMITED,
                     email=account["email"], account_id=account["_id"])
        elif totp.counter_for(secret, "".join(request.form.getlist("code"))) is None:
            # Se pide antes de encenderla para que nadie se deje fuera de su
            # cuenta por haber escaneado mal: la app tiene que demostrar que
            # guardó el secreto.
            errors["code"] = t("error_code_invalid")
            log_auth(db, events.TWO_FACTOR, events.INVALID,
                     email=account["email"], account_id=account["_id"])
        else:
            codes = totp.new_recovery_codes()
            accounts.enable_two_factor(db, account["_id"], secret,
                                       totp.hash_all(codes))
            session.pop(SETUP_KEY, None)
            session.pop(TWO_FACTOR_OK, None)
            log_auth(db, events.TWO_FACTOR, events.OK,
                     email=account["email"], account_id=account["_id"])
            deliver(db, lambda d, a: send_two_factor_changed(d, a, on=True),
                    account, kind=events.TWO_FACTOR)
            return render_template("two-factor-codes.html", codes=codes)

    session[SETUP_KEY] = secret
    return render_template(
        "two-factor-scan.html", errors=errors, secret=secret,
        qr=Markup(totp.qr_svg(secret, account["email"])))


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
                return redirect(url_for("auth.settings", section="seguridad",
                                        cambiada=1))

    return render_template("password.html", errors=errors)
