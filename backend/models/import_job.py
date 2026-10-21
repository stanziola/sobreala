"""The imports collection: one document per file somebody uploaded.

It exists for three reasons, and only one of them is the screen. It makes the
limits checkable —ten a day, one at a time— it answers "what happened to the
file I uploaded on Tuesday" months later, and it is what lets this move to a
process outside the request without touching a single stored document: the work
changes place, the record does not.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

RUNNING = "running"
DONE = "done"
# The account reached its contact limit. Not a failure: what got in stays in,
# which is what docs/pricing.md promises.
STOPPED = "stopped"
FAILED = "failed"


def now() -> datetime:
    return datetime.now(timezone.utc)


def start(db, account_id, *, filename: str, tags: list[str],
          consent: dict[str, Any], job_id=None) -> Any:
    """`job_id` is chosen by the caller when its contacts carry it in their
    `consent.import_id` (October 2026)."""
    doc = {
        **({"_id": job_id} if job_id is not None else {}),
        "account_id": account_id,
        "filename": filename[:200],
        "tags": tags,
        "consent": consent,
        "status": RUNNING,
        "read": 0, "added": 0, "updated": 0, "invalid": 0, "suppressed": 0,
        "error": "",
        "created_at": now(),
        "finished_at": None,
    }
    return db.imports.insert_one(doc).inserted_id


def finish(db, job_id, *, status: str, counts: dict[str, int],
           error: str = "") -> None:
    db.imports.update_one({"_id": job_id}, {"$set": {
        "status": status, "error": error[:300],
        "finished_at": now(), **counts,
    }})


def running(db, account_id) -> dict[str, Any] | None:
    """The import this account has in flight, if any.

    Anything still marked running after an hour is a process that died halfway
    —a restart, a crash— and must not block the account forever.
    """
    return db.imports.find_one({
        "account_id": account_id, "status": RUNNING,
        "created_at": {"$gt": now() - timedelta(hours=1)},
    })


def today(db, account_id) -> int:
    """How many were started in the last 24 hours, whatever their outcome."""
    return db.imports.count_documents({
        "account_id": account_id,
        "created_at": {"$gt": now() - timedelta(days=1)},
    })


def for_account(db, account_id, *, limit: int = 10) -> list[dict[str, Any]]:
    return list(db.imports.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))
