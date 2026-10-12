"""Registration, email confirmation and session.

Four rules run through the whole file:

  * The screen never reveals whether an address has an account. Signing in and
    recovering answer identically either way. This is what shapes the code
    screens: every wrong code gets the same answer, whether or not a code was
    ever issued.
  * A confirmation code is only ever compared as a hash, and it is spent once.
  * If the email cannot be sent, a registration is undone. An account that
    exists but can never be confirmed is worse than no account at all.
  * Every attempt is recorded in auth_events, with what really happened. The log
    knows more than the screen says, and that is the point: it is the audit
    trail, read only by the admin.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from ipaddress import ip_address

from bson import ObjectId
from bson.errors import InvalidId
from email_validator import EmailNotValidError, validate_email
from flask import (Blueprint, Response, abort, current_app, g,
                   has_request_context, redirect, render_template, request,
                   session, url_for)
from markupsafe import Markup

from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import auth_event as events
from models import mail_log
from models import invoice as invoices
from models import payment as payments
from models import session as sessions
from models import token as tokens
from models import verification_doc as verification_docs
from services import countries
from services import mailer
from services import notices
from services import paguelofacil
from services import paypal
from services import plans
from services import renewals
from services import stats
from services import totp
from services import upgrade
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
# La dirección escrita al pedir el código, exista o no, para que «Pedir otro
# código» no la pregunte otra vez. Es lo que escribió quien mira, así que
# guardarla no le cuenta nada que no supiera.
RESET_EMAIL = "reset_email"
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
    # Vaciar la sesión le quita también su duración: sin guardarla, la galleta
    # de las que quedan moriría al cerrar el navegador y sus sesiones seguirían
    # vivas sin testigo.
    permanent = session.permanent
    session.clear()
    if others:
        session[OPEN_KEY] = others
        session.permanent = permanent


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
    # que se le ocurra salir. Lo mismo con un usuario desactivado y con uno
    # cuya empresa acaban de suspender.
    if accounts.is_suspended(account) or not member_may_enter(get_db(), account):
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
        return {"bar_account": account, "bar_admin": accounts.is_admin(account),
                # Qué filas enseñarle: un usuario ve solo lo que su empresa le
                # dio. Las rutas lo comprueban igual, porque esconder una fila
                # no es un permiso. Una empresa cerrada las ve todas: cada una
                # la lleva a contratar o a pedir la demostración (`needs()`).
                "bar_can": {name: accounts.can(account, name)
                            for name in accounts.PERMISSIONS},
                # Una empresa que todavía no se abrió, ni con la demostración
                # ni con el pago: Configuración lo avisa en amarillo.
                "bar_closed": is_closed(account),
                # El nombre de arriba es el de la empresa, también para un
                # usuario suyo: es la cuenta en la que está trabajando.
                "bar_company": (current_workspace() or {}).get("company_name", "")}
    except Exception:  # noqa: BLE001 - the page is worth more than the menu
        return {"bar_account": None, "bar_admin": False, "bar_can": {},
                "bar_closed": False, "bar_company": ""}


def landing(account: dict | None) -> str:
    """A dónde va alguien que acaba de entrar, que salta de cuenta o que vuelve
    de la lista de sus cuentas.

    **Al sitio público, sea quien sea.** Es la portada: desde ahí se elige a
    dónde ir con el menú de siempre, que para una cuenta de administrador
    enseña Administración de primera fila. Antes un cliente caía en
    Estadísticas y un administrador en `/admin`, que son dos pantallas
    concretas y dos reglas distintas para el mismo momento; se nota al probar
    con varias cuentas abiertas, donde saltar a una te dejaba en un sitio y
    saltar a otra en otro.

    No se confunda con `not_for_admins()`, que es la puerta que devuelve a
    `/admin` a quien abre una pantalla de cliente que su cuenta no tiene.

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


# La plantilla de muestra de la portada que se pulsó sin sesión. Como el plan,
# se guarda su nombre y nunca una dirección; el nombre solo puede ser esto, y
# `designs.sample()` comprueba además que exista su ZIP.
WANTED_SAMPLE = "wanted_sample"
SAMPLE_NAME = re.compile(r"[a-z0-9-]{1,40}")


def remember_sample(raw: str | None) -> None:
    """Anotar la muestra que se quería abrir. Como `remember_plan()`, solo
    escribe."""
    if raw and SAMPLE_NAME.fullmatch(raw):
        session[WANTED_SAMPLE] = raw


def after_sign_in(account: dict | None) -> str:
    """A dónde va quien acaba de abrir sesión.

    Si llegó desde el botón de un plan, sigue a contratarlo en vez de aterrizar
    en su panel y tener que buscarlo otra vez; si llegó desde una plantilla de
    la portada, sigue a su lienzo. Un administrador nunca: su cuenta no compra
    ni tiene plantillas.
    """
    wanted = session.pop(WANTED_PLAN, None)
    sample = session.pop(WANTED_SAMPLE, None)
    if accounts.is_admin(account):
        return landing(account)
    if wanted and wanted in plans.PLANS:
        return url_for("auth.checkout", plan=wanted)
    if sample and SAMPLE_NAME.fullmatch(sample):
        return url_for("designs.sample", slug=sample)
    return landing(account)


def member_may_enter(db, account: dict | None) -> bool:
    """Si un usuario de una empresa puede estar dentro.

    Dos cosas lo dejan fuera y ninguna es suya: que el dueño lo haya
    desactivado, y que la empresa esté suspendida. Una empresa suspendida sin
    esto seguiría teniendo a su equipo dentro.
    """
    if not accounts.is_member(account):
        return True
    if account.get("status") == accounts.DISABLED:
        return False
    owner = accounts.by_id(db, account["owner_id"])
    return owner is not None and not accounts.is_suspended(owner)


def current_workspace() -> dict | None:
    """**De quién son los datos** que esta petición mira: de la empresa.

    Para una empresa es ella misma. Para un usuario que ella creó, la cuenta
    del dueño. Así los contactos, las plantillas y las campañas siguen
    colgando de un solo `account_id` y ninguna consulta tuvo que cambiar: lo
    que cambia es de quién es la cuenta que se les pasa.

    `current_account()` sigue diciendo **quién** es, que es otra cosa: el
    segundo factor, los dispositivos y la contraseña son de la persona.
    """
    if hasattr(g, "_workspace"):
        return g._workspace
    account = current_account()
    g._workspace = (accounts.owner_of(get_db(), account)
                    if accounts.is_member(account) else account)
    return g._workspace


# A dónde llevar a un usuario según lo que puede. En orden: la primera que
# pueda abrir es su pantalla de entrada, y si no puede ninguna le queda su
# Seguridad, que siempre es suya.
HOMES = (
    (accounts.STATS, "auth.panel"),
    (accounts.CAMPAIGNS, "campaigns.index"),
    (accounts.CONTACTS, "contacts.index"),
    (accounts.DESIGNS, "designs.index"),
)


def home_for(account: dict | None) -> str:
    for permission, where in HOMES:
        if accounts.can(account, permission):
            return url_for(where)
    return url_for("auth.settings", section="security")


def is_closed(account: dict | None) -> bool:
    """Si quien mira es de una empresa que todavía no se abrió.

    Se pregunta por la empresa y no por la persona: un usuario de una cuenta
    abierta entra aunque su propio documento no diga nada. Un administrador no
    tiene empresa que abrir, y sin sesión no hay nada que cerrar.
    """
    if account is None or accounts.is_admin(account):
        return False
    return not accounts.is_open(current_workspace())


def needs(account: dict | None, permission: str):
    """Un redirect si esta cuenta no puede abrir esa pantalla.

    Se comprueba en la ruta y no solo en el menú, como con los administradores:
    esconder una fila no es un permiso. Quien no la tiene cae en la primera que
    sí pueda abrir, no en una pantalla de error.

    Antes que el permiso va la empresa: una que todavía no se abrió, ni con la
    demostración ni con el pago, cae en su bienvenida, donde se contrata o se
    pide la demostración, y la bienvenida dice qué pantalla quería abrir. Las
    cuatro pantallas de cliente pasan por aquí, así que una nueva hereda la
    puerta sin que nadie se acuerde de ponérsela.

    Devuelve None cuando no hay nada que hacer, para poder escribir
    `answer = needs(account, ...)` sin envolver cada vista en un decorador.
    """
    if is_closed(account):
        return redirect(url_for("auth.welcome", para=permission))
    if accounts.can(account, permission):
        return None
    return redirect(home_for(account))


