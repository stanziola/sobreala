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
from models import download as downloads_model
from models import event as events
from models import image as images
from models import suppression as suppressions
from services import fields as columns
from services import canvas, downloads, imaging, render, unsubscribe

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

    def html(self, *, plan: str | None, unsubscribe_url: str, postal: str = "") -> str:
        if self.design.get("source") == campaigns.SINGLE:
            # El correo individual: su texto y, si lleva archivo, el botón para
            # bajarlo. **Sin baja ni marca de agua** (octubre de 2026): es un
            # correo de una persona a otra, no una campaña. La dirección postal
            # sí va.
            body = render.text_to_html(self.design.get("body", ""))
            if self.design.get("download"):
                body += render.download_button(**self.design["download"])
            return render.email_from_body(body, plan=plan, unsubscribe="",
                                          postal=postal, watermark=False)
        if self.design.get("source") == designs.CANVAS:
            # Lo arma el mismo código que la vista previa del lienzo, así que
            # lo que se vio es lo que sale.
            doc = canvas.read(self.design.get("canvas")) or canvas.blank()
            urls = [imaging.url_of(one) if one else None
                    for one in self.design.get("backgrounds") or []]
            shades = self.design.get("shades") or []
            return render.email_from_body(
                canvas.to_html(doc, urls, shades), plan=plan,
                unsubscribe=unsubscribe_url, style=canvas.dark_css(doc, shades),
                postal=postal)
        if self.built_in:
            return render.email(self.design.get("template", ""),
                                self.design.get("fields") or {},
                                plan=plan, unsubscribe=unsubscribe_url, postal=postal)
        return render.email_from_html(self.design.get("html", ""), plan=plan, postal=postal,
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


def sender_email(account: dict[str, Any]) -> str:
    """La dirección de la que sale una campaña, o vacío si todavía no hay.

    Con su dominio verificado y una dirección elegida, de ese dominio. Si no, de
    su usuario en `SENDING_DOMAIN`. **Nunca de `SYSTEM_FROM_EMAIL`**: esa es
    la de los códigos y los recibos, y una lista mala de un cliente no puede
    llevárselos a spam. Sin usuario, vacío, y `blocked()` dice `sender`.
    """
    mine = accounts.sender_of(account)
    if accounts.domain_ready(account):
        return f"{mine['domain_local']}@{mine['domain']}"
    if mine.get("handle"):
        return f"{mine['handle']}@{Config.SENDING_DOMAIN}"
    return ""


def from_address(account: dict[str, Any]) -> str:
    """De quién sale la campaña, con el nombre de la empresa a la vista."""
    name = (account.get("company_name") or Config.SYSTEM_FROM_NAME).strip()
    return formataddr((name, sender_email(account)))


def reply_to(account: dict[str, Any]) -> str:
    """A dónde llegan las respuestas: la que el cliente confirmó, o el correo
    con el que entra el dueño. La conversación es suya, no nuestra."""
    return accounts.sender_of(account).get("reply_to") or account.get("email", "")


def build(account: dict[str, Any], campaign: dict[str, Any], piece: Piece,
          contact: dict[str, Any],
          fields: list[dict[str, Any]] | None = None) -> EmailMessage:
    """El correo de un destinatario, entero, con sus cabeceras.

    Aquí es donde el correo deja de ser el mismo para todos: las marcas de la
    pieza —`*|CIUDAD|*`— se cambian por lo que dice **este** contacto. El asunto
    también, que es donde más rinde y lo primero que se lee.

    **Y sale etiquetado** con la cuenta, la campaña y el envío. SES devuelve
    esas etiquetas dentro de cada aviso, y son lo único que dice de quién es un
    rebote: la misma dirección puede estar en las listas de tres clientes, y
    anularla en las tres por el rebote de una sería anular por cuenta ajena.
    """
    fields = fields or []
    single = campaign.get("kind") == campaigns.SINGLE
    # El individual no lleva baja: puede ir a alguien que no está en Contactos,
    # y no es una campaña.
    url = "" if single else unsubscribe.link(contact["_id"])
    html = piece.html(plan=accounts.plan_of(account), unsubscribe_url=url,
                      postal=accounts.postal_of(account))
    html = columns.fill(html, contact, fields)

    message = EmailMessage(policy=POLICY)
    message["From"] = from_address(account)
    message["To"] = contact["email"]
    # Sin escapar: un asunto es texto, y ahí «&» es «&» y no «&amp;».
    message["Subject"] = columns.fill(campaign["subject"], contact, fields,
                                      html=False)
    # Responder le llega al cliente, no a nosotros: la conversación es suya.
    if reply_to(account):
        message["Reply-To"] = reply_to(account)
    # Las dos cabeceras de la baja de un clic. La segunda es la que hace que
    # Gmail y Outlook enseñen su propio botón: sin ella, el enlace del pie es
    # lo único que hay.
    if url:
        message["List-Unsubscribe"] = f"<{url}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    # La cabecera que SES convierte en etiquetas del mensaje y quita antes de
    # entregarlo. Los valores son identificadores de Mongo, que solo llevan
    # letras y números, que es lo que SES acepta ahí.
    tags = [("account", account.get("_id")), ("campaign", campaign.get("_id")),
            ("run", campaign.get("run_id"))]
    message["X-SES-MESSAGE-TAGS"] = ", ".join(
        f"{name}={value}" for name, value in tags if value)
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


def download_of(db, campaign: dict[str, Any]) -> dict[str, str] | None:
    """El botón del archivo de un correo individual: su enlace, su nombre y su
    tamaño. None si no lleva archivo o ya no está."""
    if not campaign.get("download_id"):
        return None
    found = downloads_model.by_id(db, campaign["download_id"])
    if found is None:
        return None
    return {"url": downloads.link(found["_id"]), "name": found["name"],
            "size": downloads.size_label(found["size"])}


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
    # Sin la dirección de la empresa no sale: la ley la pide al pie.
    if not accounts.postal_of(account):
        why.append("postal")
    # Sin usuario de envío no hay de quién salir, y caer a la dirección del
    # sistema es justo lo que no se hace.
    if not sender_email(account):
        why.append("sender")
    # La limitó el administrador desde la ficha, o la pausó el panel solo por
    # rebotes o quejas (`services/reputation.py`). Entra, prepara y paga, pero
    # no envía hasta que se le quite (ver «el límite» en models/account.py).
    # Son dos claves porque al cliente se le dice algo distinto en cada caso.
    if accounts.is_paused(account):
        why.append("paused")
    elif accounts.limited_of(account):
        why.append("limited")
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

    single = campaign.get("kind") == campaigns.SINGLE
    if single:
        # El correo individual no tiene pieza guardada: es su propio texto, y
        # el botón de su archivo si lo lleva.
        piece = {"source": campaigns.SINGLE, "body": campaign.get("body", ""),
                 "download": download_of(db, campaign)}
    else:
        piece = designs.by_id(db, account_id, campaign["design_id"])
    if piece is None:
        # La pieza se borró después de programar la campaña.
        campaigns.finish(db, account_id, campaign["_id"])
        return {"blocked": ["piece"], "sent": 0, "left": 0}

    wanted = campaigns.tags_of(campaign)
    # A quien le falte una columna no se le manda nada, así que tampoco se
    # cuenta: el total y las tandas miran lo mismo.
    fields = accounts.fields_of(account)
    if single:
        total = 1
    else:
        total = contacts.matching_count(db, account_id, tags=wanted,
                                        complete=fields)
    if campaign["status"] == campaigns.SCHEDULED:
        run_id = campaigns.start(db, account_id, campaign["_id"], total)
        # El envío tiene su id desde que arranca, y cada correo sale con él.
        campaign = {**campaign, "run_id": run_id}

    position = int(campaign.get("position", 0))
    # La cuota manda sobre el tope de la tanda: no se arma lo que no puede salir.
    room = min(limit, accounts.quota_left(account))
    if single:
        # A cualquier dirección: si está en Contactos sale con lo suyo (sus
        # columnas); si no, solo con su dirección, sin guardarla.
        who = (contacts.by_id(db, account_id, campaign["contact_id"])
               if campaign.get("contact_id") else None)
        to = campaign.get("to", "")
        who = who or ({"_id": None, "email": to, "email_normalized": to} if to else None)
        people = [who] if who and position == 0 and room > 0 else []
    else:
        people = contacts.batch_for_sending(db, account_id, tags=wanted,
                                            complete=fields,
                                            skip=position, limit=room)
    if (piece.get("source") == designs.CANVAS
            and (piece.get("canvas") or {}).get("v") != canvas.VERSION):
        # Guardada cuando el lienzo iba por diapositivas: sus imágenes son de
        # otra forma. Se rehacen una vez, antes del primer correo.
        piece = designs.upgrade_canvas(db, account_id, piece)
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
                      campaign_id=campaign["_id"],
                      run_id=campaign.get("run_id"), email=one["email"])

    if sent:
        # Estos correos van a pedir sus imágenes cada vez que alguien los abra:
        # desde ahora, borrar o volver a guardar la pieza ya no las borra.
        # Se leen del correo armado, así vale para las tres clases de pieza, y
        # en cada tanda, porque la pieza puede cambiar a mitad de un envío.
        images.mark_sent(db, account_id, imaging.names_in(
            ready.html(plan=accounts.plan_of(account), unsubscribe_url="")))

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
