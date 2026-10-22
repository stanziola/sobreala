"""Plantillas: el lienzo, y las que se cargaron en HTML y las prediseñadas de
antes.

  * **El HTML propio ya no se carga** (septiembre de 2026): las plantillas se
    arman en el lienzo, y lo que se carga es el ZIP de un lienzo, que se abre
    en el editor tal como estaba. Las cargadas antes siguen en su lista y se
    editan como código.
  * **Cada HTML se revisa cada vez que se guarda**, y esa revisión es
    automática y es la única que hay sobre el archivo. La mirada de una persona
    ocurre una vez por cuenta, antes de su primera campaña, y es sobre de dónde
    salió su lista, no sobre el HTML.

El HTML de un cliente **se dibuja solo para él, y solo en un marco aislado**:
sin permiso para ejecutar nada, con origen opaco y con su propia cabecera de
seguridad, y después de pasar el validador. Es lo que deja editarlo viendo cómo
queda. El panel del administrador sigue sin dibujarlo: lo baja como texto.

Las prediseñadas ya no se ofrecen. Las piezas que alguien armó con ellas siguen
en su lista y se editan con el formulario de siempre.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, Response, abort, g, jsonify, redirect,
                   render_template, request, url_for)
from markupsafe import escape

from blueprints.auth.routes import (SAMPLE_NAME, current_account,
                                    current_workspace, is_prefetch, needs,
                                    not_for_admins)
from db import get_db
from i18n import CANVAS_KEYS, TEXTS, t
from models import account as accounts
from models import contact as contacts
from models import design as designs
from models import image as images
from services import fields as columns
from services import canvas, html_check, imaging, pieces, plans, render
from services import canvas_pdf as canvas_pdf_service
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
    # Sin sesión, una muestra va a entrar ella misma, recordando cuál era:
    # la puerta de aquí la mandaría a Seguridad y se perdería.
    if account is None and request.endpoint == "designs.sample":
        return None
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
    """Lo que toda la pantalla necesita."""
    return {"account": account, **extra}


def editor_url(one) -> str:
    """Dónde se edita cada clase de plantilla: el lienzo, el HTML cargado
    antes o la prediseñada de antes."""
    if one.get("source") == designs.CANVAS:
        return url_for("designs.edit_canvas", raw=one["_id"])
    if one.get("source") == designs.UPLOAD:
        return url_for("designs.edit_html", raw=one["_id"])
    return url_for("designs.piece", raw=one["_id"])


def listed_at(account, folder_id, **args) -> str:
    """A dónde se vuelve después de guardar, duplicar, mover o borrar: a la
    carpeta donde estaba, si todavía existe, y si no a Mis plantillas."""
    if designs.folder_of(account, folder_id) is not None:
        return url_for("designs.folder", raw=folder_id, **args)
    return url_for("designs.index", **args)


def sending_choice(account) -> dict | None:
    """La elección de «Sale de» y «Responder a» que llegó al guardar (octubre
    de 2026): solo un remitente que pueda salir y una dirección confirmada de
    esta cuenta; lo demás es el predeterminado. None si el formulario no trae
    las listas."""
    if "remitente" not in request.form and "responder" not in request.form:
        return None
    raw = request.form.get("remitente", "")
    found = accounts.from_of(account, as_id(raw)) if raw else None
    reply = request.form.get("responder", "")
    return {"send_from": found["id"] if found and found["ready"] else None,
            "reply_to": reply if reply in accounts.reply_tos_of(account) else None}


def sending_context(account, found, choice=None) -> dict:
    """Lo que necesitan las dos listas de un editor: lo que se puede elegir, los
    predeterminados y lo elegido (lo que llegó, si vuelve con un error)."""
    chosen = choice if choice is not None else {
        "send_from": (found or {}).get("send_from"), "reply_to": (found or {}).get("reply_to")}
    return {"senders": [one for one in accounts.froms_of(account) if one["ready"]],
            "replies": accounts.reply_tos_of(account),
            "default_from": accounts.default_from(account),
            "default_reply": accounts.default_reply(account),
            "chosen": chosen}


# Los avisos de las carpetas, por lo que llega en `?carpeta_hecha=`.
FOLDER_DONE = {"nueva": "folders_done_new", "nombre": "folders_done_name",
               "color": "folders_done_color", "eliminada": "folders_done_deleted"}
# What each tray does, by the word in `?editar=`, so a link works without
# JavaScript: the page opens with that form in sight.
FOLDER_EDITS = {"nombre": "rename", "color": "color", "eliminar": "delete"}


def editing_of(account) -> dict | None:
    """La bandeja que pide la dirección (`?nueva=1`, o `?carpeta=<id>&editar=`),
    para dibujarla abierta: es lo que hace un enlace del menú sin JavaScript."""
    if request.args.get("nueva"):
        return {"what": "new", "folder": None, "form": {}, "errors": {}}
    what = FOLDER_EDITS.get(request.args.get("editar", ""))
    found = designs.folder_of(account, as_id(request.args.get("carpeta")))
    if what and found is not None:
        return {"what": what, "folder": found, "form": {}, "errors": {}}
    return None


def shelf_screen(db, account, *, folder=None, editing=None):
    """Mis plantillas, o una de sus carpetas: la misma pantalla con otra lista.

    Las tarjetas son las de siempre: da igual de dónde salió cada plantilla, se
    editan, se duplican, se mueven y se borran desde la misma fila.
    """
    folders = designs.folders_of(account)
    context = {
        "named": {one["key"]: one["name"] for one in offered()},
        "folders": folders, "colors": designs.FOLDER_COLORS,
        "editor_url": editor_url, "editing": editing or editing_of(account),
        "saved": bool(request.args.get("saved")),
        "updated": bool(request.args.get("changed")),
        "copied": bool(request.args.get("copy")),
        "full": bool(request.args.get("full")),
        "designs_limit": designs.LIMIT,
        # Cuántas se movieron: una con «Mover a…», o varias arrastrándolas.
        "moved": request.args.get("movida", default=0, type=int),
        "folder_done": FOLDER_DONE.get(request.args.get("carpeta_hecha", "")),
        "folder_limit": designs.FOLDER_LIMIT,
    }
    if folder is not None:
        return render_template(
            "designs/folder.html", section="plantillas", folder=folder,
            mine=designs.in_folder(db, account["_id"], folder["id"]),
            **shared(db, account, **context))
    found = designs.shelf(db, account)
    return render_template(
        "designs/index.html", section="plantillas", mine=found["loose"],
        counts=found["counts"], peek=found["peek"],
        **shared(db, account, **context))


@bp.route("/templates")
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    return shelf_screen(get_db(), account)


@bp.route("/templates/folders/<raw>")
def folder(raw):
    """Una carpeta, con todas sus plantillas. La de otra cuenta no está."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    found = designs.folder_of(account, as_id(raw))
    if found is None:
        abort(404)
    return shelf_screen(get_db(), account, folder=found)