def owner_only(account: dict | None):
    """Un redirect si quien mira es un usuario y no el dueño.

    La cuenta, la facturación, contratar un plan, la dirección postal y los
    usuarios son de la empresa. Un usuario tiene su Seguridad, y nada más.
    """
    if accounts.is_member(account):
        return redirect(url_for("auth.settings", section="security"))
    return None


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
    sample = session.get(WANTED_SAMPLE)

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
    if sample:
        session[WANTED_SAMPLE] = sample
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

    Says what nobody guesses: that the account exists but opens one of two
    ways, with the demo or with a plan, and what the demo brings. The button
    goes to the welcome screen, which is where the demo is asked for.
    """
    panel = f"{Config.APP_BASE_URL}{url_for('auth.welcome')}"
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

@bp.route("/signup", methods=["GET", "POST"])
def register():
    # Con «agregar» la pantalla se dibuja aunque ya haya una sesión: es crear
    # **otra** cuenta sin cerrar la que está abierta, el mismo camino que ya
    # tiene entrar. Sin la marca, quien ya está dentro no tiene nada que hacer
    # aquí y vuelve a la portada, como siempre.
    adding = bool(request.args.get("add"))
    if current_session() and not adding:
        return redirect(landing(current_account()))
    if request.method == "GET":
        # Vive en la sesión porque el camino pasa por la pantalla del código,
        # que llega sin parámetros. La gasta `confirm()` al abrir la sesión.
        if adding:
            session[ADDING] = True
        else:
            session.pop(ADDING, None)

    form = {"company_name": "", "contact_name": "", "email": "", "phone": "",
            "phone_country": countries.DEFAULT, "address": ""}
    company: list[dict[str, str]] = []
    errors: dict[str, str] = {}

    if request.method == "POST":
        db = get_db()
        form = {k: request.form.get(k, "").strip() for k in form}
        company = typed_company_phones()
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

            # Desde octubre de 2026 el registro trae lo que después se verifica:
            # el teléfono personal, la dirección y la identificación personal. Los
            # números de la empresa son opcionales.
            phone = accounts.clean_phone(form["phone"], form["phone_country"])
            if not form["phone"]:
                errors["phone"] = t("error_required")
            elif not phone:
                errors["phone"] = t("error_phone")
            company_phones, bad_phone = accounts.clean_phones(
                [one["number"] for one in company], [one["country"] for one in company])
            if bad_phone:
                errors["company_phones"] = t("error_phone")
            address = accounts.clean_postal(form["address"])
            if address is None:
                errors["address"] = t("settings_postal_bad", min=accounts.POSTAL_MIN,
                                      max=accounts.POSTAL_MAX)
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
                    phone=phone,
                    company_phones=company_phones,
                    postal_address=address,
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
                        return register_screen(form, errors, adding, company)
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
                    return register_screen(form, errors, adding, company)
                return redirect(url_for("auth.confirm"))

    return register_screen(form, errors, adding, company)


def typed_company_phones() -> list[dict[str, str]]:
    """Los números de la empresa tal como llegaron del formulario, hasta tres,
    para limpiarlos y para volver a dibujarlos si algo falló."""
    numbers = request.form.getlist("company_phone")
    chosen = request.form.getlist("company_phone_country")
    return [{"number": number.strip()[:40],
             "country": (chosen[i] if i < len(chosen) else countries.DEFAULT)}
            for i, number in enumerate(numbers[:accounts.COMPANY_PHONES_MAX])]


def register_screen(form: dict, errors: dict, adding: bool,
                    company: list[dict[str, str]]):
    return render_template("register.html", form=form, errors=errors,
                           adding=adding, company=company,
                           phone_options=countries.options(),
                           company_max=accounts.COMPANY_PHONES_MAX,
                           postal_max=accounts.POSTAL_MAX)


# -------------------------------------------------------------------- confirm

@bp.route("/confirm", methods=["GET", "POST"])
def confirm():
    """Ask for the six digit code and check it.

    Every refusal reads the same — a wrong code, an expired one, and an account
    that never had one all get one message — because the difference between them
    is exactly what rule 7 forbids showing. The real reason goes to auth_events.
    """
    errors: dict[str, str] = {}
    account_id = as_object_id(session.get(PENDING_KEY))
    # La vuelta de «Pedir otro código», que dice cómo le fue. Solo al dibujar
    # la pantalla: el formulario del código se manda a esta misma dirección, con
    # el parámetro puesto, y un código mal escrito no es un reenvío.
    resent = request.method == "GET" and request.args.get("resent") == "ok"
    if request.method == "GET" and request.args.get("resent") in RESEND_ERRORS:
        errors["form"] = t(RESEND_ERRORS[request.args["resent"]])

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
                    # Y a quien administra, que se registró alguien. No puede
                    # romper una confirmación que ya pasó: se traga lo suyo.
                    notices.signup_to_admins(db, account)
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

    return render_template("confirm.html", errors=errors, resent=resent,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left())


# Cómo le fue a «Pedir otro código» cuando no salió, en el parámetro con el que
# vuelve a la pantalla del código.
RESEND_ERRORS = {"wait": "error_too_many", "failed": "code_resend_failed",
                 "expired": "error_csrf"}


def waiting_account(db) -> dict | None:
    """La cuenta a la que va «Pedir otro código» en la confirmación.

    La que este navegador acaba de registrar y está confirmando, que es la de
    `PENDING_KEY`. Si no hay ninguna, la cuenta abierta, que es la del aviso
    del panel a quien entró sin haber confirmado su correo.
    """
    pending = as_object_id(session.get(PENDING_KEY))
    if pending:
        return accounts.by_id(db, pending)
    return current_account()


@bp.route("/resend-confirmation", methods=["GET", "POST"])
def resend():
    """Otro código para la cuenta que se está confirmando, sin preguntar a dónde.

    Antes se escribía la dirección otra vez, y la pantalla contestaba igual
    existiera o no la cuenta, que es la regla 7. Aquí no se escribe ninguna: el
    código va a la que este navegador registró, o a la que tiene abierta, así
    que no hay nada que esconder y la vuelta puede decir cómo le fue.

    Es un POST porque manda un correo, y un GET lo mandaría una precarga del
    navegador. El GET solo vuelve a la pantalla del código.
    """
    if request.method == "GET":
        return redirect(url_for("auth.confirm"))

    db = get_db()
    account = waiting_account(db)
    account_id = account["_id"] if account else None
    email = account["email"] if account else ""

    if not csrf_ok(request.form.get("csrf_token")):
        log_auth(db, events.RESEND, events.CSRF_FAILED, email=email,
                 account_id=account_id)
        return redirect(url_for("auth.confirm", resent="expired"))
    if account is None:
        # Nada que confirmar en este navegador: se entra con la contraseña, y
        # dentro el aviso del panel vuelve a ofrecer el código.
        log_auth(db, events.RESEND, events.NO_ACCOUNT)
        return redirect(url_for("auth.login"))
    if accounts.is_confirmed(account):
        log_auth(db, events.RESEND, events.ALREADY_CONFIRMED, email=email,
                 account_id=account_id)
        session.pop(PENDING_KEY, None)
        return redirect(url_for("auth.login"))
    if not (rate_limit(db, f"resend:ip:{client_ip()}", *RESEND_PER_IP)
            and rate_limit(db, f"resend:mail:{accounts.normalize_email(email)}",
                           *RESEND_PER_EMAIL)):
        log_auth(db, events.RESEND, events.RATE_LIMITED, email=email,
                 account_id=account_id)
        return redirect(url_for("auth.confirm", resent="wait"))

    if not deliver(db, send_confirmation, account, kind=events.RESEND):
        # deliver() ya dejó el fallo en auth_events y en mail_log.
        return redirect(url_for("auth.confirm", resent="failed"))
    log_auth(db, events.RESEND, events.SENT, email=email, account_id=account_id)
    # Desde el panel no había ninguna pendiente: desde aquí la hay, y es la que
    # compara la pantalla del código.
    await_code(account_id)
    return redirect(url_for("auth.confirm", resent="ok"))


# ---------------------------------------------------------------------- login

@bp.route("/login", methods=["GET", "POST"])
def login():
    # Con «agregar» la pantalla se dibuja aunque ya haya una sesión abierta: es
    # la única forma de sumar una segunda cuenta, y pasa por aquí entera —con su
    # contraseña y su segundo paso— como cualquier otra.
    adding = bool(request.args.get("add"))
    if current_session() and not adding:
        return redirect(landing(current_account()))

    # Quien llegó desde el botón de un plan sigue hasta él al abrir sesión. Se
    # anota al dibujar la pantalla, para que sobreviva al segundo paso.
    if request.method == "GET":
        remember_plan(request.args.get("plan"))
        remember_sample(request.args.get("sample"))
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
            if adding and account and any(
                    one["account"]["_id"] == account["_id"]
                    for one in open_accounts()):
                # Agregar una cuenta que ya está abierta aquí abría otra sesión
                # y cerraba la de antes. Se dice antes de mirar la contraseña,
                # y no revela nada: esas cuentas ya salen en /switch-account.
                # No va a auth_events: no se comprobó nada, y la actividad del
                # administrador lo pintaría como una entrada.
                errors["form"] = t("login_already_open")
                return render_template("login.html", errors=errors,
                                       email=email_value, remember=remember,
                                       adding=adding)
            # Called even when there is no account, so a wrong address and a
            # wrong password take a similar amount of time.
            if verify_password(password, account and account.get("password_hash")):
                # Suspendida es suspendida: hasta ahora el estado se enseñaba y
                # no impedía nada. Se comprueba después de la contraseña, para
                # no decirle a un desconocido qué cuentas están suspendidas.
                if accounts.is_suspended(account) or not member_may_enter(db, account):
                    # Suspendida es suspendida, y un usuario desactivado —o uno
                    # cuya empresa está suspendida— tampoco entra. Se comprueba
                    # después de la contraseña, para no decirle a un desconocido
                    # qué cuentas están suspendidas.
                    errors["form"] = t("error_suspended")
                    log_auth(db, events.LOGIN, events.SUSPENDED,
                             email=email_value, account_id=account["_id"])
                    return render_template("login.html", errors=errors,
                                           email=email_value, remember=remember,
                                           adding=adding)
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
                           switched=bool(request.args.get("change"))
                           and not errors)


@bp.route("/login/code", methods=["GET", "POST"])
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


@bp.route("/logout", methods=["GET", "POST"])
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


@bp.route("/switch-account", methods=["GET", "POST"])
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
        wanted = as_object_id(request.form.get("account"))
        chosen = next((one for one in open_accounts()
                       if one["account"]["_id"] == wanted), None)
        if chosen is None:
            return redirect(url_for("auth.switch_account"))

        if request.form.get("action") == "quitar":
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
    # Volver lleva a la portada, que es donde se aterriza al entrar y al
    # saltar de cuenta, y no a las Estadísticas de la cuenta en uso.
    return render_template(
        "accounts.html", accounts=mine, max_accounts=MAX_ACCOUNTS,
        back=landing(current_account()))


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

@bp.route("/recover", methods=["GET", "POST"])
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
    # La marca la pone /login?add=1 y vive hasta que se abre la sesión
    # nueva, así que sigue puesta al pasar por aquí.
    adding = bool(session.get(ADDING))
    known = account is not None and not adding
    errors: dict[str, str] = {}
    email_value = account["email"] if known else ""

    if request.method == "POST":
        db = get_db()
        if not known:
            # «Pedir otro código» no trae el campo: vale la que se escribió la
            # primera vez. Pasa por todo lo de abajo igual que ella, límites y
            # regla 7 incluidos.
            email_value = request.form.get(
                "email", session.get(RESET_EMAIL, "")).strip()

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
                session[RESET_EMAIL] = email
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
                # La vuelta de «Pedir otro código» lo dice, exista o no la
                # cuenta: la pantalla del código ya dice que se envió en los dos
                # casos.
                again = {"resent": "ok"} if request.form.get("otro") else {}
                return redirect(url_for("auth.recover_code", **again))

    return render_template("recover.html", errors=errors, email=email_value,
                           known=known)


@bp.route("/recover/code", methods=["GET", "POST"])
def recover_code():
    """The same six boxes as the confirmation, for the recovery code."""
    errors: dict[str, str] = {}
    account_id = as_object_id(session.get(RESET_KEY))
    # Solo al dibujarla, como en la confirmación: el código se manda a esta
    # misma dirección, con el parámetro puesto.
    resent = request.method == "GET" and request.args.get("resent") == "ok"

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

    return render_template("recover-code.html", errors=errors, resent=resent,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left(RESET_DEADLINE))


@bp.route("/recover/new", methods=["GET", "POST"])
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
                return redirect(url_for("auth.panel", updated=1))

    return render_template("recover-new.html", errors=errors)


# ---------------------------------------------------------------------- panel

@bp.route("/welcome")
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

    **Mientras la cuenta siga cerrada es la pantalla de la demostración**: lo
    que incluye, el formulario para pedirla y el otro camino, que es contratar.
    Es a donde la devuelven las cuatro pantallas de cliente (`needs()`).
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account)
    if answer:
        return answer
    if accounts.plan_of(account):
        return redirect(url_for("auth.panel"))

    if not is_closed(account):
        return render_template("welcome.html", account=account, closed=False)
    return demo_screen(account)


# La pantalla que quería abrir una cuenta cerrada, con el nombre que lleva en el
# menú: es lo que dice la bienvenida al recibirla (`?para=`, que pone `needs()`).
GATE_NAMES = {
    accounts.STATS: "nav_panel",
    accounts.CAMPAIGNS: "menu_send",
    accounts.SEND: "menu_send",
    accounts.CONTACTS: "menu_contacts",
    accounts.DESIGNS: "menu_designs",
}


def demo_screen(account: dict, *, errors: dict | None = None,
                form: dict | None = None):
    """La bienvenida de una cuenta cerrada.

    Si ya pidió la demostración, en lugar del formulario sale el aviso de que
    se recibió: se pide una sola vez. Si no, el formulario, con lo que acaba de
    escribir si algo salió mal. El número al que se le escribe es el teléfono
    personal del registro.

    Si llegó desde una de las cuatro pantallas, arriba dice cuál quería abrir y
    que se abre contratando o con la demostración. Un valor que no es una
    pantalla no dice nada: la dirección la escribe cualquiera.
    """
    company = current_workspace() or account
    wanted = GATE_NAMES.get(request.args.get("para", ""))
    return render_template(
        "welcome.html", account=account, closed=True, errors=errors or {},
        form=form or {},
        # Lo que quedó guardado, no lo que se acaba de escribir mal.
        asked=company.get("demo_requested_at"),
        asked_phone=company.get("phone", ""),
        contact_choices=accounts.DEMO_CONTACTS,
        source_choices=accounts.DEMO_SOURCES,
        gate=t(wanted) if wanted else "")


@bp.route("/welcome/demo", methods=["POST"])
def request_demo():
    """Pedir la demostración: a qué se dedica el negocio, para qué usará
    Sobreala, cuántos contactos tiene, de dónde salieron y, si quiere, su sitio
    web. Se le escribe al teléfono personal del registro.

    Solo el dueño, y con el correo confirmado como para comprar: es a donde va
    el aviso de que se abrió, y un registro sin confirmar se borra a las 24
    horas. **Se pide una sola vez**: con una ya hecha no se guarda nada ni se
    vuelve a avisar a quien administra, y se vuelve a la bienvenida.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    # Una cuenta abierta no tiene nada que pedir.
    if not is_closed(account):
        return redirect(url_for("auth.welcome"))
    company = current_workspace() or account
    if company.get("demo_requested_at"):
        return redirect(url_for("auth.welcome"))

    db = get_db()
    form = {name: request.form.get(name, "")[:1000]
            for name in ("business", "purpose", "contacts", "source", "website")}
    errors: dict[str, str] = {}
    if not csrf_ok(request.form.get("csrf_token")):
        errors["form"] = t("error_csrf")
    elif not accounts.is_confirmed(account):
        errors["form"] = t("demo_needs_email")
    else:
        business = accounts.clean_answer(form["business"])
        purpose = accounts.clean_answer(form["purpose"])
        for name, answer in (("business", business), ("purpose", purpose)):
            if answer is None:
                errors[name] = t("error_demo_answer", min=accounts.DEMO_ANSWER[0],
                                 max=accounts.DEMO_ANSWER[1])
        if form["contacts"] not in accounts.DEMO_CONTACTS:
            errors["contacts"] = t("error_demo_choose")
        if form["source"] not in accounts.DEMO_SOURCES:
            errors["source"] = t("error_demo_choose")
        website = accounts.clean_website(form["website"])
        if website is None:
            errors["website"] = t("error_demo_website")
        if not errors:
            accounts.request_demo(
                db, account["_id"], business=business, purpose=purpose,
                contacts=form["contacts"], source=form["source"], website=website)
            # A quien administra, con el teléfono y las respuestas dentro. No
            # puede romper una petición que ya quedó guardada: se traga lo suyo.
            notices.demo_to_admins(db, accounts.by_id(db, account["_id"]))
            return redirect(url_for("auth.welcome"))
    return demo_screen(account, errors=errors, form=form)


