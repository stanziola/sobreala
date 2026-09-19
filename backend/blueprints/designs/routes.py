"""Plantillas: las que carga el cliente en HTML, y las prediseñadas de antes.

Dos reglas de CLAUDE.md mandan aquí:

  * **Cargar HTML propio es de Negocio en adelante**, y eso lo dice
    `docs/pricing.md`, no una lista copiada a este archivo. Con otro plan el
    botón sale apagado, y la ruta lo comprueba igual.
  * **Cada HTML se revisa al entrar y cada vez que se guarda**, y esa revisión
    es automática y es la única que hay sobre el archivo. La mirada de una
    persona ocurre una vez por cuenta, antes de su primera campaña, y es sobre
    de dónde salió su lista, no sobre el HTML.

El HTML de un cliente **se dibuja solo para él, y solo en un marco aislado**:
sin permiso para ejecutar nada, con origen opaco y con su propia cabecera de
seguridad, y después de pasar el validador. Es lo que deja editarlo viendo cómo
queda. El panel del administrador sigue sin dibujarlo: lo baja como texto.

Las prediseñadas ya no se ofrecen. Las piezas que alguien armó con ellas siguen
en su lista y se editan con el formulario de siempre.
"""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, Response, abort, g, jsonify, redirect,
                   render_template, request, url_for)
from markupsafe import escape

from blueprints.auth.routes import (current_account, current_workspace, needs,
                                    not_for_admins)
from db import get_db
from i18n import TEXTS, t
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import image as images
from services import fields as columns
from services import canvas, html_check, imaging, plans, render
from services.security import csrf_ok

bp = Blueprint("designs", __name__)

@bp.before_request
def keep_out():
    """Quién no entra aquí: un administrador, que no tiene plantillas que
    mirar, y un usuario de una cuenta sin ese permiso.

    Va aquí y no en un decorador por ruta: esta pantalla tiene varias y una
    nueva heredaría la puerta sin que nadie se acuerde de ponérsela.
    """
    account = current_account()
    return not_for_admins(account) or needs(account, accounts.DESIGNS)


def signed_in():
    """La cuenta de la empresa: las plantillas son suyas, también cuando las
    arma un usuario que ella creó."""
    return current_workspace()


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


def marks_for(account) -> list[dict]:
    """Los botones de marcas: el nombre y el correo, que trae todo contacto, y
    después las columnas de la cuenta."""
    return columns.built_in_marks() + accounts.fields_of(account)


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def shared(db, account, **extra):
    """Lo que toda la pantalla necesita: qué permite el plan y qué hay guardado."""
    plan = accounts.plan_of(account)
    return {
        "account": account,
        # Todas juntas: da igual de dónde salió cada una, se editan, se
        # duplican y se borran desde la misma fila.
        "mine": designs.for_account(db, account["_id"]),
        "named": {one["key"]: one["name"] for one in offered()},
        "can_upload": plans.can_upload(plan),
        # A quién ofrecerle el salto cuando su plan todavía no puede.
        "upload_plan": plan_needed(),
        "max_kb": html_check.MAX_BYTES // 1024,
        # Las columnas propias de la cuenta, para poder escribirlas dentro de
        # una pieza sin tener que acordarse de cómo se llamaban.
        "columns": marks_for(account),
        **extra,
    }


@bp.route("/plantillas")
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    return render_template(
        "designs/index.html", section="plantillas",
        **shared(get_db(), account, errors={},
                 saved=bool(request.args.get("guardado")),
                 updated=bool(request.args.get("cambiado")),
                 copied=bool(request.args.get("copia"))))


