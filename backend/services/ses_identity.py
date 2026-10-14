"""Los dominios propios de los clientes, en SES.

El único sitio que habla con la API v2 de SES (`sesv2`). Cuando un cliente
conecta su dominio, el panel lo crea aquí como identidad con Easy DKIM: SES
devuelve tres tokens, el cliente pone tres CNAME en su DNS, y SES ve que el
dominio es suyo. Nadie tiene que entrar a la consola de Amazon por cada cliente.

**Sin MAIL_BACKEND=ses todo es de mentira**, como el resto del envío: devuelve
tokens inventados y da el dominio por verificado al comprobarlo. Así el flujo
entero se recorre en local y en las pruebas sin credenciales de AWS.
"""

from __future__ import annotations

import hashlib
from typing import Any

from config import Config

VERIFIED = "verified"
PENDING = "pending"
FAILED = "failed"


class IdentityError(Exception):
    """SES no contestó, o contestó algo que no se esperaba."""


def _client():
    # Importado aquí para que desarrollar sin boto3 nunca lo necesite.
    import boto3

    return boto3.client("sesv2", region_name=Config.AWS_REGION)


def _fake() -> bool:
    return Config.MAIL_BACKEND != "ses"


def records(domain: str, tokens: list[str]) -> list[dict[str, str]]:
    """Los tres CNAME que el cliente pone en su DNS, como los pide SES."""
    return [{"type": "CNAME", "name": f"{token}._domainkey.{domain}",
             "value": f"{token}.dkim.amazonses.com"} for token in tokens]


def zone_file(domain: str, tokens: list[str]) -> str:
    """Los mismos registros como archivo de zona (formato BIND), que Cloudflare
    importa de una vez (DNS, Registros, «Importar y exportar») y que aceptan
    casi todos los proveedores de DNS.

    Los nombres van completos y con su punto final, para que no se lean como
    relativos al dominio. `cf_tags=cf-proxied:false` le dice a Cloudflare que
    entren sin proxy («Solo DNS»): un CNAME de DKIM detrás del proxy no lo
    encuentra Amazon."""
    lines = [f"; Sobreala: los registros de {domain} para Amazon SES (DKIM).",
             "; En Cloudflare: DNS, Registros, Importar y exportar.", ""]
    for one in records(domain, tokens):
        lines.append(f"{one['name']}.\t3600\tIN\t{one['type']}\t{one['value']}."
                     "\t; cf_tags=cf-proxied:false")
    return "\n".join(lines) + "\n"


def create(domain: str) -> list[str]:
    """Crear la identidad y devolver sus tres tokens de DKIM.

    Si ya existía en SES (la creó antes esta misma cuenta y la soltó a medias),
    se leen los suyos en vez de fallar."""
    if _fake():
        seed = hashlib.sha256(domain.encode()).hexdigest()
        return [seed[i:i + 32] for i in (0, 16, 32)]
    try:
        client = _client()
        try:
            answer = client.create_email_identity(
                EmailIdentity=domain,
                DkimSigningAttributes={"NextSigningKeyLength": "RSA_2048_BIT"})
        except client.exceptions.AlreadyExistsException:
            answer = client.get_email_identity(EmailIdentity=domain)
        return list(answer.get("DkimAttributes", {}).get("Tokens") or [])
    except Exception as exc:  # noqa: BLE001 - reported to the screen as one error
        raise IdentityError(f"{type(exc).__name__}: {str(exc)[:160]}") from exc


def status(domain: str) -> str:
    """Si SES ya ve los registros: `verified`, `pending` o `failed`."""
    if _fake():
        return VERIFIED
    try:
        answer: dict[str, Any] = _client().get_email_identity(EmailIdentity=domain)
    except Exception as exc:  # noqa: BLE001
        raise IdentityError(f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    dkim = (answer.get("DkimAttributes") or {}).get("Status", "")
    if answer.get("VerifiedForSendingStatus") and dkim == "SUCCESS":
        return VERIFIED
    if dkim in ("FAILED", "TEMPORARY_FAILURE"):
        return FAILED
    return PENDING


def delete(domain: str) -> None:
    """Soltar el dominio. Que ya no exista en SES no es un error."""
    if _fake():
        return
    try:
        client = _client()
        try:
            client.delete_email_identity(EmailIdentity=domain)
        except client.exceptions.NotFoundException:
            pass
    except Exception as exc:  # noqa: BLE001
        raise IdentityError(f"{type(exc).__name__}: {str(exc)[:160]}") from exc