@bp.route("/dashboard")
def panel():
    """Las estadísticas de la cuenta: sus cifras y las gráficas de sus envíos.

    La dirección sigue siendo /dashboard aunque la pantalla se llame Estadísticas:
    cambiarla rompería los enlaces guardados y el correo de bienvenida a cambio
    de nada.

    La llena `services/stats.py`, el mismo que llena la del administrador, para
    que las dos no puedan separarse.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or needs(account, accounts.STATS)
    if answer:
        return answer

    db = get_db()
    # Las cifras son las de la empresa, también cuando las mira un usuario suyo.
    company = current_workspace()
    # Sin proceso en segundo plano, entrar al panel es el único momento en que
    # alguien puede enterarse de que su plan está por vencerse o ya venció. El
    # aviso es de la empresa y va a su dirección, no a la de quien miró.
    notices.plan_watch(db, company)

    return render_template(
        "stats.html", account=company, pick=None,
        **stats.screen(db, company,
                       period=request.args.get("period", ""),
                       tag=request.args.get("tag", ""),
                       campaign=request.args.get("campaign", "")))


# --------------------------------------------------------------- settings

# The four sections, in the order the sidebar lists them.
MEMBER_SECTIONS = ("security",)
SECTIONS = ("account", "security", "notifications", "billing")

# Del administrador dos. Cuenta y Pagos no significan nada en una cuenta que no
# compra. Seguridad sí: es la cuenta que puede aprobar y suspender a todas las
# demás. Y Notificaciones también, pero con otra lista: la suya es de lo que
# hacen los clientes, no de lo que pasa en su cuenta.
ADMIN_SECTIONS = ("security", "notifications")


def sections_for(account: dict | None) -> tuple[str, ...]:
    """Las secciones que esa cuenta puede abrir. La primera es la de entrada.

    Un usuario tiene **solo Seguridad**: su contraseña, su autenticación de
    múltiples factores y sus dispositivos. La cuenta, los avisos y la
    facturación son de la empresa que lo creó.
    """
    if accounts.is_admin(account):
        return ADMIN_SECTIONS
    if accounts.is_member(account):
        return MEMBER_SECTIONS
    return SECTIONS


@bp.route("/settings", methods=["GET", "POST"])
@bp.route("/settings/<section>", methods=["GET", "POST"])
def settings(section: str = "account"):
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
    postal_error = ""
    account_errors: dict[str, str] = {}
    company: list[dict[str, str]] | None = None
    # Qué fila se está editando: cada una se ve como texto y «Editar» la abre
    # (octubre de 2026). Solo la ve el dueño.
    editing = request.args.get("editar", "") if (
        section == "account" and not accounts.is_admin(account)
        and not accounts.is_member(account)) else ""
    if editing not in ("address", "phones"):
        editing = ""
    if request.method == "POST" and section == "account":
        # Lo que se escribe en Cuenta: la dirección y los teléfonos, cada uno
        # con su propio formulario (`what`).
        if not csrf_ok(request.form.get("csrf_token")):
            return redirect(url_for("auth.settings", section="account"))
        what = request.form.get("what", "address")
        if what == "phones":
            phone = accounts.clean_phone(request.form.get("phone", ""),
                                         request.form.get("phone_country", ""))
            company = typed_company_phones()
            company_phones, bad = accounts.clean_phones(
                [one["number"] for one in company], [one["country"] for one in company])
            if phone and not bad:
                accounts.set_phones(db, account["_id"], phone=phone,
                                    company_phones=company_phones)
                return redirect(url_for("auth.settings", section="account",
                                        phones=1) + "#phones")
            account_errors["phones"] = t("error_phone")
            editing = "phones"
        else:
            address = accounts.clean_postal(request.form.get("address", ""))
            if address is not None:
                if address != accounts.postal_of(account):
                    accounts.set_postal(db, account["_id"], address)
                    changed_verified(db, account, accounts.ADDRESS)
                return redirect(url_for("auth.settings", section="account",
                                        address=1) + "#address")
            postal_error = t("settings_postal_bad", min=accounts.POSTAL_MIN,
                             max=accounts.POSTAL_MAX)
            editing = "address"
    elif request.method == "POST":
        if section != "notifications":
            return redirect(url_for("auth.settings", section=section))
        if csrf_ok(request.form.get("csrf_token")):
            # Only the names models/account.py knows are read. A field naming a
            # security notice is dropped here rather than written, so no form
            # —or anything pretending to be one— can turn the alarm off. Y las
            # que se leen son las suyas: un administrador tiene otra lista.
            mine = accounts.notices_for(account)
            accounts.set_notifications(db, account["_id"], {
                name: bool(request.form.get(name)) for name in mine},
                names=mine)
            log_auth(db, events.SETTINGS, events.OK, email=account["email"],
                     account_id=account["_id"])
        else:
            log_auth(db, events.SETTINGS, events.CSRF_FAILED,
                     email=account["email"], account_id=account["_id"])
        return redirect(url_for("auth.settings", section="notifications",
                                saved=1))

    here = current_session()
    # La renovación automática: por si el aviso de PayPal no llegó, al abrir
    # Facturación se le pregunta qué cobró. Un error de PayPal no la rompe.
    if section == "billing" and accounts.renewal_on(account):
        renewals.sync(db, account)
        account = accounts.by_id(db, account["_id"]) or account
    paid = payments.for_account(db, account["_id"], only_paid=True, limit=100)
    return render_template(
        "settings.html", section=section, sections=sections, account=account,
        plans=plans.PLANS, cycles=plans.CYCLES, currency=plans.CURRENCY,
        plan_until=accounts.plan_until(account),
        # Solo lo cobrado: los intentos a medias se miran desde la ficha.
        payments=paid,
        invoices=invoices.paid_with_invoice(db, account["_id"]),
        invoices_shown=invoices.SHOWN,
        confirmed=accounts.is_confirmed(account),
        plan=accounts.plan_of(account),
        two_step=accounts.two_factor_on(account),
        is_admin=accounts.is_admin(account),
        notifications={name: accounts.wants(account, name)
                       for name in accounts.notices_for(account)},
        devices=sessions.for_account(db, account["_id"]),
        here=here["_id"] if here else None,
        describe=sessions.describe,
        postal=(request.form.get("address", "") if postal_error
                else accounts.postal_of(account)),
        postal_error=postal_error,
        postal_max=accounts.POSTAL_MAX,
        account_errors=account_errors,
        editing=editing,
        renewals_ready=paypal.renewals_ready(),
        vault=accounts.paypal_vault_of(account),
        vault_ready=paypal.vault_ready(),
        subscription=accounts.subscription_of(account),
        renewal_on=accounts.renewal_on(account),
        can_renew=bool(accounts.current_plan(account)) and accounts.can_buy(account),
        **account_screen(db, account, company),
        # Los usuarios de la cuenta, en Seguridad. Un usuario no los ve: esta
        # pantalla es suya para su contraseña y su segundo factor.
        is_member=accounts.is_member(account),
        **({} if accounts.is_member(account) or accounts.is_admin(account)
           else users_screen(db, account)),
    )


def changed_verified(db, account: dict, kind: str) -> None:
    """El dato de una verificación cambió: lo que se miró era el de antes, así
    que vuelve a faltar el documento, y el que esperaba revisión ya no sirve."""
    if accounts.verification_of(account, kind)["status"] != accounts.MISSING:
        accounts.forget_verification(db, account["_id"], kind)
        verification_docs.remove(db, account["_id"], kind)


def account_screen(db, account: dict, company: list[dict[str, str]] | None) -> dict:
    """Lo que dibuja Cuenta además de lo de siempre: los teléfonos, si faltan
    documentos y el límite. Para un administrador o un usuario, nada: esa
    sección no es suya."""
    if accounts.is_admin(account) or accounts.is_member(account):
        return {}
    country, number = countries.split(account.get("phone", ""))
    if company is None:
        company = []
        for stored in account.get("company_phones") or []:
            iso, digits = countries.split(stored)
            company.append({"country": iso, "number": digits})
    return {
        "phone_options": countries.options(),
        "phone_country": country, "phone_number": number,
        "company": company, "company_max": accounts.COMPANY_PHONES_MAX,
        # Lo que se ve cuando no se está editando: los números tal como se
        # guardaron, el personal primero.
        "phones_text": [one for one in [account.get("phone", "")]
                        + list(account.get("company_phones") or []) if one],
        "documents_due": bool(documents_due(account)),
        "limited": accounts.limited_of(account),
    }


def documents_due(account: dict) -> list[str]:
    """Los documentos que todavía hay que enviar: los que faltan y los que se
    rechazaron. Los que están en revisión o verificados no."""
    return [kind for kind in accounts.VERIFY_KINDS
            if accounts.verification_of(account, kind)["status"]
            in (accounts.MISSING, accounts.REJECTED)]


@bp.route("/verification", methods=["GET", "POST"])
def verification():
    """El formulario donde se envían los documentos de la identificación y de la
    dirección. Hasta octubre de 2026 se subían dentro de Configuración → Cuenta.

    Pide **los dos de una vez**, en un solo envío, y después no los enseña: el
    cliente no ve ni cambia lo que mandó, y solo vuelve a pedirse el que se
    rechaza. Los mira una persona de Sobreala desde la ficha y el archivo se
    borra al decidir. Solo el dueño; un usuario y un administrador no.

    PDF, JPG o PNG de hasta 5 MB, reconocidos por cómo empiezan. Si uno de los
    archivos no sirve no se guarda ninguno: así no queda uno solo a medias.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer

    db = get_db()
    due = documents_due(account)
    errors: dict[str, str] = {}
    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif due:
            read = {}
            for kind in due:
                archivo = request.files.get(kind)
                raw = archivo.read(verification_docs.MAX_BYTES + 1) if archivo else b""
                found = verification_docs.file_type(raw) if raw else None
                if not raw or len(raw) > verification_docs.MAX_BYTES or found is None:
                    errors[kind] = t("verify_bad",
                                     mb=verification_docs.MAX_BYTES // (1024 * 1024))
                else:
                    read[kind] = (raw, found)
            if not errors:
                for kind, (raw, (mime, ext)) in read.items():
                    verification_docs.save(db, account["_id"], kind, data=raw,
                                           mime=mime, ext=ext)
                    accounts.set_verification(db, account["_id"], kind,
                                              accounts.REVIEW)
                return redirect(url_for("auth.verification", sent=1))
        else:
            return redirect(url_for("auth.verification"))

    return render_template(
        "verification.html", account=account, due=due, errors=errors,
        states={kind: accounts.verification_of(account, kind)
                for kind in accounts.VERIFY_KINDS},
        kinds=accounts.VERIFY_KINDS, sent=bool(request.args.get("sent")),
        limited=accounts.limited_of(account))


# ---------------------------------------------------------------- devices

@bp.route("/session/close/<token>", methods=["GET", "POST"])
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


@bp.route("/devices/close", methods=["POST"])
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
        return redirect(url_for("auth.settings", section="security"))

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
        # Cerrar la que está en uso es salir de esta cuenta, y solo de esta.
        # Antes se vaciaba la galleta entera, y las otras cuentas abiertas en el
        # navegador se quedaban vivas sin su testigo: filas de más en su
        # Seguridad, con la misma IP. Si queda alguna, se elige entre ellas.
        if here and target == here["_id"]:
            forget_active()
            if open_tokens():
                return redirect(url_for("auth.switch_account"))
            return redirect(url_for("auth.login"))
    return redirect(url_for("auth.settings", section="security"))


# ------------------------------------------------------------------- pagos

@bp.route("/checkout/<plan>")
def checkout(plan: str):
    """El resumen de lo que se va a pagar: el plan en el ciclo que se eligió en
    /pricing, el descuento por los correos sin usar si es una mejora, el total, y
    con qué pagar.

    Es a donde llevan los botones de /pricing. El sitio público es estático y
    vive en otro dominio, así que no puede iniciar un cobro por su cuenta: eso
    es un formulario con testigo y tiene que salir de aquí.

    No cobra nada. El botón hace POST a `start_payment()`, que vuelve a hacer
    todas las cuentas y es el único que habla con quien cobra.
    """
    account = current_account()
    if account is None:
        # El plan viaja por su nombre para que, al entrar, siga hasta aquí.
        return redirect(url_for("auth.login", plan=plan))
    # Un usuario de la cuenta no compra planes: eso es del dueño.
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer

    # Un plan que no está en docs/pricing.md no se compra.
    if not plans.buyable(plan):
        return redirect(url_for("auth.settings", section="billing", error="plan"))

    # El ciclo con que se llegó desde /pricing; un valor inventado se lee como
    # mensual. Si ese no se puede y el otro sí (quien tiene un anual y pulsó
    # un mensual), se enseña el que sí.
    wanted = plans.YEARLY if request.args.get("cycle") == "yearly" else plans.MONTHLY
    other = plans.MONTHLY if wanted == plans.YEARLY else plans.YEARLY
    why = upgrade.refused(account, plan, wanted)
    if why and not upgrade.refused(account, plan, other):
        wanted, other, why = other, wanted, ""
    return render_template(
        "checkout.html", plan=plan, one=plans.PLANS[plan], cycle=wanted,
        # Por qué no se puede comprar: bajar de plan (lo que ya se pagó no se
        # devuelve, y eso se habla), repetir el que se tiene (se vuelve a
        # comprar cuando vence) o un mensual teniendo un anual.
        why=why,
        quote=upgrade.quote(account, plan, wanted),
        # El otro ciclo, si también se puede, para cambiar sin volver a /pricing.
        other=None if upgrade.refused(account, plan, other) else other,
        other_quote=upgrade.quote(account, plan, other),
        itbms_rate=itbms_rate(),
        pay_logos=PAY_LOGOS,
        currency=plans.CURRENCY,
        can_buy=accounts.can_buy(account),
        suspended=accounts.is_suspended(account),
        methods=ready_methods(),
        # Los que faltan se enseñan igual y dicen «pronto»: esconderlos haría
        # que quien no tiene PayPal cerrara la página creyendo que no puede
        # pagar de ninguna forma.
        soon=[one for one in payments.ALL if one not in ready_methods()],
        current=accounts.plan_of(account),
        plan_until=accounts.plan_until(account),
        # La cuenta de PayPal guardada: con ella pagar es un clic.
        saved_paypal=accounts.paypal_vault_of(account),
        # «Renovar solo con PayPal»: solo se ofrece si PayPal está entre los
        # métodos y el aviso está montado, y no en una mejora, que se paga suelta.
        renew_option=(paypal.renewals_ready() and payments.PAYPAL in ready_methods()
                      and not accounts.current_plan(account)))


@bp.route("/settings/billing/invoice/<raw>")
def invoice_file(raw):
    """Bajar la factura de un pago. Solo la cuenta dueña, y siempre como archivo:
    un PDF no se abre dentro de una página del panel."""
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    try:
        payment_id = ObjectId(raw)
    except (InvalidId, TypeError):
        abort(404)
    found = invoices.for_payment(get_db(), account["_id"], payment_id)
    if found is None or not invoices.SHOWN:
        abort(404)
    paid = get_db().payments.find_one({"_id": payment_id,
                                       "account_id": account["_id"]}) or {}
    when = paid.get("completed_at") or found.get("uploaded_at")
    name = f"factura-sobreala-{when:%Y-%m-%d}.pdf" if when else "factura-sobreala.pdf"
    return Response(bytes(found["data"]), mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "no-store"})


