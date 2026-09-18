"""Las facturas que el administrador sube a cada pago cobrado.

Las facturas se emiten a mano, fuera del panel, y aquí se guarda el PDF de cada
una colgado de su pago para que el cliente la descargue desde Facturación. Una
por pago: subir otra la reemplaza, que es lo que se hace cuando alguien se
equivocó.

Viven en la base, como las imágenes, porque son pocas y pequeñas (hasta 2 MB).
Se sirven solo a la cuenta dueña y siempre como archivo para descargar, nunca
dentro de una página del panel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson.binary import Binary

MAX_BYTES = 2 * 1024 * 1024
# Así empieza todo PDF. Se mira lo que trae dentro, no cómo se llama.
MAGIC = b"%PDF-"


def now() -> datetime:
    return datetime.now(timezone.utc)


def is_pdf(raw: bytes) -> bool:
    return raw.startswith(MAGIC)


def save(db, account_id, payment_id, *, data: bytes, uploaded_by) -> bool:
    """Guardar la factura de un pago. True si es la primera de ese pago."""
    result = db.invoices.update_one(
        {"account_id": account_id, "payment_id": payment_id},
        {"$set": {"data": Binary(data), "bytes": len(data),
                  "uploaded_by": uploaded_by, "uploaded_at": now()},
         "$setOnInsert": {"created_at": now()}},
        upsert=True)
    return result.upserted_id is not None


def paid_with_invoice(db, account_id) -> dict[Any, dict[str, Any]]:
    """Qué pagos de la cuenta ya tienen factura, sin traer los PDF."""
    return {one["payment_id"]: one for one in db.invoices.find(
        {"account_id": account_id}, {"data": 0})}


def for_payment(db, account_id, payment_id) -> dict[str, Any] | None:
    """La factura de ese pago, si es de esa cuenta. La cuenta va en la consulta."""
    return db.invoices.find_one({"account_id": account_id,
                                 "payment_id": payment_id})
