"""Plantillas: las prediseñadas del producto y el HTML que sube el cliente.

Dos reglas de CLAUDE.md mandan aquí:

  * **Subir HTML propio es de Negocio en adelante**, y eso lo dice
    `docs/pricing.md`, no una lista copiada a este archivo. El Básico ve las
    prediseñadas y una línea que explica desde qué plan se puede subir.
  * **Cada subida se revisa al entrar**, y esa revisión es automática y es la
    única que hay sobre el archivo. La mirada de una persona ocurre una vez por
    cuenta, antes de su primera campaña, y es sobre de dónde salió su lista, no
    sobre el HTML.

El HTML subido **no se dibuja dentro del panel**. Es de otro y puede traer
cualquier cosa; enseñarlo aquí sería meter el documento de un cliente dentro de
una página nuestra con su sesión abierta. La pantalla enseña qué es y cuánto
pesa.

Las prediseñadas sí se dibujan, porque el HTML es nuestro y lo que escribió el
cliente va escapado. Aun así van dentro de un marco aislado: el texto de dentro
es de otro y esta página lleva una sesión abierta.
"""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, Response, abort, g, redirect, render_template,
                   request, url_for)

from blueprints.auth.routes import current_account, not_for_admins
from db import get_db
from i18n import TEXTS, t
from models import account as accounts
from models import design as designs
from models import image as images
from services import fields as columns
from services import html_check, imaging, plans, render
from services.security import csrf_ok

bp = Blueprint("designs", __name__)

@bp.before_request
def keep_admins_out():
    """Un administrador no tiene plantillas que mirar, así que vuelve a /admin.

    Va aquí y no en un decorador por ruta: esta pantalla tiene varias y una
    nueva heredaría la puerta sin que nadie se acuerde de ponérsela.
    """
    return not_for_admins(current_account())


def signed_in():
    return current_account()


def offered() -> list[dict[str, str]]:
    """Las prediseñadas que se pueden elegir, en el orden en que se ofrecen.

    El nombre lo declara cada archivo y la explicación está en `i18n.py`. Una
    plantilla nueva sin esa línea se ofrece igual, sin explicación: agregar la
    quinta sigue siendo dejar caer un archivo.
    """
    return [{"key": key, "name": one["label"],
             "text": TEXTS.get("designs_tpl_" + key, "")}
            for key, one in render.TEMPLATE_LIST.items()]


