"""Two-step verification with the codes a phone app generates.

TOTP: the phone and the server share a secret and both turn the clock into the
same six digits, so nothing has to travel for the code to be checked. That is
what makes it stronger than a code by email — it keeps working, and keeps
protecting, even for someone whose mailbox has been taken over.

One thing has to be said plainly: **the secret cannot be stored as a hash**. The
server has to produce the same digits as the phone, so it needs the secret
itself. That is inherent to TOTP, not a shortcut taken here. The recovery codes
are a different matter and are stored hashed, like every other code in this
project.

Clocks drift, so a code from the window before or after is accepted, and the
window it belonged to is handed back to the caller: refusing a window that was
already used is what stops a code read over someone's shoulder from working a
second time.
"""

from __future__ import annotations

import io
import secrets
import time

from services.security import hash_keyed

PERIOD = 30          # seconds a code lives, the value every app assumes
DRIFT = 1            # how many windows of slack for a phone with a late clock
RECOVERY_CODES = 8

# No I, O, 0 or 1: these get read off paper and typed by hand.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ISSUER = "Panamails"


def new_secret() -> str:
    """The shared secret, in the base32 the apps expect."""
    import pyotp

    return pyotp.random_base32()


def uri(secret: str, email: str) -> str:
    """The otpauth:// address the QR encodes."""
    import pyotp

    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_svg(secret: str, email: str) -> str:
    """The QR as SVG markup, to drop straight into the page.

    Dark on white on purpose, whatever theme the page is in: a scanner needs the
    contrast, and a QR drawn dark on a dark background does not read.
    """
    import segno

    out = io.BytesIO()
    segno.make(uri(secret, email), error="m").save(
        out, kind="svg", scale=5, border=2, dark="#0E1B2A", light="#FFFFFF",
        xmldecl=False, svgns=False, nl=False, svgclass=None, lineclass=None)
    return out.getvalue().decode("utf-8")


def clean(code: str | None) -> str:
    return "".join(ch for ch in (code or "") if ch.isdigit())


def counter_for(secret: str, code: str) -> int | None:
    """The 30-second window this code belongs to, or None if it is not valid.

    The counter travels back so the caller can store it and refuse anything at
    or before it next time. Compared in constant time, like every other secret
    in this project.
    """
    import pyotp

    typed = clean(code)
    if len(typed) != 6:
        return None
    totp = pyotp.TOTP(secret)
    moment = int(time.time())
    for offset in range(-DRIFT, DRIFT + 1):
        when = moment + offset * PERIOD
        if secrets.compare_digest(totp.at(when), typed):
            return when // PERIOD
    return None


# ------------------------------------------------------------ recovery codes

def new_recovery_codes() -> list[str]:
    """Eight codes to write down, in the shape people copy without mistakes."""
    def one() -> str:
        raw = "".join(secrets.choice(ALPHABET) for _ in range(8))
        return f"{raw[:4]}-{raw[4:]}"

    return [one() for _ in range(RECOVERY_CODES)]


def normalize_recovery(code: str | None) -> str:
    """What was typed, as it was stored: no dashes, no spaces, upper case."""
    return "".join(ch for ch in (code or "").upper() if ch in ALPHABET)


def hash_recovery(code: str) -> str:
    return hash_keyed(normalize_recovery(code))


def hash_all(codes: list[str]) -> list[str]:
    return [hash_recovery(code) for code in codes]
