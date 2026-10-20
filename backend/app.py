"""The Flask application."""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, g, jsonify, render_template, request, session
from flask.sessions import SecureCookieSessionInterface
from pymongo.errors import PyMongoError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

# La ficha que manda un botón de descarga (`_download_arrived`).
DOWNLOAD_TOKEN = re.compile(r"[A-Za-z0-9]{8,32}")
from db import ensure_indexes_once, health, indexes_ready
from i18n import ago, at_moment, on_date, t
from models.account import (current_plan, is_admin, is_open, plan_cycle,
                            status_of as account_status_of)
from services import dashboard, mailer
from services.plans import money
from services.security import MIN_PASSWORD_LENGTH, csrf_token


# A crumb the public site can read. It carries "1" for a client and "admin" for
# an administrator, and nothing else: unlike the session cookie it is NOT
# HttpOnly, so any script on sobreala.com can see it, and anything with a name
# or an address in it would be handing that to a static site with no reason to
# know it.
#
# El rol va ahí porque el menú del sitio público le ofrecía a un administrador
# el panel de envíos y los contactos, que su cuenta no tiene. Cuesta que
# cualquier script de ese dominio pueda saber que quien mira es administrador;
# no hay forma de que un sitio estático lo sepa sin que se lo digan.
HINT_COOKIE = "sa_in"


def company_state(company: dict | None) -> str:
    """En qué punto está la empresa, para los botones del sitio (octubre de
    2026): `paid` con un plan vigente, `demo` abierta sin plan (por la
    demostración, o con un plan vencido), `requested` si pidió la demostración
    y todavía no se abrió, y `closed` si no. Sin esto el sitio le ofrecía
    «Solicitar demo» a quien ya la tenía o ya había pagado."""
    if current_plan(company):
        return "paid"
    if is_open(company):
        return "demo"
    if (company or {}).get("demo_requested_at"):
        return "requested"
    return "closed"


def hint_domain() -> str | None:
    """The parent domain both deploys hang off, or None when there is none.

    The panel lives at app.sobreala.com and the site at sobreala.com, so the
    crumb goes on .sobreala.com to be readable from both. Running locally there
    is nothing to share —cookies ignore ports— and the domain is left out,
    because a browser refuses one that does not match the host.
    """
    host = urlparse(Config.PUBLIC_SITE_URL).hostname or ""
    if not host or host == "localhost" or host.replace(".", "").isdigit():
        return None
    return f".{host}"


def is_api() -> bool:
    """Si esta petición es de la API pública (octubre de 2026)."""
    return request.path.startswith("/api/")


class PanelSessions(SecureCookieSessionInterface):
    """La galleta de siempre, menos bajo `/api/`.

    La API entra con una llave y nunca con la sesión del navegador. Ahí la
    sesión es la vacía de Flask (`NullSession`): no lee la galleta, revienta si
    algo intenta escribirle, y no se guarda, así que ninguna respuesta de la API
    pone una galleta.
    """

    def open_session(self, app, request):
        if request.path.startswith("/api/"):
            return self.make_null_session(app)
        return super().open_session(app, request)