@bp.route("/templates/folders", methods=["POST"])
def folders():
    """Crear una carpeta, cambiarle el nombre o el color, o eliminarla, según
    `action`. Se vuelve a donde se estaba (`back`: la carpeta abierta, o nada
    para Mis plantillas). Si algo no se puede, la pantalla vuelve con la bandeja
    abierta y el porqué."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    back = as_id(request.form.get("back"))
    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(listed_at(account, back))

    action = request.form.get("action", "")
    found = designs.folder_of(account, as_id(request.form.get("folder")))
    name = request.form.get("nombre", "")
    color = request.form.get("color", "")
    if action == "new":
        new_id, wrong = designs.add_folder(db, account, name, color)
        if new_id is not None:
            return redirect(url_for("designs.index", carpeta_hecha="nueva"))
    elif found is None or action not in ("rename", "color", "delete"):
        return redirect(listed_at(account, back))
    elif action == "delete":
        designs.remove_folder(db, account, found["id"])
        return redirect(url_for("designs.index", carpeta_hecha="eliminada"))
    else:
        wrong = (designs.rename_folder(db, account, found["id"], name)
                 if action == "rename"
                 else designs.recolor_folder(db, account, found["id"], color))
        if wrong == "same":
            return redirect(listed_at(account, back, same=1))
        if not wrong:
            return redirect(listed_at(account, back, carpeta_hecha=(
                "nombre" if action == "rename" else "color")))

    errors = {"form": {"required": t("error_required"),
                       "taken": t("folders_error_taken"),
                       "full": t("folders_error_full", n=designs.FOLDER_LIMIT),
                       "color": t("folders_error_color")}.get(wrong, t("error_required"))}
    editing = {"what": action, "folder": found, "errors": errors,
               "form": {"nombre": name, "color": color}}
    here = designs.folder_of(account, back)
    return shelf_screen(db, account, folder=here, editing=editing)


# Cuántas se mueven en un solo envío: las que caben elegidas en una lista.
MOVE_MAX = 200


@bp.route("/templates/move", methods=["POST"])
def move():
    """Pasar plantillas a una carpeta, o sacarlas («Sin carpeta»). Una desde
    «Mover a…», o varias arrastrándolas juntas (octubre de 2026). Las que no
    son de la cuenta se ignoran."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    back = as_id(request.form.get("back"))
    raw = request.form.get("folder", "")
    target = as_id(raw) if raw else None
    if not csrf_ok(request.form.get("csrf_token")) or (raw and target is None):
        return redirect(listed_at(account, back))
    moved = designs.move_many(get_db(), account,
                              [as_id(one) for one in request.form.getlist("id")[:MOVE_MAX]
                               if one], target)
    if moved:
        return redirect(listed_at(account, back, movida=moved))
    return redirect(listed_at(account, back))


