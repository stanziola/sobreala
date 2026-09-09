"""Los planes y lo que cuestan, leídos de docs/pricing.md.

Las cifras no se copian aquí. `docs/pricing.md` es la fuente de verdad —el sitio
público ya lee sus tablas al construirse— y esto lee las mismas dos filas, así
que cambiar un precio ahí lo cambia en el sitio, en el panel y en lo que se le
cobra a alguien. Copiarlas sería garantizar que un día digan cosas distintas.

Se parsea una sola vez, al importar: el archivo viaja con el repositorio y no
cambia mientras el proceso vive.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

PRICING = Path(__file__).resolve().parent.parent.parent / "docs" / "pricing.md"

# Lo que se cobra. Panamá usa el dólar, y PayPal necesita saberlo.
CURRENCY = "USD"

MONTHLY = "monthly"
YEARLY = "yearly"
CYCLES = (MONTHLY, YEARLY)


def slug(name: str) -> str:
    """«Básico» → «basico», que es como se guarda el plan en la cuenta."""
    plain = unicodedata.normalize("NFKD", name)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return plain.strip().lower()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _amount(raw: str) -> Decimal | None:
    """«$1,200» → Decimal('1200'). None si esa celda no trae un precio."""
    found = re.search(r"\$\s*([\d.,]+)", raw)
    if not found:
        return None
    return Decimal(found.group(1).replace(",", ""))


def read(path: Path = PRICING) -> dict[str, dict[str, Any]]:
    """Cada plan con su nombre, sus dos precios y si el precio es público."""
    text = path.read_text(encoding="utf-8")
    names: list[str] = []
    prices: dict[str, list[Decimal | None]] = {}

    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if not names and len(cells) > 2 and not cells[0]:
            # La fila de encabezado: la primera celda va vacía y las demás son
            # los nombres de los planes.
            names = cells[1:]
        elif "Precio mensual" in cells[0]:
            prices[MONTHLY] = [_amount(c) for c in cells[1:]]
        elif "Precio anual" in cells[0]:
            prices[YEARLY] = [_amount(c) for c in cells[1:]]

    if not names or MONTHLY not in prices or YEARLY not in prices:
        raise RuntimeError(f"no encontré las filas de precios en {path}")

    # Corporativo se publica sin precio visible: «a la medida, contáctanos».
    # Eso no es un detalle de diseño, es lo que decide si se puede comprar por
    # la web o hay que hablar antes.
    hidden = {slug(name) for name in names
              if f"**{name} se publica sin precio visible**" in text}

    plans: dict[str, dict[str, Any]] = {}
    for index, name in enumerate(names):
        key = slug(name)
        plans[key] = {
            "name": name,
            MONTHLY: prices[MONTHLY][index],
            YEARLY: prices[YEARLY][index],
            "public": key not in hidden,
        }
    return plans


PLANS = read()


def price(plan: str, cycle: str) -> Decimal | None:
    """Lo que cuesta ese plan en ese ciclo, o None si no se vende así."""
    if cycle not in CYCLES:
        return None
    found = PLANS.get(plan)
    return found[cycle] if found else None


def buyable(plan: str) -> bool:
    """Si se puede contratar desde la web.

    Corporativo no: va sin precio público y se acuerda hablando. Dejarlo
    comprable pondría un precio donde el documento dice que no hay ninguno.
    """
    found = PLANS.get(plan)
    return bool(found and found["public"])


def amount(plan: str, cycle: str) -> str | None:
    """El monto tal como lo quiere PayPal: dos decimales, en texto."""
    value = price(plan, cycle)
    return f"{value:.2f}" if value is not None else None
