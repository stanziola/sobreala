"""Lo que SES cuenta de cada correo después de aceptarlo.

Un aviso por cosa que pasa: entregado, rebotó, queja, rechazado, lo abrieron,
pulsaron un enlace. Llega por SNS a `blueprints/webhooks/` y aquí se decide a
dónde va cada uno.

**De quién es un aviso lo dicen sus etiquetas, nunca la dirección.** Cada
correo de campaña sale con la cuenta, la campaña y el envío en la cabecera
`X-SES-MESSAGE-TAGS`, y SES las devuelve dentro de `mail.tags`. La misma
dirección puede estar en las listas de tres clientes, y anularla en las tres por
el rebote de una sería anular por cuenta ajena. Un correo del sistema no lleva
esas etiquetas: se encuentra en `mail_log` por el identificador que SES devolvió
al enviarlo.

Lo que **no** se puede saber y conviene no olvidar: «entregado» es que el
servidor del destinatario lo aceptó. Si después lo puso en la bandeja, en correo
no deseado o en cuarentena, no se lo cuenta a nadie.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from models import event as events
from models import mail_log
from models import suppression as suppressions

# Los nombres que usa SES en `eventType` (conjuntos de configuración) o en
# `notificationType` (avisos de identidad), y el tipo de evento nuestro.
KINDS = {
    "Delivery": events.DELIVERED,
    "Bounce": events.BOUNCE,
    "Complaint": events.COMPLAINT,
    "Reject": events.REJECT,
    "Open": events.OPEN,
    "Click": events.CLICK,
}


def _when(raw: str | None) -> datetime:
    """La hora del aviso, o ahora si no la trae o no se entiende."""
    try:
        return datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _tag(tags: dict[str, Any], name: str):
    """Una etiqueta como id de Mongo, o None. SES las manda como listas."""
    value = (tags.get(name) or [None])[0]
    try:
        return ObjectId(value) if value else None
    except (InvalidId, TypeError):
        return None


def _who(message: dict[str, Any], kind: str) -> list[dict[str, str]]:
    """A quién le pasó, con el detalle que traiga cada uno.

    Un rebote o una queja nombran a sus destinatarios; una entrega también. Una
    apertura, un clic y un rechazo no: esos van a la dirección del mensaje.
    """
    mail = message.get("mail") or {}
    if kind == "Bounce":
        return [{"email": one.get("emailAddress", ""),
                 "detail": one.get("diagnosticCode") or one.get("status") or ""}
                for one in (message.get("bounce") or {}).get("bouncedRecipients", [])]
    if kind == "Complaint":
        return [{"email": one.get("emailAddress", ""), "detail": ""}
                for one in (message.get("complaint") or {}).get("complainedRecipients", [])]
    if kind == "Delivery":
        return [{"email": one, "detail": ""}
                for one in (message.get("delivery") or {}).get("recipients", [])]
    if kind == "Reject":
        reason = (message.get("reject") or {}).get("reason", "")
        return [{"email": one, "detail": reason} for one in mail.get("destination", [])]
    return [{"email": one, "detail": ""} for one in mail.get("destination", [])]


def handle(db, message: dict[str, Any]) -> str:
    """Guardar un aviso. Devuelve qué se hizo con él, para el registro.

    Nunca lanza por un aviso raro: quien llama contesta 200 igual, porque un
    error aquí haría que SNS lo reintentara durante horas.
    """
    kind = message.get("eventType") or message.get("notificationType") or ""
    ours = KINDS.get(kind)
    if ours is None:
        # «Send» lo anota quien envía; lo demás no se usa.
        return f"ignorado: {kind or 'sin tipo'}"

    mail = message.get("mail") or {}
    tags = mail.get("tags") or {}
    account_id = _tag(tags, "account")
    campaign_id = _tag(tags, "campaign")
    at = _when((message.get(kind[0].lower() + kind[1:]) or {}).get("timestamp")
               or mail.get("timestamp"))
    people = _who(message, kind)

    if account_id and campaign_id:
        return _campaign(db, message, kind, ours, account_id, campaign_id,
                         _tag(tags, "run"), people, at)
    return _system(db, message, kind, mail.get("messageId"), people)


def _campaign(db, message, kind, ours, account_id, campaign_id, run_id,
              people, at) -> str:
    """Un aviso de un correo de campaña: evento, y anular si toca."""
    permanent = (kind == "Bounce" and
                 (message.get("bounce") or {}).get("bounceType") == "Permanent")
    # La dirección que pulsó, que solo viene en los avisos de clic. Se guarda
    # dentro del mismo evento: el clic sigue siendo uno por persona.
    link = (message.get("click") or {}).get("link") or "" if kind == "Click" else ""
    for one in people:
        if not one["email"]:
            continue
        events.record(db, account_id, kind=ours, campaign_id=campaign_id,
                      run_id=run_id, email=one["email"], at=at, link=link)
        # Un rebote permanente es una dirección que no existe, y una queja es
        # alguien que dijo que esto es spam: las dos se anulan **en esa cuenta**
        # y no se pueden levantar. Un rebote pasajero (buzón lleno, servidor
        # caído) no anula a nadie.
        if permanent:
            suppressions.add(db, account_id, one["email"],
                             reason=suppressions.HARD_BOUNCE, source="ses")
        elif kind == "Complaint":
            suppressions.add(db, account_id, one["email"],
                             reason=suppressions.COMPLAINT, source="ses")
    return f"campaña: {ours} x{len(people)}"


def _system(db, message, kind, message_id, people) -> str:
    """Un aviso de un correo del sistema: se marca su fila de `mail_log`.

    No anula a nadie: estos correos van a la dirección de una cuenta, no a los
    contactos de un cliente, y la supresión es de contactos.
    """
    detail = next((one["detail"] for one in people if one["detail"]), "")
    if kind == "Delivery":
        outcome = mail_log.DELIVERED
    elif kind == "Bounce":
        permanent = (message.get("bounce") or {}).get("bounceType") == "Permanent"
        outcome = mail_log.BOUNCED if permanent else mail_log.SOFT_BOUNCED
    elif kind == "Complaint":
        outcome = mail_log.COMPLAINED
    elif kind == "Reject":
        outcome = mail_log.REJECTED
    else:
        # Aperturas y clics no se miden en el correo del sistema.
        return f"sistema: {kind} sin uso"
    marked = mail_log.mark(db, message_id, outcome=outcome, detail=detail)
    return f"sistema: {outcome}" if marked else "sistema: sin fila"
