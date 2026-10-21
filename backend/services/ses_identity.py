"""Los dominios propios de los clientes, en SES.

El único sitio que habla con la API v2 de SES (`sesv2`). Cuando un cliente
conecta su dominio, el panel lo crea aquí como identidad con Easy DKIM: SES
devuelve tres tokens, el cliente pone tres CNAME en su DNS, y SES ve que el
dominio es suyo. Nadie tiene que entrar a la consola de Amazon por cada cliente.

**Y su propio MAIL FROM** (octubre de 2026): `envios.<dominio>`, con un MX y un
SPF más en su DNS. Es el dominio del sobre, el que Gmail enseña en «enviado
por»: sin él decía `us-east-1.amazonses.com`. Mientras falten esos dos
registros se envía igual, con el de Amazon (`USE_DEFAULT_VALUE`): lo que pide el
envío sigue siendo DKIM. Pedírselo a SES necesita el permiso
`ses:PutEmailIdentityMailFromAttributes` (`docs/ses.md`).

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
    # De uno en uno: gunicorn atiende con hilos (services/aws.py).
    from services import aws

    return aws.client("sesv2")


def _fake() -> bool:
    return Config.MAIL_BACKEND != "ses"


# El subdominio del sobre de cada dominio propio: «enviado por envios.coop.com».
MAIL_FROM_PREFIX = "envios"
SPF = "v=spf1 include:amazonses.com ~all"


def mail_from_domain(domain: str) -> str:
    return f"{MAIL_FROM_PREFIX}.{domain}"


def dkim_records(domain: str, tokens: list[str]) -> list[dict[str, str]]:
    """Los tres CNAME de DKIM, como los pide SES."""
    return [{"type": "CNAME", "name": f"{token}._domainkey.{domain}",
             "value": f"{token}.dkim.amazonses.com"} for token in tokens]


def mail_from_records(domain: str) -> list[dict[str, str]]:
    """El MX y el SPF del MAIL FROM. El MX va a la región de la cuenta de SES."""
    return [{"type": "MX", "name": mail_from_domain(domain), "priority": "10",
             "value": f"feedback-smtp.{Config.AWS_REGION}.amazonses.com"},
            {"type": "TXT", "name": mail_from_domain(domain), "value": SPF}]


def records(domain: str, tokens: list[str]) -> list[dict[str, str]]:
    """Los cinco registros que el cliente pone en su DNS: DKIM y MAIL FROM."""
    return dkim_records(domain, tokens) + mail_from_records(domain)


def zone_file(domain: str, tokens: list[str]) -> str:
    """Los mismos registros como archivo de zona (formato BIND), el que importan
    de una vez los proveedores de DNS que lo permiten (Cloudflare, Route 53 y
    otros). No da por hecho ninguno: no todos tienen ahí su dominio.

    Los nombres van completos y con su punto final, para que no se lean como
    relativos al dominio. `cf_tags=cf-proxied:false` va como comentario al final
    de cada CNAME: los demás proveedores no lo leen, y a Cloudflare le dice que
    entren sin proxy («Solo DNS») aunque al importar se marque lo contrario,
    porque un CNAME de DKIM detrás del proxy no lo encuentra Amazon."""
    lines = [f"; Sobreala: los registros DNS de {domain} para Amazon SES (DKIM y MAIL FROM).",
             "; Impórtalo en tu proveedor de DNS si lo permite, o copia cada registro a mano.",
             ""]
    for one in dkim_records(domain, tokens):
        lines.append(f"{one['name']}.\t3600\tIN\t{one['type']}\t{one['value']}."
                     "\t; cf_tags=cf-proxied:false")
    # El MX y el TXT no pasan por el proxy de Cloudflare: no llevan la marca.
    for one in mail_from_records(domain):
        if one["type"] == "MX":
            lines.append(f"{one['name']}.\t3600\tIN\tMX\t{one['priority']} {one['value']}.")
        else:
            lines.append(f"{one['name']}.\t3600\tIN\tTXT\t\"{one['value']}\"")
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
        _put_mail_from(client, domain)
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


def _put_mail_from(client, domain: str) -> None:
    """Pedirle a SES el MAIL FROM propio. Sin sus registros, el de Amazon."""
    client.put_email_identity_mail_from_attributes(
        EmailIdentity=domain, MailFromDomain=mail_from_domain(domain),
        BehaviorOnMxFailure="USE_DEFAULT_VALUE")


def mail_from(domain: str) -> str:
    """En qué está el MAIL FROM: `verified`, `pending` o `failed`.

    Si la identidad todavía no lo tiene (un dominio conectado antes de octubre
    de 2026), se le pone aquí, una vez: así nadie tiene que volver a
    conectarlo."""
    if _fake():
        return VERIFIED
    try:
        client = _client()
        answer: dict[str, Any] = client.get_email_identity(EmailIdentity=domain)
        found = answer.get("MailFromAttributes") or {}
        if found.get("MailFromDomain") != mail_from_domain(domain):
            _put_mail_from(client, domain)
            return PENDING
    except Exception as exc:  # noqa: BLE001
        raise IdentityError(f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    state = found.get("MailFromDomainStatus", "")
    if state == "SUCCESS":
        return VERIFIED
    if state in ("FAILED", "TEMPORARY_FAILURE"):
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