def ready_methods() -> list[str]:
    """Con qué se puede pagar ahora mismo: los métodos que tienen cobro hecho y,
    de esos, los que tienen sus credenciales puestas."""
    ready = {payments.PAYPAL: paypal.configured(),
             payments.CARD: paguelofacil.configured()}
    return [one for one in payments.METHODS if ready.get(one)]


@bp.route("/settings/billing/checkout", methods=["POST"])
def start_payment():
    """Crear la orden en PayPal, o el enlace de pago de Paguélofácil si es con
    tarjeta, y mandar al cliente a pagarla.

    Nada se activa aquí. Lo único que hace esta ruta es anotar el intento y
    abrir el checkout; quien decide si alguien pagó es la vuelta, comparando lo
    que responda quien cobra contra lo que ese plan cuesta.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    # Una cuenta de administrador no compra planes: no tiene a quién
    # escribirle. Un usuario tampoco: el plan es de la empresa.
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer

    db = get_db()
    back = url_for("auth.settings", section="billing")
    plan = request.form.get("plan", "")
    cycle = request.form.get("cycle", "")

    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    # Correo confirmado y cuenta no suspendida, nada más. Se comprueba aquí y
    # no solo en la pantalla, porque un formulario se escribe a mano.
    if not accounts.can_buy(account):
        return redirect(url_for("auth.settings", section="billing", error="status"))
    # Un plan que no está en docs/pricing.md no se compra.
    amount = plans.amount(plan, cycle) if plans.buyable(plan) else None
    if amount is None:
        return redirect(url_for("auth.settings", section="billing", error="plan"))
    # Se comprueba aquí y no solo en la pantalla, porque un formulario se
    # escribe a mano y el botón gris del sitio es solo un aviso: con un plan
    # vigente solo se mejora (`upgrade.refused()`).
    if upgrade.refused(account, plan, cycle):
        return redirect(url_for("auth.checkout", plan=plan))
    # Hasta octubre de 2026 aquí se pedía el RUC o la cédula. La identificación
    # ya no se escribe: se verifica con un documento (ver `/verification`).
    # El total con el descuento por los correos sin usar, calculado aquí y
    # guardado en el intento: es lo que se compara al cobrar.
    quote = upgrade.quote(account, plan, cycle)
    amount = f"{quote['total']:.2f}"
    upgrading = accounts.current_plan(account) is not None

    # Con qué eligió pagar. Lo que no se pueda usar ahora mismo se lee como
    # PayPal: el formulario se puede escribir a mano, y Yappy (o la tarjeta sin
    # sus credenciales) está anunciado pero no cobra nada.
    ready = ready_methods()
    method = request.form.get("metodo", "")
    if method not in ready:
        method = payments.PAYPAL
    if method not in ready:
        return redirect(url_for("auth.settings", section="billing", error="paypal"))

    # Mejorar de plan con la renovación encendida: la suscripción cobraría el plan
    # de antes, así que se cancela y la mejora se paga suelta, con su prorrateo.
    # Al terminar se vuelve a activar para el plan nuevo, desde Facturación.
    if upgrading and accounts.renewal_on(account):
        if not renewals.cancel(db, account, "Mejora de plan"):
            return redirect(url_for("auth.settings", section="billing", error="paypal"))

    # «Renovar solo con PayPal»: en lugar de una orden suelta, una suscripción
    # que cobra el primer periodo al aprobarla y los siguientes por su cuenta.
    # Solo con PayPal, solo si el aviso está montado, y no en una mejora, que
    # lleva prorrateo y se paga suelta (la renovación se activa después).
    if (request.form.get("renovar") and method == payments.PAYPAL
            and paypal.renewals_ready() and not upgrading):
        try:
            approve = renewals.start(
                db, account, plan, cycle,
                return_url=f"{Config.APP_BASE_URL}{url_for('auth.finish_renewal')}",
                cancel_url=f"{Config.APP_BASE_URL}{back}?error=cancelled")
        except paypal.PayPalError:
            return redirect(url_for("auth.settings", section="billing", error="paypal"))
        log_auth(db, events.PAYMENT, events.CREATED, email=account["email"],
                 account_id=account["_id"])
        return redirect(approve)

    attempt = payments.start(db, account["_id"], plan=plan, cycle=cycle,
                             amount=amount, currency=plans.CURRENCY,
                             method=method, price=f"{quote['price']:.2f}",
                             credit=f"{quote['credit']['amount']:.2f}",
                             upgrade=upgrading)
    # Con la cuenta de PayPal guardada se cobra sin mandar al cliente a PayPal.
    saved = accounts.paypal_vault_of(account)
    if method == payments.PAYPAL and saved:
        try:
            order_id, result = paypal.pay_saved(
                vault_id=saved["id"], amount=amount, currency=plans.CURRENCY,
                description=f"Sobreala {plans.PLANS[plan]['name']}",
                reference=str(attempt))
        except paypal.PayPalError as exc:
            payments.fail(db, attempt, str(exc))
            return redirect(f"{back}?error=paypal")
        payments.attach_order(db, attempt, order_id)
        log_auth(db, events.PAYMENT, events.CREATED, email=account["email"],
                 account_id=account["_id"])
        return complete_paypal(db, account,
                               payments.by_order(db, account["_id"], order_id),
                               result, back)

    if method == payments.CARD:
        try:
            code, checkout_url = paguelofacil.create_link(
                amount=amount,
                description=f"Sobreala {plans.PLANS[plan]['name']}",
                reference=str(attempt),
                return_url=f"{Config.APP_BASE_URL}{url_for('auth.finish_card')}")
        except paguelofacil.PagueloFacilError as exc:
            payments.fail(db, attempt, str(exc))
            return redirect(url_for("auth.settings", section="billing", error="card"))
        payments.attach_link(db, attempt, code)
        log_auth(db, events.PAYMENT, events.CREATED, email=account["email"],
                 account_id=account["_id"])
        return redirect(checkout_url)

    try:
        order_id, approve = paypal.create(
            amount=amount, currency=plans.CURRENCY,
            description=f"Sobreala {plans.PLANS[plan]['name']}",
            reference=str(attempt),
            return_url=f"{Config.APP_BASE_URL}{url_for('auth.finish_payment')}",
            cancel_url=f"{Config.APP_BASE_URL}{back}?error=cancelled")
    except paypal.PayPalError as exc:
        payments.fail(db, attempt, str(exc))
        return redirect(url_for("auth.settings", section="billing", error="paypal"))

    payments.attach_order(db, attempt, order_id)
    log_auth(db, events.PAYMENT, events.CREATED, email=account["email"],
             account_id=account["_id"])
    return redirect(approve)


@bp.route("/settings/billing/renewal", methods=["POST"])
def start_renewal():
    """Activar la renovación automática desde Facturación, para quien ya pagó
    suelto: la suscripción cobra **el día que vence lo que pagó**, no antes.

    Solo el dueño, con un plan vigente (si no, se contrata en el pago, donde está
    la misma casilla), y solo si el aviso de PayPal está montado.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    back = url_for("auth.settings", section="billing")
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    plan = accounts.current_plan(account)
    if (not plan or not accounts.can_buy(account) or not paypal.renewals_ready()
            or accounts.renewal_on(account)):
        return redirect(back)
    db = get_db()
    try:
        approve = renewals.start(
            db, account, plan, accounts.plan_cycle(account),
            first_charge=accounts.plan_until(account),
            return_url=f"{Config.APP_BASE_URL}{url_for('auth.finish_renewal')}",
            cancel_url=f"{Config.APP_BASE_URL}{back}?error=cancelled")
    except paypal.PayPalError:
        return redirect(f"{back}?error=paypal")
    return redirect(approve)