@bp.route("/plantillas/cargar", methods=["GET", "POST"])
def upload():
    """Cargar un HTML. Con JavaScript el formulario sale en una bandeja encima
    de la lista; sin él, esta es su página. Las dos mandan aquí."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}
    if not plans.can_upload(accounts.plan_of(account)):
        # El plan se comprueba en el servidor y no solo apagando el botón:
        # esconder un botón no es un permiso.
        errors["form"] = t("designs_locked", plan=plan_needed())
    elif request.method == "POST":
        archivo = request.files.get("archivo")
        name = designs.clean_name(request.form.get("nombre", ""))
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
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
                new_id = designs.save(db, account["_id"],
                                      name=name or archivo.filename,
                                      html=raw.decode("utf-8"),
                                      uploaded_by=account["_id"])
                # Directo al editor: lo siguiente que se quiere es verla y
                # ponerle las columnas.
                return redirect(url_for("designs.edit_html", raw=new_id,
                                        nueva=1))

    return render_template("designs/upload.html", section="plantillas",
                           **shared(db, account, errors=errors))


# --------------------------------------------------------- editar un HTML

def html_preview(html: str, plan) -> Response:
    """El HTML del cliente como saldría, para el marco aislado de al lado.

    Pasa por el validador antes de dibujarse: lo que no se puede guardar
    tampoco se enseña, y en su lugar sale por qué. Lleva la cabecera de un
    correo (la pone `app.py` al ver `email_preview`), que no deja ejecutar
    nada, y el marco no tiene permiso para scripts ni origen propio.
    """
    g.email_preview = True
    problems = html_check.check(html.encode("utf-8"))
    if problems:
        page = ("<!doctype html><meta charset=\"utf-8\">"
                "<body style=\"font-family:Arial,sans-serif;padding:24px;"
                "color:#18181B;\"><p>" + escape(explain(problems)) + "</p>")
        return Response(page, mimetype="text/html")
    email = render.email_from_html(html, plan=plan, preview=True,
                                   postal=accounts.postal_of(current_workspace()))
    return Response(filled_for(get_db(), current_workspace(), email),
                    mimetype="text/html")


def filled_for(db, account, email: str) -> str:
    """La vista previa con las marcas llenas: con los datos del contacto que se
    eligió al lado, o con el nombre de cada columna en una pastilla.

    El contacto se busca con la cuenta en la consulta: el de otra cuenta no
    encuentra nada y la vista sale con las pastillas.
    """
    fields = accounts.fields_of(account)
    wanted = as_id(request.form.get("contacto"))
    person = contacts.by_id(db, account["_id"], wanted) if wanted else None
    if person is None:
        return columns.preview_fill(email, fields)
    return columns.fill(email, person, fields)


@bp.route("/plantillas/html/<raw>", methods=["GET", "POST"])
def edit_html(raw):
    """El código a un lado y cómo queda al otro. La cuenta va en la consulta."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    design_id = as_id(raw)
    found = designs.by_id(db, account["_id"], design_id) if design_id else None
    if found is None or found.get("source") != designs.UPLOAD:
        abort(404)

    errors: dict[str, str] = {}
    plan = accounts.plan_of(account)
    html = found.get("html", "")
    name = found.get("name", "")

    if request.method == "POST":
        html = request.form.get("html", "")
        name = designs.clean_name(request.form.get("nombre", "")) or name
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif request.form.get("accion") == "vista":
            return html_preview(html, plan)
        elif not plans.can_upload(plan):
            # Quien bajó de plan conserva lo que cargó y lo puede seguir
            # usando, pero cambiar el HTML es cargar HTML.
            errors["form"] = t("designs_locked", plan=plan_needed())
        else:
            problems = html_check.check(html.encode("utf-8"))
            if problems:
                errors["html"] = explain(problems)
            else:
                designs.update_html(db, account["_id"], found["_id"],
                                    name=name, html=html)
                return redirect(url_for("designs.index", cambiado=1))

    return render_template(
        "designs/html.html", section="plantillas", account=account,
        found=found, html=html, name=name, errors=errors,
        fresh=bool(request.args.get("nueva")),
        columns=marks_for(account),
        people=contacts.for_preview(db, account["_id"]),
        max_kb=html_check.MAX_BYTES // 1024,
        kb=round(len(html.encode("utf-8")) / 1024, 1),
        watermark=plans.has_watermark(plan))


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

    En un lienzo, sus fotos y sus fondos fundidos. En una prediseñada, se le
    pregunta a la plantilla cuáles de sus casillas son imágenes, en vez de
    adivinarlo mirando el contenido: la plantilla es quien lo sabe.
    """
    if found.get("source") == designs.CANVAS:
        return (canvas.images_of(found.get("canvas"))
                + [one for one in found.get("backgrounds") or [] if one])
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
    html = render.email(key, filled, plan=plan, preview=True,
                        postal=accounts.postal_of(current_workspace()))
    return Response(columns.preview_fill(html, fields),
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
        columns=marks_for(account),
        image_mb=imaging.MAX_UPLOAD // (1024 * 1024),
        watermark=plans.has_watermark(plan))


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


# --------------------------------------------------------------- el lienzo

def drop_unused(db, account_id, names) -> None:
    """Borrar las imágenes que ya no nombra ninguna pieza de la cuenta.

    Se pregunta a todas y no solo a la que cambió: al duplicar, la copia y la
    original nombran las mismas.
    """
    still = {name for one in designs.for_account(db, account_id, limit=0)
             for name in images_in(one)}
    images.remove(db, account_id, [one for one in names if one and one not in still])


def canvas_problems(db, account_id, doc) -> list[str]:
    return canvas.problems(
        doc, owns=lambda name: (imaging.valid_name(name)
                                and images.owns(db, account_id, name)))


def canvas_explain(problems: list[str]) -> str:
    return " ".join(t("canvas_bad_" + one, kb=html_check.MAX_BYTES // 1024)
                    for one in problems)


def canvas_email(doc, plan, urls: list[str | None], shades=None, *,
                 unsubscribe: str = "#", preview: bool = False) -> str:
    """El correo entero de un lienzo: el cuerpo, el sobre y las reglas del modo
    oscuro. Lo mismo que arma el envío (`sender.Piece`)."""
    return render.email_from_body(canvas.to_html(doc, urls, shades), plan=plan,
                                  unsubscribe=unsubscribe, preview=preview,
                                  style=canvas.dark_css(doc, shades),
                                  postal=accounts.postal_of(current_workspace()))


def canvas_size(doc, plan, urls: list[str | None]) -> int:
    """Lo que pesa el correo entero, con el sobre y la baja, que es lo que
    cuenta Gmail para recortarlo."""
    email = canvas_email(doc, plan, urls, [doc["bg"]] * len(urls),
                         unsubscribe=UNSUBSCRIBE_SAMPLE)
    return len(email.encode("utf-8"))


# Una dirección de baja del largo de las de verdad, para pesar el correo.
UNSUBSCRIBE_SAMPLE = "https://panel.panamails.com/baja/" + "x" * 96


def sample_grounds(doc) -> list[str | None]:
    """Direcciones de imagen del mismo largo que las que tendrá al guardarse."""
    sample = imaging.url_of("x" * 22 + ".jpg")
    return [sample if one["kind"] in ("picture", "backdrop") else None
            for one in canvas.groups(doc)]


def review_texts(found: list[dict]) -> list[str]:
    return [t("canvas_spam_" + one["key"], **{k: v for k, v in one.items() if k != "key"})
            for one in found]


def canvas_editor(account, found):
    """El lienzo, el mismo para una nueva y para una guardada.

    Si algo no se puede guardar, la pantalla vuelve con lo que se mandó y no con
    lo guardado: perder el trabajo por un texto encimado sería castigar el
    intento.
    """
    db = get_db()
    errors: dict[str, str] = {}
    doc = (canvas.read(found.get("canvas")) if found else None) or canvas.blank()
    name = found.get("name", "") if found else ""

    if request.method == "POST":
        name = designs.clean_name(request.form.get("nombre", "")) or name
        posted = canvas.parse(request.form.get("lienzo", ""))
        doc = posted or doc
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        else:
            problems = canvas_problems(db, account["_id"], posted)
            spam = [] if problems or posted is None else canvas.review(
                posted, canvas_size(posted, accounts.plan_of(account),
                                    sample_grounds(posted)),
                limit=html_check.MAX_BYTES)
            if not name:
                errors["nombre"] = t("error_required")
            if problems:
                errors["form"] = canvas_explain(problems)
            elif spam:
                # Solo se guarda lo que tiene pocas probabilidades de ir a spam.
                errors["form"] = " ".join(review_texts(spam))
            elif not errors:
                load = lambda one: images.data_of(db, account["_id"], one)  # noqa: E731
                grounds, shades = canvas.store(db, account["_id"], posted, load)
                html = canvas.to_html(posted, [imaging.url_of(one) if one else None
                                               for one in grounds], shades)
                if len(html.encode("utf-8")) > html_check.MAX_BYTES:
                    images.remove(db, account["_id"], grounds)
                    errors["form"] = canvas_explain(["too_big"])
                else:
                    if found is None:
                        designs.save_canvas(db, account["_id"], name=name,
                                            doc=posted, backgrounds=grounds,
                                            shades=shades)
                        return redirect(url_for("designs.index", guardado=1))
                    designs.update_canvas(db, account["_id"], found["_id"],
                                          name=name, doc=posted, backgrounds=grounds,
                                          shades=shades)
                    drop_unused(db, account["_id"], found.get("backgrounds") or [])
                    return redirect(url_for("designs.index", cambiado=1))

    return render_template(
        "designs/canvas.html", section="plantillas", account=account,
        found=found, doc=doc, name=name, errors=errors,
        fonts=list(canvas.FONTS), font_stacks=canvas.FONTS,
        columns=marks_for(account),
        people=contacts.for_preview(db, account["_id"]),
        limits={"minSize": canvas.MIN_SIZE, "maxSize": canvas.MAX_SIZE,
                "minHeight": canvas.MIN_HEIGHT, "maxHeight": canvas.MAX_HEIGHT,
                "maxItems": canvas.MAX_ITEMS, "altMax": canvas.ALT_MAX,
                "width": canvas.WIDTH},
        image_mb=imaging.MAX_UPLOAD // (1024 * 1024),
        watermark=plans.has_watermark(accounts.plan_of(account)))


@bp.route("/plantillas/crear", methods=["GET", "POST"])
def create():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    return canvas_editor(account, None)


@bp.route("/plantillas/lienzo/<raw>", methods=["GET", "POST"])
def edit_canvas(raw):
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    design_id = as_id(raw)
    found = (designs.by_id(get_db(), account["_id"], design_id)
             if design_id else None)
    if found is None or found.get("source") != designs.CANVAS:
        abort(404)
    return canvas_editor(account, found)


@bp.route("/plantillas/lienzo/revisar", methods=["POST"])
def canvas_review():
    """Cuánto pesa y qué le falta para no ir a spam. Lo pide el editor mientras
    se trabaja, para la barra y la lista; es la misma revisión que al guardar."""
    account = signed_in()
    if account is None or not csrf_ok(request.form.get("csrf_token")):
        abort(403)
    db = get_db()
    doc = canvas.parse(request.form.get("lienzo", ""))
    if doc is None:
        return jsonify(ok=False, bytes=0, max=html_check.MAX_BYTES,
                       issues=[canvas_explain(["broken"])])
    size = canvas_size(doc, accounts.plan_of(account), sample_grounds(doc))
    problems = canvas_problems(db, account["_id"], doc)
    issues = ([canvas_explain([one]) for one in problems]
              + review_texts(canvas.review(doc, size, limit=html_check.MAX_BYTES)))
    return jsonify(ok=not issues, bytes=size, max=html_check.MAX_BYTES,
                   issues=issues)


@bp.route("/plantillas/lienzo/vista", methods=["POST"])
def canvas_preview():
    """El lienzo como saldría, para el marco de al lado. Los fondos van dentro
    de la respuesta: mirar cómo queda no guarda nada."""
    account = signed_in()
    if account is None or not csrf_ok(request.form.get("csrf_token")):
        abort(403)
    db = get_db()
    g.email_preview = True
    doc = canvas.parse(request.form.get("lienzo", ""))
    if doc is None:
        return Response("", mimetype="text/html")
    # Solo las imágenes de esta cuenta: `data_of` pregunta con ella.
    load = lambda one: images.data_of(db, account["_id"], one)  # noqa: E731
    made = canvas.parts(doc, load)
    email = canvas_email(doc, accounts.plan_of(account),
                         [canvas.data_url(raw) if raw else None for raw in made],
                         [canvas.average(raw, doc["bg"]) if raw else None
                          for raw in made], preview=True)
    return Response(filled_for(db, account, email), mimetype="text/html")


# El ancho al que se guardan las fotos del lienzo: al doble de lo que se ven, para
# que el fondo fundido salga nítido en un teléfono.
CANVAS_PHOTO_WIDTH = canvas.WIDTH * canvas.SCALE


@bp.route("/plantillas/lienzo/imagen", methods=["POST"])
def canvas_image():
    """Subir una foto al lienzo. Contesta en JSON: la pide el editor."""
    account = signed_in()
    if account is None:
        abort(403)
    if not csrf_ok(request.form.get("csrf_token")):
        return jsonify(error=t("error_csrf")), 400
    db = get_db()
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return jsonify(error=t("error_required")), 400
    if images.count(db, account["_id"]) >= images.LIMIT:
        return jsonify(error=t("designs_image_limit", n=images.LIMIT)), 400
    raw = archivo.read(imaging.MAX_UPLOAD + 1)
    if len(raw) > imaging.MAX_UPLOAD:
        return jsonify(error=t("designs_image_heavy",
                               mb=imaging.MAX_UPLOAD // (1024 * 1024))), 400
    try:
        # Sin los bordes transparentes: la caja queda justo en lo que se ve.
        data, ext, mime = imaging.shrink(imaging.trim(raw), width=CANVAS_PHOTO_WIDTH)
    except imaging.ImageError as exc:
        return jsonify(error=t(IMAGE_PROBLEMS.get(str(exc), "designs_image_bad"),
                               kb=imaging.STORED_MAX // 1024)), 400
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(data)) as opened:
        width, height = opened.size
    name = images.save(db, account["_id"], data=data, ext=ext, mime=mime)
    return jsonify(name=name, url=imaging.url_of(name), width=width, height=height)


@bp.route("/plantillas/duplicar", methods=["POST"])
def copy():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        design_id = as_id(request.form.get("id"))
        db = get_db()
        found = designs.by_id(db, account["_id"], design_id) if design_id else None
        if found is not None:
            designs.duplicate(db, account["_id"], found["_id"],
                              name=t("designs_copy_name", name=found.get("name", "")))
            return redirect(url_for("designs.index", copia=1))
    return redirect(url_for("designs.index"))


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
                # para siempre lo que alguien pidió borrar. Menos las que
                # todavía nombra otra, que es lo que deja una copia al
                # duplicar.
                drop_unused(db, account["_id"], images_in(gone))
    return redirect(url_for("designs.index"))
