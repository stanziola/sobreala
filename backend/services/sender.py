"""Mandar una campaña: armar cada correo y entregarlo, por tandas.

**Es el único sitio que le manda un correo a un contacto de un cliente.** Los
del sistema —códigos, avisos de la cuenta— salen por `services/mailer.py`, que
es otro camino con otras reglas: aquellos no llevan baja ni marca de agua
(regla 8) y estos las llevan siempre (reglas 3 y 4).

Cuatro cosas que pasan aquí y que la pantalla no puede saltarse:

  * **Los suprimidos se saltan y no gastan cuota.** Es la regla 1, y la consulta
    va en lote, que es la 10: nunca una por contacto.
  * **La baja se inyecta al armar cada correo**, distinta para cada
    destinatario, y va también en la cabecera `List-Unsubscribe` para que el
    botón de «cancelar suscripción» del buzón funcione sin abrir el correo.
  * **La cuota del mes manda.** Si quedan cien correos, salen cien y la campaña
    se queda donde está.
  * **Se anota hasta dónde se llegó** antes de cada tanda, así que cortar a la
    mitad —porque se acabó la cuota, porque falló la red— no le manda a nadie
    dos veces.

Sale por tandas dentro de la petición porque todavía no hay proceso en segundo
plano. El día que lo haya, llama a `run()` en bucle y no cambia nada más.
"""

from __future__ import annotations

import os
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.utils import formataddr
from html.parser import HTMLParser
from typing import Any

from config import Config
from models import account as accounts
from models import campaign as campaigns
from models import contact as contacts
from models import design as designs
from models import event as events
from models import suppression as suppressions
from services import fields as columns
from services import render, unsubscribe

# Cuántos destinatarios por vuelta. El tope existe porque esto corre dentro de
# una petición y Railway la corta: mejor mandar cien y decir que faltan que
# quedarse a medias sin saber dónde.
BATCH = 100

# Fin de línea CRLF, que es lo que espera SMTP, y líneas largas permitidas.
# Lo segundo no es un detalle: con el límite de 78 caracteres, la cabecera
# `List-Unsubscribe` no cabe en una línea, y como una dirección no tiene
# espacios por donde partirla, Python la parte **codificándola**. Codificada,
# el botón de «cancelar suscripción» del buzón no la entiende y deja de
# funcionar justo lo que la regla 3 obliga a ofrecer. 998 es el máximo que
# permite el estándar.
POLICY = policy.SMTP.clone(max_line_length=998)


class Piece:
    """La pieza de la campaña, lista para armarse con la baja de cada uno."""

    def __init__(self, design: dict[str, Any]):
        self.design = design
        self.built_in = design.get("source") == designs.BUILT_IN

    def html(self, *, plan: str | None, unsubscribe_url: str) -> str:
        if self.built_in:
            return render.email(self.design.get("template", ""),
                                self.design.get("fields") or {},
                                plan=plan, unsubscribe=unsubscribe_url)
        return render.email_from_html(self.design.get("html", ""), plan=plan,
                                      unsubscribe=unsubscribe_url)


