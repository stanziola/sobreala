"""Los respaldos de cada cliente (octubre de 2026).

Cada cliente elige cada cuánto se respaldan sus datos (`account.backup.every`:
cada día, semana o mes, o nunca) y puede bajarlos desde Configuración →
Respaldos. Un respaldo es un ZIP con lo suyo y nada de otra cuenta:

  * `contactos.csv`, el mismo de Contactos → Exportar, que se vuelve a importar;
  * `bajas.csv`, las direcciones dadas de baja, con su motivo y su fecha;
  * `plantillas/`, cada plantilla del lienzo como su ZIP, que se vuelve a cargar;
  * `campanas.csv`, cada campaña con su asunto, fechas y cifras.

Se guarda en S3 (`services/storage.py`) y se conservan los últimos `KEEP`. Los
hace `backend/backups.py`, que corre cada hora como servicio Cron de Railway:
respalda a las cuentas a las que les toca, y si una falla, sigue con las demás.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from i18n import t
from models import campaign as campaigns
from models import contact as contacts
from models import design as designs
from services import storage

EVERY = {"daily": timedelta(days=1), "weekly": timedelta(days=7),
         "monthly": timedelta(days=30)}
CHOICES = ("", "daily", "weekly", "monthly")
# Cuántos se guardan por cuenta; el más viejo se borra al hacer uno nuevo.
KEEP = 5
# La tarea corre cada hora: un respaldo diario hecho a las 10:02 tiene que
# volver a tocarle a las 10:00 del día siguiente, no a las 11:00.
SLACK = timedelta(minutes=10)


def now() -> datetime:
    return datetime.now(timezone.utc)


def setting(account: dict[str, Any] | None) -> dict[str, Any]:
    return dict((account or {}).get("backup") or {})


def set_every(db, account_id, every: str) -> None:
    db.accounts.update_one({"_id": account_id}, {"$set": {
        "backup.every": every if every in EVERY else ""}})


def due(account: dict[str, Any], moment: datetime | None = None) -> bool:
    """Si a esta cuenta le toca un respaldo ahora."""
    mine = setting(account)
    every = EVERY.get(mine.get("every", ""))
    if every is None:
        return False
    last = mine.get("last_at")
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (moment or now()) - last >= every - SLACK


def _csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    for row in rows:
        writer.writerow(row)
    return "﻿" + buffer.getvalue()


def _day(value) -> str:
    return value.date().isoformat() if isinstance(value, datetime) else ""


def build(db, account: dict[str, Any]) -> bytes:
    """El ZIP de esta cuenta. Solo lo suyo: todo se busca por su `_id`."""
    # Imported here: the blueprints import the services, not the other way.
    from blueprints.contacts.routes import csv_lines
    from blueprints.designs.routes import canvas_zip

    account_id = account["_id"]
    blocked = {d["email_normalized"] for d in
               db.suppressions.find({"account_id": account_id},
                                    {"email_normalized": 1})}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as pack:
        pack.writestr("contactos.csv", "".join(
            csv_lines(account, contacts.all_of(db, account_id), blocked)).encode("utf-8"))

        pack.writestr("bajas.csv", _csv(
            [[t("backup_col_email"), t("backup_col_reason"), t("backup_col_date")]]
            + [[one.get("email_normalized", ""), one.get("reason", ""),
                _day(one.get("created_at"))]
               for one in db.suppressions.find({"account_id": account_id})
                                         .sort("created_at", 1)]).encode("utf-8"))

        rows = [[t("backup_col_subject"), t("backup_col_created"), t("backup_col_status"),
                 t("backup_col_total"), t("backup_col_sent")]]
        for one in db.campaigns.find({"account_id": account_id}).sort("created_at", 1):
            rows.append([one.get("subject", ""), _day(one.get("created_at")),
                         one.get("status", ""), str(one.get("total", 0)),
                         str(one.get("sent", 0))])
        pack.writestr("campanas.csv", _csv(rows).encode("utf-8"))

        names: set[str] = set()
        for found in db.designs.find({"account_id": account_id,
                                      "source": designs.CANVAS}):
            name, data = canvas_zip(db, account, found)
            base, n = name, 2
            while name in names:
                name = base.replace(".zip", f" ({n}).zip")
                n += 1
            names.add(name)
            pack.writestr(f"plantillas/{name}", data, compress_type=zipfile.ZIP_STORED)
    return out.getvalue()


def make(db, account: dict[str, Any], *, auto: bool) -> dict[str, Any]:
    """Hacer un respaldo, guardarlo y quedarse con los últimos `KEEP`.

    Si algo falla, queda escrito en la cuenta (`backup.last_error`) y se
    devuelve el error a quien llama."""
    moment = now()
    key = f"respaldos/{account['_id']}/{moment:%Y%m%d-%H%M%S}.zip"
    try:
        data = build(db, account)
        storage.put(key, data, "application/zip")
    except Exception as exc:
        db.accounts.update_one({"_id": account["_id"]}, {"$set": {
            "backup.last_error": f"{type(exc).__name__}: {str(exc)[:160]}",
            "backup.last_try_at": moment}})
        raise
    doc = {"account_id": account["_id"], "key": key, "size": len(data),
           "created_at": moment, "auto": auto}
    doc["_id"] = db.backups.insert_one(doc).inserted_id
    db.accounts.update_one({"_id": account["_id"]}, {
        "$set": {"backup.last_at": moment, "backup.last_try_at": moment},
        "$unset": {"backup.last_error": ""}})
    for old in list(db.backups.find({"account_id": account["_id"]})
                    .sort("created_at", -1).skip(KEEP)):
        try:
            storage.delete(old["key"])
        except storage.StorageError:
            continue
        db.backups.delete_one({"_id": old["_id"]})
    return doc


def list_for(db, account_id) -> list[dict[str, Any]]:
    return list(db.backups.find({"account_id": account_id})
                .sort("created_at", -1).limit(KEEP))


def fetch(db, account_id, raw: str) -> tuple[str, bytes] | None:
    """El archivo de un respaldo, solo si es de esta cuenta."""
    try:
        backup_id = ObjectId(raw)
    except (InvalidId, TypeError):
        return None
    found = db.backups.find_one({"_id": backup_id, "account_id": account_id})
    if found is None:
        return None
    name = f"respaldo-sobreala-{found['created_at']:%Y-%m-%d-%H%M}.zip"
    return name, storage.get(found["key"])


def run_due(db, moment: datetime | None = None) -> dict[str, int]:
    """Lo que hace la tarea de cada hora: respaldar a quien le toca."""
    made = failed = 0
    for account in db.accounts.find({"backup.every": {"$in": list(EVERY)},
                                     "owner_id": {"$exists": False}}):
        if not due(account, moment):
            continue
        try:
            make(db, account, auto=True)
            made += 1
        except Exception as exc:  # noqa: BLE001 - one account never stops the rest
            failed += 1
            print(f"  [respaldos] {account['_id']}: {type(exc).__name__}: {str(exc)[:160]}",
                  flush=True)
    return {"made": made, "failed": failed}
