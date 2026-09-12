"""Las campañas: a quién se le escribe, con qué pieza y cuándo.

Un documento por envío. Guarda lo que se eligió —la lista, la plantilla, el
asunto, la hora— y **hasta dónde llegó**, que es el campo que hace que un envío
se pueda cortar y retomar sin mandarle dos veces a nadie.

Esa posición no es un adorno de hoy. Mientras no exista el proceso en segundo
plano, el envío sale por tandas dentro de la petición y la pantalla ofrece
continuar; el día que exista, ese proceso llama a la misma función en bucle y
lee la misma posición. Es también lo que va a permitir pausar por cuota y
retomar, que es para lo que CLAUDE.md la pedía.

**Editar y borrar solo mientras no haya empezado a salir.** Cambiar el asunto de
algo que ya va por la mitad es mandarle dos cosas distintas a dos mitades de la
misma lista.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SUBJECT_MAX = 150

# Los estados por los que pasa. No hay «fallida»: un correo que no sale se
# cuenta y se anota con su motivo, pero la campaña sigue con el siguiente.
SCHEDULED = "scheduled"    # tiene hora y no ha empezado
SENDING = "sending"        # empezó y le faltan destinatarios
SENT = "sent"              # terminó
STATES = (SCHEDULED, SENDING, SENT)

# Cuántos errores se guardan para enseñarlos. Los primeros bastan para entender
# qué pasa; guardarlos todos convertiría el documento en un registro.
ERRORS_KEPT = 10


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_subject(raw: str) -> str:
    return " ".join((raw or "").split())[:SUBJECT_MAX]


def create(db, account_id, *, subject: str, design_id, tag: str,
           scheduled_at: datetime) -> Any:
    """Dejar la campaña en cola. Devuelve su id."""
    return db.campaigns.insert_one({
        "account_id": account_id,
        "subject": clean_subject(subject),
        "design_id": design_id,
        # Vacío es «todos mis contactos». Se guarda el nombre de la etiqueta y
        # no su posición: las etiquetas se pueden reordenar.
        "tag": tag or "",
        "scheduled_at": scheduled_at,
        "status": SCHEDULED,
        # Hasta qué destinatario se llegó, contando también los que se saltaron.
        "position": 0,
        "total": 0,
        "sent": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "created_at": now(),
        "updated_at": now(),
        "started_at": None,
        "finished_at": None,
    }).inserted_id


def for_account(db, account_id, *, limit: int = 50) -> list[dict[str, Any]]:
    return list(db.campaigns.find({"account_id": account_id})
                .sort("scheduled_at", -1).limit(limit))


def recent(db, account_id, *, limit: int = 20) -> list[dict[str, Any]]:
    """Las últimas de esta cuenta, por cuándo se armaron.

    `for_account()` ordena por la hora de envío, que es lo que la pantalla del
    cliente enseña; la actividad de la ficha ordena por cuándo pasaron las
    cosas, y una campaña armada hoy para dentro de un mes no es lo más viejo
    que tiene esa cuenta.
    """
    return list(db.campaigns.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))


def by_id(db, account_id, campaign_id) -> dict[str, Any] | None:
    """Una de esta cuenta. La cuenta va en la consulta, no se comprueba después."""
    return db.campaigns.find_one({"_id": campaign_id, "account_id": account_id})


def editable(campaign: dict[str, Any] | None) -> bool:
    """Si todavía se puede cambiar o borrar.

    Mientras no haya empezado a salir. Que le haya pasado la hora no la cierra:
    sin proceso en segundo plano nadie la despertó, así que sigue esperando y
    todavía se puede corregir.
    """
    return bool(campaign) and campaign.get("status") == SCHEDULED


def update(db, account_id, campaign_id, *, subject: str, design_id, tag: str,
           scheduled_at: datetime) -> bool:
    """Cambiarla. False si ya había empezado a salir.

    El estado va en la consulta y no en una comprobación previa: entre mirar y
    escribir hay sitio para que el envío arranque.
    """
    return db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id, "status": SCHEDULED},
        {"$set": {"subject": clean_subject(subject), "design_id": design_id,
                  "tag": tag or "", "scheduled_at": scheduled_at,
                  "updated_at": now()}}).matched_count == 1


def remove(db, account_id, campaign_id) -> bool:
    """Borrarla, mientras no haya empezado."""
    return db.campaigns.delete_one(
        {"_id": campaign_id, "account_id": account_id,
         "status": SCHEDULED}).deleted_count == 1


def due(campaign: dict[str, Any] | None) -> bool:
    """Si ya le llegó la hora y sigue esperando a que alguien la mande."""
    when = (campaign or {}).get("scheduled_at")
    return bool(when) and when <= now() and editable(campaign)


def start(db, account_id, campaign_id, total: int) -> bool:
    """Marcar que empezó. False si otro la arrancó primero.

    Es la escritura que cierra la puerta de editar: a partir de aquí el asunto y
    la lista ya no se pueden cambiar.
    """
    return db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id, "status": SCHEDULED},
        {"$set": {"status": SENDING, "total": total, "started_at": now(),
                  "updated_at": now()}}).matched_count == 1


def advance(db, account_id, campaign_id, *, position: int, sent: int,
            skipped: int, failed: int, errors: list[dict[str, str]]) -> None:
    """Anotar lo que hizo una tanda."""
    db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id},
        {"$set": {"position": position, "updated_at": now()},
         "$inc": {"sent": sent, "skipped": skipped, "failed": failed},
         "$push": {"errors": {"$each": errors[:ERRORS_KEPT],
                              "$slice": ERRORS_KEPT}}})


def finish(db, account_id, campaign_id) -> None:
    db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id},
        {"$set": {"status": SENT, "finished_at": now(), "updated_at": now()}})


def count(db, account_id) -> int:
    return db.campaigns.count_documents({"account_id": account_id})
