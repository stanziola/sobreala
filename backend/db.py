"""MongoDB client, index setup and a health probe.

The indexes are the real guarantees, not the application code: the unique index
on the normalised email is what makes duplicate accounts impossible even under a
race between two simultaneous registrations, and the TTL indexes are what keep
expired tokens and rate-limit counters from piling up forever.

Creating them must NOT happen while the application boots. It used to, and a
database that was briefly unreachable killed every gunicorn worker at import
time: the platform then served an opaque 502 with nothing readable anywhere.
`ensure_indexes` is now called lazily, per request, until one attempt succeeds.
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure

from config import Config

# Five seconds instead of the thirty-second default: a network hiccup should
# fail fast and say so, not leave the request hanging.
SERVER_SELECTION_TIMEOUT_MS = 5000

_client: MongoClient | None = None
_indexes_ready = False


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            Config.MONGODB_URI,
            tz_aware=True,
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        )
    return _client


def get_db(name: str | None = None) -> Database:
    return get_client()[name or Config.MONGODB_DB]


def ensure_indexes(db: Database | None = None) -> None:
    """Create every index the application relies on. Safe to call repeatedly."""
    db = db if db is not None else get_db()

    # One account per address, whatever case or spacing was typed. Same
    # normalisation rule the contacts collection will use.
    db.accounts.create_index([("email_normalized", ASCENDING)], unique=True,
                             name="uniq_email_normalized")
    db.accounts.create_index([("status", ASCENDING)], name="by_status")

    # A confirmation code is looked up by the account it belongs to, because the
    # session already says which one that is. One document per account and
    # purpose: issue() deletes the previous one before writing the new one.
    db.account_tokens.create_index([("account_id", ASCENDING), ("purpose", ASCENDING)],
                                   name="by_account_purpose")
    # Left over from the era of links: a unique index on a field no document has
    # any more, which would reject the second insert as a duplicate null. Dropped
    # here rather than by hand, so a deploy fixes itself.
    try:
        db.account_tokens.drop_index("uniq_token_hash")
    except OperationFailure:
        pass  # never existed, or already gone
    # Mongo deletes the document once purge_at passes: expiry plus a grace
    # window, so an expired link still gets a useful message.
    db.account_tokens.create_index([("purge_at", ASCENDING)], expireAfterSeconds=0,
                                   name="ttl_purge_at")

    db.rate_limits.create_index([("key", ASCENDING)], name="by_key")
    db.rate_limits.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                                name="ttl_expires_at")

    # Every system email that was attempted, body included, so a confirmation
    # that never arrived can be read back exactly as it left.
    db.mail_log.create_index([("to_normalized", ASCENDING)], name="by_to")
    db.mail_log.create_index([("created_at", DESCENDING)], name="by_created_at")

    # Audit trail of registration and sign-in attempts. No TTL here on purpose,
    # unlike the two collections above: the history is kept until someone
    # decides otherwise, because that is what an abuse report is investigated
    # with weeks after the fact.
    db.auth_events.create_index([("email_normalized", ASCENDING)], name="by_email")
    db.auth_events.create_index([("ip", ASCENDING)], name="by_ip")
    db.auth_events.create_index([("created_at", DESCENDING)], name="by_created_at")


def indexes_ready() -> bool:
    return _indexes_ready


def ensure_indexes_once() -> bool:
    """Try to create the indexes, at most once successfully.

    Returns True when they are in place. Never raises: a caller that needs the
    database will fail on its own query with a message worth reading, instead of
    the whole process dying before it can serve anything.
    """
    global _indexes_ready
    if _indexes_ready:
        return True
    try:
        ensure_indexes()
        _indexes_ready = True
    except Exception as exc:  # noqa: BLE001 - the reason is logged, not handled
        print(f"  [db] no se pudieron crear los indices: {type(exc).__name__}: "
              f"{str(exc)[:160]}", flush=True)
    return _indexes_ready


def health() -> dict:
    """Whether the database answers, for the /salud route.

    `ping` is the cheapest command there is, so this stays safe to call often.
    """
    status: dict = {"database": "down", "indexes": _indexes_ready}
    try:
        get_client().admin.command("ping")
        status["database"] = "up"
        status["name"] = Config.MONGODB_DB
    except Exception as exc:  # noqa: BLE001
        status["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return status
