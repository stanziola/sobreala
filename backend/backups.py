"""La tarea de los respaldos: respalda a las cuentas a las que les toca.

Corre como **servicio Cron de Railway**, cada hora (`0 * * * *`), con el mismo
código y las mismas variables que el panel:

    python backend/backups.py

Cada cliente elige cada cuánto (Configuración → Respaldos); esto solo mira a
quién le toca y lo hace. Una cuenta que falla no frena a las demás, y el
resultado queda en el registro del servicio. Sin `S3_BUCKET` no hace nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from db import get_db               # noqa: E402
from services import backups, storage  # noqa: E402


def main() -> int:
    if not storage.ready():
        print("Sin S3_BUCKET: no hay dónde guardar los respaldos.")
        return 0
    app = create_app()
    # Una petición de mentira: los respaldos arman las plantillas con lo mismo
    # que el panel, que necesita saber su propia dirección.
    with app.test_request_context(base_url=Config.APP_BASE_URL):
        result = backups.run_due(get_db())
    print(f"Respaldos: {result['made']} hechos, {result['failed']} con error.")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
