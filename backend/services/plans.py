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
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PRICING = Path(__file__).resolve().parent.parent.parent / "docs" / "pricing.md"

# Lo que se cobra. Panamá usa el dólar, y PayPal necesita saberlo.
CURRENCY = "USD"

# El ITBMS de Panamá, que los precios ya llevan dentro («Precios con ITBMS
# incluido» en /pricing). Es lo que el desglose del pago y el recibo dicen que
# incluye el total.
ITBMS = Decimal("0.07")

# Lo que dice «Ilimitadas» en la tabla. Un número y no None, para que quien
# compare no tenga que acordarse de tratar el caso aparte.
UNLIMITED = 10 ** 6

# Etiquetas de una cuenta sin plan: las mismas que el Básico, para que quien
# prueba pueda organizar un grupo y ver cómo funciona.
FREE_TAGS = 1

# Y las columnas propias del contacto, por lo mismo: quien todavía no paga
# prueba con lo que trae el Básico.
FREE_FIELDS = 1
# Y cuántas personas entran a una cuenta sin plan: el dueño, y nadie más.
FREE_USERS = 1

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


def _count(raw: str) -> int | None:
    """«4» → 4, «Ilimitadas» → UNLIMITED, «—» → None."""
    plain = raw.strip()
    if not plain or plain in ("—", "-"):
        return None
    if plain.lower().startswith("ilimitad"):
        return UNLIMITED
    digits = "".join(c for c in plain if c.isdigit())
    return int(digits) if digits else None


