"""Armar, revisar, guardar y bajar una plantilla del lienzo, fuera de la
pantalla (octubre de 2026).

Vivía en `blueprints/designs/routes.py`, que lo sigue usando igual; la API lo
usa también. Por eso aquí todo recibe la cuenta a mano y nada mira la sesión,
la petición ni `g`: la cabecera de correo de la vista previa la sigue poniendo
la ruta del panel.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any

from i18n import t
from models import account as accounts
from models import design as designs
from models import image as images
from services import canvas, html_check, imaging, plans, render

# Cuánto espera una foto subida sin guardar en ninguna plantilla antes de que
# se la pueda recoger: un día, para no quitarle a nadie la que acaba de subir y
# todavía no guarda.
ORPHAN_AFTER = timedelta(hours=24)

# El ancho al que se guardan las fotos del lienzo: al doble de lo que se ven, para
# que el fondo fundido salga nítido en un teléfono.
CANVAS_PHOTO_WIDTH = canvas.WIDTH * canvas.SCALE

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

# Una dirección de baja del largo de las de verdad, para pesar el correo.
UNSUBSCRIBE_SAMPLE = "https://app.sobreala.com/unsubscribe/" + "x" * 96


# ------------------------------------------------------------ las fotos

def photo_limit(account) -> int:
    """Cuántas fotos caben en la cuenta: lo dice su plan (`docs/pricing.md`)."""
    return plans.image_limit(accounts.plan_of(account))


def photo_room(db, account, wanted: int = 1) -> bool:
    """Si caben `wanted` fotos más. Si no caben, antes de decir que no se
    recogen las que quedaron fuera de toda plantilla hace más de un día: una
    foto subida en el editor cuenta desde que se sube, aunque la plantilla no
    se guarde nunca, y es lo que dejaba el tope lleno después de borrar."""
    limit = photo_limit(account)
    if images.count(db, account["_id"]) + wanted <= limit:
        return True
    free_orphans(db, account["_id"])
    return images.count(db, account["_id"]) + wanted <= limit


def free_orphans(db, account_id) -> int:
    """Quitar las fotos que no nombra ninguna plantilla de la cuenta y tienen
    más de un día. Pasan por `images.remove()`, así que una que salió en un
    envío se retira y no se borra."""
    still = {name for one in designs.for_account(db, account_id, limit=0)
             for name in images_in(one)}
    stale = images.uploaded_before(db, account_id, datetime.now(timezone.utc) - ORPHAN_AFTER)
    return images.remove(db, account_id, [one for one in stale if one not in still])


def drop_unused(db, account_id, names) -> None:
    """Borrar las imágenes que ya no nombra ninguna pieza de la cuenta.

    Se pregunta a todas y no solo a la que cambió: al duplicar, la copia y la
    original nombran las mismas.
    """
    still = {name for one in designs.for_account(db, account_id, limit=0)
             for name in images_in(one)}
    images.remove(db, account_id, [one for one in names if one and one not in still])


def images_in(found) -> list[str]:
    """Las imágenes que nombra una pieza guardada.

    En un lienzo, sus fotos y sus fondos fundidos. En una prediseñada, se le
    pregunta a la plantilla cuáles de sus casillas son imágenes, en vez de
    adivinarlo mirando el contenido: la plantilla es quien lo sabe. En una
    cargada, las del panel que nombra su HTML, que es el caso del HTML bajado
    de un lienzo y vuelto a cargar.
    """
    if found.get("source") == designs.CANVAS:
        return (canvas.images_of(found.get("canvas"))
                + [one for one in found.get("backgrounds") or [] if one])
    if found.get("source") == designs.UPLOAD:
        return imaging.names_in(found.get("html", ""))
    fields = found.get("fields") or {}
    return [fields[one["name"]]
            for one in render.fields_of(found.get("template", ""))
            if one.get("type") == "image" and fields.get(one["name"])]


def save_photo(db, account, raw: bytes, *,
               limit: int = imaging.MAX_UPLOAD) -> tuple[dict[str, Any] | None, str]:
    """Una foto para el lienzo: revisada, sin sus bordes transparentes y
    achicada. Devuelve (su nombre, dirección y medidas, "") o (None, por qué
    no), en la frase del cliente. `limit` es lo que puede pesar al llegar: el
    editor acepta más que la API."""
    if not photo_room(db, account):
        return None, t("designs_image_limit", n=photo_limit(account))
    if len(raw) > limit:
        return None, t("designs_image_heavy", mb=limit // (1024 * 1024))
    try:
        # Sin los bordes transparentes: la caja queda justo en lo que se ve.
        data, ext, mime = imaging.shrink(imaging.trim(raw), width=CANVAS_PHOTO_WIDTH)
    except imaging.ImageError as exc:
        return None, t(IMAGE_PROBLEMS.get(str(exc), "designs_image_bad"),
                       kb=imaging.STORED_MAX // 1024)
    from PIL import Image

    with Image.open(io.BytesIO(data)) as opened:
        width, height = opened.size
    name = images.save(db, account["_id"], data=data, ext=ext, mime=mime,
                       width=width, height=height)
    return {"name": name, "url": imaging.url_of(name), "width": width, "height": height}, ""


# ------------------------------------------------------------ la revisión

def canvas_problems(db, account_id, doc) -> list[str]:
    return canvas.problems(
        doc, owns=lambda name: (imaging.valid_name(name)
                                and images.owns(db, account_id, name)))


def canvas_explain(problems: list[str]) -> str:
    return " ".join(t("canvas_bad_" + one, kb=html_check.MAX_BYTES // 1024)
                    for one in problems)


def canvas_email(doc, plan, urls: list[str | None], shades=None, *,
                 unsubscribe: str = "#", preview: bool = False, postal: str = "") -> str:
    """El correo entero de un lienzo: el cuerpo, el sobre y las reglas del modo
    oscuro. Lo mismo que arma el envío (`sender.Piece`)."""
    return render.email_from_body(canvas.to_html(doc, urls, shades), plan=plan,
                                  unsubscribe=unsubscribe, preview=preview,
                                  style=canvas.dark_css(doc, shades), postal=postal)


def canvas_size(doc, plan, urls: list[str | None], *, postal: str = "") -> int:
    """Lo que pesa el correo entero, con el sobre y la baja, que es lo que
    cuenta Gmail para recortarlo."""
    email = canvas_email(doc, plan, urls, [doc["bg"]] * len(urls),
                         unsubscribe=UNSUBSCRIBE_SAMPLE, postal=postal)
    return len(email.encode("utf-8"))


def sample_grounds(doc) -> list[str | None]:
    """Direcciones de imagen del mismo largo que las que tendrá al guardarse."""
    sample = imaging.url_of("x" * 22 + ".jpg")
    return [sample if one["kind"] in ("picture", "backdrop") else None
            for one in canvas.groups(doc)]


def review_texts(found: list[dict]) -> list[str]:
    return [t("canvas_spam_" + one["key"], **{k: v for k, v in one.items() if k != "key"})
            for one in found]


def rule_texts(doc, size: int, problems: list[str], found: list[dict], *,
               named: bool) -> list[dict]:
    """La ventana de requisitos: cada regla, si se cumple y su frase con las
    cifras de ahora. El nombre va primero y lo mira quien llama, que no es del
    lienzo: viaja aparte, como al guardar."""
    rules = [{"group": "build", "ok": named, "text": t("canvas_rule_name")}]
    for one in canvas.checklist(doc, size, limit=html_check.MAX_BYTES,
                                failed=problems, found=found):
        # Los miles con coma, como se escriben en Panamá: 4,000 px.
        values = {k: (f"{v:,}" if isinstance(v, int) else v) for k, v in one.items()
                  if k not in ("key", "group", "ok")}
        text = t("canvas_rule_" + one["key"], **values)
        if not one["ok"] and one.get("what"):
            # Qué palabra o qué acortador: lo que hay que cambiar.
            text += " " + t("canvas_rule_found", what=one["what"])
        rules.append({"group": one["group"], "ok": one["ok"], "text": text})
    return rules


def review(db, account, doc, *, named: bool) -> dict[str, Any]:
    """Cuánto pesa, qué le falta para no ir a spam y cómo va cada requisito: la
    misma revisión que al guardar. `ok` es lo que apaga Guardar; el nombre no
    cuenta ahí, que se pide al pulsarlo con su propio aviso."""
    if doc is None:
        return {"ok": False, "bytes": 0, "max": html_check.MAX_BYTES,
                "issues": [canvas_explain(["broken"])], "rules": []}
    size = canvas_size(doc, accounts.plan_of(account), sample_grounds(doc),
                       postal=accounts.postal_of(account))
    problems = canvas_problems(db, account["_id"], doc)
    found = canvas.review(doc, size, limit=html_check.MAX_BYTES)
    issues = [canvas_explain([one]) for one in problems] + review_texts(found)
    return {"ok": not issues, "bytes": size, "max": html_check.MAX_BYTES,
            "issues": issues, "rules": rule_texts(doc, size, problems, found, named=named)}


def canvas_refused(db, account, doc) -> str:
    """Por qué no se puede guardar este lienzo, en la frase del cliente, o
    vacío si se puede: las reglas para armar el correo y la revisión antispam.
    Lo mismo al guardarlo en el editor, al cargarlo de un ZIP y por la API."""
    problems = canvas_problems(db, account["_id"], doc)
    if problems:
        return canvas_explain(problems)
    spam = canvas.review(doc, canvas_size(doc, accounts.plan_of(account),
                                          sample_grounds(doc),
                                          postal=accounts.postal_of(account)),
                         limit=html_check.MAX_BYTES)
    return " ".join(review_texts(spam))


def canvas_hard(db, account, doc) -> str:
    """Lo que ni como borrador se guarda (`canvas.hard_problems()`), en la frase
    del cliente, o vacío."""
    return canvas_explain(canvas.hard_problems(
        doc, owns=lambda name: (imaging.valid_name(name)
                                and images.owns(db, account["_id"], name))))


def draft_issues(db, account, doc) -> list[str]:
    """Lo que le falta a un borrador para poder enviarse, una frase por regla:
    lo mismo que dice la revisión del editor."""
    return review(db, account, doc, named=True)["issues"]


def canvas_fused(db, account, doc):
    """Las imágenes fundidas de un lienzo que ya pasó `canvas_refused()`, y sus
    colores. None si el correo armado pasa de los 102 KB, y entonces no queda
    ninguna guardada."""
    load = lambda one: images.data_of(db, account["_id"], one)  # noqa: E731
    grounds, shades = canvas.store(db, account["_id"], doc, load)
    html = canvas.to_html(doc, [imaging.url_of(one) if one else None
                                for one in grounds], shades)
    if len(html.encode("utf-8")) > html_check.MAX_BYTES:
        images.remove(db, account["_id"], grounds)
        return None
    return grounds, shades


# ------------------------------------------------------------ el ZIP

def canvas_from_pack(db, account, raw: bytes, *, name: str,
                     filename: str, folder_id=None) -> tuple[Any, str]:
    """Un lienzo nuevo a partir del ZIP que baja el editor. Devuelve (id, "")
    o (None, por qué no).

    Sus fotos entran **a la cuenta que carga**, por la misma revisión y el
    mismo achique que una foto del lienzo, y cuentan contra sus veinte: así
    cada cuenta es dueña de las suyas y ninguna depende de otra. Después el
    lienzo pasa exactamente lo que pasa Guardar (`canvas_refused()` y
    `canvas_fused()`): del JSON no se fía nada, y si una regla no se cumple no
    se carga. Si algo falla no queda nada guardado.
    """
    if not designs.has_room(db, account["_id"]):
        return None, t("designs_full", n=designs.LIMIT)
    try:
        page, files = imaging.unpack(raw, most=photo_limit(account))
    except imaging.PackError as exc:
        return None, t("designs_" + str(exc), n=photo_limit(account),
                       mb=imaging.MAX_UPLOAD // (1024 * 1024))
    try:
        data = json.loads(page.decode("utf-8"), parse_constant=canvas._not_json)
    except (UnicodeDecodeError, ValueError, RecursionError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None, t("designs_zip_canvas_bad")

    photos = [one for one in data["items"]
              if isinstance(one, dict) and one.get("t") == "image" and one.get("name")]
    wanted = list(dict.fromkeys(str(one["name"]) for one in photos))
    missing = [one for one in wanted if one not in files]
    if missing:
        return None, t("designs_zip_missing", what=missing[0])
    if not photo_room(db, account, len(wanted)):
        free = photo_limit(account) - images.count(db, account["_id"])
        return None, t("designs_zip_limit", n=len(wanted), free=max(free, 0),
                       limit=photo_limit(account))

    ready = []
    for one in wanted:
        try:
            ready.append((one, *imaging.shrink(files[one], width=CANVAS_PHOTO_WIDTH)))
        except imaging.ImageError as exc:
            return None, one + ": " + t(IMAGE_PROBLEMS.get(str(exc), "designs_image_bad"),
                                        kb=imaging.STORED_MAX // 1024)
    saved: dict[str, str] = {}
    for one, content, ext, mime in ready:
        saved[one] = images.save(db, account["_id"], data=content, ext=ext, mime=mime)
    for one in photos:
        one["name"] = saved[str(one["name"])]

    doc = canvas.parse(json.dumps(data))
    refused = canvas_refused(db, account, doc) if doc else t("designs_zip_canvas_bad")
    fused = None if refused else canvas_fused(db, account, doc)
    if fused is None:
        images.remove(db, account["_id"], list(saved.values()))
        return None, refused or canvas_explain(["too_big"])
    grounds, shades = fused
    title = name or designs.clean_name(str(data.get("name") or "")) or filename
    return designs.save_canvas(db, account["_id"], name=title, doc=doc,
                               backgrounds=grounds, shades=shades,
                               folder_id=folder_id), ""


def canvas_zip(db, account, found) -> tuple[str, bytes]:
    """El ZIP de una plantilla del lienzo y su nombre de archivo: el lienzo
    con sus fotos, y el HTML sin nuestro pie con sus imágenes fundidas (ver la
    descarga en `blueprints/designs/routes.py`)."""
    if (found.get("canvas") or {}).get("v") != canvas.VERSION:
        # Guardada por diapositivas: sus imágenes eran de otra forma. Se
        # rehacen como antes del primer correo.
        found = designs.upgrade_canvas(db, account["_id"], found)
    doc = canvas.read(found.get("canvas")) or canvas.blank()
    urls, files = [], []
    for i, one in enumerate(found.get("backgrounds") or [], 1):
        data = images.data_of(db, account["_id"], one) if one else None
        path = f"{imaging.ZIP_FOLDER}{i}.{one.rsplit('.', 1)[-1]}" if data else None
        urls.append(path)
        if data:
            files.append((path, data))
    shades = found.get("shades") or []
    email = render.email_from_body(canvas.to_html(doc, urls, shades),
                                   plan=accounts.plan_of(account),
                                   style=canvas.dark_css(doc, shades), bare=True)
    name = found.get("name", "")
    # Las fotos del lienzo, cada una con un nombre corto: el de verdad es la
    # dirección de la imagen en esta cuenta, y en otra no significa nada.
    photos: dict[str, str] = {}
    for one in canvas.images_of(doc):
        data = images.data_of(db, account["_id"], one)
        if data and one not in photos:
            photos[one] = f"{imaging.ZIP_PHOTOS}{len(photos) + 1}.{one.rsplit('.', 1)[-1]}"
            files.append((photos[one], data))
    items = [{**one, "name": photos.get(one["name"], one["name"])} if one["t"] == "image"
             else one for one in doc["items"]]
    board = {"name": name, **doc, "items": items}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as pack:
        pack.writestr(file_name(name, "html"), email.encode("utf-8"))
        pack.writestr(imaging.ZIP_CANVAS, json.dumps(board, ensure_ascii=False, indent=1))
        for path, data in files:
            # Ya van comprimidas: guardarlas tal cual es más rápido e igual de
            # liviano.
            pack.writestr(path, data, compress_type=zipfile.ZIP_STORED)
    return file_name(name, "zip"), out.getvalue()


# Lo que puede ir en el nombre de un archivo sin romper la cabecera ni el disco
# de nadie. Lo que no, se cae; sin nada legible queda «plantilla».
FILE_NAME = re.compile(r"[^A-Za-z0-9 ._-]+")


def file_name(name: str, ext: str) -> str:
    clean = FILE_NAME.sub("", unicodedata.normalize("NFKD", name)).strip()
    return f"{clean or 'plantilla'}.{ext}"
