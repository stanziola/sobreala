"""Entrar y registrarse con Apple (octubre de 2026).

Lo mismo que Google y GitHub (`google_auth.py`, `github_auth.py`), con lo que
Apple hace distinto:

  * **La clave secreta no es fija**: es un JWT firmado con ES256 y la clave
    `.p8` de la cuenta de Apple Developer (`client_secret()`), que vale cinco
    minutos. Por eso hace falta `cryptography`.
  * **Apple vuelve con un POST** desde su dominio (`response_mode=form_post`,
    obligatorio al pedir el nombre y el correo). El navegador no manda la
    galleta de sesión en ese POST, así que la ruta lo reenvía una vez desde
    nuestra propia página (`oauth-relay.html`) y ahí sí la manda.
  * **Quién es lo dice el `id_token`** que devuelve el servidor de Apple al
    nuestro, por HTTPS y a cambio del código y de la clave secreta. Llega
    directo de Apple, así que no se baja su llave para comprobar la firma (lo
    permite OpenID Connect, 3.1.3.7): se comprueban el emisor, la audiencia, el
    vencimiento y el `nonce` que se mandó al salir.
  * **«Ocultar mi correo»**: muchos entran con una dirección
    `@privaterelay.appleid.com`. Se acepta: es verificada y le llega lo que se
    le mande, si `sobreala.com` está registrado en el servicio de reenvío de
    Apple (`docs/cuenta.md`).
  * **El nombre llega solo la primera vez**, en el mismo POST (`user`), y no en
    el token. Sirve para llenar el registro, que se puede corregir.

Lo que se guarda de Apple es solo el `sub`, en `accounts.apple_sub`.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from config import Config

ISSUER = "https://appleid.apple.com"
AUTH_URL = "https://appleid.apple.com/auth/authorize"
TOKEN_URL = "https://appleid.apple.com/auth/token"
SCOPES = "name email"
SECRET_SECONDS = 300
# Cuánto se tolera de diferencia entre nuestro reloj y el de Apple.
LEEWAY = 120


class AppleError(RuntimeError):
    """Algo salió mal hablando con Apple. El detalle va al registro."""


def configured() -> bool:
    return bool(Config.APPLE_CLIENT_ID and Config.APPLE_TEAM_ID and Config.APPLE_KEY_ID
                and Config.APPLE_PRIVATE_KEY)


def new_request() -> dict[str, str]:
    """El `state` y el `nonce`. Apple no usa PKCE: el `nonce` viaja al salir y
    vuelve dentro del token, y es lo que ata la vuelta a esta salida. Va en los
    dos sitios que usan los otros proveedores (`challenge` al salir y
    `verifier` al volver)."""
    nonce = secrets.token_urlsafe(32)
    return {"state": secrets.token_urlsafe(24), "verifier": nonce, "challenge": nonce}


def authorize_url(*, state: str, challenge: str, redirect_uri: str) -> str:
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": Config.APPLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "response_mode": "form_post",
        "scope": SCOPES,
        "state": state,
        "nonce": challenge,
    })


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _private_key():
    # En Railway la clave se pega entera; si llega con «\n» escritos, se arreglan.
    pem = Config.APPLE_PRIVATE_KEY.replace("\\n", "\n").strip().encode("ascii")
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise AppleError("apple: la clave no es de curva elíptica")
    return key


def client_secret(now: float | None = None) -> str:
    """El JWT que hace de clave secreta: ES256, de nuestro equipo, para Apple."""
    moment = int(now if now is not None else time.time())
    header = {"alg": "ES256", "kid": Config.APPLE_KEY_ID}
    payload = {"iss": Config.APPLE_TEAM_ID, "iat": moment,
               "exp": moment + SECRET_SECONDS, "aud": ISSUER,
               "sub": Config.APPLE_CLIENT_ID}
    signing = (_b64(json.dumps(header, separators=(",", ":")).encode())
               + "." + _b64(json.dumps(payload, separators=(",", ":")).encode()))
    der = _private_key().sign(signing.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return signing + "." + _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def _claims(id_token: str) -> dict[str, Any]:
    try:
        part = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (IndexError, ValueError) as exc:
        raise AppleError("apple: token ilegible") from exc


def _token(code: str, redirect_uri: str) -> dict[str, Any]:
    body = urllib.parse.urlencode({
        "client_id": Config.APPLE_CLIENT_ID, "client_secret": client_secret(),
        "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri,
    }).encode("ascii")
    request = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:  # noqa: S310
            return json.loads(answer.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        print(f"  [apple] {TOKEN_URL} devolvio {exc.code}: {detail}", flush=True)
        raise AppleError(f"apple {exc.code}") from exc
    except (OSError, ValueError) as exc:
        print(f"  [apple] no se pudo hablar con Apple: {type(exc).__name__}", flush=True)
        raise AppleError("apple unreachable") from exc


def name_from(raw: str) -> str:
    """El nombre del POST de la primera vez (`user`), si vino. Es solo para
    llenar el registro: lo manda el navegador, así que no decide nada."""
    try:
        found = json.loads(raw or "{}").get("name") or {}
    except (ValueError, AttributeError):
        return ""
    if not isinstance(found, dict):
        return ""
    parts = [found.get("firstName"), found.get("lastName")]
    return " ".join(str(one).strip() for one in parts if isinstance(one, str)
                    and one.strip())[:120]


def who(code: str, *, verifier: str, redirect_uri: str) -> dict[str, Any]:
    """Cambiar el código por el `id_token` y leer quién es.

    Devuelve `sub`, `email`, `email_verified` y `name` (vacío: Apple no lo pone
    en el token)."""
    claims = _claims(str(_token(code, redirect_uri).get("id_token") or ""))
    now = time.time()
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if (claims.get("iss") != ISSUER or Config.APPLE_CLIENT_ID not in audiences
            or not isinstance(claims.get("exp"), (int, float))
            or claims["exp"] + LEEWAY < now
            or not isinstance(claims.get("nonce"), str)
            or not secrets.compare_digest(claims["nonce"], verifier or "")):
        raise AppleError("apple: token que no es para nosotros")
    if not claims.get("sub") or not claims.get("email"):
        raise AppleError("apple: sin identidad")
    verified = claims.get("email_verified")
    return {"sub": str(claims["sub"])[:64],
            "email": str(claims["email"]).strip()[:254],
            "email_verified": verified is True or verified == "true",
            "name": ""}
