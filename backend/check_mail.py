#!/usr/bin/env python3
"""Send one message through the configured backend and say what happened.

    python backend/check_mail.py luis@ejemplo.com

This is the tool that turns "the mail never arrives" into something anyone can
act on. It prints the settings it is about to use, sends, and on failure shows
the provider's own words — SES answers things like

    MessageRejected: Email address is not verified. The following identities
    failed the check in region US-EAST-1: notifications@mail.sobreala.com

which says exactly what is missing. The attempt goes through mailer.send(), so
it is written to mail_log like any other message, with purpose "check".

Nothing here is used by the application at runtime.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# The Spanish here has accents and the Windows console does not always default
# to UTF-8; without this they come out as question marks.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):  # not a real console, or too old
    pass

from config import Config  # noqa: E402
from models import mail_log  # noqa: E402
from services import mailer  # noqa: E402

SUBJECT = "Prueba de envío de Sobreala"

HINTS = {
    "MessageRejected": "La dirección o el dominio no están verificados en SES, "
                       "o el remitente no es la identidad verificada.",
    "AccessDenied": "Las credenciales existen pero al usuario IAM le falta "
                    "permiso de ses:SendEmail sobre esa identidad.",
    "InvalidClientTokenId": "AWS_ACCESS_KEY_ID no es válida en esta cuenta.",
    "SignatureDoesNotMatch": "AWS_SECRET_ACCESS_KEY no corresponde a esa clave.",
    "NoCredentialsError": "boto3 no encontró credenciales: faltan "
                          "AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY.",
    "EndpointConnectionError": "No se pudo alcanzar el endpoint de SES: revisa "
                               "AWS_REGION y la salida a internet.",
    "ModuleNotFoundError": "Falta boto3: pip install -r requirements.txt",
}


def body(to: str) -> tuple[str, str]:
    moment = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (f"Prueba de envío de Sobreala.\n\n"
            f"Backend: {Config.MAIL_BACKEND}\n"
            f"Para: {to}\n"
            f"Fecha: {moment}\n\n"
            f"Si te llegó este mensaje, el envío del sistema funciona.\n")
    html = ("<p>Prueba de envío de <b>Sobreala</b>.</p>"
            f"<ul><li>Backend: {Config.MAIL_BACKEND}</li>"
            f"<li>Para: {to}</li><li>Fecha: {moment}</li></ul>"
            "<p>Si te llegó este mensaje, el envío del sistema funciona.</p>")
    return html, text


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    to = argv[1]

    print(f"  backend:   {Config.MAIL_BACKEND}")
    print(f"  de:        {Config.SYSTEM_FROM_NAME} <{Config.SYSTEM_FROM_EMAIL}>")
    print(f"  para:      {to}")
    if Config.MAIL_BACKEND == "ses":
        print(f"  region:    {Config.AWS_REGION}")
        print(f"  clave:     {'puesta' if Config.AWS_ACCESS_KEY_ID else 'FALTA'}")
        print(f"  secreto:   {'puesto' if Config.AWS_SECRET_ACCESS_KEY else 'FALTA'}")
        print(f"  conj. de configuración: "
              f"{Config.SES_TRANSACTIONAL_CONFIGURATION_SET or '(ninguno)'}")
    elif Config.MAIL_BACKEND == "smtp":
        print(f"  servidor:  {Config.MAIL_SMTP_HOST}:{Config.MAIL_SMTP_PORT}")
    else:
        print(f"  carpeta:   {Config.MAIL_OUTBOX_DIR}")

    html, text = body(to)
    try:
        identifier = mailer.send(to=to, subject=SUBJECT, html=html, text=text,
                                 purpose=mail_log.CHECK)
    except Exception as exc:  # noqa: BLE001 - this is the whole point
        name = type(exc).__name__
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "") \
            if hasattr(exc, "response") else ""
        print(f"\n  FALLÓ: {name}: {exc}")
        hint = HINTS.get(code) or HINTS.get(name)
        if hint:
            print(f"  {hint}")
        print("  El intento quedó en mail_log con el error completo.")
        return 1

    print(f"\n  ENVIADO. Identificador del proveedor: {identifier}")
    if Config.MAIL_BACKEND == "ses":
        print("  Si no llega en unos minutos, revisa la carpeta de spam y, en "
              "SES, si la cuenta sigue en sandbox.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