@bp.route("/templates/upload", methods=["GET", "POST"])
def upload():
    """Cargar el ZIP de un lienzo, bajado del editor de esta cuenta o de otra:
    queda un lienzo nuevo y se abre en el editor tal como estaba. Es de todos
    los planes, como el lienzo. Con JavaScript el formulario sale en una
    bandeja encima de la lista; sin él, esta es su página. Las dos mandan aquí.

    El HTML propio ya no se carga, ni suelto ni en un ZIP sin lienzo.
    """
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
        elif not archivo or not archivo.filename:
            errors["archivo"] = t("error_required")
        else:
            raw = archivo.read(imaging.MAX_UPLOAD + 1)
            if not imaging.is_zip(raw):
                errors["archivo"] = t("designs_only_zip")
            else:
                new_id, wrong = pieces.canvas_from_pack(db, account, raw, name=name,
                                                        filename=archivo.filename)
                if new_id is None:
                    errors["archivo"] = wrong
                else:
                    # Directo al editor: se sigue trabajando donde se dejó.
                    return redirect(url_for("designs.edit_canvas", raw=new_id))

    return render_template("designs/upload.html", section="plantillas",
                           **shared(db, account, errors=errors))


# ------------------------------------------------ las plantillas de muestra

# Los ZIP de lienzo de la tira de la portada, uno por plantilla, con el nombre
# que usa el sitio (`SAMPLES` en landing/content.py). Van con el código, iguales
# para todos: el sitio es estático y lo que enseña tiene que existir al
# construirlo. Agregar una es dejar su ZIP aquí y su fila allá.
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "sample_templates"


def sample_file(slug: str) -> Path | None:
    """El ZIP de esa muestra, o None. El nombre se comprueba antes de tocar el
    disco: viene de la dirección y no puede salir de la carpeta."""
    if not SAMPLE_NAME.fullmatch(slug or ""):
        return None
    path = SAMPLES_DIR / f"{slug}.zip"
    return path if path.is_file() else None


@bp.route("/templates/sample/<slug>")
def sample(slug):
    """Pulsar una plantilla de la portada: queda como plantilla de la cuenta y
    se abre su lienzo. Es lo mismo que cargar su ZIP, así que pasa por la misma
    revisión y sus fotos cuentan contra el tope de la cuenta. Cada vez que se
    pulsa queda otra copia, como al cargar el mismo ZIP dos veces.

    Es un GET porque llega desde un enlace del sitio público, que está en otro
    dominio. A una precarga del navegador no se le crea nada.
    """
    path = sample_file(slug)
    if path is None:
        abort(404)
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login", sample=slug))
    if is_prefetch():
        return Response(status=204)

    db = get_db()
    new_id, wrong = pieces.canvas_from_pack(db, account, path.read_bytes(), name="",
                                            filename=slug)
    if new_id is None:
        # Lo que no se deja cargar se dice donde se cargan los ZIP.
        return render_template("designs/upload.html", section="plantillas",
                               **shared(db, account, errors={"archivo": wrong}))
    return redirect(url_for("designs.edit_canvas", raw=new_id))


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


