"""The Flask application."""

from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, g, jsonify, render_template, request, session
from pymongo.errors import PyMongoError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from db import ensure_indexes_once, health, indexes_ready
from i18n import ago, t
from models.account import is_admin, status_of as account_status_of
from services.security import MIN_PASSWORD_LENGTH, csrf_token


# A crumb the public site can read. It carries "1" for a client and "admin" for
# an administrator, and nothing else: unlike the session cookie it is NOT
# HttpOnly, so any script on panamails.com can see it, and anything with a name
# or an address in it would be handing that to a static site with no reason to
# know it.
#
# El rol va ahí porque el menú del sitio público le ofrecía a un administrador
# el panel de envíos y los contactos, que su cuenta no tiene. Cuesta que
# cualquier script de ese dominio pueda saber que quien mira es administrador;
# no hay forma de que un sitio estático lo sepa sin que se lo digan.
HINT_COOKIE = "pm_in"


def hint_domain() -> str | None:
    """The parent domain both deploys hang off, or None when there is none.

    The panel lives at panel.panamails.com and the site at panamails.com, so the
    crumb goes on .panamails.com to be readable from both. Running locally there
    is nothing to share —cookies ignore ports— and the domain is left out,
    because a browser refuses one that does not match the host.
    """
    host = urlparse(Config.PUBLIC_SITE_URL).hostname or ""
    if not host or host == "localhost" or host.replace(".", "").isdigit():
        return None
    return f".{host}"


def asset_version() -> str:
    """A short stamp that changes when the stylesheet or the script does.

    Appended to their URLs so a browser holding yesterday's panel.css does not
    keep it. Without this, a page whose colours moved into the stylesheet drew
    with the old one: the logo, which takes its fill from a CSS variable, came
    out black.
    """
    stamp = 0.0
    for name in ("static/css/panel.css", "static/js/panel.js"):
        path = Path(__file__).resolve().parent / name
        if path.exists():
            stamp = max(stamp, path.stat().st_mtime)
    return str(int(stamp))


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

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
    app.register_blueprint(auth_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(designs_bp)
    app.register_blueprint(admin_bp)

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
                                 password_min=MIN_PASSWORD_LENGTH)
    app.jinja_env.filters["ago"] = ago

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
    def _session_hint(response):
        """Keep the crumb in step with the session.

        It is a hint, never a proof: a session closed from another device leaves
        it behind, the public site keeps offering "Mi panel", and the panel then
        asks whoever clicks to sign in. That is the right order — the crumb is
        for drawing a button, not for letting anyone in.
        """
        from blueprints.auth.routes import SESSION_KEY

        from blueprints.auth.routes import current_account

        signed_in = bool(session.get(SESSION_KEY))
        # Se compara contra el valor que debería tener, no contra su presencia:
        # así el día que una cuenta pasa a administrador la galleta se reescribe
        # sola en la siguiente página.
        wanted = ""
        if signed_in:
            try:
                wanted = "admin" if is_admin(current_account()) else "1"
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
        nonce = g.get("csp_nonce", "")
        response.headers["Content-Security-Policy"] = "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            # El pago sale de aquí y acaba en PayPal. `form-action` gobierna
            # también la redirección que viene después de enviar el
            # formulario, así que sin este destino el navegador se planta y el
            # botón de pagar parece no hacer nada.
            f"form-action 'self' {Config.paypal_checkout()}",
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
    @app.errorhandler(PyMongoError)
    def database_unavailable(exc):
        app.logger.exception("base de datos inaccesible en %s", request.path)
        return error_page("error_db_title", "error_db_lead"), 503

    @app.errorhandler(413)
    def file_too_big(exc):
        """A file over the limit never reaches the importer.

        Werkzeug cuts the request off while it is still arriving, so this page
        is what the visitor gets instead of a blank error: the whole point of
        the limit is that a five megabyte cap is not enforced by reading five
        megabytes first.
        """
        return error_page("error_upload_big_title", "error_upload_big_lead"), 413

    @app.errorhandler(500)
    def internal_error(exc):
        app.logger.exception("error no manejado en %s", request.path)
        return error_page("error_unknown_title", "error_unknown_lead"), 500

    @app.get("/salud")
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
