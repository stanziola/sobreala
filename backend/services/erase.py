"""Eliminar una cuenta y sus datos (octubre de 2026).

Hasta entonces se borraba a mano el documento de `accounts`, y todo lo demás
(contactos, campañas, envíos, eventos, plantillas, imágenes, sesiones) se
quedaba en la base para siempre, sin dueño. Este es el único sitio que borra
una cuenta: lo llaman el dueño desde Configuración → Cuenta y el administrador
desde la ficha.

**Lo que se borra** es lo de la empresa y lo de sus usuarios. **Lo que se
queda** lo prometen la privacidad y los términos, o lo pide la ley:

  * `suppressions`: las bajas y supresiones se guardan siempre, para que nadie
    le vuelva a escribir a quien pidió no recibir («ni tú ni nosotros las
    borramos»);
  * `payments` e `invoices`: las obligaciones contables y fiscales;
  * `auth_events`, `mail_log` y `admin_events`: la bitácora de accesos y de
    correos del sistema, que se guarda como registro de seguridad.

Afuera, el dominio propio se suelta en Amazon, la renovación automática se
cancela en PayPal y las cuentas de PayPal guardadas se olvidan. Si algo de
afuera falla se anota y se sigue: nada de afuera impide borrar lo de adentro.
"""

from __future__ import annotations

from typing import Any

from models import account as accounts
from models import admin_event as decisions

# Todo lo que guarda `account_id` y se va con la cuenta.
ERASED = ("contacts", "campaigns", "campaign_runs", "events", "designs", "images",
          "imports", "downloads", "sessions", "account_tokens", "verification_docs")
# Lo que se queda, a propósito (ver arriba).
KEPT = ("suppressions", "payments", "invoices", "auth_events", "mail_log",
        "admin_events")


def _outside(db, account: dict[str, Any]) -> list[str]:
    """Soltar lo que vive afuera. Devuelve lo que no se pudo, para anotarlo."""
    from services import paypal, renewals, ses_identity

    failed = []
    domain = (account.get("sender") or {}).get("domain")
    if domain:
        try:
            ses_identity.delete(domain)
        except Exception as exc:  # noqa: BLE001 - anotado, no detiene
            failed.append(f"ses {domain}: {type(exc).__name__}")
    sub = accounts.subscription_of(account)
    if sub and sub.get("id") and sub.get("status") != accounts.SUB_CANCELLED:
        try:
            if not renewals.cancel(db, account, "La cuenta se eliminó"):
                failed.append("paypal: renovación")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"paypal: renovación {type(exc).__name__}")
    for vault in accounts.paypal_vaults_of(account):
        try:
            paypal.delete_payment_token(vault["id"])
        except Exception as exc:  # noqa: BLE001
            failed.append(f"paypal: cuenta guardada {type(exc).__name__}")
    return failed


def erase(db, owner_id, *, by: Any, reason: str) -> dict[str, int]:
    """Borrar la empresa `owner_id` y a sus usuarios. Devuelve cuántos
    documentos se borraron de cada colección.

    `by` es quién la borra: la propia cuenta o un administrador. Queda una línea
    en `admin_events` con cuántos documentos se fueron, sin ninguna dirección.
    """
    owner = accounts.by_id(db, owner_id)
    if owner is None:
        return {}
    members = list(db.accounts.find({"owner_id": owner_id}))
    ids = [owner_id] + [one["_id"] for one in members]

    problems = _outside(db, owner)
    counts = {}
    for name in ERASED:
        counts[name] = db[name].delete_many({"account_id": {"$in": ids}}).deleted_count
    counts["accounts"] = db.accounts.delete_many({"_id": {"$in": ids}}).deleted_count

    decisions.record(db, kind=decisions.ERASE, admin_id=by, account_id=owner_id,
                     before=owner.get("company_name", ""),
                     after={"counts": counts, "outside_failed": problems},
                     reason=reason)
    if problems:
        print(f"  [erase] {owner_id}: no se pudo soltar {', '.join(problems)}", flush=True)
    return counts