def asset_version() -> str:
    """A short stamp that changes when the stylesheet or the script does.

    Appended to their URLs so a browser holding yesterday's panel.css does not
    keep it. Without this, a page whose colours moved into the stylesheet drew
    with the old one: the logo, which takes its fill from a CSS variable, came
    out black.
    """
    stamp = 0.0
    for name in ("static/css/panel.css", "static/js/panel.js",
                 "static/js/canvas.js"):
        path = Path(__file__).resolve().parent / name
        if path.exists():
            stamp = max(stamp, path.stat().st_mtime)
    return str(int(stamp))


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.session_interface = PanelSessions()

    app.permanent_session_lifetime = timedelta(
        seconds=app.config["PERMANENT_SESSION_LIFETIME"]
    )

    # Behind Railway's proxy every request would otherwise arrive with the
    # proxy's own address, so the per-IP rate limit could not tell one visitor
    # from another and would block them all together. This reads the real
    # address, and the scheme, from the headers the proxy sets.
    if not app.config.get("TESTING"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Configuration is checked at boot on purpose: a missing SECRET_KEY is a
    # mistake in the deploy, not a passing network problem, and starting anyway
    # would only hide it.
    #
    # The database is NOT touched here. It used to be, and an unreachable
    # database killed every worker at import time, which the platform reported
    # as a bare 502 with nothing readable anywhere.
    if not app.config.get("TESTING"):
        Config.check()

    from blueprints.admin import bp as admin_bp
    from blueprints.auth import bp as auth_bp
    from blueprints.contacts import bp as contacts_bp
    from blueprints.designs import bp as designs_bp
    from blueprints.campaigns import bp as campaigns_bp
    from blueprints.analytics import bp as analytics_bp
    from blueprints.media import bp as media_bp
    from blueprints.unsubscribe import bp as unsubscribe_bp
    from blueprints.downloads import bp as downloads_bp
    from blueprints.search import bp as search_bp
    from blueprints.webhooks import bp as webhooks_bp
    from blueprints.api import bp as api_bp
    from blueprints.developers import bp as developers_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(designs_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(campaigns_bp)
    # Bajarse lo que enseña Estadísticas, en CSV y en PDF.
    app.register_blueprint(analytics_bp)
    # Las imagenes de las plantillas y la baja son lo unico que se sirve sin
    # sesion, porque quien las pide no es el cliente: es el lector de correo de
    # cada persona que recibio la campana, y la persona misma.
    app.register_blueprint(media_bp)
    app.register_blueprint(unsubscribe_bp)
    # El archivo de un correo individual: lo baja quien lo recibió, sin sesión.
    app.register_blueprint(downloads_bp)
    # La búsqueda de la barra, con sesión.
    app.register_blueprint(search_bp)
    # Los avisos de Amazon. Tampoco llevan sesion: quien llama es SNS, y lo que
    # lo autoriza es el secreto de la direccion.
    app.register_blueprint(webhooks_bp)
    # La API pública (octubre de 2026): entra con una llave, nunca con la
    # sesión. Y la rama «API» del Dashboard, donde el dueño maneja sus llaves.
    app.register_blueprint(api_bp)
    app.register_blueprint(developers_bp)

    # The size limit on an imported file, enforced by Flask before the request
    # reaches any code of ours: an oversized upload is refused without being
    # read. The margin is for the rest of the form, which is a few hundred
    # bytes.
    # setdefault no vale aquí: Flask ya trae la clave puesta en None, así que
    # nunca la escribiría y el corte no llegaría a hacerse nunca.
    if not app.config.get("MAX_CONTENT_LENGTH"):
        app.config["MAX_CONTENT_LENGTH"] = Config.IMPORT_MAX_BYTES + 64 * 1024

    @app.before_request
    def _prepare_indexes():
        # Lazily, and only until one attempt succeeds. The unique index on the
        # email is what prevents duplicate accounts, so it cannot be quietly
        # skipped just because the database was down when the process started.
        if not app.config.get("TESTING") and not indexes_ready():
            ensure_indexes_once()

    # Templates hold no Spanish of their own: they ask i18n for it.
    app.jinja_env.globals.update(t=t, csrf_token=csrf_token,
                                 # Para que un estado viejo en la base no
                                 # convierta una pantalla en un error.
                                 status_of=account_status_of,
                                 asset_version=asset_version(),
                                 site_url=Config.PUBLIC_SITE_URL,
                                 # El mismo número que refuerza el servidor, para
                                 # que la lista de la pantalla no pueda mentir.
                                 password_min=MIN_PASSWORD_LENGTH,
                                 # El árbol del Dashboard y la fila marcada.
                                 dash_tree=dashboard.tree,
                                 dash_here=dashboard.here,
                                 dash_holds=dashboard.holds,
                                 # El pie de los correos del sistema.
                                 mail_links=mailer.footer_links())
    app.jinja_env.filters["ago"] = ago
    # Para lo que va a pasar, no para lo que pasó: «17 de septiembre a las 09:00».
    app.jinja_env.filters["at_moment"] = at_moment
    app.jinja_env.filters["on_date"] = on_date
    # Un monto del historial: «USD 15».
    app.jinja_env.filters["money"] = money
    # El nombre en español de un permiso de usuario, para la lista de Usuarios.
    app.jinja_env.filters["permission_name"] = lambda name: t("users_can_" + name)

    @app.before_request
    def _csp_nonce():
        # One per response, for the single inline script in the page head: the
        # one that picks the theme before the first paint. Everything else is a
        # file under /static, so the policy can refuse inline code outright.
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _expose_nonce():
        return {"csp_nonce": g.get("csp_nonce", "")}

    @app.after_request
    def _download_arrived(response):
        """Avisarle al botón que pidió una descarga que el archivo ya llegó.

        Una descarga no cambia de página, así que el botón que gira no tiene
        cómo enterarse (octubre de 2026). El botón manda una ficha al azar
        (`dl`), y la respuesta que trae el archivo la devuelve en una galleta
        corta que `panel.js` mira cada poco. Solo la ficha: ni qué se bajó ni
        de quién.
        """
        # Primero si es un archivo: solo entonces se lee el formulario. Leerlo
        # en cualquier otra respuesta volvería a pasar por el cuerpo, y en una
        # que Flask ya cortó por grande (413) eso rompería la respuesta. La API
        # no pone galletas.
        if is_api() or not response.headers.get("Content-Disposition", "").startswith("attachment"):
            return response
        token = request.args.get("dl") or (request.form.get("dl") if request.method == "POST" else "")
        if token and DOWNLOAD_TOKEN.fullmatch(token):
            response.set_cookie("sa_dl", token, max_age=60, path="/", samesite="Lax",
                                secure=request.is_secure)
        return response

    @app.after_request
    def _session_hint(response):
        """Keep the crumb in step with the session.

        It is a hint, never a proof: a session closed from another device leaves
        it behind, the public site keeps offering "Mi panel", and the panel then
        asks whoever clicks to sign in. That is the right order — the crumb is
        for drawing a button, not for letting anyone in.
        """
        from blueprints.auth.routes import SESSION_KEY

        from blueprints.auth.routes import current_account, current_workspace

        # La API no tiene sesión ni pone galletas.
        if is_api():
            return response
        signed_in = bool(session.get(SESSION_KEY))
        # Se compara contra el valor que debería tener, no contra su presencia:
        # así el día que una cuenta pasa a administrador la galleta se reescribe
        # sola en la siguiente página.
        wanted = ""
        if signed_in:
            try:
                account = current_account()
                if is_admin(account):
                    wanted = "admin"
                else:
                    # «1:<plan>:<ciclo>:<estado>[:<logo>]». El plan vigente va para que
                    # /pricing pueda apagar el que ya se tiene y los menores
                    # (vencido no va, que es cuando se vuelve a comprar), y el
                    # estado de la empresa (`company_state`) para que la
                    # portada no le ofrezca la demostración a quien ya la tiene.
                    # Y el nombre del logo, si tiene (octubre de 2026), para que
                    # la barra del sitio lo enseñe como la del panel: ya es
                    # público, es la dirección de una imagen. Son de la
                    # empresa, también para un usuario suyo. Cuesta lo mismo
                    # que costó el rol, y es el mismo trato: cualquier script
                    # de ese dominio puede leerlo.
                    company = current_workspace() or account
                    plan = current_plan(company)
                    cycle = plan_cycle(company) if plan else ""
                    logo = (company or {}).get("logo") or ""
                    wanted = (f"1:{plan or ''}:{cycle}:{company_state(company)}"
                              + (f":{logo}" if logo else ""))
                # La última zona en la que se vio esta cuenta: es la de los
                # correos que le llegan sin estar mirando, como un plan que
                # vence. Solo se escribe cuando cambia.
                from services import clock
                seen = clock.cookie_zone()
                if account and seen and account.get("time_zone") != seen:
                    from db import get_db
                    get_db().accounts.update_one(
                        {"_id": account["_id"]}, {"$set": {"time_zone": seen}})
            except Exception:  # noqa: BLE001 - la página vale más que la migaja
                wanted = "1"
        if wanted and request.cookies.get(HINT_COOKIE) != wanted:
            response.set_cookie(
                HINT_COOKIE, wanted,
                max_age=app.config["PERMANENT_SESSION_LIFETIME"],
                domain=hint_domain(), samesite="Lax", httponly=False,
                secure=app.config.get("SESSION_COOKIE_SECURE", False))
        elif not wanted and request.cookies.get(HINT_COOKIE) is not None:
            response.delete_cookie(HINT_COOKIE, domain=hint_domain())
        return response

    @app.after_request
    def _security_headers(response):
        """What the browser is allowed to do with this page.

        The policy is deliberately narrow: everything the panel loads is served
        from this same origin, so anything injected into a page — a script tag,
        a remote stylesheet, a form pointed somewhere else — has nowhere to go.
        """
        if is_api():
            # La API responde JSON (o un archivo), nunca una página: nada se
            # dibuja, nada se enmarca y nada se guarda. Va antes que la del
            # correo, que una ruta del lienzo puede encender.
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; sandbox")
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers.setdefault("Cache-Control", "no-store")
            return response
        if g.get("email_preview", False):
            # Esta respuesta no es una página del panel: es un correo, y va
            # dentro de un marco aislado. Necesita justo lo contrario que el
            # resto —estilos en línea, imágenes de nuestro almacén, y dejarse
            # enmarcar por nosotros— así que lleva su propia política, no una
            # relajación de la de arriba.
            response.headers["Content-Security-Policy"] = "; ".join([
                "default-src 'none'",
                # Un correo se escribe con style= en cada etiqueta: es lo
                # único que entienden todos los lectores.
                "style-src 'unsafe-inline'",
                # El marco va con origen opaco, asi que 'self' ahi no
                # significa nada: la direccion del panel se nombra entera.
                f"img-src {Config.APP_BASE_URL} https: data:",
                "frame-ancestors 'self'",
                "form-action 'none'",
                "base-uri 'none'",
            ])
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Cache-Control"] = "no-store"
            return response

        nonce = g.get("csp_nonce", "")
        response.headers["Content-Security-Policy"] = "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            # `form-action` gobierna también la redirección que viene
            # después de enviar un formulario, así que aquí va todo sitio al
            # que se pueda acabar yendo desde uno: el checkout de PayPal, el
            # de Paguélofácil, y el sitio público, que es donde aterriza un
            # cliente al entrar. Sin ellos el navegador se planta y el botón
            # parece no hacer nada.
            f"form-action 'self' {Config.paypal_checkout()} "
            f"{' '.join(Config.paguelofacil_checkout())} {Config.PUBLIC_SITE_URL}",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "object-src 'none'",
        ])
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if response.mimetype == "text/html":
            # These pages are behind a session and some carry a confirmation
            # code; no cache should keep them, least of all a shared one.
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))

    def error_page(title_key: str, lead_key: str) -> str:
        """The error page, with a plain-text fallback.

        Raising inside an error handler produces exactly the blank server page
        this exists to replace, so nothing here may throw.
        """
        try:
            return render_template("error.html", title=t(title_key),
                                   lead=t(lead_key), hint=t("error_retry"))
        except Exception:  # noqa: BLE001 - last resort, must not raise
            return "El servicio no está disponible. Intenta de nuevo en unos minutos."

    # An unreachable database is the one dependency that fails while the
    # application itself is fine. It used to surface as the server's bare
    # "Internal Server Error", which tells the visitor nothing and whoever has
    # to fix it even less. 503 rather than 500 because it is temporary, and the
    # exception text stays in the platform log, never on the screen.
    def api_error(status: int):
        """Bajo `/api/`, los errores van en JSON y no como página."""
        from blueprints.api.core import json_error_for

        return json_error_for(status)

    @app.errorhandler(PyMongoError)
    def database_unavailable(exc):
        app.logger.exception("base de datos inaccesible en %s", request.path)
        if is_api():
            return api_error(503)
        return error_page("error_db_title", "error_db_lead"), 503

    @app.errorhandler(404)
    @app.errorhandler(405)
    def not_routed(exc: HTTPException):
        """Una dirección que no existe o un método que no va: en la API, en
        JSON; en el panel, la página de siempre de Werkzeug."""
        if is_api():
            return api_error(exc.code)
        return exc

    @app.errorhandler(413)
    def file_too_big(exc):
        """A file over the limit never reaches the importer.

        Werkzeug cuts the request off while it is still arriving, so this page
        is what the visitor gets instead of a blank error: the whole point of
        the limit is that a five megabyte cap is not enforced by reading five
        megabytes first.
        """
        if is_api():
            return api_error(413)
        return error_page("error_upload_big_title", "error_upload_big_lead"), 413

    @app.errorhandler(500)
    def internal_error(exc):
        app.logger.exception("error no manejado en %s", request.path)
        if is_api():
            return api_error(500)
        return error_page("error_unknown_title", "error_unknown_lead"), 500

    @app.get("/health")
    def salud():
        """Is the application up, does the database answer, are the indexes in.

        Readable from outside with no dashboard, which is what tells a dead
        application apart from a database it cannot reach, or a proxy in the
        way. Deliberately says nothing about credentials or connection strings.
        """
        state = health()
        # Which mail backend this deploy came up with. It is the fastest way to
        # tell from outside whether the new variables were picked up, and it
        # names a mode, never a credential.
        payload = {"app": "up", "mail": Config.MAIL_BACKEND, **state}
        return jsonify(payload), (200 if state["database"] == "up" else 503)

    return app
