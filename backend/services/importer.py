"""Reading a list of contacts out of a CSV, without ever holding it whole.

The file arrives from a browser and can be five megabytes. It is read row by
row, written in batches, and the two questions each batch needs —who is already
here, who is suppressed— are asked once per batch and never once per row. That
is rule 10 of CLAUDE.md, and it is the difference between an import that takes a
second and one that makes a thousand round trips.

What the file looks like is not something anyone will get right the first time:
a cooperative exports from Excel in Spanish and gets semicolons, a school pastes
one column with no header at all. So the shape is worked out from the file
rather than demanded of it.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from typing import Any, Iterator

from email_validator import EmailNotValidError, validate_email

from models import contact as contacts
from models import suppression as suppressions
from models.account import normalize_email
from services import address_check
from services import fields as columns_of

# What a column of addresses tends to be called, and what a column of names
# tends to be called, in the files these clients actually have.
EMAIL_HEADERS = ("correo", "correo electronico", "correos", "email", "e-mail",
                 "mail", "direccion", "direccion de correo")
NAME_HEADERS = ("nombre", "nombres", "nombre completo", "name", "contacto",
                "socio", "cliente")

# Excel in Spanish writes semicolons; almost everything else writes commas.
DELIMITERS = (",", ";", "\t", "|")

# A row longer than this is not a row, it is a file with no line breaks.
MAX_FIELD = 2000


def fold(text: str) -> str:
    """Lowercase, without accents, for comparing a header to a known name."""
    stripped = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in stripped if not unicodedata.combining(c)).strip().lower()


def clean(email: str) -> str | None:
    """The address, or None if it is not one.

    The same check the registration form uses, so a row rejected here would
    have been rejected there: one rule for addresses in the whole project.
    """
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized
    except (EmailNotValidError, ValueError):
        return None


def sniff(line: str) -> str:
    """Which character separates the columns, decided by counting them."""
    return max(DELIMITERS, key=line.count)


def columns(header: list[str]) -> tuple[int | None, int | None]:
    """Which column holds the address and which the name, by their titles."""
    email_at = name_at = None
    for index, cell in enumerate(header):
        folded = fold(cell)
        if email_at is None and folded in EMAIL_HEADERS:
            email_at = index
        elif name_at is None and folded in NAME_HEADERS:
            name_at = index
    return email_at, name_at


def open_rows(stream: Any) -> tuple[list[str], Iterator[list[str]]]:
    """El archivo abierto: su cabecera y sus filas, sin leerlo entero.

    La cabecera sale vacía cuando el archivo no tiene ninguna —una columna de
    direcciones pegada y ya—, y entonces esa primera línea viaja dentro de las
    filas, que es donde le toca.
    """
    # utf-8-sig eats the mark Excel puts at the start of the file, and errors
    # are replaced instead of raised: one accented name in Latin-1 must not
    # throw away the other nine hundred rows.
    text = io.TextIOWrapper(stream, encoding="utf-8-sig", errors="replace",
                            newline="")
    first = text.readline()
    if not first.strip():
        return [], iter(())

    apart = sniff(first)
    head = next(csv.reader(io.StringIO(first), delimiter=apart), [])
    # A line with an address in it is data, not a header.
    is_header = not any("@" in cell for cell in head)

    def walk() -> Iterator[list[str]]:
        if not is_header:
            yield head
        for row in csv.reader(text, delimiter=apart):
            if row:
                yield row

    return (head if is_header else []), walk()


def header_of(stream: Any) -> list[str]:
    """Solo los títulos, para preguntar qué columna es cuál. Vacío si el
    archivo no trae ninguno.

    Lee un trozo y no envuelve el archivo: `TextIOWrapper` lo cierra cuando se
    lo lleva el recolector, y este mismo archivo hay que volver a leerlo entero
    para importarlo. Quien llama lo pone al principio otra vez.
    """
    chunk = stream.read(64 * 1024)
    if not chunk:
        return []
    if isinstance(chunk, bytes):
        chunk = chunk.decode("utf-8-sig", errors="replace")
    line = re.split(r"\r\n|\r|\n", chunk, maxsplit=1)[0]
    if not line.strip():
        return []
    head = next(csv.reader(io.StringIO(line), delimiter=sniff(line)), [])
    # Una línea con una dirección dentro son datos, no títulos: ese archivo no
    # tiene nada que elegir.
    if any("@" in cell for cell in head):
        return []
    return [cell.strip()[:MAX_FIELD] for cell in head]


def matching(header: list[str],
             definitions: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Qué columna del archivo va a cada columna de la cuenta, por su título.

    Es el respaldo de la pantalla, que es la que pregunta: si nadie eligió
    nada, un archivo cuya cabecera dice «Ciudad» llena la columna «Ciudad» que
    esa cuenta ya tiene. Nada se crea aquí.
    """
    found: dict[int, dict[str, Any]] = {}
    used: set[str] = set()
    for index, cell in enumerate(header):
        title = columns_of.fold(cell)
        for one in definitions:
            if one["key"] in used:
                continue
            if title and title == columns_of.fold(one["label"]):
                found[index] = one
                used.add(one["key"])
                break
    return found


