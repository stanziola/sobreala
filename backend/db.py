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

import threading

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure

from config import Config

# Five seconds instead of the thirty-second default: a network hiccup should
# fail fast and say so, not leave the request hanging.
SERVER_SELECTION_TIMEOUT_MS = 5000

_client: MongoClient | None = None
_indexes_ready = False
# Con hilos (octubre de 2026), dos peticiones a la vez podían crear dos
# clientes, cada uno con su propio grupo de conexiones.
_client_lock = threading.Lock()


def get_client() -> MongoClient:
    global _client
    if _client is None:
        with _client_lock:
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
    # Los usuarios que crea una empresa: su documento es una cuenta más, con el
    # dueño apuntado aquí. Es lo que lista su Configuración y lo que la tabla de
    # administración deja fuera.
    db.accounts.create_index([("owner_id", ASCENDING)], name="by_owner")
    # make_admin.py --lista pregunta justamente por esto.
    db.accounts.create_index([("role", ASCENDING)], name="by_role")
    # Who a campaign leaves from: one handle on the sending domain per account,
    # and domains of their own that no other account has. Partial, so accounts
    # without them don't collide on a missing value.
    db.accounts.create_index([("sender.handle", ASCENDING)], unique=True,
                             name="uniq_sender_handle",
                             partialFilterExpression={"sender.handle": {"$type": "string"}})
    # Hasta octubre de 2026 había un solo dominio por cuenta (`sender.domain`)
    # y un solo «Responder a»: se pasan a las listas una vez, y el índice del
    # dominio de antes se borra aquí y no a mano, para que un despliegue se
    # arregle solo. Uno por dominio, aunque esté en una lista: el índice es
    # de varias claves y no deja que otra cuenta lo repita.
    from models import account as accounts

    accounts.migrate_sender(db)
    try:
        db.accounts.drop_index("uniq_sender_domain")
    except OperationFailure:
        pass  # never existed, or already gone
    db.accounts.create_index([("sender.domains.name", ASCENDING)], unique=True,
                             name="uniq_sender_domains",
                             partialFilterExpression={"sender.domains.name": {"$type": "string"}})
    # Las cuentas de antes de que el rol existiera. Una sola vez: a partir de
    # ahí no encuentra ninguna. Va aquí porque es la única función que corre
    # sola al arrancar y ya es la que deja la base como tiene que estar.
    db.accounts.update_many({"role": {"$exists": False}},
                            {"$set": {"role": "client"}})
    # Las etiquetas que ya estaban puestas en contactos, pasadas al registro de
    # su cuenta. Una vez: después ninguna cuenta cae en el filtro.
    for account in db.accounts.find({"contact_tags": {"$exists": False}}, {"_id": 1}):
        db.accounts.update_one(
            {"_id": account["_id"]},
            {"$set": {"contact_tags": sorted(
                db.contacts.distinct("tags", {"account_id": account["_id"]}))}})
    # Registrations that never get confirmed. confirm_email() removes the field,
    # so a finished account is never a candidate.
    db.accounts.create_index([("purge_at", ASCENDING)], expireAfterSeconds=0,
                             name="ttl_purge_at")

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

    # One document per signed-in device. Looked up by the hash of what the
    # cookie carries, listed by account, and swept by Mongo when it expires.
    db.sessions.create_index([("token_hash", ASCENDING)], unique=True,
                             name="uniq_session_token")
    db.sessions.create_index([("account_id", ASCENDING), ("last_seen_at", DESCENDING)],
                             name="by_account_last_seen")
    db.sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                             name="ttl_expires_at")

    db.rate_limits.create_index([("key", ASCENDING)], name="by_key")
    db.rate_limits.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                                name="ttl_expires_at")

    # Every system email that was attempted, body included, so a confirmation
    # that never arrived can be read back exactly as it left.
    db.mail_log.create_index([("to_normalized", ASCENDING)], name="by_to")
    # Por donde lo busca el aviso de SES, que trae el identificador del mensaje
    # y nada más.
    db.mail_log.create_index([("provider_id", ASCENDING)], name="by_provider")
    db.mail_log.create_index([("created_at", DESCENDING)], name="by_created_at")

    # Audit trail of registration and sign-in attempts. No TTL here on purpose,
    # unlike the two collections above: the history is kept until someone
    # decides otherwise, because that is what an abuse report is investigated
    # with weeks after the fact.
    db.auth_events.create_index([("email_normalized", ASCENDING)], name="by_email")
    db.auth_events.create_index([("ip", ASCENDING)], name="by_ip")
    db.auth_events.create_index([("created_at", DESCENDING)], name="by_created_at")

    # One document per address per account, and the unique index is what says
    # so: rule 5 of CLAUDE.md is enforced by the database, not by remembering
    # to check. Every import is an upsert against exactly this pair.
    db.contacts.create_index([("account_id", ASCENDING),
                              ("email_normalized", ASCENDING)],
                             unique=True, name="uniq_account_email")
    # Lists are tags on the document, so filtering by list is a query on this.
    db.contacts.create_index([("account_id", ASCENDING), ("tags", ASCENDING)],
                             name="by_account_tag")
    db.contacts.create_index([("account_id", ASCENDING), ("created_at", DESCENDING)],
                             name="by_account_created")

    # Addresses an account may never write to again. Scoped to the account and
    # never global: a bajada in one account says nothing about the others.
    db.suppressions.create_index([("account_id", ASCENDING),
                                  ("email_normalized", ASCENDING)],
                                 unique=True, name="uniq_account_email")
    db.suppressions.create_index([("account_id", ASCENDING), ("reason", ASCENDING)],
                                 name="by_account_reason")

    # One document per uploaded file. No TTL: it is the answer to "what
    # happened to the list I uploaded in March".
    db.imports.create_index([("account_id", ASCENDING), ("created_at", DESCENDING)],
                            name="by_account_created")
    db.imports.create_index([("account_id", ASCENDING), ("status", ASCENDING)],
                            name="by_account_status")

    # Lo que un administrador decidió sobre una cuenta, con su motivo. Sin TTL,
    # como auth_events: es el papel que se lee cuando alguien reclame.
    db.admin_events.create_index([("account_id", ASCENDING),
                                  ("created_at", DESCENDING)],
                                 name="by_account_created")
    db.admin_events.create_index([("created_at", DESCENDING)],
                                 name="by_created_at")

    # Un documento por intento de pago, escrito antes de mandar a nadie a
    # PayPal. Sin TTL: es la respuesta a «¿este cliente pagó?» meses después.
    db.payments.create_index([("account_id", ASCENDING),
                              ("created_at", DESCENDING)],
                             name="by_account_created")
    db.payments.create_index([("order_id", ASCENDING)], name="by_order")
    # Un cobro de la suscripción de PayPal se anota una sola vez: su id es único.
    # Parcial, porque los pagos sueltos no lo llevan.
    db.payments.create_index([("transaction_id", ASCENDING)], unique=True,
                             partialFilterExpression={"transaction_id": {"$type": "string"}},
                             name="by_transaction")
    db.paypal_plans.create_index([("key", ASCENDING)], unique=True, name="by_key")
    # El archivo de un correo individual: Atlas lo borra solo a los 30 días
    # (`models/download.py`).
    db.downloads.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                              name="ttl_expires")

    # Un documento por evento de SES. Es lo que más crece: unos tres por correo
    # enviado. Todavía no lo llena nadie, pero el índice va puesto desde ya para
    # que el primer evento no llegue a una colección sin ordenar.
    db.events.create_index([("account_id", ASCENDING),
                            ("created_at", DESCENDING)],
                           name="by_account_created")
    # Las cifras de cada envío en «Campañas enviadas».
    db.events.create_index([("account_id", ASCENDING), ("run_id", ASCENDING),
                            ("kind", ASCENDING)], name="by_account_run_kind")
    db.events.create_index([("account_id", ASCENDING), ("kind", ASCENDING),
                            ("created_at", DESCENDING)],
                           name="by_account_kind_created")
    # Lo de todas las cuentas juntas, en administración: la salud de la cuenta
    # de Amazon en Clientes, y lo último que pasó en Eventos.
    db.events.create_index([("kind", ASCENDING), ("created_at", DESCENDING)],
                           name="by_kind_created")
    # Uno por envío, persona y tipo (`events.record()`), y el detalle de un
    # envío, que agrupa por persona.
    db.events.create_index([("account_id", ASCENDING), ("run_id", ASCENDING),
                            ("email_normalized", ASCENDING), ("kind", ASCENDING)],
                           name="by_account_run_email_kind")

    # El HTML que sube cada cliente. Sin TTL: una pieza aprobada es lo que hay
    # que poder volver a mirar cuando alguien pregunte qué se envió.
    db.designs.create_index([("account_id", ASCENDING),
                             ("created_at", DESCENDING)],
                            name="by_account_created")
    # La cola de revisión del administrador: lo que espera, primero lo viejo.
    db.designs.create_index([("status", ASCENDING), ("created_at", ASCENDING)],
                            name="by_status_created")

    # Una campaña por envío. Se listan por cuenta y por cuándo salen, que es
    # como las enseña la pantalla y como las va a buscar el proceso en segundo
    # plano el día que exista: «las que ya les tocaba».
    db.campaigns.create_index([("account_id", ASCENDING),
                               ("scheduled_at", DESCENDING)],
                              name="by_account_when")
    db.campaigns.create_index([("status", ASCENDING), ("scheduled_at", ASCENDING)],
                              name="by_status_when")

    # Un documento cada vez que una campaña sale. Se listan por cuenta y por
    # cuándo terminaron, que es como los enseña la pantalla, y por campaña para
    # decir cuántas veces salió cada una.
    db.campaign_runs.create_index([("account_id", ASCENDING),
                                   ("finished_at", DESCENDING)],
                                  name="by_account_finished")
    db.campaign_runs.create_index([("account_id", ASCENDING),
                                   ("campaign_id", ASCENDING)],
                                  name="by_account_campaign")

    # Las imágenes que los clientes ponen en sus plantillas. Se buscan por su
    # nombre, que es la dirección con la que las pide el lector de correo de
    # quien recibió la campaña, y ese nombre no se puede repetir.
    db.images.create_index([("name", ASCENDING)], unique=True, name="by_name")
    db.images.create_index([("account_id", ASCENDING)], name="by_account")
    # Una imagen que salió en un envío y que ya no nombra ninguna pieza: se
    # borra sola doce meses después del último envío (`images.remove()`). Las
    # que no llevan `expires_at` no vencen nunca.
    db.images.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                           name="ttl_expires_at")

    # Los documentos de las verificaciones: uno por cuenta y por clase, y se
    # borran al verificarse o rechazarse (models/verification_doc.py).
    db.verification_docs.create_index([("account_id", ASCENDING), ("kind", ASCENDING)],
                                      unique=True, name="by_account_kind")

    # La API (octubre de 2026). Una llave se busca por el hash de lo que llega
    # en `Authorization`, y ese hash no se repite.
    db.api_keys.create_index([("token_hash", ASCENDING)], unique=True,
                             name="uniq_token_hash")
    db.api_keys.create_index([("account_id", ASCENDING), ("created_at", DESCENDING)],
                             name="by_account_created")
    # Lo que falló, que Mongo borra solo a la semana (`models/api_log.py`).
    from models import api_log

    db.api_log.create_index([("account_id", ASCENDING), ("created_at", DESCENDING)],
                            name="by_account_created")
    db.api_log.create_index([("created_at", ASCENDING)],
                            expireAfterSeconds=api_log.KEEP_DAYS * 86400,
                            name="ttl_created_at")
    # Una respuesta por cuenta, llave, método, ruta e `Idempotency-Key`; se van
    # solas al día (`models/idempotency.py`).
    db.api_idempotency.create_index([("account_id", ASCENDING), ("key_id", ASCENDING),
                                     ("method", ASCENDING), ("path", ASCENDING),
                                     ("key", ASCENDING)],
                                    unique=True, name="uniq_request")
    db.api_idempotency.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                                    name="ttl_expires_at")
    # La lista de contactos y la de supresiones, por la API, se recorren por
    # `_id`, con cursor.
    db.contacts.create_index([("account_id", ASCENDING), ("_id", DESCENDING)],
                             name="by_account_id")
    db.suppressions.create_index([("account_id", ASCENDING), ("_id", DESCENDING)],
                                 name="by_account_id")
    # El id de su sistema (octubre de 2026): no se repite en una cuenta. Parcial,
    # porque casi ningún contacto lo tiene.
    db.contacts.create_index([("account_id", ASCENDING), ("external_id", ASCENDING)],
                             unique=True, name="uniq_account_external_id",
                             partialFilterExpression={"external_id": {"$type": "string"}})
    # Los candados cortos (`models/lock.py`): Mongo borra los vencidos.
    db.locks.create_index([("until", ASCENDING)], expireAfterSeconds=0,
                          name="ttl_until")
    # Los correos de la API (`models/message.py`): se listan por cuenta, de los
    # más nuevos; una `Idempotency-Key` tiene uno solo; se van a los 30 días.
    db.messages.create_index([("account_id", ASCENDING), ("_id", DESCENDING)],
                             name="by_account_id")
    db.messages.create_index([("account_id", ASCENDING), ("key_id", ASCENDING),
                              ("request_key", ASCENDING)],
                             unique=True, name="uniq_request_key",
                             partialFilterExpression={"request_key": {"$type": "string"}})
    db.messages.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0,
                             name="ttl_expires_at")


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
    """Whether the database answers, for the /health route.

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
