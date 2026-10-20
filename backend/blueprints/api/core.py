"""La puerta de la API pública (octubre de 2026).

Todo lo que entra por `/api/v1` pasa por aquí antes de llegar a una ruta, y
cada regla está en un solo sitio para que una ruta nueva la herede sin que
nadie se acuerde de ponérsela:

  * **Solo `Authorization: Bearer <llave>`.** La sesión del navegador no cuenta:
    bajo `/api/` la aplicación usa una sesión vacía (`app.py`), y aquí además se
    deja `current_account()` en None, así nada de otra cuenta se cuela por una
    galleta. Sin galletas no hace falta CSRF.
  * **Denegado por omisión.** Cada ruta se declara con `api_route(...,
    scope=...)`; la que no está en `ROUTES` no tiene permiso que la abra. Una
    llave de prueba solo pasa por lo que puede hacer una de prueba.
  * **Errores en JSON y en español**, con su código, y el mismo 401 para una
    llave mala, vencida o revocada.
  * **Límites** por cuenta y por clase de ruta, y por IP para las llaves malas
    (sin frenar nunca a una llave buena que comparta esa IP).

Lo que no sale bien y llevaba una llave buena queda en `api_log`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, g, jsonify, make_response, request

from db import get_db
from i18n import t
from models import account as accounts
from models import api_key as api_keys
from models import api_log
from models import idempotency
from services import api_auth
from services.security import rate_state

bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Lo que cada ruta declara: su regla, sus métodos, su permiso y sus límites. La
# prueba de la documentación lo compara con `api_spec.py`.
ROUTES: dict[str, dict[str, Any]] = {}

ANY = "any"        # cualquier llave buena
PUBLIC = "public"  # sin llave: solo la descripción

JSON_MAX = 1024 * 1024
UPLOAD_MAX = 6 * 1024 * 1024

# (cuántas, en cuántos segundos)
ACCOUNT_LIMIT = (600, 60)
LIMITS = {
    "emails": (120, 60),
    "contacts": (30, 60),
    "templates": (5, 60),
    "images": (20, 60),
    "stats": (30, 60),
}
BAD_KEYS = (20, 600)

PAGE_DEFAULT = 25
PAGE_MAX = 100


class ApiError(Exception):
    """Una respuesta de error de la API. Se lanza desde cualquier sitio y la
    convierte `error_response()`."""

    def __init__(self, code: str, status: int, *, fields: dict | None = None,
                 extra: dict | None = None, retry_after: int | None = None, **fmt):
        super().__init__(code)
        self.code = code
        self.status = status
        self.fields = fields
        self.extra = extra
        self.retry_after = retry_after
        self.fmt = fmt


def fail(code: str, status: int, **kwargs):
    raise ApiError(code, status, **kwargs)


def error_response(code: str, status: int, *, fields: dict | None = None,
                   extra: dict | None = None, retry_after: int | None = None,
                   **fmt):
    """El cuerpo de un error: código, frase en español y el id de la petición."""
    g.api_error_code = code
    error: dict[str, Any] = {"code": code, "message": t("api_error_" + code, **fmt),
                             "request_id": g.get("api_request_id", "")}
    if fields:
        error["fields"] = fields
    if extra:
        error.update(extra)
    response = jsonify({"error": error})
    response.status_code = status
    if retry_after:
        response.headers["Retry-After"] = str(int(retry_after))
    if status == 401:
        response.headers["WWW-Authenticate"] = 'Bearer realm="sobreala"'
    return response


@bp.errorhandler(ApiError)
def _api_error(exc: ApiError):
    return error_response(exc.code, exc.status, fields=exc.fields, extra=exc.extra,
                          retry_after=exc.retry_after, **exc.fmt)


def ok(data: Any, status: int = 200):
    response = jsonify(data)
    response.status_code = status
    return response


# ------------------------------------------------------------ las rutas

def api_route(rule: str, *, methods=("GET",), scope: str, limit: str = "",
              max_bytes: int = JSON_MAX, idempotent: bool = False):
    """Declarar una ruta de la API con su permiso. Sin esto no responde."""
    def wrap(view):
        endpoint = view.__name__

        @wraps(view)
        def run(**kwargs):
            if idempotent:
                return _idempotent(view, kwargs)
            return view(**kwargs)

        bp.add_url_rule(rule, endpoint, run, methods=list(methods))
        ROUTES[f"{bp.name}.{endpoint}"] = {
            "rule": bp.url_prefix + rule, "methods": tuple(methods), "scope": scope,
            "limit": limit, "max_bytes": max_bytes, "idempotent": idempotent}
        return view
    return wrap


def account() -> dict[str, Any]:
    """La empresa de la llave que llama."""
    return g.api_account


def key() -> dict[str, Any]:
    return g.api_key


def is_test() -> bool:
    return (g.get("api_key") or {}).get("mode") == api_keys.TEST


@bp.before_request
def gate():
    # Ninguna sesión: lo que pregunte por la cuenta del navegador no encuentra
    # nada (`current_account()` lee primero esto).
    g._account = None
    g._workspace = None
    g.api_key = None
    g.api_account = None
    g.api_request_id = "req_" + secrets.token_hex(8)
    g.api_started = time.monotonic()
    meta = ROUTES.get(request.endpoint or "")
    if meta is None:
        return None
    request.max_content_length = meta["max_bytes"]
    db = get_db()

    # Una llave en la dirección ya quedó escrita en registros ajenos (el de
    # gunicorn, el de Cloudflare): no vuelve a servir.
    for value in request.args.values():
        if api_keys.looks_like(value):
            exposed = api_keys.find(db, value)
            if exposed is not None:
                _revoke_exposed(db, exposed)
            return error_response("key_in_url", 400)

    if meta["scope"] == PUBLIC:
        return None

    ip = api_auth.caller_ip()
    g.api_ip = ip
    raw = api_auth.bearer()
    found = api_keys.find(db, raw) if raw else None
    if found is None:
        allowed, _, reset = rate_state(db, f"api:badkey:{api_auth.bucket(ip)}", *BAD_KEYS)
        if not allowed:
            return error_response("rate_limited", 429, retry_after=reset)
        return error_response("unauthorized", 401)

    company = accounts.by_id(db, found["account_id"])
    if (company is None or accounts.is_admin(company) or accounts.is_member(company)):
        return error_response("unauthorized", 401)
    g.api_key = found
    g.api_account = company
    if not api_auth.ip_allowed(ip, found.get("ips") or []):
        return error_response("ip_not_allowed", 403)
    if accounts.is_suspended(company):
        return error_response("account_suspended", 403)
    if not accounts.is_open(company):
        return error_response("account_closed", 403)

    scope = meta["scope"]
    if scope != ANY:
        if found.get("mode") == api_keys.TEST and scope not in api_keys.TEST_SCOPES:
            return error_response("test_key_cannot", 403)
        if scope not in (found.get("scopes") or []):
            return error_response("missing_scope", 403, scope=scope)

    allowed, _, reset = rate_state(db, f"api:account:{company['_id']}", *ACCOUNT_LIMIT)
    if not allowed:
        return error_response("rate_limited", 429, retry_after=reset)
    if meta["limit"]:
        allowed, _, reset = rate_state(db, f"api:{meta['limit']}:{company['_id']}",
                                       *LIMITS[meta["limit"]])
        if not allowed:
            return error_response("rate_limited", 429, retry_after=reset)
    api_keys.touch(db, found, ip)
    return None


@bp.after_request
def after(response):
    response.headers["X-Request-Id"] = g.get("api_request_id", "")
    found = g.get("api_key")
    if found is not None and response.status_code >= 400:
        api_log.record(get_db(), account_id=found["account_id"], key_id=found["_id"],
                       method=request.method, path=request.path,
                       status=response.status_code,
                       ms=int((time.monotonic() - g.get("api_started", time.monotonic()))
                              * 1000),
                       ip=g.get("api_ip", ""), code=g.get("api_error_code", ""),
                       request_id=g.get("api_request_id", ""))
    return response


def _revoke_exposed(db, exposed: dict[str, Any]) -> None:
    """Revocar una llave que llegó en la dirección, y decírselo al dueño."""
    from services import notices

    if api_keys.revoke(db, exposed["account_id"], exposed["_id"],
                       reason=t("api_key_exposed_reason")):
        owner = accounts.by_id(db, exposed["account_id"])
        if owner is not None:
            notices.api_key_exposed(owner, name=exposed.get("name", ""))


def json_error_for(status: int):
    """Los errores que no pasan por una ruta de la API (no existe, método, muy
    grande, base caída, error nuestro), en JSON. Lo llama `app.py`."""
    if not g.get("api_request_id"):
        g.api_request_id = "req_" + secrets.token_hex(8)
    code = {404: "not_found", 405: "method_not_allowed", 413: "too_large",
            503: "unavailable"}.get(status, "internal_error")
    response = error_response(code, status,
                              retry_after=5 if status == 503 else None)
    response.headers["X-Request-Id"] = g.api_request_id
    return response


# ------------------------------------------------------------ idempotencia

IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,%d}$" % idempotency.KEY_MAX)


def _idempotent(view, kwargs):
    """Correr la ruta una sola vez por `Idempotency-Key` (ver
    `models/idempotency.py`). Con una llave de prueba no se guarda nada."""
    wanted = request.headers.get("Idempotency-Key")
    if wanted is None or is_test():
        return view(**kwargs)
    if not IDEMPOTENCY_KEY.match(wanted):
        fail("bad_idempotency_key", 400)
    db = get_db()
    body_hash = hashlib.sha256(request.get_data(cache=True)).hexdigest()
    state, record = idempotency.begin(
        db, account_id=account()["_id"], key_id=key()["_id"], method=request.method,
        path=request.path, key=wanted, body_hash=body_hash)
    if state == idempotency.REPLAY:
        response = ok(record.get("body"), record["status"])
        response.headers["Idempotent-Replayed"] = "true"
        return response
    if state == idempotency.MISMATCH:
        fail("idempotency_mismatch", 422)
    if state == idempotency.BUSY or record is None:
        fail("idempotency_busy", 409)
    try:
        response = make_response(view(**kwargs))
    except ApiError as exc:
        response = error_response(exc.code, exc.status, fields=exc.fields,
                                  extra=exc.extra, retry_after=exc.retry_after,
                                  **exc.fmt)
    except Exception:
        idempotency.drop(db, record["_id"])
        raise
    if response.status_code >= 500 or response.status_code == 429:
        idempotency.drop(db, record["_id"])
        return response
    body = response.get_json(silent=True)
    if len(response.get_data()) > idempotency.BODY_MAX and isinstance(body, dict):
        # Lo esencial: lo que no es una lista ni un objeto (el id, el estado,
        # los conteos), sin el detalle de cada fila.
        body = {name: value for name, value in body.items()
                if not isinstance(value, (list, dict))}
    idempotency.finish(db, record["_id"], status=response.status_code, body=body)
    return response


# ------------------------------------------------------------ el cuerpo

def body(allowed, required=()) -> dict[str, Any]:
    """El cuerpo JSON: un objeto, sin campos que la ruta no conozca."""
    if request.mimetype != "application/json":
        fail("unsupported_media_type", 415)
    try:
        data = json.loads(request.get_data(cache=True) or b"null")
    except (ValueError, RecursionError, UnicodeDecodeError):
        fail("bad_json", 400)
    if not isinstance(data, dict):
        fail("bad_json", 400)
    errors = {name: t("api_field_unknown") for name in data if name not in allowed}
    errors.update({name: t("api_field_required") for name in required
                   if name not in data or data[name] in (None, "")})
    if errors:
        fail("validation_failed", 422, fields=errors)
    return data


class Fields:
    """Leer los campos de un cuerpo con su tipo, juntando todos los errores para
    decirlos de una vez. Un valor de otro tipo (un objeto donde va un texto) es
    un error y nunca llega a una consulta."""

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.errors: dict[str, str] = {}

    def has(self, name: str) -> bool:
        return name in self.data

    def text(self, name: str, *, max_len: int, required: bool = False,
             default: str = "") -> str:
        value = self.data.get(name)
        if value is None:
            if required:
                self.errors[name] = t("api_field_required")
            return default
        if not isinstance(value, str):
            self.errors[name] = t("api_field_text")
            return default
        if len(value) > max_len:
            self.errors[name] = t("api_field_long", n=max_len)
            return default
        if required and not value.strip():
            self.errors[name] = t("api_field_required")
        return value

    def boolean(self, name: str, default: bool = False) -> bool:
        value = self.data.get(name, default)
        if not isinstance(value, bool):
            self.errors[name] = t("api_field_bool")
            return default
        return value

    def integer(self, name: str, *, low: int, high: int, default: int | None = None):
        value = self.data.get(name, default)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            self.errors[name] = t("api_field_int", low=low, high=high)
            return default
        return value

    def strings(self, name: str, *, max_items: int, max_len: int) -> list[str] | None:
        value = self.data.get(name)
        if value is None:
            return None
        if (not isinstance(value, list) or len(value) > max_items
                or not all(isinstance(one, str) and len(one) <= max_len for one in value)):
            self.errors[name] = t("api_field_strings", n=max_items)
            return None
        return value

    def object_id(self, name: str, *, required: bool = False, nullable: bool = False):
        """Un id de 24 caracteres. Con `nullable`, null es «ninguno» y se
        devuelve `None` distinguible de «no vino» con `has()`."""
        value = self.data.get(name)
        if value is None:
            if required and not nullable:
                self.errors[name] = t("api_field_required")
            return None
        if not isinstance(value, str):
            self.errors[name] = t("api_field_id")
            return None
        found = parse_id(value)
        if found is None:
            self.errors[name] = t("api_field_id")
        return found

    def check(self) -> None:
        if self.errors:
            fail("validation_failed", 422, fields=self.errors)


def parse_id(raw: str | None):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9a-f]{24}", raw):
        return None
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def path_id(raw: str):
    """Un id de la ruta. Otro formato es lo mismo que uno de otra cuenta: 404."""
    found = parse_id(raw)
    if found is None:
        fail("not_found", 404)
    return found


# ------------------------------------------------------------ paginar

def page_limit() -> int:
    raw = request.args.get("limit", "")
    if not raw:
        return PAGE_DEFAULT
    if not raw.isdigit() or not 1 <= int(raw) <= PAGE_MAX:
        fail("validation_failed", 422,
             fields={"limit": t("api_field_int", low=1, high=PAGE_MAX)})
    return int(raw)


def page_cursor():
    """El cursor de la página: un ObjectId en base64, o None. Otra cosa, 400."""
    raw = request.args.get("cursor", "")
    if not raw:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{16}", raw):
        fail("bad_cursor", 400)
    try:
        return ObjectId(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except (ValueError, InvalidId, TypeError):
        fail("bad_cursor", 400)


def cursor_of(one_id) -> str:
    return base64.urlsafe_b64encode(one_id.binary).decode("ascii").rstrip("=")


def paged(rows: list, limit: int, shape) -> dict[str, Any]:
    """`rows` trae una de más: si llegó, hay otra página."""
    more = len(rows) > limit
    rows = rows[:limit]
    return {"data": [shape(one) for one in rows],
            "next_cursor": cursor_of(rows[-1]["_id"]) if more and rows else None}


# ------------------------------------------------------------ cómo se escribe

def iso(when: datetime | None) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def when_of(raw, name: str, fields: Fields) -> datetime | None:
    """Una fecha y hora ISO 8601 **con zona**; sin zona es ambigua y se rechaza."""
    if raw is None:
        return None
    if not isinstance(raw, str) or len(raw) > 40:
        fields.errors[name] = t("api_field_when")
        return None
    try:
        found = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        fields.errors[name] = t("api_field_when")
        return None
    if found.tzinfo is None:
        fields.errors[name] = t("api_field_when")
        return None
    return found.astimezone(timezone.utc)


def key_shape(found: dict[str, Any]) -> dict[str, Any]:
    """Cómo se enseña una llave: nunca su valor."""
    return {"id": str(found["_id"]), "name": found.get("name", ""),
            "mode": found.get("mode"), "scopes": list(found.get("scopes") or []),
            "prefix": found.get("prefix", ""), "last4": found.get("last4", ""),
            "expires_at": iso(found.get("expires_at")),
            "created_at": iso(found.get("created_at"))}
