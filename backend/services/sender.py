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

Sale por tandas: la primera dentro de la petición que pulsa Enviar, y las
demás (y las programadas) desde el proceso en segundo plano (`worker.py`,
octubre de 2026), que llama a `run()` en bucle con su turno.
"""

from __future__ import annotations

import os
import time
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
from services import canvas, downloads, imaging, plans, render, unsubscribe

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


# Lo que sale de un texto escrito y no de una plantilla guardada (octubre de
# 2026: el individual y, desde entonces, también el masivo).
WRITTEN = "written"


class Piece:
    """Lo que dice el correo, listo para armarse con la baja de cada uno.

    Sale de una plantilla guardada (las tres clases de pieza) o de un texto
    escrito (`source: written`), y en los dos casos puede ser un correo
    individual o una campaña (octubre de 2026). **El individual va sin baja ni
    marca de agua**: es un correo de una persona a otra, no una campaña. La
    dirección postal sí va, y su archivo, si lleva, va como botón justo encima
    del pie. El texto escrito puede llevar el logo de la empresa arriba.
    """

    def __init__(self, design: dict[str, Any], *, single: bool = False,
                 download: dict[str, str] | None = None, logo: str = "",
                 untracked: bool = False):
        self.design = design
        self.single = single
        # Sin contar clics (`render.no_track`): el transaccional de la API.
        self.untracked = untracked
        self.download = download
        self.logo = logo
        self.built_in = design.get("source") == designs.BUILT_IN

    def html(self, *, plan: str | None, unsubscribe_url: str, postal: str = "") -> str:
        # El individual, sin baja y sin marca; una campaña, con su baja y con
        # la marca que diga su plan.
        unsubscribe_url = "" if self.single else unsubscribe_url
        watermark = False if self.single else None
        extra = render.download_button(**self.download) if self.download else ""
        source = self.design.get("source")
        if source == WRITTEN:
            body = self.logo + render.text_to_html(self.design.get("body", ""))
            return render.email_from_body(body + extra, plan=plan, unsubscribe=unsubscribe_url,
                                          postal=postal, watermark=watermark)
        if source == designs.CANVAS:
            # Lo arma el mismo código que la vista previa del lienzo, así que
            # lo que se vio es lo que sale.
            doc = canvas.read(self.design.get("canvas")) or canvas.blank()
            urls = [imaging.url_of(one) if one else None
                    for one in self.design.get("backgrounds") or []]
            shades = self.design.get("shades") or []
            return render.email_from_body(
                canvas.to_html(doc, urls, shades) + extra, plan=plan,
                unsubscribe=unsubscribe_url, style=canvas.dark_css(doc, shades),
                postal=postal, watermark=watermark)
        if self.built_in:
            return render.email(self.design.get("template", ""),
                                self.design.get("fields") or {},
                                plan=plan, unsubscribe=unsubscribe_url, postal=postal,
                                watermark=watermark, extra=extra)
        return render.email_from_html(self.design.get("html", ""), plan=plan, postal=postal,
                                      unsubscribe=unsubscribe_url, watermark=watermark,
                                      extra=extra)


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
        elif tag in ("td", "th"):
            # Las celdas de una fila, separadas: la tabla de una lista
            # (octubre de 2026) se leía «1 de octubre150Depósito».
            self.parts.append(" ")

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


def remitente(account: dict[str, Any], design: dict[str, Any] | None = None):
    """El remitente de un correo: el que eligió su plantilla
    (`designs.send_from`), si todavía existe y puede salir; si no, el
    predeterminado de la cuenta. None si no hay ninguno que pueda (octubre de
    2026: hay varios)."""
    chosen = accounts.from_of(account, (design or {}).get("send_from"))
    if chosen is not None and chosen["ready"]:
        return chosen
    return accounts.default_from(account)


def sender_email(account: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    """La dirección de la que sale, o vacío si todavía no hay.

    De su usuario en `SENDING_DOMAIN` o de uno de sus dominios verificados,
    según el remitente. **Nunca de `SYSTEM_FROM_EMAIL`**: esa es la de los
    códigos y los recibos, y una lista mala de un cliente no puede llevárselos
    a spam. Sin remitente, vacío, y `blocked()` dice `sender`.
    """
    found = remitente(account, design)
    return found["address"] if found else ""


def from_address(account: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    """De quién sale, con su nombre a la vista: el del remitente, o el de la
    empresa."""
    found = remitente(account, design)
    name = ((found or {}).get("label") or account.get("company_name")
            or Config.SYSTEM_FROM_NAME).strip()
    return formataddr((name, found["address"] if found else ""))


def reply_to(account: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    """A dónde llegan las respuestas: el «Responder a» que eligió la plantilla,
    si sigue confirmado; si no, el predeterminado, o el correo con el que entra
    el dueño. La conversación es suya, no nuestra."""
    chosen = (design or {}).get("reply_to")
    if chosen and chosen in accounts.reply_tos_of(account):
        return chosen
    return accounts.default_reply(account)


def build(account: dict[str, Any], campaign: dict[str, Any], piece: Piece,
          contact: dict[str, Any],
          fields: list[dict[str, Any]] | None = None, *,
          data: dict[str, Any] | None = None) -> EmailMessage:
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
    html = columns.fill(html, contact, fields, data=data)
    if piece.untracked:
        # Un transaccional de la API (octubre de 2026): sus enlaces suelen ser
        # privados (cambiar la contraseña, ver una factura) y el contador de
        # clics de SES los guardaría.
        html = render.no_track(html)

    message = EmailMessage(policy=POLICY)
    # De quién sale y a dónde se responde los elige la plantilla (octubre de
    # 2026); lo escrito no tiene plantilla y va con los predeterminados.
    message["From"] = from_address(account, piece.design)
    message["To"] = contact["email"]
    # Sin escapar: un asunto es texto, y ahí «&» es «&» y no «&amp;».
    message["Subject"] = columns.fill(campaign["subject"], contact, fields,
                                      html=False, data=data)
    # Responder le llega al cliente, no a nosotros: la conversación es suya.
    answer = reply_to(account, piece.design)
    if answer:
        message["Reply-To"] = answer
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

    from services import aws

    client = aws.client("ses")
    # La dirección va explícita (octubre de 2026): aunque algo se colara en
    # una cabecera, SES no se lo entrega a nadie más.
    kwargs: dict[str, Any] = {"RawMessage": {"Data": bytes(message)},
                              "Destinations": [str(message["To"])]}
    if Config.SES_CONFIGURATION_SET:
        kwargs["ConfigurationSetName"] = Config.SES_CONFIGURATION_SET
    return client.send_raw_email(**kwargs)["MessageId"]


# El logo arriba de un correo escrito: ni más ancho ni más alto que esto.
LOGO_BOX = (180, 64)


def logo_block(db, account: dict[str, Any]) -> str:
    """El logo de la empresa para ponerlo arriba de un correo escrito, a su
    medida dentro de `LOGO_BOX`. Vacío si no tiene o no se puede leer."""
    name = accounts.logo_of(account)
    raw = images.data_of(db, account["_id"], name) if name else None
    if not raw:
        return ""
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(raw)) as opened:
            width, height = opened.size
    except Exception:  # noqa: BLE001 - sin logo es mejor que sin correo
        return ""
    scale = min(LOGO_BOX[0] / width, LOGO_BOX[1] / height, 1)
    return render.logo_header(imaging.url_of(name), alt=account.get("company_name", ""),
                              width=max(1, round(width * scale)),
                              height=max(1, round(height * scale)))


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
    if accounts.in_demo(account):
        # La demostración envía sin plan, pero solo a sus direcciones de prueba
        # confirmadas y hasta `DEMO_SENDS` correos (octubre de 2026).
        if not accounts.confirmed_test_addresses(account):
            why.append("demo_addresses")
        elif accounts.demo_left(account) <= 0:
            why.append("demo_used")
    elif not accounts.plan_of(account):
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
        limit: int | None = None, lease_by: str | None = None,
        stop=None, pace: float = 0.0) -> dict[str, Any]:
    """Mandar una tanda. Devuelve qué pasó y si queda algo pendiente.

    El tope se lee aquí y no en la firma: así se puede cambiar el de arriba y
    esta función obedece, que es lo que hace falta para probarla con tandas de
    dos y para ajustarlo el día que se sepa cuánto aguanta el servidor.

    Desde octubre de 2026 la llama también el proceso en segundo plano, y nadie
    recibe dos veces aunque dos la manden a la vez o una se caiga a la mitad:

      * si `start()` dice que otro la arrancó primero, no se manda nada;
      * la lista se recorre por `_id` desde el último que se procesó
        (`cursor_id`), así borrar contactos a mitad de camino no salta a nadie;
      * quien ya tiene su correo de este envío no lo vuelve a recibir;
      * la cuota se **aparta antes** de mandar y lo que no salió se devuelve;
      * con `lease_by`, avanzar y cerrar solo escriben si el turno sigue siendo
        de ese proceso; `stop()` corta entre un correo y otro (al apagarse), y
        si SES pide esperar la tanda para ahí sin dar a nadie por fallado.

    `pace` son los segundos entre un correo y otro: el proceso de fondo no pasa
    del ritmo que Amazon le permite a la cuenta.
    """
    limit = BATCH if limit is None else limit
    account_id = account["_id"]
    why = blocked(account)
    if why:
        return {"blocked": why, "sent": 0, "left": 0}

    single = campaign.get("kind") == campaigns.SINGLE
    if campaigns.written(campaign):
        # Un texto escrito, sin plantilla guardada: el individual de siempre y,
        # desde octubre de 2026, también el masivo.
        piece = {"source": WRITTEN, "body": campaign.get("body", "")}
    else:
        piece = designs.by_id(db, account_id, campaign["design_id"])
    if piece is None:
        # La pieza se borró después de programar la campaña.
        campaigns.finish(db, account_id, campaign["_id"], by=lease_by)
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
        if run_id is None:
            # Otro la arrancó primero (dos clics en Enviar, o el proceso de
            # fondo): mandar aquí también sería mandar la tanda dos veces.
            return {"blocked": ["busy"], "sent": 0, "left": 0}
        # El envío tiene su id desde que arranca, y cada correo sale con él.
        campaign = {**campaign, "run_id": run_id, "position": 0, "cursor_id": None}

    position = int(campaign.get("position", 0))
    cursor_id = campaign.get("cursor_id")
    # La cuota manda sobre el tope de la tanda: no se arma lo que no puede salir.
    # En la demostración, la cuota son los correos de prueba que le quedan; la
    # tanda se arma igual de larga, porque casi todos se van a saltar.
    demo = accounts.in_demo(account)
    testers = accounts.confirmed_test_addresses(account) if demo else set()
    room = limit if demo and accounts.demo_left(account) > 0 else (
        0 if demo else min(limit, accounts.quota_left(account)))
    if single:
        # A cualquier dirección: si está en Contactos sale con lo suyo (sus
        # columnas); si no, solo con su dirección, sin guardarla.
        who = (contacts.by_id(db, account_id, campaign["contact_id"])
               if campaign.get("contact_id") else None)
        to = campaign.get("to", "")
        who = who or ({"_id": None, "email": to, "email_normalized": to} if to else None)
        people = [who] if who and position == 0 and room > 0 else []
    elif cursor_id is None and position > 0:
        # A medias desde antes del cursor (octubre de 2026): sigue por posición
        # esta vez, y desde la próxima por `_id`.
        people = contacts.batch_for_sending(db, account_id, tags=wanted,
                                            complete=fields, skip=position, limit=room)
    else:
        people = contacts.batch_for_sending(db, account_id, tags=wanted,
                                            complete=fields, after_id=cursor_id,
                                            limit=room)
    if (piece.get("source") == designs.CANVAS
            and (piece.get("canvas") or {}).get("v") != canvas.VERSION):
        # Guardada cuando el lienzo iba por diapositivas: sus imágenes son de
        # otra forma. Se rehacen una vez, antes del primer correo.
        piece = designs.upgrade_canvas(db, account_id, piece)
    ready = Piece(piece, single=single,
                  download=download_of(db, campaign) if single else None,
                  logo=logo_block(db, account) if campaign.get("logo") else "")

    def key_of(one: dict[str, Any]) -> str:
        return one.get("email_normalized") or normalize(one["email"])

    among = suppressions.among(db, account_id,
                               [one["email"] for one in people])
    # Quien ya tiene su correo de este envío (una tanda que se cortó después de
    # entregar y antes de anotar), en una consulta.
    already = {row["email_normalized"] for row in db.events.find(
        {"account_id": account_id, "run_id": campaign.get("run_id"), "kind": events.SENT,
         "email_normalized": {"$in": [key_of(one) for one in people]}},
        {"email_normalized": 1})} if people and campaign.get("run_id") else set()
    # Quién de esta tanda va a salir. Regla 1: el suprimido se salta y no gasta
    # cuota. Lo mismo una dirección de un dominio que no recibe correo, que es
    # un rebote seguro (`services/address_check.py`). En la demostración solo
    # sale a las direcciones de prueba, y hasta lo que le queda.
    going: set[int] = set()
    skipped = 0
    for index, one in enumerate(people):
        key = key_of(one)
        if key in already:
            continue
        if one["email"] in among or key in among or one.get("invalid"):
            skipped += 1
        elif demo and (key not in testers or len(going) >= accounts.demo_left(account)):
            skipped += 1
        else:
            going.add(index)
    # La cuota se aparta antes de mandar: dos envíos a la vez no se pasan.
    if demo:
        reserved = accounts.reserve_demo(db, account_id, len(going))
    else:
        reserved = accounts.reserve_quota(
            db, account_id, len(going), plans.emails_a_month(accounts.plan_of(account)))
    if not reserved:
        return {"blocked": ["demo_used" if demo else "quota"], "sent": 0,
                "left": max(0, total - position)}

    sent = failed = done = 0
    last_id = cursor_id
    throttled = stopped = False
    errors: list[dict[str, str]] = []
    for index, one in enumerate(people):
        if stop is not None and stop():
            stopped = True
            break
        if index in going:
            try:
                deliver(build(account, campaign, ready, one, fields))
            except Exception as exc:  # noqa: BLE001 - se anota y se sigue
                if _throttled(exc):
                    # Amazon pidió esperar: este y los que siguen salen en la
                    # vuelta siguiente, sin darlos por fallados.
                    throttled = True
                    break
                failed += 1
                errors.append({"email": one["email"],
                               "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            else:
                sent += 1
                events.record(db, account_id, kind=events.SENT,
                              campaign_id=campaign["_id"],
                              run_id=campaign.get("run_id"), email=one["email"])
                if pace:
                    time.sleep(pace)
        done += 1
        last_id = one.get("_id") if one.get("_id") is not None else last_id

    # Lo apartado que no salió vuelve al mismo mes.
    if demo:
        accounts.release_demo(db, account_id, len(going) - sent)
        accounts.add_sent(db, account_id, sent)
    else:
        accounts.release_quota(db, account_id, len(going) - sent)

    if sent:
        # Estos correos van a pedir sus imágenes cada vez que alguien los abra:
        # desde ahora, borrar o volver a guardar la pieza ya no las borra.
        # Se leen del correo armado, así vale para las tres clases de pieza, y
        # en cada tanda, porque la pieza puede cambiar a mitad de un envío.
        images.mark_sent(db, account_id, imaging.names_in(
            ready.html(plan=accounts.plan_of(account), unsubscribe_url="")))

    position += done
    if not campaigns.advance(db, account_id, campaign["_id"], position=position,
                             sent=sent, skipped=skipped, failed=failed, errors=errors,
                             cursor_id=None if single else last_id, by=lease_by):
        # Perdió el turno a mitad de la tanda: lo que sigue lo anota quien lo tiene.
        return {"blocked": ["busy"], "sent": sent, "skipped": skipped, "failed": failed,
                "left": max(0, total - position), "errors": errors}

    # Se termina cuando la lista se acaba: una tanda que trajo menos de los que
    # pidió, o ninguno. No por el conteo, que se encoge si alguien borra
    # contactos a mitad de camino y cerraría la campaña con gente sin recibir.
    finished = not (stopped or throttled) and (not people or len(people) < room)
    left = max(0, total - position)
    if finished:
        campaigns.finish(db, account_id, campaign["_id"], by=lease_by)
        left = 0
    else:
        left = max(1, left)
    return {"blocked": [], "sent": sent, "skipped": skipped, "failed": failed,
            "left": left, "errors": errors, "throttled": throttled, "stopped": stopped}


# ------------------------------------------------- un correo de la API (octubre de 2026)

# Lo único que frena un transaccional: quien no existe y quien dijo que es spam.
# Quien se dio de baja de las promociones sigue necesitando su recibo.
TRANSACTIONAL_STOPS = (suppressions.HARD_BOUNCE, suppressions.COMPLAINT)
# Lo que dice SES cuando hay que esperar: no es un fallo del correo.
THROTTLED = ("Throttling", "ThrottlingException", "MaxSendingRateExceeded")
# En el envío de un correo de la API, la campaña es el propio mensaje.
API = "api"


def lacking(account: dict[str, Any], piece: Piece, subject: str,
            contact: dict[str, Any] | None, data: dict[str, Any] | None) -> list[str]:
    """Las marcas de la plantilla y del asunto que se quedarían en blanco: ni
    en los datos, ni en el contacto. A diferencia de una campaña, un correo de
    la API con una marca vacía no sale."""
    html = piece.html(plan=None, unsubscribe_url="")
    return columns.lacking(html + "\n" + subject, contact, accounts.fields_of(account), data)


def _throttled(exc: Exception) -> bool:
    code = (getattr(exc, "response", None) or {}).get("Error", {}).get("Code", "")
    return code in THROTTLED


def send_one(db, account: dict[str, Any], *, kind: str, to: str, design: dict[str, Any],
             subject: str, data: dict[str, Any] | None = None, logo: bool = False,
             key_id=None, request_key: str | None = None,
             simulate: bool = False) -> dict[str, Any]:
    """Un correo de la API a una persona, transaccional o promocional.

    Devuelve `{"refused": motivo, ...}` si no puede salir (nada se gasta ni se
    guarda), `{"status": "simulated", "preview": ...}` con una llave de prueba,
    o el mensaje guardado (`{"status": "sent" | "failed", "message": ...}`).

    El transaccional va sin baja ni marca de agua y sin contar clics, a
    cualquier dirección; solo lo frenan un rebote permanente o una queja en
    esta cuenta, o un dominio que no recibe correo. El promocional es como una
    campaña de una persona: a un contacto completo y sin ninguna supresión, con
    su baja y la marca de su plan. Los dos gastan cuota, respetan la pausa y,
    en la demostración, solo van a sus direcciones de prueba.
    """
    from models import message as messages
    from services import address_check

    why = blocked(account)
    if why:
        return {"refused": "cannot_send", "blocked": why}
    account_id = account["_id"]
    fields = accounts.fields_of(account)
    promotional = kind == messages.PROMOTIONAL
    contact = contacts.by_email(db, account_id, to)
    if promotional:
        if contact is None:
            return {"refused": "not_a_contact"}
        if contact.get("invalid"):
            return {"refused": "undeliverable"}
        if suppressions.among(db, account_id, [to]):
            return {"refused": "suppressed"}
        missing = columns.missing(contact, fields)
        if missing:
            return {"refused": "contact_incomplete", "missing": missing}
    else:
        if suppressions.among(db, account_id, [to], reasons=TRANSACTIONAL_STOPS):
            return {"refused": "suppressed"}
        if (contact or {}).get("invalid") or address_check.undeliverable([to], max_domains=1):
            return {"refused": "undeliverable"}
    demo = accounts.in_demo(account)
    if demo and normalize(to) not in accounts.confirmed_test_addresses(account):
        return {"refused": "demo_address"}

    piece = Piece(design, single=not promotional, untracked=not promotional,
                  logo=logo_block(db, account) if logo else "")
    absent = lacking(account, piece, subject, contact, data)
    if absent:
        return {"refused": "missing_data", "missing": absent}
    who = contact or {"_id": None, "email": to, "email_normalized": normalize(to)}
    if simulate:
        made = _built(account, {"_id": None, "subject": subject,
                                "kind": API if promotional else campaigns.SINGLE},
                      piece, who, fields, data)
        if isinstance(made, dict):
            return made
        return {"status": "simulated", "preview": {
            "subject": str(made["Subject"]),
            "html": made.get_body(("html",)).get_content(),
            "text": made.get_body(("plain",)).get_content()}}

    message_id = messages.start(
        db, account_id=account_id, key_id=key_id, kind=kind, to=to,
        contact_id=(contact or {}).get("_id"), subject=subject,
        template_id=design.get("_id"), sent_from=sender_email(account, design),
        reply_to=reply_to(account, design), request_key=request_key)
    if message_id is None:
        return {"refused": "replay"}
    # La cuota se aparta antes de mandar: dos a la vez no se pasan.
    if demo:
        reserved = accounts.reserve_demo(db, account_id, 1)
    else:
        reserved = accounts.reserve_quota(
            db, account_id, 1, plans.emails_a_month(accounts.plan_of(account)))
    if not reserved:
        messages.failed(db, message_id, error="quota")
        messages.forget(db, message_id)
        return {"refused": "cannot_send", "blocked": ["demo_used" if demo else "quota"]}

    def give_back() -> None:
        if demo:
            accounts.release_demo(db, account_id, 1)
        else:
            accounts.release_quota(db, account_id, 1)

    made = _built(account, {"_id": message_id, "run_id": message_id, "subject": subject,
                            "kind": API if promotional else campaigns.SINGLE},
                  piece, who, fields, data)
    if isinstance(made, dict):
        give_back()
        messages.failed(db, message_id, error=made["refused"])
        messages.forget(db, message_id)
        return made
    try:
        ses_id = deliver(made)
    except Exception as exc:  # noqa: BLE001 - se anota y se dice
        give_back()
        if _throttled(exc):
            messages.failed(db, message_id, error="throttled")
            messages.forget(db, message_id)
            return {"refused": "throttled"}
        messages.failed(db, message_id, error=f"{type(exc).__name__}: {str(exc)[:200]}")
        return {"status": messages.FAILED, "message": messages.by_id(db, account_id, message_id)}
    messages.sent(db, message_id, ses_id=str(ses_id))
    if demo:
        accounts.add_sent(db, account_id, 1)
    events.record(db, account_id, kind=events.SENT, campaign_id=message_id,
                  run_id=message_id, email=to)
    images.mark_sent(db, account_id, imaging.names_in(
        piece.html(plan=accounts.plan_of(account), unsubscribe_url="")))
    return {"status": messages.SENT, "message": messages.by_id(db, account_id, message_id)}


def normalize(email: str) -> str:
    return accounts.normalize_email(email)


def _built(account, campaign, piece, who, fields, data):
    """El correo armado, o `{"refused": "bad_subject"}` si el asunto lleno no
    cabe en una cabecera (un dato del contacto con un salto de línea)."""
    try:
        return build(account, campaign, piece, who, fields, data=data)
    except ValueError:
        return {"refused": "bad_subject"}