@bp.route("/templates/html/<raw>", methods=["GET", "POST"])
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

    choice = sending_choice(account) if request.method == "POST" else None
    if request.method == "POST":
        html = request.form.get("html", "")
        name = designs.clean_name(request.form.get("nombre", "")) or name
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif request.form.get("action") == "vista":
            return html_preview(html, plan)
        else:
            problems = html_check.check(html.encode("utf-8"))
            if problems:
                errors["html"] = explain(problems)
            else:
                designs.update_html(db, account["_id"], found["_id"], name=name,
                                    html=html)
                if choice is not None:
                    designs.set_sending(db, account["_id"], found["_id"], **choice)
                images.keep(db, account["_id"], imaging.names_in(html))
                # Las que el HTML de antes nombraba y este ya no (una foto
                # cambiada con «Cambiar», por ejemplo).
                pieces.drop_unused(db, account["_id"], pieces.images_in(found))
                return redirect(listed_at(account, found.get("folder_id"), changed=1))

    return render_template(
        "designs/html.html", section="plantillas", account=account,
        found=found, html=html, name=name, errors=errors,
        **sending_context(account, found, choice),
        columns=marks_for(account),
        people=contacts.for_preview(db, account["_id"]),
        max_kb=html_check.MAX_BYTES // 1024,
        kb=round(len(html.encode("utf-8")) / 1024, 1),
        watermark=plans.has_watermark(plan),
        pictures=html_images(db, account["_id"], html))


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


class _Sources(HTMLParser):
    """Las direcciones de las `<img>` de un HTML, en orden y sin repetir."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag != "img":
            return
        src = (dict(attrs).get("src") or "").strip()
        if src and src not in self.found:
            self.found.append(src)

    handle_startendtag = handle_starttag


def html_images(db, account_id, html: str) -> list[dict]:
    """Cada imagen de un HTML cargado y de dónde sale, para avisar.

    `ok` es del panel y de esta cuenta. `gone`, del panel pero ya no existe:
    sale rota. `other`, del panel pero de otra cuenta: no se copia, y sale rota
    el día que esa cuenta la borre. `outside`, de otro sitio: se ve mientras
    quien la publica la mantenga, y el panel no va a buscarla. `inside`, dentro
    del archivo: Gmail no la muestra y pesa.
    """
    reader = _Sources()
    try:
        reader.feed(html or "")
        reader.close()
    except Exception:  # noqa: BLE001 - lo roto ya lo dice html_check
        return []
    out = []
    for src in reader.found:
        if src.lower().startswith("data:"):
            state = "inside"
        else:
            names = imaging.names_in(src)
            found = images.by_name(db, names[0]) if names else None
            if not names:
                state = "outside"
            elif found is None:
                state = "gone"
            elif found["account_id"] == account_id:
                # También la retirada: guardar este HTML la vuelve a dejar fija.
                state = "ok"
            else:
                state = "other"
        # Lo que se enseña: una dirección cortada, que un `data:` son megas.
        shown = "data:…" if state == "inside" else (src if len(src) <= 70 else src[:67] + "…")
        out.append({"src": src, "shown": shown, "state": state})
    return out


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

    if not pieces.photo_room(db, account):
        errors[which] = t("designs_image_limit", n=pieces.photo_limit(account))
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
        errors[which] = t(pieces.IMAGE_PROBLEMS.get(str(exc), "designs_image_bad"),
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
        action, _, which = request.form.get("action", "").partition(":")

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
            elif found is None and not designs.has_room(db, account["_id"]):
                errors["form"] = t("designs_full", n=designs.LIMIT)
            elif found is None:
                designs.save_filled(db, account["_id"], name=name,
                                    template=key, filled=filled)
                return redirect(url_for("designs.index", saved=1))
            else:
                designs.update_filled(db, account["_id"], found["_id"],
                                      name=name, filled=filled)
                choice = sending_choice(account)
                if choice is not None:
                    designs.set_sending(db, account["_id"], found["_id"], **choice)
                return redirect(listed_at(account, found.get("folder_id"), changed=1))

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
        watermark=plans.has_watermark(plan),
        **sending_context(account, found,
                          sending_choice(account) if request.method == "POST" else None))


@bp.route("/templates/piece/<raw>", methods=["GET", "POST"])
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


@bp.route("/templates/<raw>/preview")
def piece_view(raw):
    """Una pieza guardada, armada como correo, para el marco de su tarjeta.

    La misma vista que se dibuja al editarla, pero de lo guardado y por GET, que
    es lo que un `<iframe>` puede pedir. Sirve para las tres clases de pieza. La
    cuenta va en la consulta: la de otra no encuentra nada.

    Lleva la cabecera de un correo (la pone `app.py` al ver `email_preview`) y
    el marco va con `sandbox` y sin permisos: el HTML de dentro es del cliente.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    design_id = as_id(raw)
    found = designs.by_id(db, account["_id"], design_id) if design_id else None
    if found is None:
        abort(404)

    plan = accounts.plan_of(account)
    source = found.get("source")
    if source == designs.UPLOAD:
        return html_preview(found.get("html", ""), plan)
    if source == designs.CANVAS:
        g.email_preview = True
        doc = canvas.read(found.get("canvas"))
        if doc is None:
            return Response("", mimetype="text/html")
        grounds = found.get("backgrounds") or []
        shades = found.get("shades") or []
        email = pieces.canvas_email(
            doc, plan,
            [imaging.url_of(one) if one else None for one in grounds],
            shades, preview=True, postal=accounts.postal_of(account))
        return Response(filled_for(db, account, email), mimetype="text/html")
    if not render.known(found.get("template", "")):
        abort(404)
    return preview(found["template"], render.clean(found["template"],
                                                   found.get("fields") or {}),
                   plan, accounts.fields_of(account))