@bp.route("/settings/billing/renewal/return")
def finish_renewal():
    """La vuelta de PayPal después de aprobar la suscripción.

    Lo que trae la dirección es el identificador de la suscripción y nada más:
    se le pregunta a PayPal si es de esta cuenta y si está aprobada
    (`renewals.confirm()`), y después se le piden sus cobros (`renewals.sync()`),
    que es lo único que activa el plan. Quien paga por primera vez con la casilla
    aterriza en su recibo."""
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    db = get_db()
    back = url_for("auth.settings", section="billing")
    sub_id = request.args.get("subscription_id", "")[:64]
    if not renewals.confirm(db, account, sub_id):
        return redirect(f"{back}?error=cancelled")
    new = renewals.sync(db, accounts.by_id(db, account["_id"]))
    fresh = accounts.by_id(db, account["_id"])
    sub = accounts.subscription_of(fresh) or {}
    until = accounts.plan_until(fresh)
    if until and sub.get("plan"):
        notices.renewal_on(fresh, plan=sub["plan"], cycle=sub["cycle"], when=until)
    if not new:
        # Quien la activó para cuando venza lo que ya pagó: todavía no cobra.
        return redirect(f"{back}?renewal=on")
    return redirect(url_for("auth.receipt", raw=new[0]))


