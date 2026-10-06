"""Sending system email.

Two backends, chosen with MAIL_BACKEND:

  file  writes the message next to the project and prints the link. Lets the
        whole flow be exercised while SES is still in its sandbox, where it can
        only reach verified addresses.
  smtp  a plain SMTP server, e.g. Gmail with an app password. A bridge for the
        handful of confirmations sent before SES production access arrives.
        CLAUDE.md rules out SMTP for CAMPAIGNS, which are bulk mail on behalf of
        third parties; a few transactional messages are a different matter.
        Read the caveat on MAIL_SMTP_* in config.py before using it.
  ses   Amazon SES over its HTTPS API, never SMTP, as decided in CLAUDE.md.

Every attempt is written to the mail_log collection, whichever backend was used
and whether or not it worked, so what left the server can be read back later.

These are TRANSACTIONAL messages. They carry no unsubscribe link and no
watermark: those rules belong to client campaigns, not to the mail that lets
someone into their account.
"""

from __future__ import annotations

import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any

from config import Config
from models import mail_log

# Every socket step gets this long at most. Kept well under gunicorn's 60s
# request timeout: a provider that never answers has to fail inside the
# request, because a worker killed mid-send answers the visitor with a bare 502.
SMTP_TIMEOUT = 10


def send(to: str, subject: str, html: str, text: str, *,
         purpose: str = "", account_id: Any = None) -> str:
    """Send one message. Returns an identifier for the log.

    The attempt is recorded either way. On failure the row is written first and
    the original exception is then allowed to travel, so the caller still sees
    the real error while the evidence survives.
    """
    backend = Config.MAIL_BACKEND if Config.MAIL_BACKEND in ("ses", "smtp") else "file"
    try:
        if backend == "ses":
            identifier = _send_ses(to, subject, html, text)
        elif backend == "smtp":
            identifier = _send_smtp(to, subject, html, text)
        else:
            identifier = _send_file(to, subject, html, text)
    except Exception as exc:
        _record(to=to, subject=subject, backend=backend, status=mail_log.FAILED,
                html=html, text=text, purpose=purpose, account_id=account_id,
                error=f"{type(exc).__name__}: {exc}")
        raise
    _record(to=to, subject=subject, backend=backend, status=mail_log.SENT,
            html=html, text=text, purpose=purpose, account_id=account_id,
            provider_id=str(identifier))
    return identifier


def _record(**fields) -> None:
    """Write one row to mail_log. Never raises.

    The message has already been handed to the provider by the time this runs,
    so a database that is unreachable must not turn a delivered mail into a
    failed request. The reason goes to the platform log instead.
    """
    try:
        # Imported here so this module can be used, and tested, without the
        # database being reachable at import time.
        from db import get_db
        mail_log.record(get_db(), **fields)
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [mail_log] no se pudo registrar el correo: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)


def _from_address() -> str:
    """The address the message really comes from.

    Over SMTP this must be the mailbox that is actually authenticating. Sending
    as notifications@mail.sobreala.com through Gmail's servers fails SPF and DKIM
    alignment and lands in spam, so the SMTP user wins when it is set.
    """
    if Config.MAIL_BACKEND == "smtp" and Config.MAIL_SMTP_FROM:
        return Config.MAIL_SMTP_FROM
    return Config.SYSTEM_FROM_EMAIL


def _sender() -> str:
    return formataddr((Config.SYSTEM_FROM_NAME, _from_address()))


def _send_file(to: str, subject: str, html: str, text: str) -> str:
    outbox = Path(Config.MAIL_OUTBOX_DIR)
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    safe_to = re.sub(r"[^A-Za-z0-9._-]", "_", to)
    name = f"{stamp}_{safe_to}"

    (outbox / f"{name}.html").write_text(
        f"<!-- De: {_sender()}\n     Para: {to}\n     Asunto: {subject} -->\n{html}",
        encoding="utf-8",
    )
    (outbox / f"{name}.txt").write_text(
        f"De: {_sender()}\nPara: {to}\nAsunto: {subject}\n\n{text}",
        encoding="utf-8",
    )

    # The code, or the link in the messages that still carry one, is what a
    # developer actually needs; print it so the flow can be followed without
    # opening the file.
    for found in re.findall(r"https?://\S+|^\d{6}$", text, flags=re.M):
        print(f"  [correo] {to}: {found}", flush=True)
    print(f"  [correo] guardado en {outbox / (name + '.html')}", flush=True)
    return name


def _send_ses(to: str, subject: str, html: str, text: str) -> str:
    # Imported here so development without AWS credentials never needs boto3.
    import boto3

    client = boto3.client("ses", region_name=Config.AWS_REGION)
    kwargs = {
        "Source": _sender(),
        "Destination": {"ToAddresses": [to]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text, "Charset": "UTF-8"},
                "Html": {"Data": html, "Charset": "UTF-8"},
            },
        },
    }
    if Config.SES_TRANSACTIONAL_CONFIGURATION_SET:
        kwargs["ConfigurationSetName"] = Config.SES_TRANSACTIONAL_CONFIGURATION_SET
    return client.send_email(**kwargs)["MessageId"]


def _send_smtp(to: str, subject: str, html: str, text: str) -> str:
    """Send through an ordinary SMTP server.

    Meant as a bridge, not a destination: providers like Gmail cap daily
    volume and will throttle or block a sender that starts looking like bulk
    mail. Campaigns must go through SES.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _sender()
    message["To"] = to
    if Config.SYSTEM_FROM_EMAIL != _from_address():
        # Replies still reach the branded address even though the envelope
        # belongs to the authenticating mailbox.
        message["Reply-To"] = Config.SYSTEM_FROM_EMAIL
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    if Config.MAIL_SMTP_SSL:
        server = smtplib.SMTP_SSL(Config.MAIL_SMTP_HOST, Config.MAIL_SMTP_PORT,
                                  context=context, timeout=SMTP_TIMEOUT)
    else:
        server = smtplib.SMTP(Config.MAIL_SMTP_HOST, Config.MAIL_SMTP_PORT,
                              timeout=SMTP_TIMEOUT)
    with server:
        if not Config.MAIL_SMTP_SSL:
            server.starttls(context=context)
        if Config.MAIL_SMTP_USER:
            server.login(Config.MAIL_SMTP_USER, Config.MAIL_SMTP_PASSWORD)
        server.send_message(message)
    return f"smtp:{to}"