# --------------------------------------------------------------- el lienzo

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
    # La carpeta elegida junto al nombre (octubre de 2026). La de otra cuenta,
    # o una que ya no existe, es ninguna.
    folder_id = found.get("folder_id") if found else None
    if request.method == "POST" and "carpeta" in request.form:
        picked = designs.folder_of(account, as_id(request.form.get("carpeta")))
        folder_id = picked["id"] if picked else None
    # Y de quién sale y a dónde se responde, si el formulario lo trae.
    choice = sending_choice(account) if request.method == "POST" else None

    if request.method == "POST":
        name = designs.clean_name(request.form.get("nombre", "")) or name
        posted = canvas.parse(request.form.get("lienzo", ""))
        doc = posted or doc
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        else:
            # Solo se guarda lo que arma bien el correo y tiene pocas
            # probabilidades de ir a spam.
            refused = pieces.canvas_refused(db, account, posted)
            if not name:
                errors["nombre"] = t("error_required")
            if refused:
                errors["form"] = refused
            elif found is None and not designs.has_room(db, account["_id"]):
                errors["form"] = t("designs_full", n=designs.LIMIT)
            elif not errors:
                fused = pieces.canvas_fused(db, account, posted)
                if fused is None:
                    errors["form"] = pieces.canvas_explain(["too_big"])
                else:
                    grounds, shades = fused
                    if found is None:
                        new_id = designs.save_canvas(
                            db, account["_id"], name=name, doc=posted, backgrounds=grounds,
                            shades=shades, folder_id=folder_id)
                        if choice is not None:
                            designs.set_sending(db, account["_id"], new_id, **choice)
                        return redirect(listed_at(account, folder_id, saved=1))
                    designs.update_canvas(db, account["_id"], found["_id"],
                                          name=name, doc=posted, backgrounds=grounds,
                                          shades=shades, folder_id=folder_id)
                    if choice is not None:
                        designs.set_sending(db, account["_id"], found["_id"], **choice)
                    # Lo que la versión de antes nombraba y esta ya no: sus
                    # imágenes fundidas y las fotos que se quitaron del lienzo.
                    pieces.drop_unused(db, account["_id"], pieces.images_in(found))
                    return redirect(listed_at(account, folder_id, changed=1))

    return render_template(
        "designs/canvas.html", section="plantillas", account=account,
        found=found, doc=doc, name=name, errors=errors,
        folders=designs.folders_of(account), folder_id=folder_id,
        **sending_context(account, found, choice),
        fonts=list(canvas.FONTS), font_stacks=canvas.FONTS,
        columns=marks_for(account), keys=CANVAS_KEYS,
        people=contacts.for_preview(db, account["_id"]),
        limits={"minSize": canvas.MIN_SIZE, "maxSize": canvas.MAX_SIZE,
                "minHeight": canvas.MIN_HEIGHT, "maxHeight": canvas.MAX_HEIGHT,
                "maxItems": canvas.MAX_ITEMS, "altMax": canvas.ALT_MAX,
                "width": canvas.WIDTH, "lineMin": canvas.LINE_MIN,
                "lineMax": canvas.LINE_MAX},
        image_mb=imaging.MAX_UPLOAD // (1024 * 1024),
        watermark=plans.has_watermark(accounts.plan_of(account)),
        # «Mi logo» sale solo si la empresa tiene uno (octubre de 2026).
        has_logo=bool(accounts.logo_of(account)))


