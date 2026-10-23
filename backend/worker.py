"""El proceso en segundo plano (octubre de 2026). En Railway es un servicio
aparte del mismo repositorio, sin dominio público, con Start Command
`python backend/worker.py` y las mismas variables que el web (por referencia):
ver `docs/api.md`.

Da vueltas hasta que le piden parar: en cada una deja su latido, comprueba que
su `SECRET_KEY` es la del web y manda una tanda de cada campaña que toca
(`services/background.py`). Sin nada que mandar duerme `WORKER_TICK_SECONDS`.

**Los avisos a su sistema van en su propio hilo** (`services/webhooks.py`): un
servidor lento de un cliente tarda hasta cinco segundos por intento, y eso no
puede frenar los envíos de nadie.

Corre dentro de un contexto de petición con la dirección del panel: los avisos
y los enlaces usan `url_for` y `render_template`, que fuera de una petición
fallarían. Al recibir SIGTERM (un despliegue) termina el correo en curso, anota
hasta dónde llegó y sale; lo que falte lo retoma el siguiente.
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from db import ensure_indexes_once, get_db  # noqa: E402
from services import background, webhooks  # noqa: E402


def deliver_loop(app, stopping: dict) -> None:
    """Entregar los avisos a su sistema, en su propio hilo."""
    with app.test_request_context(base_url=Config.APP_BASE_URL):
        while not stopping["now"]:
            tried = 0
            try:
                db = get_db()
                # Con otra llave el secreto de cada aviso saldría distinto, y
                # cada firma, mala.
                if background.key_ok(db):
                    tried = webhooks.deliver_tick(db)
            except Exception as exc:  # noqa: BLE001 - el hilo sigue
                print(f"  [worker] avisos: {type(exc).__name__}: {str(exc)[:200]}",
                      flush=True)
            if not tried:
                time.sleep(1)


def main() -> None:
    app = create_app()
    stopping = {"now": False}

    def stop(*_args) -> None:
        stopping["now"] = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    name = f"worker:{socket.gethostname()}:{os.getpid()}"
    print(f"  [worker] {name} arrancó", flush=True)
    threading.Thread(target=deliver_loop, args=(app, stopping), daemon=True,
                     name="avisos").start()
    with app.test_request_context(base_url=Config.APP_BASE_URL):
        ensure_indexes_once()
        while not stopping["now"]:
            db = get_db()
            sent = 0
            try:
                key = background.key_ok(db)
                if key:
                    # El ritmo lo pone cada envío (`services/send_rate.py`).
                    sent = background.campaigns_tick(db, name, stop=lambda: stopping["now"])
                elif key is False:
                    print("  [worker] la SECRET_KEY no es la del web: no se manda "
                          "nada hasta que coincidan", flush=True)
                background.beat(db, name, key=key, sent=sent)
            except Exception as exc:  # noqa: BLE001 - la base caída no mata el bucle
                print(f"  [worker] vuelta fallida: {type(exc).__name__}: {str(exc)[:200]}",
                      flush=True)
            if not sent:
                # Dormir a pedacitos, para salir pronto si piden parar.
                for _ in range(Config.WORKER_TICK_SECONDS * 4):
                    if stopping["now"]:
                        break
                    time.sleep(0.25)
    print(f"  [worker] {name} paró", flush=True)


if __name__ == "__main__":
    main()
