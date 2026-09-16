"""Los envíos: un documento cada vez que una campaña sale.

La campaña es lo que se guarda —el asunto, la pieza, la lista— y se manda las
veces que haga falta: un boletín mensual es una campaña y doce envíos. Esto es
lo otro, lo que pasó cada vez.

**Aparte y no dentro del documento de la campaña**, por tres razones. No hay
tope: treinta envíos son treinta líneas y no las últimas doce que cupieran en un
arreglo. El documento de la campaña no crece sin límite. Y el asunto y la lista
van **copiados**, así que el historial sigue contando la verdad aunque después
se le cambie el asunto a la campaña o se borre entera: lo que salió, salió.

De los destinatarios no se guarda nada, como en toda esta pantalla: cuántos
salieron, cuántos se saltaron por estar suprimidos y cuántos fallaron. Lo único
con una dirección dentro son los errores, que son los que hay que poder mirar
para saber por qué a alguien no le llegó, y vienen ya recortados de la campaña.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now() -> datetime:
    return datetime.now(timezone.utc)


def record(db, campaign: dict[str, Any], *, run_id=None) -> Any:
    """Anotar el envío que acaba de terminar. Devuelve su id.

    `run_id` es el que se le dio al arrancar, con el que salió etiquetado cada
    correo: la línea usa ese mismo, que es lo que cruza las cifras de SES con
    el envío al que pertenecen.
    """
    doc: dict[str, Any] = {}
    if run_id is not None:
        doc["_id"] = run_id
    return db.campaign_runs.insert_one({
        **doc,
        "account_id": campaign["account_id"],
        "campaign_id": campaign["_id"],
        # Copiados a propósito: ver más arriba.
        "subject": campaign.get("subject", ""),
        "tags": list(campaign.get("tags") or []),
        "total": campaign.get("total", 0),
        "sent": campaign.get("sent", 0),
        "skipped": campaign.get("skipped", 0),
        "failed": campaign.get("failed", 0),
        "errors": campaign.get("errors") or [],
        "started_at": campaign.get("started_at"),
        "finished_at": campaign.get("finished_at") or now(),
    }).inserted_id


def for_account(db, account_id, *, limit: int = 50) -> list[dict[str, Any]]:
    """Lo que ha salido de esta cuenta, lo más reciente primero."""
    return list(db.campaign_runs.find({"account_id": account_id})
                .sort("finished_at", -1).limit(limit))


def for_campaign(db, account_id, campaign_id, *,
                 limit: int = 50) -> list[dict[str, Any]]:
    return list(db.campaign_runs
                .find({"account_id": account_id, "campaign_id": campaign_id})
                .sort("finished_at", -1).limit(limit))


def times(db, account_id, campaign_id) -> int:
    """Cuántas veces ha salido esa campaña."""
    return db.campaign_runs.count_documents({"account_id": account_id,
                                             "campaign_id": campaign_id})


def times_by_campaign(db, account_id) -> dict[Any, dict[str, Any]]:
    """Cuántas veces salió cada campaña y cuándo fue la última.

    En una consulta y no una por fila: la pantalla las enseña todas juntas, y
    preguntar por cada una es lo que convierte una lista larga en cincuenta
    viajes a la base.
    """
    rows = db.campaign_runs.aggregate([
        {"$match": {"account_id": account_id}},
        {"$group": {"_id": "$campaign_id", "times": {"$sum": 1},
                    "last": {"$max": "$finished_at"}}},
    ])
    return {row["_id"]: {"times": row["times"], "last": row["last"]}
            for row in rows}