@bp.route("/settings/billing/renewal/cancel", methods=["POST"])
def cancel_renewal():
    """Cancelar la renovación automática. Lo ya pagado sigue hasta su fecha."""
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    back = url_for("auth.settings", section="billing")
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    mine = accounts.subscription_of(account) or {}
    if mine.get("status") in (accounts.SUB_ACTIVE, accounts.SUB_SUSPENDED):
        if not renewals.cancel(get_db(), account):
            return redirect(f"{back}?error=paypal")
    return redirect(f"{back}?renewal=off")


@bp.route("/settings/billing/paypal", methods=["POST"])
def add_paypal():
    """Guardar la cuenta de PayPal: se manda al cliente a entrar a PayPal una vez,
    sin plan y sin cobro. Solo el dueño."""
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    back = url_for("auth.settings", section="billing")
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    if not paypal.vault_ready() or accounts.paypal_vault_of(account):
        return redirect(back)
    db = get_db()
    try:
        setup_id, approve = paypal.create_setup_token(
            reference=str(account["_id"]),
            return_url=f"{Config.APP_BASE_URL}{url_for('auth.finish_paypal')}",
            cancel_url=f"{Config.APP_BASE_URL}{back}?error=cancelled")
    except paypal.PayPalError:
        return redirect(f"{back}?error=paypal")
    accounts.start_paypal_setup(db, account["_id"], setup_id)
    return redirect(approve)


