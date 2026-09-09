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
import unicodedata
from typing import Any, Iterator

from email_validator import EmailNotValidError, validate_email

from models import contact as contacts
from models import suppression as suppressions
from models.account import normalize_email

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


def rows(stream: Any) -> Iterator[tuple[str, str]]:
    """Yield (address, name) out of the uploaded file, one row at a time.

    Never reads more than a row into memory. The first line decides three
    things: the separator, whether there is a header, and which columns to
    take; after that it is a straight walk to the end of the file.
    """
    # utf-8-sig eats the mark Excel puts at the start of the file, and errors
    # are replaced instead of raised: one accented name in Latin-1 must not
    # throw away the other nine hundred rows.
    text = io.TextIOWrapper(stream, encoding="utf-8-sig", errors="replace",
                            newline="")
    first = text.readline()
    if not first.strip():
        return

    reader = csv.reader(io.StringIO(first), delimiter=sniff(first))
    header = next(reader, [])
    # A line with an address in it is data, not a header.
    is_header = not any("@" in cell for cell in header)
    email_at, name_at = columns(header) if is_header else (None, None)

    if not is_header:
        email_at = next((i for i, c in enumerate(header) if "@" in c), 0)
        yield header[email_at][:MAX_FIELD], _cell(header, name_at)

    walker = csv.reader(text, delimiter=sniff(first))
    for row in walker:
        if not row:
            continue
        if email_at is None:
            # A header that named no column of addresses: take the first one
            # that holds an address in the first row that has any.
            email_at = next((i for i, c in enumerate(row) if "@" in c), None)
            if email_at is None:
                continue
        if email_at >= len(row):
            continue
        yield row[email_at][:MAX_FIELD], _cell(row, name_at)


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index][:MAX_FIELD]


def run(db, account_id, stream: Any, *, tags: list[str],
        consent: dict[str, Any], limit: int) -> tuple[dict[str, int], bool]:
    """Import the whole file. Returns (counts, hit_the_limit).

    Reaching the limit is not a failure: what already went in stays in, which
    is what docs/pricing.md promises. The caller says so on the screen and
    invites them to move up a plan.
    """
    counts = {"read": 0, "added": 0, "updated": 0, "invalid": 0, "suppressed": 0}
    room = max(0, limit - contacts.count(db, account_id))
    stopped = False
    batch: list[tuple[str, str]] = []
    seen: set[str] = set()

    def flush() -> bool:
        """Write one batch. True when the limit was reached inside it."""
        nonlocal room
        if not batch:
            return False
        keys = [normalize_email(e) for e, _ in batch]

        # The two bulk questions, one query each: who is already here, and who
        # may not be written to.
        known = {d["email_normalized"] for d in db.contacts.find(
            {"account_id": account_id, "email_normalized": {"$in": keys}},
            {"email_normalized": 1})}
        counts["suppressed"] += len(suppressions.among(db, account_id, keys))

        # Somebody already in the account costs no room; a new one does. What
        # does not fit is left out, in the order the file had them.
        fits, full = [], False
        for (email, name), key in zip(batch, keys):
            if key in known:
                fits.append((email, name))
            elif room > 0:
                room -= 1
                fits.append((email, name))
            else:
                full = True
                break

        added, updated = contacts.upsert_many(db, account_id, fits,
                                              tags=tags, consent=consent)
        counts["added"] += added
        counts["updated"] += updated
        batch.clear()
        seen.clear()
        return full

    for raw_email, name in rows(stream):
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
        batch.append((address, name))
        if len(batch) >= contacts.BATCH:
            if flush():
                stopped = True
                break

    if not stopped and flush():
        stopped = True
    return counts, stopped
