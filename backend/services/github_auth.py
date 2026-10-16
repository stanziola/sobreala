"""Entrar y registrarse con GitHub (octubre de 2026).

Lo mismo que `google_auth.py`, con lo que GitHub tiene distinto. OAuth 2.0 con
el código de autorización y PKCE (GitHub lo admite en las aplicaciones OAuth
desde julio de 2025; el secreto se sigue mandando, desde el servidor), con
`urllib` y nada más.

Lo único que se le pide a GitHub es **quién es**: el identificador de su cuenta,
el nombre y sus correos (`read:user user:email`). Ni repositorios, ni nada más.

**Quién es lo dice la respuesta de GitHub al servidor**, nunca el navegador: la
vuelta trae un código que el servidor cambia por un token hablando él mismo con
GitHub, y con ese token le pregunta por la persona. GitHub no da un correo
verificado junto con el usuario: lo da la lista de sus correos, y de ella vale
**solo el principal y verificado**. Sin él, la cuenta cuenta como sin verificar.

`who()` devuelve lo mismo que el de Google, así lo que pasa después es uno solo.
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

AUTH_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
EMAILS_URL = "https://api.github.com/user/emails"
SCOPES = "read:user user:email"
# Sin User-Agent, la API de GitHub contesta que no a todo.
USER_AGENT = "Sobreala"


class GitHubError(RuntimeError):
    """Algo salió mal hablando con GitHub. El detalle va al registro."""


def configured() -> bool:
    return bool(Config.GITHUB_CLIENT_ID and Config.GITHUB_CLIENT_SECRET)


def new_request() -> dict[str, str]:
    """El `state` (contra que otro sitio inicie la vuelta) y el verificador de
    PKCE (contra que alguien use un código robado). Los dos viven en la sesión."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return {"state": secrets.token_urlsafe(24), "verifier": verifier,
            "challenge": challenge}


def authorize_url(*, state: str, challenge: str, redirect_uri: str) -> str:
    """A dónde se manda a la persona para que autorice con su cuenta de GitHub."""
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": Config.GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


def _json(request: urllib.request.Request) -> Any:
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return json.loads(answer.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        print(f"  [github] {request.full_url.split('?')[0]} devolvio {exc.code}: {detail}",
              flush=True)
        raise GitHubError(f"github {exc.code}") from exc
    except (OSError, ValueError) as exc:
        print(f"  [github] no se pudo hablar con GitHub: {type(exc).__name__}", flush=True)
        raise GitHubError("github unreachable") from exc


def _api(url: str, token: str) -> Any:
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    return _json(request)


def primary_email(emails: Any) -> tuple[str, bool]:
    """El correo principal de la lista de GitHub, y si está verificado. Uno que
    no es el principal no cuenta, aunque esté verificado."""
    for one in emails if isinstance(emails, list) else []:
        if isinstance(one, dict) and one.get("primary") is True and one.get("email"):
            return str(one["email"]).strip()[:254], one.get("verified") is True
    return "", False


def who(code: str, *, verifier: str, redirect_uri: str) -> dict[str, Any]:
    """Cambiar el código por un token y preguntarle a GitHub quién es.

    Devuelve `sub` (el identificador de la cuenta), `email`, `email_verified` y
    `name`, como `google_auth.who()`."""
    body = urllib.parse.urlencode({
        "client_id": Config.GITHUB_CLIENT_ID,
        "client_secret": Config.GITHUB_CLIENT_SECRET,
        "code": code, "redirect_uri": redirect_uri, "code_verifier": verifier,
    }).encode("ascii")
    request = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    answer = _json(request)
    # GitHub contesta 200 también cuando el código no vale, con un `error`.
    token = answer.get("access_token") if isinstance(answer, dict) else None
    if not token:
        raise GitHubError(f"github: sin token ({(answer or {}).get('error', '')})"
                          if isinstance(answer, dict) else "github: sin token")

    user = _api(USER_URL, token)
    if not isinstance(user, dict) or not user.get("id"):
        raise GitHubError("github: sin identidad")
    email, verified = primary_email(_api(EMAILS_URL, token))
    if not email:
        # Sin correo principal en la lista: sin verificar, y no entra.
        verified = False
    return {"sub": str(user["id"])[:64], "email": email, "email_verified": verified,
            "name": str(user.get("name") or user.get("login") or "").strip()[:120]}