def rows(stream: Any, take: dict[int, dict[str, Any]] | None = None
         ) -> Iterator[tuple[str, str, dict[str, str]]]:
    """Yield (address, name, columns) out of the uploaded file, one at a time.

    Never reads more than a row into memory. `take` dice qué columna del
    archivo se guarda en qué columna de la cuenta; lo que no esté ahí se ignora,
    que es lo que hace que un archivo de quince columnas se pueda importar con
    un plan que permite dos.
    """
    header, walker = open_rows(stream)
    email_at, name_at = columns(header) if header else (None, None)
    wanted = take or {}

    for row in walker:
        if email_at is None:
            # A header that named no column of addresses: take the first one
            # that holds an address in the first row that has any.
            email_at = next((i for i, c in enumerate(row) if "@" in c), None)
            if email_at is None:
                continue
        if email_at >= len(row):
            continue
        values: dict[str, str] = {}
        for index, one in wanted.items():
            raw = _cell(row, index)
            if not raw:
                continue
            # Lo que no es de ese tipo no se escribe. Guardar «el martes» en una
            # columna de fecha es guardar algo que después no se puede enseñar.
            value = columns_of.parse(raw, one.get("type", columns_of.TEXT))
            if value:
                values[one["key"]] = value
        yield row[email_at][:MAX_FIELD], _cell(row, name_at), values


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index][:MAX_FIELD]


def run(db, account_id, stream: Any, *, tags: list[str],
        consent: dict[str, Any], limit: int,
        take: dict[int, dict[str, Any]] | None = None,
        required: list[dict[str, Any]] | None = None
        ) -> tuple[dict[str, int], bool]:
    """Import the whole file. Returns (counts, hit_the_limit).

    Reaching the limit is not a failure: what already went in stays in, which
    is what docs/pricing.md promises. The caller says so on the screen and
    invites them to move up a plan.
    """
    counts = {"read": 0, "added": 0, "updated": 0, "invalid": 0,
              "suppressed": 0, "incomplete": 0,
              # Revisadas antes de enviar (`services/address_check.py`): las de
              # un dominio que no recibe correo entran marcadas, y los errores
              # de dedo se cuentan con su sugerencia (las primeras cinco).
              "undeliverable": 0, "typos": 0, "typos_sample": []}
    domains_seen: set[str] = set()
    # Las columnas de la cuenta. Un contacto **nuevo** solo entra con todas
    # llenas: sin ellas no podría recibir nada, así que entrar sería entrar de
    # peso muerto. A uno que ya existe se le actualiza lo que venga.
    wanted = [one["key"] for one in (required or [])]
    # Los anulados no ocupan sitio: no pueden recibir nada.
    room = max(0, limit - contacts.active_count(db, account_id))
    stopped = False
    batch: list[tuple[str, str, dict[str, str]]] = []
    seen: set[str] = set()

    def flush() -> bool:
        """Write one batch. True when the limit was reached inside it."""
        nonlocal room
        if not batch:
            return False
        keys = [normalize_email(one[0]) for one in batch]

        # The two bulk questions, one query each: who is already here, and who
        # may not be written to.
        known = {d["email_normalized"] for d in db.contacts.find(
            {"account_id": account_id, "email_normalized": {"$in": keys}},
            {"email_normalized": 1})}
        counts["suppressed"] += len(suppressions.among(db, account_id, keys))

        # Somebody already in the account costs no room; a new one does. What
        # does not fit is left out, in the order the file had them.
        fits, full = [], False
        for one, key in zip(batch, keys):
            if key not in known and any(not one[2].get(name) for name in wanted):
                # Nuevo y sin todas sus columnas: no entra, y se cuenta aparte
                # para poder decir cuántos se quedaron fuera y por qué.
                counts["incomplete"] += 1
                continue
            if key in known:
                fits.append(one)
            elif room > 0:
                room -= 1
                fits.append(one)
            else:
                full = True
                break

        added, updated = contacts.upsert_many(db, account_id, fits,
                                              tags=tags, consent=consent)
        counts["added"] += added
        counts["updated"] += updated
        bad = address_check.undeliverable([one[0] for one in fits], seen=domains_seen)
        counts["undeliverable"] += contacts.mark_invalid(
            db, account_id, [normalize_email(one) for one in bad])
        for one in fits:
            better = address_check.suggestion(one[0])
            if better and one[0] not in bad:
                counts["typos"] += 1
                if len(counts["typos_sample"]) < 5:
                    counts["typos_sample"].append([one[0], better])
        batch.clear()
        seen.clear()
        return full

    for raw_email, name, values in rows(stream, take):
        counts["read"] += 1
        address = clean(raw_email)
        if not address:
            counts["invalid"] += 1
            continue
        key = normalize_email(address)
        # Inside one batch a repeat is not just wasteful: two upserts on the
        # same key in one bulkWrite collide on the unique index.
        if key in seen:
            continue
        seen.add(key)
        batch.append((address, name, values))
        if len(batch) >= contacts.BATCH:
            if flush():
                stopped = True
                break

    if not stopped and flush():
        stopped = True
    return counts, stopped
