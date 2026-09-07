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

from config import Config


def send(to: str, subject: str, html: str, text: str) -> str:
    """Send one message. Returns an identifier for the log."""
    if Config.MAIL_BACKEND == "ses":
        return _send_ses(to, subject, html, text)
    if Config.MAIL_BACKEND == "smtp":
        return _send_smtp(to, subject, html, text)
    return _send_file(to, subject, html, text)


def _from_address() -> str:
    """The address the message really comes from.

    Over SMTP this must be the mailbox that is actually authenticating. Sending
    as cuenta@mail.panamails.com through Gmail's servers fails SPF and DKIM
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

    # The link is what a developer actually needs; print it so the flow can be
    # followed without opening the file.
    for url in re.findall(r"https?://\S+", text):
        print(f"  [correo] {to}: {url}", flush=True)
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
                                  context=context, timeout=20)
    else:
        server = smtplib.SMTP(Config.MAIL_SMTP_HOST, Config.MAIL_SMTP_PORT, timeout=20)
    with server:
        if not Config.MAIL_SMTP_SSL:
            server.starttls(context=context)
        if Config.MAIL_SMTP_USER:
            server.login(Config.MAIL_SMTP_USER, Config.MAIL_SMTP_PASSWORD)
        server.send_message(message)
    return f"smtp:{to}"