def label_of(name: str) -> str:
    """Cómo se llama una casilla en la pantalla.

    Los bloques del boletín se numeran solos, para no repetir doce líneas de
    traducción que solo se diferencian en un número.
    """
    if name.startswith("bloque") and "_" in name:
        head, _, rest = name.partition("_")
        return t("designs_field_block", n=head[len("bloque"):],
                 what=TEXTS.get("designs_field_" + rest, rest).lower())
    return TEXTS.get("designs_field_" + name, name)


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
    """Lo que toda la pantalla necesita: qué permite el plan y qué hay guardado."""
    plan = accounts.plan_of(account)
    mine = designs.for_account(db, account["_id"])
    return {
        "account": account,
        "built_in": offered(),
        # Las llenas y las subidas se enseñan aparte: una se edita y la otra se
        # baja, y no tienen ni las mismas columnas ni los mismos botones.
        "filled": [one for one in mine
                   if one.get("source") == designs.BUILT_IN],
        "uploaded": [one for one in mine
                     if one.get("source") != designs.BUILT_IN],
        "named": {one["key"]: one["name"] for one in offered()},
        "can_upload": plans.can_upload(plan),
        # A quién ofrecerle el salto cuando su plan todavía no puede.
        "upload_plan": plan_needed(),
        "max_kb": html_check.MAX_BYTES // 1024,
        # Las columnas propias de la cuenta, para poder escribirlas dentro de
        # una pieza sin tener que acordarse de cómo se llamaban.
        "columns": accounts.fields_of(account),
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
                # Pasó el validador, así que queda lista. Lo que se revisa a
                # mano es la cuenta, una vez, antes de su primera campaña.
                designs.save(db, account["_id"],
                             name=name or archivo.filename,
                             html=raw.decode("utf-8"),
                             uploaded_by=account["_id"])
                return redirect(url_for("designs.index", guardado=1))

    return render_template(
        "designs/index.html", section="plantillas",
        **shared(db, account, errors=errors,
                 saved=bool(request.args.get("guardado")),
                 updated=bool(request.args.get("cambiado"))))


# --------------------------------------------------- llenar una prediseñada

def mine_only(db, account_id, key: str,
              filled: dict[str, str]) -> dict[str, str]:
    """Deja en las casillas de imagen solo las que son de esta cuenta.

    El nombre de la imagen viaja en un campo escondido del formulario, y un
    campo escondido lo puede escribir cualquiera. Sin esto, el correo de un
    cliente podría acabar enseñando la imagen de otro, o pidiéndosela a un
    servidor ajeno con la dirección de quien lo abra.
    """
    for field in render.fields_of(key):
        if field.get("type") != "image":
            continue
        name = field["name"]
        value = filled.get(name) or ""
        if value and not (imaging.valid_name(value)
                          and images.owns(db, account_id, value)):
            filled[name] = ""
    return filled


def images_in(found) -> list[str]:
    """Las imágenes que nombra una pieza guardada.

    Se le pregunta a la plantilla cuáles de sus casillas son imágenes, en vez
    de adivinarlo mirando el contenido: la plantilla es quien lo sabe.
    """
    fields = found.get("fields") or {}
    return [fields[one["name"]]
            for one in render.fields_of(found.get("template", ""))
            if one.get("type") == "image" and fields.get(one["name"])]


# Qué se le dice al cliente por cada motivo por el que una imagen no entra.
# Los motivos los pone services/imaging.py como claves y no como frases, para
# que la misma razón se lea igual desde cualquier pantalla.
IMAGE_PROBLEMS = {
    "not_image": "designs_image_bad",
    "unreadable": "designs_image_bad",
    "too_many_pixels": "designs_image_bad",
    "gif_too_big": "designs_image_gif",
    "too_big": "designs_image_big",
}


def keep_image(db, account, which: str, current: str,
               errors: dict[str, str]) -> str:
    """Guardar la imagen que acaba de elegir, y decir qué pasó si no se pudo.

    Si algo falla se queda la que había: perder la anterior por intentar
    cambiarla sería castigar el intento.
    """
    archivo = request.files.get("archivo_" + which)
    if not archivo or not archivo.filename:
        errors[which] = t("error_required")
        return current

    if images.count(db, account["_id"]) >= images.LIMIT:
        errors[which] = t("designs_image_limit", n=images.LIMIT)
        return current

    raw = archivo.read(imaging.MAX_UPLOAD + 1)
    if len(raw) > imaging.MAX_UPLOAD:
        errors[which] = t("designs_image_heavy",
                          mb=imaging.MAX_UPLOAD // (1024 * 1024))
        return current
    try:
        # Se mira lo que trae dentro y no cómo se llama —un archivo llamado
        # .png puede ser cualquier cosa— y sale achicada al ancho al que la
        # dibuja la plantilla, que es lo que hace que quepa en la base.
        data, ext, mime = imaging.shrink(raw)
    except imaging.ImageError as exc:
        errors[which] = t(IMAGE_PROBLEMS.get(str(exc), "designs_image_bad"),
                          kb=imaging.STORED_MAX // 1024)
        return current
    return images.save(db, account["_id"], data=data, ext=ext, mime=mime)


def preview(key: str, filled: dict[str, str], plan,
            fields: list[dict] | None = None) -> Response:
    """El correo entero, tal como saldría, para dibujarlo en el marco aislado.

    Lleva sus propias cabeceras —las pone `app.py` al ver esta marca—: un
    correo necesita justo lo que el panel prohíbe, estilos en línea e imágenes
    de nuestro almacén.

    Las columnas propias se dibujan **con su respaldo**, que es exactamente lo
    que va a recibir quien no tenga ese dato: la vista previa enseña el caso
    peor y no uno inventado que siempre se ve bien.
    """
    g.email_preview = True
    fields = fields or []
    html = render.email(key, filled, plan=plan, preview=True)
    return Response(columns.fill(html, columns.sample(fields), fields),
                    mimetype="text/html")


def compose(account, key: str, found):
    """La pantalla de llenar, la misma para una nueva y para una guardada.

    Un solo formulario y varios botones: guardar, ver cómo queda, y subir o
    quitar cada imagen. El que se pulsó llega en `accion`, así que todo lo
    escrito sobrevive a cualquiera de ellos.
    """
    db = get_db()
    errors: dict[str, str] = {}
    plan = accounts.plan_of(account)
    filled = (render.clean(key, found.get("fields") or {}) if found
              else {one["name"]: "" for one in render.fields_of(key)})
    name = found.get("name", "") if found else ""

    if request.method == "POST":
        filled = mine_only(db, account["_id"], key,
                           render.clean(key, request.form))
        name = designs.clean_name(
            request.form.get("nombre") or filled.get("titulo", ""))
        action, _, which = request.form.get("accion", "").partition(":")

        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif action == "vista":
            return preview(key, filled, plan, accounts.fields_of(account))
        elif action == "imagen":
            filled[which] = keep_image(db, account, which,
                                       filled.get(which, ""), errors)
        elif action == "quitar":
            # La imagen no se borra del almacén aquí: si la pieza guardada
            # todavía la nombra y esto no llega a guardarse, la dejaríamos
            # rota. Se borran todas juntas cuando se borra la pieza.
            filled[which] = ""
        else:
            empty = render.missing(key, filled)
            if empty:
                errors["form"] = t("designs_fill_missing")
                for one in empty:
                    errors[one] = t("error_required")
            elif found is None:
                designs.save_filled(db, account["_id"], name=name,
                                    template=key, filled=filled)
                return redirect(url_for("designs.index", guardado=1))
            else:
                designs.update_filled(db, account["_id"], found["_id"],
                                      name=name, filled=filled)
                return redirect(url_for("designs.index", cambiado=1))

    return render_template(
        "designs/fill.html", section="plantillas", account=account,
        template_key=key, template_name=render.TEMPLATE_LIST[key]["label"],
        # La dirección de la miniatura se arma aquí y no en la plantilla,
        # con la misma cuenta que hace `render` para el correo.
        fields=[dict(one, label=label_of(one["name"]),
                     value=filled.get(one["name"], ""),
                     url=(imaging.url_of(filled.get(one["name"], ""))
                          if one.get("type") == "image" else ""))
                for one in render.fields_of(key)],
        name=name, errors=errors, found=found,
        columns=accounts.fields_of(account),
        image_mb=imaging.MAX_UPLOAD // (1024 * 1024),
        watermark=plans.has_watermark(plan))


@bp.route("/plantillas/nueva/<key>", methods=["GET", "POST"])
def new(key):
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    if not render.known(key):
        abort(404)
    return compose(account, key, None)


@bp.route("/plantillas/pieza/<raw>", methods=["GET", "POST"])
def piece(raw):
    """Volver a abrir una guardada. La cuenta va en la consulta, siempre."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    design_id = as_id(raw)
    found = (designs.by_id(get_db(), account["_id"], design_id)
             if design_id else None)
    if (found is None or found.get("source") != designs.BUILT_IN
            or not render.known(found.get("template", ""))):
        abort(404)
    return compose(account, found["template"], found)


@bp.route("/plantillas/borrar", methods=["POST"])
def remove():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        design_id = as_id(request.form.get("id"))
        if design_id:
            db = get_db()
            gone = designs.remove(db, account["_id"], design_id)
            if gone:
                # Las imágenes se van con la pieza: dejarlas sería guardar
                # para siempre lo que alguien pidió borrar.
                images.remove(db, account["_id"], images_in(gone))
    return redirect(url_for("designs.index"))
