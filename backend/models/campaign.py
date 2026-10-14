"""Las campañas: a quién se le escribe, con qué pieza y cuándo.

**Un documento por campaña, no por envío.** Guarda lo que se eligió —la lista,
la plantilla, el asunto, la hora— y **hasta dónde llegó**, que es el campo que
hace que un envío se pueda cortar y retomar sin mandarle dos veces a nadie.

Una campaña se manda **las veces que haga falta**: un boletín mensual se arma
una vez y sale doce. Los contadores de aquí son los de la vuelta en curso;
cuando una termina queda escrita en `campaign_runs` con sus cifras, y
`restart()` los devuelve a cero para la siguiente.

Esa posición no es un adorno de hoy. Mientras no exista el proceso en segundo
plano, el envío sale por tandas dentro de la petición y la pantalla ofrece
continuar; el día que exista, ese proceso llama a la misma función en bucle y
lee la misma posición. Es también lo que va a permitir pausar por cuota y
retomar, que es para lo que CLAUDE.md la pedía.

**Editar y borrar solo mientras no esté saliendo ahora mismo.** Cambiar el
asunto de algo que va por la mitad es mandarle dos cosas distintas a dos mitades
de la misma lista. Una que ya salió sí se puede corregir: es la campaña
guardada, y arreglarle el asunto para la próxima vez es para lo que se guarda.
Lo que ya salió no cambia por eso, porque vive en `campaign_runs` con el asunto
copiado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from models import campaign_run as runs

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


def tags_of(campaign: dict[str, Any] | None) -> list[str]:
    """A qué etiquetas sale. Vacío es «todos mis contactos».

    Lee `tags`, y si el documento es de antes de que se pudiera elegir más de
    una, su `tag` suelto. Así ninguna campaña vieja se rompe y no hay nada que
    migrar.
    """
    one = campaign or {}
    if one.get("tags") is not None:
        return list(one["tags"])
    return [one["tag"]] if one.get("tag") else []


# El correo individual (octubre de 2026): una campaña de **una persona**, con su
# texto y, si quiere, un archivo adjunto. Sale por el mismo camino que las demás
# (`services/sender.py`), así que lleva la baja, la marca de agua, la dirección
# postal y sus cifras; no sale en «Tus campañas», solo en lo que ya salió.
SINGLE = "single"
BODY_MAX = 20000


def create_single(db, account_id, *, subject: str, body: str, contact_id, to: str) -> Any:
    """Dejar listo un correo a una persona, para salir ya. Devuelve su id."""
    return db.campaigns.insert_one({
        "account_id": account_id,
        "kind": SINGLE,
        "subject": clean_subject(subject),
        "body": body[:BODY_MAX],
        "design_id": None,
        "contact_id": contact_id,
        "to": to,
        "tags": [],
        "scheduled_at": now(),
        "status": SCHEDULED,
        "position": 0,
        "total": 0,
        "sent": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "created_at": now(),
        "updated_at": now(),
    }).inserted_id


def create(db, account_id, *, subject: str, design_id, tags: list[str],
           scheduled_at: datetime) -> Any:
    """Dejar la campaña en cola. Devuelve su id."""
    return db.campaigns.insert_one({
        "account_id": account_id,
        "subject": clean_subject(subject),
        "design_id": design_id,
        # Vacío es «todos mis contactos». Se guardan los nombres de las
        # etiquetas y no sus posiciones: las etiquetas se pueden reordenar.
        "tags": list(tags or []),
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


def by_id(db, account_id, campaign_id) -> dict[str, Any] | None:
    """Una de esta cuenta. La cuenta va en la consulta, no se comprueba después."""
    return db.campaigns.find_one({"_id": campaign_id, "account_id": account_id})


def editable(campaign: dict[str, Any] | None) -> bool:
    """Si todavía se puede cambiar o borrar.

    Mientras no esté saliendo ahora mismo. Que le haya pasado la hora no la
    cierra: sin proceso en segundo plano nadie la despertó, así que sigue
    esperando y todavía se puede corregir. Y una que ya salió tampoco queda
    cerrada: es la campaña guardada, y lo que salió está escrito aparte.
    """
    return bool(campaign) and campaign.get("status") != SENDING


def update(db, account_id, campaign_id, *, subject: str, design_id,
           tags: list[str], scheduled_at: datetime) -> bool:
    """Cambiarla. False si en este momento está saliendo.

    El estado va en la consulta y no en una comprobación previa: entre mirar y
    escribir hay sitio para que el envío arranque.
    """
    return db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id,
         "status": {"$ne": SENDING}},
        {"$set": {"subject": clean_subject(subject), "design_id": design_id,
                  "tags": list(tags or []), "scheduled_at": scheduled_at,
                  "updated_at": now()},
         # Una campaña de antes llevaba una sola etiqueta en otro campo. Se
         # quita al guardar, o seguiría mandando por su cuenta.
         "$unset": {"tag": ""}}).matched_count == 1


def remove(db, account_id, campaign_id) -> bool:
    """Borrarla, mientras no esté saliendo.

    **Sus envíos no se borran.** Lo que salió salió, y el historial responde
    qué se le mandó a esa lista en marzo aunque la campaña ya no exista.
    """
    return db.campaigns.delete_one(
        {"_id": campaign_id, "account_id": account_id,
         "status": {"$ne": SENDING}}).deleted_count == 1


def due(campaign: dict[str, Any] | None) -> bool:
    """Si ya le llegó la hora y sigue esperando a que alguien la mande.

    Solo mira las que esperan. Una que ya salió también tiene una hora en el
    pasado, y no está esperando nada: está guardada.
    """
    when = (campaign or {}).get("scheduled_at")
    return (bool(when) and when <= now()
            and (campaign or {}).get("status") == SCHEDULED)


def start(db, account_id, campaign_id, total: int):
    """Marcar que empezó. Devuelve el id del envío, o None si otro la arrancó
    primero.

    Es la escritura que cierra la puerta de editar: a partir de aquí el asunto y
    la lista ya no se pueden cambiar.

    **El envío tiene su id desde aquí**, aunque su línea en `campaign_runs` se
    escriba al terminar: cada correo sale etiquetado con él, y los avisos de SES
    (entregas, aperturas) llegan mientras la campaña todavía está saliendo.
    """
    run_id = ObjectId()
    matched = db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id, "status": SCHEDULED},
        {"$set": {"status": SENDING, "total": total, "started_at": now(),
                  "run_id": run_id, "updated_at": now()}}).matched_count == 1
    return run_id if matched else None


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
    """Cerrar la vuelta y dejarla escrita en el historial.

    El envío se anota aquí y no en `services/sender.py` porque por aquí pasa
    toda vuelta que termina, salga entera o se quede sin gente a mitad de lista:
    no hay forma de cerrar una sin que quede escrita.
    """
    done = db.campaigns.find_one_and_update(
        {"_id": campaign_id, "account_id": account_id},
        {"$set": {"status": SENT, "finished_at": now(), "updated_at": now()}},
        return_document=ReturnDocument.AFTER)
    # Una que nunca llegó a empezar —se le borró la pieza antes de la primera
    # tanda— no es un envío: no salió un solo correo y anotarla sería llenar el
    # historial de líneas en cero.
    if done and done.get("started_at"):
        runs.record(db, {**done, "tags": tags_of(done)},
                    run_id=done.get("run_id"))


def restart(db, account_id, campaign_id, *, when: datetime) -> bool:
    """Dejar una campaña que ya salió lista para salir otra vez.

    Los contadores vuelven a cero porque son los de la vuelta en curso; lo que
    hizo la anterior está escrito en `campaign_runs` y no se toca. Sale a toda
    la lista otra vez, que es lo que se le pide a un boletín: los suprimidos se
    siguen saltando —la regla 1— y los demás la reciben de nuevo.

    El estado va dentro de la consulta que escribe: dos clics seguidos no
    arrancan dos envíos.
    """
    return db.campaigns.update_one(
        {"_id": campaign_id, "account_id": account_id, "status": SENT},
        {"$set": {"status": SCHEDULED, "scheduled_at": when, "position": 0,
                  "total": 0, "sent": 0, "skipped": 0, "failed": 0,
                  "errors": [], "started_at": None, "finished_at": None,
                  # El envío que viene es otro, con su propio id.
                  "run_id": None,
                  "updated_at": now()}}).matched_count == 1


def count(db, account_id) -> int:
    return db.campaigns.count_documents({"account_id": account_id})