@bp.route("/templates/create", methods=["GET", "POST"])
def create():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    return canvas_editor(account, None)


@bp.route("/templates/canvas/<raw>", methods=["GET", "POST"])
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


@bp.route("/templates/canvas/check", methods=["POST"])
def canvas_review():
    """Cuánto pesa, qué le falta para no ir a spam y cómo va cada requisito. Lo
    pide el editor mientras se trabaja, para la barra, la lista y la ventana de
    requisitos; es la misma revisión que al guardar."""
    account = signed_in()
    if account is None or not csrf_ok(request.form.get("csrf_token")):
        abort(403)
    doc = canvas.parse(request.form.get("lienzo", ""))
    # El nombre se mira aquí, que no es del lienzo: viaja en el formulario.
    named = bool(designs.clean_name(request.form.get("nombre", "")))
    return jsonify(**pieces.review(get_db(), account, doc, named=named))


@bp.route("/templates/canvas/preview", methods=["POST"])
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
    email = pieces.canvas_email(doc, accounts.plan_of(account),
                                [canvas.data_url(raw) if raw else None for raw in made],
                                [canvas.average(raw, doc["bg"]) if raw else None
                                 for raw in made], preview=True,
                                postal=accounts.postal_of(account))
    return Response(filled_for(db, account, email), mimetype="text/html")