@bp.route("/settings/billing/paypal/return")
def finish_paypal():
    """La vuelta de PayPal después de aprobar. Lo que trae la dirección solo vale
    si es la petición que se le hizo a esta cuenta; lo que prueba que la cuenta
    quedó guardada es la respuesta de PayPal al servidor."""
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    back = url_for("auth.settings", section="billing")
    setup_id = request.args.get("approval_token_id", "")[:64]
    pending = (account.get("paypal_setup") or {}).get("id")
    if not setup_id or setup_id != pending:
        return redirect(f"{back}?error=cancelled")
    try:
        saved = paypal.save_payment_token(setup_id)
    except paypal.PayPalError:
        return redirect(f"{back}?error=paypal")
    accounts.set_paypal_vault(get_db(), account["_id"], token_id=saved["id"],
                              payer=saved["payer"])
    return redirect(f"{back}?paypal=saved")


@bp.route("/settings/billing/paypal/remove", methods=["POST"])
def remove_paypal():
    """Quitar la cuenta de PayPal guardada, en PayPal y aquí. Si PayPal no la
    quitó, aquí tampoco: así no queda guardada sin que se vea."""
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    back = url_for("auth.settings", section="billing")
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    saved = accounts.paypal_vault_of(account)
    if saved:
        try:
            paypal.delete_payment_token(saved["id"])
        except paypal.PayPalError:
            return redirect(f"{back}?error=paypal")
        accounts.clear_paypal_vault(get_db(), account["_id"])
    return redirect(f"{back}?paypal=removed")


@bp.route("/settings/billing/return")
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
    back = url_for("auth.settings", section="billing")
    order_id = request.args.get("token", "")[:64]
    attempt = payments.by_order(db, account["_id"], order_id) if order_id else None
    if attempt is None:
        return redirect(f"{back}?error=order")
    # Recargar esta página entra por aquí otra vez. El intento ya está cobrado,
    # así que no se cobra ni se alarga nada: se vuelve a enseñar su recibo.
    if attempt["status"] == payments.COMPLETED:
        return redirect(url_for("auth.receipt", raw=attempt["_id"]))
    if attempt["status"] != payments.CREATED:
        return redirect(f"{back}?done=1")

    try:
        result = paypal.capture(order_id)
    except paypal.PayPalError as exc:
        payments.fail(db, attempt["_id"], str(exc))
        return redirect(f"{back}?error=paypal")

    return complete_paypal(db, account, attempt, result, back)


def complete_paypal(db, account, attempt, result: dict, back: str):
    """Lo que responde PayPal al cobrar, comparado con lo que se pidió, y solo
    entonces activar. La usan la vuelta de PayPal y el pago con la cuenta guardada,
    así que las dos hacen exactamente lo mismo."""
    # Lo que se pidió cobrar, guardado en el intento: en una mejora ya lleva el
    # descuento. Los de antes no lo guardaban distinto del precio de lista.
    esperado = attempt.get("amount") or plans.amount(attempt["plan"], attempt["cycle"])
    if result["status"] != "COMPLETED":
        payments.fail(db, attempt["_id"], f"estado {result['status']}")
        return redirect(f"{back}?error=capture")
    if result["amount"] != esperado or result["currency"] != attempt["currency"]:
        # Cobró algo distinto de lo que vale el plan: no se activa nada y queda
        # escrito, que es lo que hace falta para reclamarlo.
        payments.fail(db, attempt["_id"],
                      f"cobró {result['amount']} {result['currency']}, "
                      f"esperaba {esperado} {attempt['currency']}")
        log_auth(db, events.PAYMENT, events.INVALID, email=account["email"],
                 account_id=account["_id"])
        return redirect(f"{back}?error=amount")

    settle(db, account, attempt, payer_email=result.get("payer", ""))
    return redirect(url_for("auth.receipt", raw=attempt["_id"]))


def settle(db, account, attempt, *, payer_email: str = "", last4: str = "",
           order_id: str = "") -> bool:
    """Lo que pasa después de un cobro comprobado: marcarlo, activar el plan y
    avisar. **False si ese intento ya estaba cobrado**, y entonces no se hace
    nada más.

    Es la misma para PayPal, para la vuelta de la tarjeta y para el aviso
    automático de Paguélofácil, así que las tres hacen exactamente lo mismo. La
    escritura condicional de `payments.complete()` es lo que impide que dos de
    ellas den dos periodos por un solo pago.
    """
    if not payments.complete(db, attempt["_id"], payer_email=payer_email,
                             last4=last4, order_id=order_id):
        return False

    # Una mejora (se pagó teniendo un plan vigente) empieza hoy y con el mes
    # de nuevo: su descuento ya fue por lo que quedaba del plan de antes.
    # Renovar, pagar el mismo plan que todavía corre, ya no tiene camino, pero
    # si un pago llegara así suma al final. Se mira antes de activar, que es
    # cuando la cuenta todavía dice lo que decía.
    fresh = bool(attempt.get("upgrade"))
    running = accounts.plan_until(account)
    renewed = (not fresh and accounts.plan_of(account) == attempt["plan"]
               and running is not None and running > accounts.now())
    until = payments.until(
        attempt["cycle"],
        since=accounts.now() if fresh else accounts.renews_from(account, attempt["plan"]))
    accounts.activate_plan(db, account["_id"], attempt["plan"], until,
                           cycle=attempt["cycle"], fresh_month=fresh)
    log_auth(db, events.PAYMENT, events.OK, email=account["email"],
             account_id=account["_id"])

    # Los dos correos van después de todo lo que decide algo: si el correo no
    # sale, el pago sigue cobrado y el plan activo.
    notices.paid(account, plan=attempt["plan"], until=until, renewed=renewed,
                 charged=attempt.get("amount", ""), credit=attempt.get("credit", ""))
    notices.payment_to_admins(db, account, plan=attempt["plan"])
    return True


def card_verdict(attempt, oper: str) -> tuple[str, dict | None]:
    """Si la operación `oper` de Paguélofácil paga este intento. Devuelve un
    motivo vacío si sí, o la clave del error si no, y lo que dijo Paguélofácil.

    Se le pregunta a Paguélofácil y no se mira lo que trajo el navegador, que
    cualquiera escribe. Tres cosas: que esté aprobada y capturada, que sea por
    lo que cuesta el plan, y que su descripción lleve la referencia de **este**
    intento, así una operación pagada para otro no sirve para este.
    """
    try:
        found = paguelofacil.find(oper)
    except paguelofacil.PagueloFacilError:
        return "card", None
    if not paguelofacil.paid(found):
        return "capture", found
    if str(attempt["_id"]) not in found["description"]:
        return "order", found
    wanted = attempt.get("amount") or plans.amount(attempt["plan"], attempt["cycle"])
    if found["amount"] != wanted:
        return "amount", found
    return "", found


