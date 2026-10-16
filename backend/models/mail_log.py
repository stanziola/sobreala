"""The mail_log collection: one document per system email that was attempted.

Body included, on purpose. When someone says a confirmation never arrived, the
useful question is what exactly left the server, and the answer has to be
readable months later: same subject, same HTML, same link. Storing only metadata
answers "we tried" and nothing more.

Failures are recorded too, with the reason. From the outside "the mail never
arrived" and "sending raised an exception" look identical, and they need
completely different fixes.

These are TRANSACTIONAL messages only: confirmation and account notices. Client
campaigns are a different path with its own accounting, and the unsubscribe and
watermark rules in CLAUDE.md apply there, not here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from models.account import normalize_email

SENT = "sent"
FAILED = "failed"

# What the message was for. Keeps the log readable without parsing subjects.
CONFIRM = "confirm"
EXISTS = "exists"
WELCOME = "welcome"
PASSWORD_CHANGED = "password_changed"
RECOVER = "recover"
NEW_LOGIN = "new_login"
TWO_FACTOR = "two_factor"
# Los avisos de la cuenta, que compone services/notices.py.
PLAN_PAID = "plan_paid"
PLAN_EXPIRING = "plan_expiring"
PLAN_EXPIRED = "plan_expired"
INVOICE = "invoice"
OPENED = "opened"
SUSPENDED = "suspended"
REINSTATED = "reinstated"
# El límite de envío y el resultado de las verificaciones, que manda el
# administrador cuando quiere.
LIMITED = "limited"
# La pausa automática por rebotes o quejas, al cliente y a quien administra.
PAUSED = "paused"
# El enlace que confirma una dirección de prueba de la demostración.
TEST_ADDRESS = "test_address"
ADMIN_PAUSE = "admin_pause"
# Lo de la renovación automática: se enciende, se apaga o no se pudo cobrar.
RENEWAL = "renewal"
VERIFICATION_RESULT = "verification_result"
ADMIN_PAYMENT = "admin_payment"
ADMIN_SIGNUP = "admin_signup"
ADMIN_DEMO = "admin_demo"
ADMIN_PLAN_END = "admin_plan_end"
# Cambiar el correo de la cuenta: el código va a la dirección nueva y el aviso
# a la vieja, así que son dos mensajes distintos y a dos sitios distintos.
EMAIL_CHANGE_CODE = "email_change_code"
# La invitación a entrar como usuario de una cuenta.
INVITE = "invite"
EMAIL_CHANGED = "email_changed"
# El código que confirma el «Responder a» de las campañas.
REPLY_TO_CODE = "reply_to_code"
# Eliminar la cuenta (octubre de 2026): el código sin contraseña, el aviso de
# que se eliminó, y el aviso a quien administra.
ERASE_CODE = "erase_code"
ERASED = "erased"
ADMIN_ERASED = "admin_erased"
# Sent by hand from check_mail.py, never by the application.
CHECK = "check"


def now() -> datetime:
    return datetime.now(timezone.utc)


# Lo que SES dijo del mensaje después de aceptarlo. `status` sigue siendo si
# salió de aquí; esto es otra cosa y por eso es otro campo: un correo puede
# salir perfectamente y no llegar nunca.
DELIVERED = "delivered"
BOUNCED = "bounced"
SOFT_BOUNCED = "soft_bounced"
COMPLAINED = "complained"
REJECTED = "rejected"
OUTCOMES = (DELIVERED, BOUNCED, SOFT_BOUNCED, COMPLAINED, REJECTED)


def mark(db, provider_id: str | None, *, outcome: str, detail: str = "") -> bool:
    """Anotar qué pasó con un correo que ya había salido.

    Se busca por el identificador que devolvió SES, que es el mismo que viene
    en su aviso. Sin identificador no hay nada que marcar: será un correo
    escrito en disco durante el desarrollo.
    """
    if not provider_id or outcome not in OUTCOMES:
        return False
    return db.mail_log.update_one(
        {"provider_id": provider_id},
        {"$set": {"outcome": outcome, "outcome_detail": (detail or "")[:300],
                  "outcome_at": now()}}).modified_count == 1


def for_address(db, address: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Los correos del sistema que se le mandaron a esa dirección.

    Sin el cuerpo: la pantalla de administración dice qué pasó con cada uno, y
    el texto de un código de confirmación no tiene nada que hacer ahí.
    """
    if not address:
        return []
    return list(db.mail_log.find(
        {"to_normalized": normalize_email(address)},
        {"html": 0, "text": 0}).sort("created_at", -1).limit(limit))


def record(db, *, to: str, subject: str, backend: str, status: str,
           html: str = "", text: str = "", purpose: str = "",
           provider_id: str | None = None, error: str | None = None,
           account_id: Any = None) -> Any:
    """Write one row. Returns the new document's id."""
    doc = {
        "to": to,
        # Same normalisation as accounts and contacts, so a search for an
        # address finds its mail whatever case it was typed in.
        "to_normalized": normalize_email(to) if to else "",
        "subject": subject,
        "backend": backend,
        "status": status,
        "purpose": purpose,
        "provider_id": provider_id,
        "error": error,
        "account_id": account_id,
        "html": html,
        "text": text,
        "created_at": now(),
    }
    return db.mail_log.insert_one(doc).inserted_id
