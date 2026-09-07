"""The Flask application."""

from __future__ import annotations

from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from db import ensure_indexes, get_db
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

    if not app.config.get("TESTING"):
        Config.check()
        ensure_indexes(get_db())

    from blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    # Templates hold no Spanish of their own: they ask i18n for it.
    app.jinja_env.globals.update(t=t, csrf_token=csrf_token)

    @app.get("/")
    def index():
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))

    return app