@bp.route("/settings/billing/card/return", methods=["GET", "POST"])
def finish_card():
    """La vuelta de Paguélofácil después de pagar con tarjeta.

    Trae nuestro intento en `PARM_1` y la operación en `Oper`, además de un
    «Estado» y un monto que no se leen: los escribe cualquiera. Se consulta la
    operación y solo entonces se activa. Si el aviso automático llegó antes y
    ya lo cobró, aquí solo se dice que está hecho.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    back = url_for("auth.settings", section="billing")
    values = request.values
    try:
        attempt_id = ObjectId(values.get("PARM_1", ""))
    except (InvalidId, TypeError):
        return redirect(f"{back}?error=order")
    attempt = payments.by_id(db, attempt_id, account["_id"])
    if attempt is None or attempt.get("method") != payments.CARD:
        return redirect(f"{back}?error=order")
    if attempt["status"] == payments.COMPLETED:
        return redirect(url_for("auth.receipt", raw=attempt["_id"]))
    if attempt["status"] != payments.CREATED:
        return redirect(f"{back}?done=1")

    oper = values.get("Oper", "")[:64]
    if not oper:
        # Volvió sin operación: canceló o se le venció el enlace. El intento se
        # queda como está, por si el aviso automático cuenta otra cosa.
        return redirect(f"{back}?error=cancelled")

    why, found = card_verdict(attempt, oper)
    if why == "card":
        return redirect(f"{back}?error=card")
    if why:
        payments.fail(db, attempt["_id"],
                      f"{why}: {found['status'] if found else '-'} "
                      f"{found['operation'] if found else ''} "
                      f"{found['amount'] if found else ''}")
        if why == "amount":
            log_auth(db, events.PAYMENT, events.INVALID, email=account["email"],
                     account_id=account["_id"])
        return redirect(f"{back}?error={why}")

    settle(db, account, attempt, payer_email=found["email"],
           last4=found["last4"], order_id=oper)
    return redirect(url_for("auth.receipt", raw=attempt["_id"]))


# Los logos de cada método de pago en la pantalla de contratar: el archivo que
# copia build_assets.py y su texto alternativo.
PAY_LOGOS = {
    payments.PAYPAL: [("paypal.png", "PayPal")],
    payments.CARD: [("visa.svg", "Visa"), ("mastercard.svg", "Mastercard")],
    payments.YAPPY: [("yappy.svg", "Yappy")],
}


def itbms_rate() -> str:
    """La tasa del ITBMS para escribirla: «7»."""
    return f"{(plans.ITBMS * 100).normalize():f}"


@bp.route("/settings/billing/receipt/<raw>")
def receipt(raw):
    """El recibo de un pago cobrado: a donde se llega al volver de pagar.

    Solo el de esta cuenta, y solo cobrado: un intento a medias no tiene
    recibo. Lo abre el dueño, que es quien compra.
    """
    account = current_account()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(account) or owner_only(account)
    if answer:
        return answer
    try:
        payment_id = ObjectId(raw)
    except (InvalidId, TypeError):
        abort(404)
    paid = payments.by_id(get_db(), payment_id, account["_id"])
    if paid is None or paid.get("status") != payments.COMPLETED:
        abort(404)
    return render_template(
        "receipt.html", paid=paid, plan_name=plans.PLANS.get(
            paid.get("plan", ""), {}).get("name", paid.get("plan", "")),
        number=str(paid["_id"])[-8:].upper(),
        currency=paid.get("currency") or plans.CURRENCY)


# ------------------------------------------------------ los usuarios de la cuenta

# Cuántos días vale la invitación. Una semana: lo suficiente para que alguien la
# abra el lunes siguiente, y no tanto como para que un correo viejo siga
# abriendo la cuenta meses después.
INVITE_DAYS = 7


def invite_link(db, member) -> str:
    """Un enlace nuevo para poner la contraseña. Los anteriores dejan de valer:
    si el dueño lo reenvía es porque el otro se perdió."""
    tokens.discard(db, member["_id"], tokens.INVITE)
    raw = tokens.issue_link(db, member["_id"], tokens.INVITE, {},
                            days=INVITE_DAYS)
    return f"{Config.APP_BASE_URL}{url_for('auth.accept_invite', token=raw)}"


def send_invite(db, owner, member) -> bool:
    return notices.invited(member, company=owner.get("company_name", ""),
                           link=invite_link(db, member), days=INVITE_DAYS)


def users_screen(db, owner):
    """Lo que la sección Usuarios necesita saber."""
    return {
        "members": accounts.members_of(db, owner["_id"]),
        "seats": plans.users(accounts.plan_of(owner)),
        "seats_used": accounts.seats_used(db, owner["_id"]),
        "seats_left": accounts.seats_left(db, owner),
    }


@bp.route("/settings/users/new", methods=["GET", "POST"])
@bp.route("/settings/users/<raw>", methods=["GET", "POST"])
def user_form(raw: str = ""):
    """Crear un usuario o cambiarle los permisos.

    Pantalla aparte y no una fila: los permisos son casillas con su explicación,
    y eso no cabe al lado de un nombre. Al crear no se pide contraseña: le llega
    una invitación y la pone él.
    """
    owner = current_account()
    if owner is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(owner) or owner_only(owner)
    if answer:
        return answer

    db = get_db()
    member = None
    if raw:
        member_id = as_object_id(raw)
        member = accounts.member_of(db, owner["_id"], member_id) if member_id else None
        if member is None:
            abort(404)

    errors: dict[str, str] = {}
    form = request.form
    if request.method == "POST":
        name = form.get("nombre", "").strip()[:80]
        email = clean_email(form.get("email", ""))
        wanted = accounts.clean_permissions(form.getlist("permiso"))
        if not csrf_ok(form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif member is not None:
            accounts.set_permissions(db, owner["_id"], member["_id"], wanted)
            return redirect(url_for("auth.settings", section="security",
                                    user="saved") + "#users")
        else:
            if not name:
                errors["nombre"] = t("error_required")
            if email is None:
                errors["email"] = t("error_email")
            # El sitio se mira aquí y no solo en la pantalla: el formulario se
            # escribe a mano, y una cuenta llena podría seguir invitando.
            elif accounts.seats_left(db, owner) <= 0:
                errors["form"] = t("users_no_seats")
            if not errors:
                made = accounts.add_member(db, owner, contact_name=name,
                                           email=email, permissions=wanted)
                if made is None:
                    # Esa dirección ya tiene cuenta en Sobreala. No se dice de
                    # quién es, pero sí que no se puede usar: quien invita tiene
                    # que poder arreglarlo.
                    errors["email"] = t("users_email_taken")
                else:
                    send_invite(db, owner, made)
                    log_auth(db, events.SETTINGS, events.OK,
                             email=made["email"], account_id=made["_id"])
                    return redirect(url_for("auth.settings", section="security",
                                            user="invited") + "#users")

    return render_template(
        "users.html", account=owner, member=member, errors=errors, form=form,
        permissions=accounts.PERMISSIONS, implies=accounts.IMPLIES,
        **users_screen(db, owner))


@bp.route("/settings/users/<raw>/status", methods=["POST"])
def user_state(raw):
    """Desactivar, activar, reenviar la invitación o borrar a un usuario.

    Desactivar y borrar **le cierran las sesiones**: quitarle la entrada y
    dejarlo dentro no es quitarle la entrada.
    """
    owner = current_account()
    if owner is None:
        return redirect(url_for("auth.login"))
    answer = not_for_admins(owner) or owner_only(owner)
    if answer:
        return answer

    db = get_db()
    back = url_for("auth.settings", section="security") + "#users"
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(back)
    member_id = as_object_id(raw)
    member = accounts.member_of(db, owner["_id"], member_id) if member_id else None
    if member is None:
        return redirect(back)

    what = request.form.get("action", "")
    if what == "borrar":
        sessions.revoke_others(db, member["_id"])
        accounts.remove_member(db, owner["_id"], member["_id"])
    elif what == "desactivar":
        accounts.set_member_status(db, owner["_id"], member["_id"], disabled=True)
        sessions.revoke_others(db, member["_id"])
    elif what == "activar":
        accounts.set_member_status(db, owner["_id"], member["_id"], disabled=False)
    elif what == "reenviar":
        send_invite(db, owner, member)
    return redirect(back)


@bp.route("/invitation/<token>", methods=["GET", "POST"])
def accept_invite(token):
    """Aceptar la invitación: poner la contraseña y entrar.

    El enlace es de un solo uso y vence. Lo que prueba es que esa dirección es
    suya, que es exactamente lo que probaría un código; por eso al terminar el
    correo queda confirmado y la sesión se abre aquí mismo.
    """
    db = get_db()
    found = tokens.find_link(db, token, tokens.INVITE)
    member = accounts.by_id(db, found["account_id"]) if found else None
    if member is None or not accounts.is_member(member):
        return render_template("invite.html", gone=True), 410

    owner = accounts.by_id(db, member["owner_id"])
    errors: dict[str, str] = {}
    if request.method == "POST":
        password = request.form.get("password", "")
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        else:
            problem = password_problem(password)
            if problem:
                errors["password"] = problem
            elif not tokens.spend(db, found):
                # Alguien lo usó mientras tanto: el enlace vale una vez.
                return render_template("invite.html", gone=True), 410
            else:
                accounts.accept_invitation(db, member["_id"], password)
                fresh = accounts.by_id(db, member["_id"])
                sign_in(fresh)
                log_auth(db, events.LOGIN, events.OK, email=fresh["email"],
                         account_id=fresh["_id"])
                return redirect(home_for(fresh))

    return render_template("invite.html", member=member, owner=owner,
                           errors=errors, gone=False)


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


@bp.route("/account/email", methods=["GET", "POST"])
def change_email():
    """Mover la cuenta a otra dirección: la contraseña, y después el código.

    Corregir el correo (`/confirm/corregir`) es otra cosa y es de antes: sirve
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


@bp.route("/account/email/code", methods=["GET", "POST"])
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
                    return redirect(url_for("auth.settings", section="account",
                                            email=1))
                # Se la llevó otra cuenta entre que se pidió el código y se
                # escribió. El índice único es quien lo dice.
                accounts.cancel_email_change(db, account["_id"])
                log_auth(db, events.EMAIL_CHANGE, events.TAKEN, email=waiting,
                         account_id=account["_id"])
                return redirect(url_for("auth.change_email", taken=1))

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


@bp.route("/account/two-factor", methods=["GET", "POST"])
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
              else request.args.get("action", "")) or ""
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
            return redirect(url_for("auth.settings", section="security",
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


@bp.route("/account/two-factor/enable", methods=["GET", "POST"])
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
        return redirect(url_for("auth.two_factor", expired=1))

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


@bp.route("/change-password", methods=["GET", "POST"])
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
                return redirect(url_for("auth.settings", section="security",
                                        updated=1))

    return render_template("password.html", errors=errors)
