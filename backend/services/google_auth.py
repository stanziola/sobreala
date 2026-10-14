"""Entrar y registrarse con Google (octubre de 2026).

OAuth 2.0 con el código de autorización y PKCE, con `urllib` y nada más, como
PayPal: son dos llamadas HTTP y no merecen una librería que mantener.

Lo único que se le pide a Google es **quién es**: el identificador de su cuenta
(`sub`), el correo, si ese correo está verificado, y el nombre. Ni contactos, ni
archivos, ni nada más (`openid email profile`).

**Quién es lo dice la respuesta de Google al servidor**, nunca el navegador: la
vuelta trae un código que el servidor cambia por un token hablando él mismo con
Google, y con ese token le pregunta a Google por la persona. Lo que traiga la
dirección de vuelta, aparte del código y del `state`, no se usa.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import Config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = "openid email profile"


class GoogleError(RuntimeError):
    """Algo salió mal hablando con Google. El detalle va al registro."""


def configured() -> bool:
    return bool(Config.GOOGLE_CLIENT_ID and Config.GOOGLE_CLIENT_SECRET)


def new_request() -> dict[str, str]:
    """El `state` (contra que otro sitio inicie la vuelta) y el verificador de
    PKCE (contra que alguien use un código robado). Los dos viven en la sesión."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return {"state": secrets.token_urlsafe(24), "verifier": verifier,
            "challenge": challenge}


def authorize_url(*, state: str, challenge: str, redirect_uri: str) -> str:
    """A dónde se manda a la persona para que elija su cuenta de Google."""
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })


def _json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return json.loads(answer.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        print(f"  [google] {request.full_url.split('?')[0]} devolvio {exc.code}: {detail}",
              flush=True)
        raise GoogleError(f"google {exc.code}") from exc
    except (OSError, ValueError) as exc:
        print(f"  [google] no se pudo hablar con Google: {type(exc).__name__}", flush=True)
        raise GoogleError("google unreachable") from exc


def who(code: str, *, verifier: str, redirect_uri: str) -> dict[str, Any]:
    """Cambiar el código por un token y preguntarle a Google quién es.

    Devuelve `sub`, `email`, `email_verified` y `name`."""
    body = urllib.parse.urlencode({
        "code": code, "client_id": Config.GOOGLE_CLIENT_ID,
        "client_secret": Config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        "code_verifier": verifier,
    }).encode("ascii")
    request = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    token = _json(request).get("access_token")
    if not token:
        raise GoogleError("google: sin token")

    request = urllib.request.Request(USERINFO_URL, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    found = _json(request)
    if not found.get("sub") or not found.get("email"):
        raise GoogleError("google: sin identidad")
    return {"sub": str(found["sub"])[:64],
            "email": str(found["email"]).strip()[:254],
            "email_verified": found.get("email_verified") is True,
            "name": str(found.get("name") or "").strip()[:120]}
