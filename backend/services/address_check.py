"""Revisar direcciones antes de enviar (octubre de 2026).

Lo que se puede saber gratis y sin mandar nada:

  * **que el dominio reciba correo**: que tenga MX (o, si no tiene, una
    dirección A, que es a donde se entrega entonces). `gmial.com` o el dominio
    de una empresa que cerró no reciben nada, y escribirles es un rebote seguro
    que además gasta cuota;
  * **los errores de dedo comunes** (`gmial.com`, `hotmial.com`, `yaho.com`),
    para sugerir el bueno.

Lo que **no** se puede saber es si un buzón concreto existe en un dominio bueno
(`juan.perez@gmail.com`): eso solo lo dice el rebote, que ya anula la dirección.
Preguntarle al servidor del otro lado (el «RCPT TO» sin enviar) no sirve:
Gmail y Outlook dicen que sí a todo, y hacerlo seguido manda la IP a las listas
negras.

La consulta es **una por dominio**, no por dirección, y se guarda mientras el
proceso vive. Lo que no se pudo averiguar (el DNS no contestó a tiempo) cuenta
como bueno: no se castiga a nadie por una falla nuestra.

**Sin `MAIL_BACKEND=ses` no se consulta el DNS**, como el resto del envío: en
local y en las pruebas todo dominio recibe correo, salvo que una prueba lo
cambie.
"""

from __future__ import annotations

import difflib
from functools import lru_cache

from email_validator import (EmailNotValidError, EmailUndeliverableError,
                             caching_resolver, validate_email)

from config import Config

# Cuántos dominios distintos se consultan, como mucho, en una importación: la
# importación corre dentro del request, y cada consulta puede tardar.
MAX_DOMAINS = 400
TIMEOUT = 3

# Los dominios que más se escriben mal en Panamá, para sugerir el bueno. Solo
# se sugiere uno de estos, y solo si el escrito se le parece mucho.
COMMON = ("gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com",
          "live.com", "msn.com", "yahoo.es", "hotmail.es", "outlook.es",
          "cwpanama.net", "cableonda.net", "utp.ac.pa", "up.ac.pa")
CUTOFF = 0.84

_resolver = None


def _dns():
    global _resolver
    if _resolver is None:
        _resolver = caching_resolver(timeout=TIMEOUT)
    return _resolver


def live() -> bool:
    """Si se consulta el DNS de verdad: solo con el envío de verdad."""
    return Config.MAIL_BACKEND == "ses"


@lru_cache(maxsize=20000)
def domain_receives(domain: str) -> bool:
    """Si ese dominio recibe correo. Lo que no se sabe cuenta como sí."""
    domain = (domain or "").strip().lower()
    if not domain or not live():
        return True
    try:
        validate_email(f"postmaster@{domain}", check_deliverability=True,
                       dns_resolver=_dns())
    except EmailUndeliverableError:
        return False
    except (EmailNotValidError, Exception):  # noqa: BLE001 - unknown is not bad
        return True
    return True


def domain_of(email: str) -> str:
    return (email or "").rsplit("@", 1)[-1].lower() if "@" in (email or "") else ""


def suggestion(email: str) -> str | None:
    """La dirección con el dominio corregido, si parece un error de dedo."""
    domain = domain_of(email)
    if not domain or domain in COMMON:
        return None
    close = difflib.get_close_matches(domain, COMMON, n=1, cutoff=CUTOFF)
    # Un error de dedo cambia una o dos letras, no el largo: así `yahoo.com.mx`,
    # que existe, no se «corrige» a `yahoo.com`.
    if not close or abs(len(close[0]) - len(domain)) > 2:
        return None
    return email.rsplit("@", 1)[0] + "@" + close[0]


def undeliverable(emails, *, seen: set[str] | None = None,
                  max_domains: int = MAX_DOMAINS) -> set[str]:
    """De estas direcciones, las de un dominio que no recibe correo.

    Una consulta por dominio distinto, hasta `max_domains` en total. `seen`
    lleva la cuenta entre llamadas (una importación llama una vez por tanda);
    los dominios que pasan del tope no se revisan y cuentan como buenos.
    """
    seen = set() if seen is None else seen
    by_domain: dict[str, list[str]] = {}
    for email in emails:
        domain = domain_of(email)
        if domain:
            by_domain.setdefault(domain, []).append(email)
    bad: set[str] = set()
    for domain, found in by_domain.items():
        if domain not in seen:
            if len(seen) >= max_domains:
                continue
            seen.add(domain)
        if not domain_receives(domain):
            bad.update(found)
    return bad
