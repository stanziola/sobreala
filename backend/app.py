"""The Flask application."""

from __future__ import annotations

from datetime import timedelta

from flask import Flask, jsonify, render_template, request
from pymongo.errors import PyMongoError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from db import ensure_indexes_once, health, indexes_ready
from i18n import t
from services.security import csrf_token


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

    from blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    @app.before_request
    def _prepare_indexes():
        # Lazily, and only until one attempt succeeds. The unique index on the
        # email is what prevents duplicate accounts, so it cannot be quietly
        # skipped just because the database was down when the process started.
        if not app.config.get("TESTING") and not indexes_ready():
            ensure_indexes_once()

    # Templates hold no Spanish of their own: they ask i18n for it.
    app.jinja_env.globals.update(t=t, csrf_token=csrf_token)

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
        payload = {"app": "up", **state}
        return jsonify(payload), (200 if state["database"] == "up" else 503)

    return app
