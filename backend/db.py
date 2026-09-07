"""MongoDB client and index setup.

The indexes are the real guarantees, not the application code: the unique index
on the normalised email is what makes duplicate accounts impossible even under a
race between two simultaneous registrations, and the TTL indexes are what keep
expired tokens and rate-limit counters from piling up forever.
"""

from __future__ import annotations

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from config import Config

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(Config.MONGODB_URI, tz_aware=True)
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

    # Tokens are looked up by their hash, never by the value in the link.
    db.account_tokens.create_index([("token_hash", ASCENDING)], unique=True,
                                   name="uniq_token_hash")
    db.account_tokens.create_index([("account_id", ASCENDING), ("purpose", ASCENDING)],
                                   name="by_account_purpose")
    # Mongo deletes the document once purge_at passes: expiry plus a grace
    # window, so an expired link still gets a useful message.
    db.account_tokens.create_index([("purge_at", ASCENDING)], expireAfterSeconds=0,
                                   name="ttl_purge_at")

    db.rate_limits.create_index([("key", ASCENDING)], name="by_key")
    db.rate_limits.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                                name="ttl_expires_at")