def read(path: Path = PRICING) -> dict[str, dict[str, Any]]:
    """Cada plan con su nombre, sus precios, sus etiquetas y si es público."""
    text = path.read_text(encoding="utf-8")
    names: list[str] = []
    prices: dict[str, list[Decimal | None]] = {}
    tags: list[int | None] = []
    fields: list[int | None] = []
    emails: list[int | None] = []
    clean: list[bool] = []
    users: list[int | None] = []
    images: list[int | None] = []

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
        elif cells[0].strip("* ") == "Etiquetas":
            tags = [_count(c) for c in cells[1:]]
        elif cells[0].strip("* ") == "Columnas propias del contacto":
            fields = [_count(c) for c in cells[1:]]
        elif cells[0].strip("* ") == "Correos por mes" and len(cells) - 1 == len(names):
            # La comprobación de ancho no es adorno: más abajo del documento hay
            # otras tablas de dos columnas, y una de ellas empieza por una
            # palabra que también aparece aquí arriba.
            emails = [_count(c) for c in cells[1:]]
        elif cells[0].strip("* ") == "Correos sin marca de agua":
            clean = [c.strip() == "✅" for c in cells[1:]]
        elif cells[0].strip("* ") == "Usuarios" and len(cells) - 1 == len(names):
            users = [_count(c) for c in cells[1:]]
        elif cells[0].strip("* ") == "Imágenes guardadas" and len(cells) - 1 == len(names):
            images = [_count(c) for c in cells[1:]]

    if not names or MONTHLY not in prices or YEARLY not in prices:
        raise RuntimeError(f"no encontré las filas de precios en {path}")

    plans: dict[str, dict[str, Any]] = {}
    for index, name in enumerate(names):
        key = slug(name)
        plans[key] = {
            "name": name,
            MONTHLY: prices[MONTHLY][index],
            YEARLY: prices[YEARLY][index],
            "tags": tags[index] if index < len(tags) else None,
            "fields": fields[index] if index < len(fields) else None,
            "clean": clean[index] if index < len(clean) else False,
            "emails": emails[index] if index < len(emails) else None,
            "users": users[index] if index < len(users) else None,
            "images": images[index] if index < len(images) else None,
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
    """Si se puede contratar desde la web: todo plan de `docs/pricing.md`, que
    son todos con precio. Uno que no está ahí no se compra."""
    return plan in PLANS


def field_limit(plan: str | None) -> int:
    """Cuántas columnas propias caben en ese plan, de `docs/pricing.md`.

    Leída y no copiada, como las etiquetas y como los precios: cambiar la fila
    del documento tiene que cambiarlo en un solo sitio.
    """
    found = PLANS.get(plan or "")
    if not found or found.get("fields") is None:
        return FREE_FIELDS
    return found["fields"]


def image_limit(plan: str | None) -> int:
    """Cuántas fotos puede tener guardadas una cuenta con ese plan, de
    docs/pricing.md. Sin plan, las del plan más barato, como las etiquetas: quien
    prueba, prueba con lo del Básico. Las imágenes que funde el sistema no
    cuentan (`images.count()`)."""
    found = PLANS.get(plan or "")
    if not found or found.get("images") is None:
        cheapest = next(iter(PLANS.values()), {})
        return cheapest.get("images") or 20
    return found["images"]


def itbms_in(total) -> Decimal:
    """Cuánto de un total es ITBMS, con el impuesto ya dentro del precio: $25
    llevan $1.64."""
    total = Decimal(str(total))
    return (total - total / (1 + ITBMS)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def without_itbms(amount) -> Decimal:
    """Un precio con ITBMS, sin él: $55 son $51.40 más su impuesto."""
    amount = Decimal(str(amount))
    return (amount / (1 + ITBMS)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def tag_limit(plan: str | None) -> int:
    """Cuántas etiquetas caben en ese plan, de docs/pricing.md.

    No se copia el número al backend por la misma razón que los precios:
    cambiar la fila del documento tiene que cambiarlo en el sitio y en el panel
    a la vez, o un día dicen cosas distintas.
    """
    found = PLANS.get(plan or "")
    if not found or found["tags"] is None:
        return FREE_TAGS
    return found["tags"]


def users(plan: str | None) -> int:
    """Cuántas personas pueden entrar a una cuenta de ese plan, de
    `docs/pricing.md`. **El dueño cuenta**, así que Básico es él y nadie más.

    Sin plan, una: la del dueño. Leída y no copiada, como las etiquetas.
    """
    found = PLANS.get(plan or "")
    if not found or found.get("users") is None:
        return FREE_USERS
    return found["users"]


def emails_a_month(plan: str | None) -> int | None:
    """Cuántos correos al mes puede enviar ese plan, de docs/pricing.md.

    None sin plan: no es cero, es que todavía no hay ninguno contratado, y son
    dos cosas distintas en una pantalla que enseña cifras.
    """
    found = PLANS.get(plan or "")
    return found["emails"] if found else None


def has_watermark(plan: str | None) -> bool:
    """Si a los correos de ese plan hay que ponerles la marca de agua.

    Es la regla 4 de CLAUDE.md, y sale de la fila «Correos sin marca de agua»
    de docs/pricing.md: la lleva quien no ha pagado por quitársela, o sea el
    Básico y quien todavía no tiene plan. Al subir de plan desaparece sola,
    porque nadie la copió a ningún sitio.
    """
    found = PLANS.get(plan or "")
    return not (found and found["clean"])


def rank(plan: str | None) -> int:
    """En qué puesto de la escalera está ese plan. Sin plan, -1.

    El orden es el de `docs/pricing.md`, de izquierda a derecha, que es también
    el de precio: la tabla se lee de menor a mayor y los diccionarios de Python
    conservan el orden en que se llenaron. Copiar aquí una lista de nombres
    ordenados sería una segunda fuente que un día contradiría al documento.
    """
    if not plan or plan not in PLANS:
        return -1
    return list(PLANS).index(plan)


def is_downgrade(current: str | None, wanted: str) -> bool:
    """Si pasar de uno al otro es bajar de plan.

    Quedarse en el mismo no lo es: comprar el que ya se tiene es renovarlo, y
    eso suma al final de lo que quedaba.
    """
    return rank(wanted) < rank(current)


def money(value: Any, currency: str = CURRENCY) -> str:
    """Un monto como se lee en el historial: «USD 15», «USD 38.33», «USD 1,026».
    Entero, sin decimales; con centavos, con los dos."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return f"{currency} {value}"
    if number == number.to_integral_value():
        return f"{currency} {int(number):,}"
    return f"{currency} {number:,.2f}"


def amount(plan: str, cycle: str) -> str | None:
    """El monto tal como lo quiere PayPal: dos decimales, en texto."""
    value = price(plan, cycle)
    return f"{value:.2f}" if value is not None else None


def discount(plan: str) -> int:
    """Cuánto se ahorra pagando el año, en por ciento y redondeado.

    Sale de las dos cifras de docs/pricing.md, como todo lo demás: la pantalla
    no puede anunciar un descuento que el documento no dé.
    """
    monthly = price(plan, MONTHLY)
    yearly = price(plan, YEARLY)
    if not monthly or not yearly:
        return 0
    return round((1 - yearly / (monthly * 12)) * 100)
