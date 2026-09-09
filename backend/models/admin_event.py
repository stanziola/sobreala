"""The admin_events collection: what an administrator did, and why.

Approving, suspending and changing a plan are decisions somebody made about
somebody else's business. Months later the only honest answer to "por qué me
suspendieron la cuenta" is the reason that was written at the time, so the
reason is not optional here: a change with no reason is not recorded, it is
refused by the screen before it gets this far.

No TTL, like auth_events. This is the paper trail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# What was done.
STATUS = "status"        # de un estado a otro
PLAN = "plan"            # contrató, cambió o se quedó sin plan
ROLE = "role"            # se dio o se quitó el rol de administrador


def now() -> datetime:
    return datetime.now(timezone.utc)


def record(db, *, kind: str, admin_id: Any, account_id: Any, before: Any,
           after: Any, reason: str) -> None:
    """Write one decision down. Never raises.

    Same rule as log_auth: the trail is worth having, but not at the price of
    turning an approval that already happened into an error page.
    """
    try:
        db.admin_events.insert_one({
            "kind": kind,
            "admin_id": admin_id,
            "account_id": account_id,
            "before": before,
            "after": after,
            "reason": reason.strip()[:300],
            "created_at": now(),
        })
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [admin_events] no se pudo registrar la decision: "
              f"{type(exc).__name__}: {str(exc)[:160]}", flush=True)


def for_account(db, account_id, *, limit: int = 50) -> list[dict[str, Any]]:
    return list(db.admin_events.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))


def latest(db, *, limit: int = 30) -> list[dict[str, Any]]:
    return list(db.admin_events.find().sort("created_at", -1).limit(limit))
