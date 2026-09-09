"""Configuration read from the environment, with development defaults.

Nothing secret has a default that would work in production: SECRET_KEY refuses
to fall back once FLASK_ENV is not development, so a deploy cannot start with a
predictable session key by accident.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in ("1", "true", "yes", "on")


class Config:
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = ENV == "development"

    # --- session -----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else "")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", not DEBUG)
    # Only applies to a session someone asked to keep; without the checkbox the
    # cookie dies with the browser. models/session.py holds the real expiry.
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30

    # --- database ----------------------------------------------------------
    # An Atlas cluster goes here as mongodb+srv://user:password@host/... The
    # password lives in .env, which is git-ignored, and Atlas needs the server's
    # address on its allowlist. The local server is only the fallback.
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    # panamails and panamails_demo in the cluster hold two earlier attempts
    # with a different data model; this application keeps its own database.
    MONGODB_DB = os.getenv("MONGODB_DB", "panamails_app")
    # Tests never touch the real cluster: they use this one and drop it.
    MONGODB_TEST_URI = os.getenv("MONGODB_TEST_URI", "mongodb://127.0.0.1:27017")
    MONGODB_TEST_DB = os.getenv("MONGODB_TEST_DB", "panamails_test")

    # --- email -------------------------------------------------------------
    # "file" writes the message to MAIL_OUTBOX_DIR and prints the link, so the
    # whole flow can be exercised while SES is still in its sandbox.
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "file")
    MAIL_OUTBOX_DIR = os.getenv("MAIL_OUTBOX_DIR", str(BASE_DIR / ".mail_outbox"))
    # The identity verified in SES is the domain panamails.com, which covers its
    # subdomains. The address is at the root and not at mail.panamails.com
    # because that subdomain is the MAIL FROM: its MX points at the SES feedback
    # endpoint, so a reply sent there would never reach anyone.
    SYSTEM_FROM_EMAIL = os.getenv("SYSTEM_FROM_EMAIL", "cuenta@panamails.com")
    SYSTEM_FROM_NAME = os.getenv("SYSTEM_FROM_NAME", "Panamails")
    # System mail keeps its own SES configuration set: a client's campaign
    # bounces must never affect whether confirmation mail is delivered.
    SES_TRANSACTIONAL_CONFIGURATION_SET = os.getenv("SES_TRANSACTIONAL_CONFIGURATION_SET", "")
    # us-east-2 (Ohio) is where the SES identity lives. SES is per region: the
    # same domain verified elsewhere does not count, and sending against the
    # wrong one fails with "identity not verified".
    AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
    # boto3 finds these on its own in the environment; they are read here only
    # so check() can refuse to start without them. A deploy that is missing a
    # key has to say so at boot, not at the first person who tries to register.
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    # SMTP, only for MAIL_BACKEND=smtp. A bridge until SES leaves the sandbox.
    # MAIL_SMTP_FROM must be the mailbox that authenticates: sending as another
    # domain through someone else's SMTP fails SPF and DKIM and lands in spam.
    MAIL_SMTP_HOST = os.getenv("MAIL_SMTP_HOST", "smtp.gmail.com")
    MAIL_SMTP_PORT = int(os.getenv("MAIL_SMTP_PORT", "587"))
    MAIL_SMTP_SSL = _bool("MAIL_SMTP_SSL", False)  # False uses STARTTLS on 587
    MAIL_SMTP_USER = os.getenv("MAIL_SMTP_USER", "")
    MAIL_SMTP_PASSWORD = os.getenv("MAIL_SMTP_PASSWORD", "")
    MAIL_SMTP_FROM = os.getenv("MAIL_SMTP_FROM", "") or os.getenv("MAIL_SMTP_USER", "")

    # --- links and tokens --------------------------------------------------
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    # El sitio público es otro despliegue, en Cloudflare Pages. De ahí cuelgan
    # los términos y la política de privacidad que se aceptan al registrarse.
    PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "https://panamails.com").rstrip("/")
    # Confirmation is a six digit code typed on the screen that asked for it, so
    # it does not need to survive a day in an inbox the way a link did. Minutes,
    # not hours: a short life is half of what makes a short code safe.
    CONFIRMATION_CODE_MINUTES = int(os.getenv("CONFIRMATION_CODE_MINUTES", "30"))
    # A registration that never gets confirmed is swept after this. It holds an
    # address hostage otherwise: one typed wrong stays taken forever, and the
    # address of a stranger can be reserved by registering it and stopping.
    UNCONFIRMED_HOURS = int(os.getenv("UNCONFIRMED_HOURS", "24"))
    # Spent codes stay this long after expiring, so the log can tell an expired
    # code from one that never existed.
    TOKEN_GRACE_DAYS = int(os.getenv("TOKEN_GRACE_DAYS", "7"))

    # --- contacts and importing --------------------------------------------
    # What an account with no plan may hold. The paid limits come from
    # docs/pricing.md and live in models/account.py; this is the only number
    # that is not written there, because a plan-less account is not a plan.
    # Enough to try it with a real list, small enough that Básico still buys
    # something.
    CONTACTS_FREE_LIMIT = int(os.getenv("CONTACTS_FREE_LIMIT", "500"))
    # The three limits from CLAUDE.md. The size is enforced by Flask before the
    # request reaches any code of ours, so an oversized file is refused without
    # being read.
    IMPORT_MAX_BYTES = int(os.getenv("IMPORT_MAX_BYTES", str(5 * 1024 * 1024)))
    IMPORTS_PER_DAY = int(os.getenv("IMPORTS_PER_DAY", "10"))

    @classmethod
    def check(cls) -> None:
        if not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY is required outside development")
        # Every link in the system mail hangs off this. Left at its
        # development value, a deploy sends people to their own computer, and
        # nothing looks broken from the inside: the mail leaves, it just cannot
        # be used. Better to refuse to start.
        if cls.ENV != "development" and ("127.0.0.1" in cls.APP_BASE_URL
                                         or "localhost" in cls.APP_BASE_URL):
            raise RuntimeError(
                f"APP_BASE_URL sigue apuntando al servidor de desarrollo "
                f"({cls.APP_BASE_URL}): los correos saldrian con enlaces "
                f"inservibles")
        if cls.MAIL_BACKEND not in ("file", "smtp", "ses"):
            raise RuntimeError(f"unknown MAIL_BACKEND: {cls.MAIL_BACKEND!r}")
        if cls.MAIL_BACKEND == "smtp" and not cls.MAIL_SMTP_USER:
            raise RuntimeError("MAIL_BACKEND=smtp needs MAIL_SMTP_USER and MAIL_SMTP_PASSWORD")
        if cls.MAIL_BACKEND == "ses":
            missing = [name for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                                         "AWS_REGION", "SYSTEM_FROM_EMAIL")
                       if not getattr(cls, name)]
            if missing:
                raise RuntimeError("MAIL_BACKEND=ses needs " + ", ".join(missing))
