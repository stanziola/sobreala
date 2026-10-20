"""El registro de la API: las peticiones que fallaron (octubre de 2026).

Es lo que enseña API → Registro, para que quien conecta su sistema vea por qué
algo no entró. **Solo lo que falló y con una llave buena**: una fila por cada
petición que salió bien llenaría la base en días (600 por minuto por cuenta), y
una por cada llave mala dejaría que cualquiera la llenara desde fuera. Lo que
salió bien se ve en el último uso de cada llave.

Nunca el cuerpo ni la llave: solo qué se pidió, cómo terminó y desde dónde. Se
borra solo a los `KEEP_DAYS` días, y cada cuenta escribe como mucho
`DAILY_MAX` al día.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

KEEP_DAYS = 7
DAILY_MAX = 1000
PATH_MAX = 200


def now() -> datetime:
    return datetime.now(timezone.utc)


def record(db, *, account_id, key_id, method: str, path: str, status: int,
           ms: int, ip: str, code: str, request_id: str) -> None:
    """Anotar una petición que falló. Nunca lanza: el registro no puede tumbar
    la respuesta que está contando."""
    from services.security import rate_state

    try:
        day = now().strftime("%Y-%m-%d")
        allowed, _, _ = rate_state(db, f"apilog:{account_id}:{day}", DAILY_MAX, 86400)
        if not allowed:
            return
        db.api_log.insert_one({
            "account_id": account_id, "key_id": key_id,
            "method": method, "path": path[:PATH_MAX], "status": int(status),
            "ms": int(ms), "ip": ip, "code": code, "request_id": request_id,
            "created_at": now(),
        })
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [api_log] no se pudo anotar: {type(exc).__name__}: {str(exc)[:160]}",
              flush=True)


def recent(db, account_id, *, key_id=None, limit: int = 100) -> list[dict[str, Any]]:
    """Lo último que falló, lo más nuevo primero, de una llave o de todas."""
    query: dict[str, Any] = {"account_id": account_id}
    if key_id is not None:
        query["key_id"] = key_id
    return list(db.api_log.find(query).sort("created_at", -1).limit(limit))
