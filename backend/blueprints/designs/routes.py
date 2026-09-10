"""Plantillas: las prediseñadas del producto y el HTML que sube el cliente.

Dos reglas de CLAUDE.md mandan aquí:

  * **Subir HTML propio es de Negocio en adelante**, y eso lo dice
    `docs/pricing.md`, no una lista copiada a este archivo. El Básico ve las
    prediseñadas y una línea que explica desde qué plan se puede subir.
  * **Cada subida se revisa al entrar**, y la primera de cada cliente la aprueba
    un administrador. Lo que se revisa la primera vez no es el archivo: es si
    esa organización sabe lo que está mandando.

El HTML subido **no se dibuja dentro del panel**. Es de otro y puede traer
cualquier cosa; enseñarlo aquí sería meter el documento de un cliente dentro de
una página nuestra con su sesión abierta. La pantalla enseña qué es, cuánto pesa
y en qué estado está.
"""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, redirect, render_template, request, url_for)

from blueprints.auth.routes import current_account
from db import get_db
from i18n import t
from models import account as accounts
from models import design as designs
from services import html_check, plans
from services.security import csrf_ok

bp = Blueprint("designs", __name__)

# Las prediseñadas del producto: iguales para todos y sin nada que aprobar.
# Todavía no hay ninguna hecha; la lista existe para que la pantalla tenga su
# forma definitiva desde ahora y solo haya que llenarla.
BUILT_IN: list[dict[str, str]] = []


def signed_in():
    return current_account()


def plan_needed() -> str:
    """El nombre del plan más barato que sí puede subir HTML."""
    key = plans.first_upload_plan() or ""
    return plans.PLANS.get(key, {}).get("name", "")


def explain(problems: list[str]) -> str:
    """Los motivos, en la frase que lee el cliente.

    El validador devuelve claves y no frases, para que el mismo motivo se lea
    igual aquí y en el panel del administrador.
    """
    said: list[str] = []
    for reason in problems:
        head, _, detail = reason.partition(":")
        text = t("designs_bad_" + head, what=detail,
                 kb=html_check.MAX_BYTES // 1024)
        if text not in said:
            said.append(text)
    return " ".join(said)


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def shared(db, account, **extra):
    """Lo que toda la pantalla necesita: qué permite el plan y qué hay subido."""
    plan = accounts.plan_of(account)
    return {
        "account": account,
        "built_in": BUILT_IN,
        "mine": designs.for_account(db, account["_id"]),
        "can_upload": plans.can_upload(plan),
        # A quién ofrecerle el salto cuando su plan todavía no puede.
        "upload_plan": plan_needed(),
        "max_kb": html_check.MAX_BYTES // 1024,
        **extra,
    }


@bp.route("/plantillas", methods=["GET", "POST"])
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}

    if request.method == "POST":
        archivo = request.files.get("archivo")
        name = designs.clean_name(request.form.get("nombre", ""))

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not plans.can_upload(accounts.plan_of(account)):
            # El plan se comprueba en el servidor y no solo escondiendo el
            # formulario: esconder un botón no es un permiso.
            errors["form"] = t("designs_locked", plan=plan_needed())
        elif not archivo or not archivo.filename:
            errors["archivo"] = t("error_required")
        else:
            raw = archivo.read(html_check.MAX_BYTES + 1)
            problems = html_check.check(raw)
            if problems:
                errors["archivo"] = explain(problems)
            else:
                # La primera de cada cliente espera revisión; después queda
                # habilitado y las siguientes entran aprobadas.
                status = (designs.APPROVED
                          if designs.approved_before(db, account["_id"])
                          else designs.PENDING)
                designs.save(db, account["_id"],
                             name=name or archivo.filename,
                             html=raw.decode("utf-8"), status=status,
                             uploaded_by=account["_id"])
                return redirect(url_for("designs.index", guardado=status))

    # Qué decir arriba al volver: aprobada y lista, o subida y en revisión.
    saved = request.args.get("guardado")
    return render_template(
        "designs/index.html", section="plantillas",
        **shared(db, account, errors=errors,
                 saved=saved if saved in (designs.APPROVED, designs.PENDING) else None))


@bp.route("/plantillas/borrar", methods=["POST"])
def remove():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        design_id = as_id(request.form.get("id"))
        if design_id:
            designs.remove(get_db(), account["_id"], design_id)
    return redirect(url_for("designs.index"))