class Stripper(HTMLParser):
    """Lo que dice un correo, sin etiquetas."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = False

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self.skipping = True
        elif tag in ("p", "br", "div", "tr", "h1", "h2", "h3", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head"):
            self.skipping = False

    def handle_data(self, data):
        if not self.skipping and data.strip():
            self.parts.append(" ".join(data.split()))


def plain_text(html: str) -> str:
    """Una versión en texto del correo.

    No es un lujo: un correo que solo trae HTML puntúa peor en los filtros, y
    hay quien lee en un cliente que no dibuja nada.
    """
    reader = Stripper()
    reader.feed(html)
    lines = [line.strip() for line in "".join(reader.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def from_address(account: dict[str, Any]) -> str:
    """De quién sale la campaña.

    Hoy, de la identidad que **está verificada en SES**, con el nombre de la
    empresa a la vista. CLAUDE.md dice que el día de mañana cada cliente escribe
    desde `tuempresa@envios.panamails.com`, pero ese subdominio todavía no está
    verificado y usarlo haría fallar cada envío. Es esta función y nada más: el
    día que se verifique, se cambia aquí.
    """
    name = (account.get("company_name") or Config.SYSTEM_FROM_NAME).strip()
    return formataddr((name, Config.SYSTEM_FROM_EMAIL))


def build(account: dict[str, Any], campaign: dict[str, Any], piece: Piece,
          contact: dict[str, Any],
          fields: list[dict[str, Any]] | None = None) -> EmailMessage:
    """El correo de un destinatario, entero, con sus cabeceras.

    Aquí es donde el correo deja de ser el mismo para todos: las marcas de la
    pieza —`*|CIUDAD|*`— se cambian por lo que dice **este** contacto, y lo que
    le falte usa el respaldo de su columna. El asunto también, que es donde más
    rinde y lo primero que se lee.
    """
    fields = fields or []
    url = unsubscribe.link(contact["_id"])
    html = piece.html(plan=accounts.plan_of(account), unsubscribe_url=url)
    html = columns.fill(html, contact, fields)

    message = EmailMessage(policy=POLICY)
    message["From"] = from_address(account)
    message["To"] = contact["email"]
    # Sin escapar: un asunto es texto, y ahí «&» es «&» y no «&amp;».
    message["Subject"] = columns.fill(campaign["subject"], contact, fields,
                                      html=False)
    # Responder le llega al cliente, no a nosotros: la conversación es suya.
    if account.get("email"):
        message["Reply-To"] = account["email"]
    # Las dos cabeceras de la baja de un clic. La segunda es la que hace que
    # Gmail y Outlook enseñen su propio botón: sin ella, el enlace del pie es
    # lo único que hay.
    message["List-Unsubscribe"] = f"<{url}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(plain_text(html))
    message.add_alternative(html, subtype="html")
    return message


def deliver(message: EmailMessage) -> str:
    """Entregarlo. Devuelve el identificador de quien lo aceptó.

    En desarrollo se escribe en disco, como el correo del sistema: el flujo
    entero se puede recorrer sin credenciales de AWS y leyendo lo que salió.
    """
    if Config.MAIL_BACKEND != "ses":
        folder = Config.MAIL_OUTBOX_DIR
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        safe = message["To"].replace("@", "_").replace("/", "_")
        path = os.path.join(folder, f"campana-{stamp}_{safe}.eml")
        with open(path, "wb") as handle:
            handle.write(bytes(message))
        print(f"  [campana] {message['To']}: {path}", flush=True)
        return path

    # Importado aquí para que desarrollar sin boto3 nunca lo necesite.
    import boto3

    client = boto3.client("ses", region_name=Config.AWS_REGION)
    kwargs: dict[str, Any] = {"RawMessage": {"Data": bytes(message)}}
    if Config.SES_CONFIGURATION_SET:
        kwargs["ConfigurationSetName"] = Config.SES_CONFIGURATION_SET
    return client.send_raw_email(**kwargs)["MessageId"]


def blocked(account: dict[str, Any]) -> list[str]:
    """Por qué esta cuenta todavía no puede mandar. Vacío es que sí puede.

    Son claves y no frases, para que la pantalla las traduzca y el mismo motivo
    se lea igual en todas partes.
    """
    why: list[str] = []
    if not accounts.plan_of(account):
        why.append("plan")
    elif accounts.quota_left(account) <= 0:
        why.append("quota")
    if not accounts.can_send(account):
        why.append("cleared")
    return why


def run(db, account: dict[str, Any], campaign: dict[str, Any], *,
        limit: int | None = None) -> dict[str, Any]:
    """Mandar una tanda. Devuelve qué pasó y si queda algo pendiente.

    El tope se lee aquí y no en la firma: así se puede cambiar el de arriba y
    esta función obedece, que es lo que hace falta para probarla con tandas de
    dos y para ajustarlo el día que se sepa cuánto aguanta el servidor.
    """
    limit = BATCH if limit is None else limit
    account_id = account["_id"]
    why = blocked(account)
    if why:
        return {"blocked": why, "sent": 0, "left": 0}

    piece = designs.by_id(db, account_id, campaign["design_id"])
    if piece is None:
        # La pieza se borró después de programar la campaña.
        campaigns.finish(db, account_id, campaign["_id"])
        return {"blocked": ["piece"], "sent": 0, "left": 0}

    wanted = campaigns.tags_of(campaign)
    # A quien le falte una columna no se le manda nada, así que tampoco se
    # cuenta: el total y las tandas miran lo mismo.
    fields = accounts.fields_of(account)
    total = contacts.matching_count(db, account_id, tags=wanted,
                                    complete=fields)
    if campaign["status"] == campaigns.SCHEDULED:
        campaigns.start(db, account_id, campaign["_id"], total)

    position = int(campaign.get("position", 0))
    # La cuota manda sobre el tope de la tanda: no se arma lo que no puede salir.
    room = min(limit, accounts.quota_left(account))
    people = contacts.batch_for_sending(db, account_id, tags=wanted,
                                        complete=fields,
                                        skip=position, limit=room)

    ready = Piece(piece)
    among = suppressions.among(db, account_id,
                               [one["email"] for one in people])
    sent = skipped = failed = 0
    errors: list[dict[str, str]] = []

    for one in people:
        # Regla 1: el suprimido se salta y no gasta cuota.
        if one["email"] in among or one.get("email_normalized") in among:
            skipped += 1
            continue
        try:
            deliver(build(account, campaign, ready, one, fields))
        except Exception as exc:  # noqa: BLE001 - se anota y se sigue
            failed += 1
            errors.append({"email": one["email"],
                           "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            continue
        sent += 1
        events.record(db, account_id, kind=events.SENT,
                      campaign_id=campaign["_id"], email=one["email"])

    position += len(people)
    campaigns.advance(db, account_id, campaign["_id"], position=position,
                      sent=sent, skipped=skipped, failed=failed, errors=errors)
    accounts.add_sent(db, account_id, sent)

    left = max(0, total - position)
    # Sin gente en la tanda no queda nada por hacer aunque el conteo diga otra
    # cosa: la lista se encogió mientras la campaña iba por la mitad.
    if left <= 0 or not people:
        campaigns.finish(db, account_id, campaign["_id"])
        left = 0
    return {"blocked": [], "sent": sent, "skipped": skipped, "failed": failed,
            "left": left, "errors": errors}