@bp.route("/templates/canvas/pdf", methods=["POST"])
def canvas_pdf():
    """La pieza en un PDF, para guardarla o imprimirla.

    Por POST y no por un enlace **a propósito**: baja lo que se está viendo,
    también en una pieza que todavía no se ha guardado. Es el mismo reparto que
    la vista previa.

    Solo el lienzo tiene PDF: es el único que guarda coordenadas. Una pieza de
    HTML subido pediría un dibujante de HTML, que no hay.
    """
    account = signed_in()
    if account is None or not csrf_ok(request.form.get("csrf_token")):
        abort(403)
    db = get_db()
    doc = canvas.parse(request.form.get("lienzo", ""))
    if doc is None:
        abort(400)
    name = (request.form.get("nombre") or "").strip()[:80]
    # Solo las imágenes de esta cuenta: `data_of` pregunta con ella.
    load = lambda one: images.data_of(db, account["_id"], one)  # noqa: E731
    made = canvas_pdf_service.to_pdf(doc, load, title=name)
    return Response(made, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{pieces.file_name(name, "pdf")}"'})


@bp.route("/templates/canvas/<raw>/html")
def canvas_html(raw):
    """La plantilla guardada en un ZIP, para pasársela a otra persona.

    Trae el **lienzo** (`lienzo.json`, con su nombre) y sus fotos originales en
    `fotos/`, que el lienzo nombra por su ruta: es lo que se vuelve a cargar
    (`canvas_from_pack()`) y se sigue editando como si nada. Y trae el **HTML**,
    que es lo mismo que sale al enviar (`sender.Piece`), con sus imágenes
    fundidas en `imagenes/`: al abrirlo en una computadora se ve entero, y
    sirve fuera de Sobreala. Dentro del HTML no pueden ir: una sola foto ya
    pasaba de los 102 KB.

    **Sin nuestro pie**: la baja, la dirección y la marca de agua se ponen al
    enviar, y con el pie dentro saldría dos veces. Es de la plantilla guardada y
    no de lo que haya en pantalla, porque las imágenes fundidas solo existen al
    guardar; el editor lo dice si hay cambios sin guardar. Las marcas
    `*|NOMBRE|*` se quedan escritas: lo que se baja es la plantilla.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    design_id = as_id(raw)
    found = designs.by_id(db, account["_id"], design_id) if design_id else None
    if found is None or found.get("source") != designs.CANVAS:
        abort(404)
    # La cabecera de un correo, como la vista previa: el ZIP lleva su HTML.
    g.email_preview = True
    name, data = pieces.canvas_zip(db, account, found)
    return Response(data, mimetype="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{name}"'})


@bp.route("/templates/canvas/image", methods=["POST"])
def canvas_image():
    """Subir una foto al lienzo. Contesta en JSON: la pide el editor."""
    account = signed_in()
    if account is None:
        abort(403)
    if not csrf_ok(request.form.get("csrf_token")):
        return jsonify(error=t("error_csrf")), 400
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return jsonify(error=t("error_required")), 400
    photo, wrong = pieces.save_photo(get_db(), account,
                                     archivo.read(imaging.MAX_UPLOAD + 1))
    if photo is None:
        return jsonify(error=wrong), 400
    return jsonify(**photo)


@bp.route("/templates/canvas/logo", methods=["POST"])
def canvas_logo():
    """Poner el logo de la empresa en el lienzo (octubre de 2026). Contesta lo
    mismo que subir una foto, y el editor la pone igual.

    **Entra una copia**, no el logo mismo: así la plantilla y el logo viven
    cada uno lo suyo, y cambiar o quitar el logo en Configuración no le deja un
    hueco a ninguna plantilla guardada. Por eso cuenta contra el tope de fotos,
    como cualquier otra.
    """
    account = signed_in()
    if account is None:
        abort(403)
    if not csrf_ok(request.form.get("csrf_token")):
        return jsonify(error=t("error_csrf")), 400
    db = get_db()
    logo = accounts.logo_of(account)
    data = images.data_of(db, account["_id"], logo) if logo else None
    if not data:
        return jsonify(error=t("canvas_logo_none")), 400
    if not pieces.photo_room(db, account):
        return jsonify(error=t("designs_image_limit", n=pieces.photo_limit(account))), 400
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(data)) as opened:
        width, height = opened.size
        ext = "png" if opened.format == "PNG" else "jpg"
    name = images.save(db, account["_id"], data=data, ext=ext,
                       mime="image/png" if ext == "png" else "image/jpeg")
    return jsonify(name=name, url=imaging.url_of(name), width=width, height=height)


@bp.route("/templates/duplicate", methods=["POST"])
def copy():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    # De vuelta a donde se pulsó: la carpeta abierta, o Mis plantillas. La
    # copia queda en la misma carpeta que la original.
    back = as_id(request.form.get("back"))
    if csrf_ok(request.form.get("csrf_token")):
        design_id = as_id(request.form.get("id"))
        db = get_db()
        found = designs.by_id(db, account["_id"], design_id) if design_id else None
        if found is not None and not designs.has_room(db, account["_id"]):
            return redirect(listed_at(account, back, full=1))
        if found is not None:
            designs.duplicate(db, account["_id"], found["_id"],
                              name=t("designs_copy_name", name=found.get("name", "")))
            return redirect(listed_at(account, back, copy=1))
    return redirect(listed_at(account, back))


@bp.route("/templates/delete", methods=["POST"])
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
                pieces.drop_unused(db, account["_id"], pieces.images_in(gone))
    return redirect(listed_at(account, as_id(request.form.get("back"))))
