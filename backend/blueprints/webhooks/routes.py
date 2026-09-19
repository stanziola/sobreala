"""Los avisos que llegan de fuera: los de Amazon SES por SNS, y el de
Paguélofácil cuando alguien paga con tarjeta (abajo del todo).

Quien llama aquí no es una persona con sesión, es SNS. Así que no hay testigo
ni galleta que valgan, y lo que autoriza es otra cosa:

  * **El secreto va en la dirección.** SNS no puede mandar una cabecera
    nuestra, y un secreto que no cuadra, o que no está configurado, responde
    404: para quien prueba direcciones, esta no existe.
  * **Solo se acepta el tema que se configuró**, si `SES_TOPIC_ARN` está puesto.
  * **No se comprueba la firma de SNS.** Pide verificar RSA contra un
    certificado que se descarga, y eso es una dependencia más. Con el secreto
    viajando por HTTPS y el filtro del tema alcanza; es una decisión, no un
    olvido, y este es el sitio donde ponerla el día que se quiera cerrar del
    todo.

Un aviso que **no se entiende se contesta 200**: SNS reintenta lo que no
recibe 200, y un aviso raro reintentado durante horas no se arregla por
insistir. Uno que se entiende pero **no se pudo guardar** —la base no
respondió— se contesta 500, para que SNS sí lo vuelva a mandar.
"""

from __future__ import annotations

import hmac
import json
import re
import urllib.request
from urllib.parse import urlparse

from flask import Blueprint, abort, request

from config import Config
from db import get_db
from services import ses_events

bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")

# De dónde puede venir la dirección para confirmar la suscripción. Ese campo lo
# escribe quien manda el cuerpo, así que visitarlo sin mirar sería dejar que
# cualquiera haga que el servidor abra la dirección que quiera.
SNS_HOST = re.compile(r"^sns\.[a-z0-9-]+\.amazonaws\.com$")


def confirm(url: str | None) -> bool:
    """Visitar la dirección que confirma la suscripción, si es de Amazon."""
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or not SNS_HOST.match(parsed.hostname or ""):
        print(f"  [ses] confirmación rechazada: {parsed.hostname}", flush=True)
        return False
    with urllib.request.urlopen(url, timeout=10) as answer:  # noqa: S310
        return 200 <= answer.status < 300


@bp.route("/ses/<secret>", methods=["POST"])
def ses(secret: str):
    wanted = Config.SES_WEBHOOK_SECRET
    if not wanted or not hmac.compare_digest(secret, wanted):
        abort(404)

    try:
        envelope = json.loads(request.get_data(as_text=True) or "{}")
    except ValueError:
        print("  [ses] aviso ilegible", flush=True)
        return "", 200

    if Config.SES_TOPIC_ARN and envelope.get("TopicArn") != Config.SES_TOPIC_ARN:
        print(f"  [ses] tema ajeno: {envelope.get('TopicArn')}", flush=True)
        return "", 200

    kind = envelope.get("Type")
    if kind == "SubscriptionConfirmation":
        try:
            confirm(envelope.get("SubscribeURL"))
        except OSError as exc:
            # Amazon la vuelve a mandar si no se confirma; no hay nada que
            # guardar mientras tanto.
            print(f"  [ses] no se pudo confirmar: {exc}", flush=True)
        return "", 200
    if kind != "Notification":
        return "", 200

    try:
        message = json.loads(envelope.get("Message") or "{}")
    except ValueError:
        print("  [ses] mensaje ilegible", flush=True)
        return "", 200

    try:
        done = ses_events.handle(get_db(), message)
    except Exception as exc:  # noqa: BLE001 - se anota, y SNS lo reintenta
        # Esto no es un aviso raro, es la base que no respondió: un 500 hace
        # que SNS lo vuelva a mandar, que es justo lo que hace falta.
        print(f"  [ses] no se pudo guardar: {type(exc).__name__}: "
              f"{str(exc)[:200]}", flush=True)
        return "", 500
    print(f"  [ses] {done}", flush=True)
    return "", 200


# El id de nuestro intento dentro de la descripción del pago, que es donde lo
# puso el enlace (`paguelofacil.create_link()`).
ATTEMPT = re.compile(r"\b([0-9a-f]{24})\b")


@bp.route("/paguelofacil/<secret>", methods=["POST"])
def paguelofacil(secret: str):
    """El aviso automático de Paguélofácil: alguien pagó con tarjeta.

    Sirve para quien paga y cierra el navegador antes de volver. Lo que trae el
    cuerpo **no decide nada**: de él solo se toman el número de operación y el
    intento, y se le pregunta a Paguélofácil por esa operación, igual que en la
    vuelta del navegador (`card_verdict()`). Si la vuelta llegó antes y ya lo
    cobró, aquí no pasa nada: la escritura condicional no da dos periodos.

    Como el de SES: un secreto que no cuadra es 404, lo que no se entiende es
    200, y lo que se entiende pero no se pudo comprobar es 500, para que lo
    reintenten.
    """
    wanted = Config.PAGUELOFACIL_WEBHOOK_SECRET
    if not wanted or not hmac.compare_digest(secret, wanted):
        abort(404)

    from bson import ObjectId

    from blueprints.auth.routes import card_verdict, settle
    from models import account as accounts
    from models import payment as payments

    body = request.get_json(silent=True) or request.form.to_dict() or {}
    oper = str(body.get("codOper") or body.get("Oper") or "")[:64]
    found = ATTEMPT.search(str(body.get("description") or body.get("CDSC") or "")
                           + " " + str(body.get("PARM_1") or ""))
    if not oper or not found:
        print("  [paguelofacil] aviso sin operación o sin intento", flush=True)
        return "", 200

    db = get_db()
    attempt = payments.by_id(db, ObjectId(found.group(1)))
    if attempt is None or attempt.get("method") != payments.CARD:
        return "", 200
    if attempt["status"] != payments.CREATED:
        return "", 200
    account = accounts.by_id(db, attempt["account_id"])
    if account is None:
        return "", 200

    why, checked = card_verdict(attempt, oper)
    if why == "tarjeta":
        # No se pudo preguntar: que lo reintenten.
        return "", 500
    if why:
        # Un aviso de una operación denegada o de otro pago no cambia nada: el
        # intento se queda esperando, y lo cierra su propia vuelta.
        print(f"  [paguelofacil] {oper}: {why}", flush=True)
        return "", 200
    settle(db, account, attempt, payer_email=checked["email"],
           last4=checked["last4"], order_id=oper)
    print(f"  [paguelofacil] {oper}: cobrado", flush=True)
    return "", 200
