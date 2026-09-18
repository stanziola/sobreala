"""El lienzo de «Crear plantilla»: de coordenadas libres a un correo.

Quien crea pone cada cosa donde quiere, como en una diapositiva. Ningún lector de
correo entiende «esto va a 120 px de arriba y 40 de la izquierda»: Gmail borra
las posiciones y Outlook dibuja con el motor de Word. Lo que sí respetan todos,
al píxel, son **tablas con medidas fijas**. Así que el lienzo se guarda con sus
coordenadas y al armar el correo se traduce a una cuadrícula:

  * Los textos y los botones se reparten en **franjas** (lo que comparte altura)
    y dentro de cada franja en **columnas** (lo que comparte ancho), una y otra
    vez, hasta que cada uno queda solo en su celda con los huecos medidos
    alrededor. Es un corte en guillotina: siempre existe mientras nada se
    enreda en molinillo, y eso se comprueba antes de guardar.
  * **Las imágenes no entran en la cuadrícula**: se funden en un solo fondo por
    diapositiva, que va en la celda de la diapositiva y, para Outlook, en su
    versión VML. Por eso pueden encimarse entre ellas y siempre quedan atrás.
  * Los textos y los botones son **texto de verdad**, no parte de la imagen. Es
    lo que hace que el correo no se lea como una foto (que es de lo que más va a
    spam), que las columnas `*|EDAD|*` funcionen, y que con las imágenes
    bloqueadas se siga leyendo.

**Nada de lo que llega se usa sin revisar.** El JSON lo escribe el navegador, y
el navegador lo controla quien lo tiene delante: `parse()` lo rehace desde cero
con solo lo que conoce, en los tipos que espera, y `problems()` dice qué no se
puede guardar. El texto se guarda como texto y sale escapado.
"""

from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from typing import Any

from markupsafe import escape

WIDTH = 600
# A cuántos píxeles se funde el fondo por cada píxel del lienzo: al doble, para
# que se vea nítido en una pantalla de teléfono.
SCALE = 2

MAX_SLIDES = 10
MAX_ITEMS = 30
MIN_HEIGHT = 80
MAX_HEIGHT = 1600
MIN_BOX = 16
TEXT_MAX = 2000
BUTTON_MAX = 60
HREF_MAX = 500
MIN_SIZE = 14
MAX_SIZE = 72

KINDS = ("text", "button", "image")
FRONT = ("text", "button")

# Las fuentes que existen en todos los lectores de correo, con lo que las
# reemplaza si alguno no la tiene. Una fuente de internet se ve en el editor y
# en Gmail cae a otra más ancha: el texto dejaría de caber donde se puso.
FONTS = {
    "Arial": "Arial, Helvetica, sans-serif",
    "Helvetica": "Helvetica, Arial, sans-serif",
    "Verdana": "Verdana, Geneva, sans-serif",
    "Tahoma": "Tahoma, Geneva, sans-serif",
    "Trebuchet MS": "'Trebuchet MS', Helvetica, sans-serif",
    "Georgia": "Georgia, 'Times New Roman', serif",
    "Times New Roman": "'Times New Roman', Times, serif",
    "Courier New": "'Courier New', Courier, monospace",
}
ALIGNS = ("left", "center", "right")
FITS = ("cover", "contain")

COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Un enlace de botón: una página segura o un correo. Ni `javascript:`, ni
# espacios ni comillas, que son como se rompe un atributo.
HREF = re.compile(r"^(https://|mailto:)[^\s\"'<>]+$")


def blank() -> dict[str, Any]:
    """Lo que abre «Crear plantilla»: una diapositiva blanca y vacía."""
    return {"slides": [{"h": 400, "bg": "#FFFFFF", "items": []}]}


# ------------------------------------------------------------- leer lo que llega

def _int(value, default=0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _color(value, default: str) -> str:
    value = str(value or "")
    return value.upper() if COLOR.match(value) else default


def _item(raw: dict[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("t")
    if kind not in KINDS:
        return None
    one: dict[str, Any] = {"t": kind, "x": _int(raw.get("x")), "y": _int(raw.get("y")),
                           "w": _int(raw.get("w"), 100), "h": _int(raw.get("h"), 40)}
    if kind == "image":
        one["name"] = str(raw.get("name") or "")[:80]
        one["fit"] = raw.get("fit") if raw.get("fit") in FITS else "cover"
        return one
    limit = TEXT_MAX if kind == "text" else BUTTON_MAX
    # Solo texto: los saltos de línea se quedan, el resto de controles no.
    text = str(raw.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
    one["text"] = "".join(c for c in text if c == "\n" or c >= " ")[:limit + 1]
    one["font"] = str(raw.get("font") or "Arial")
    one["size"] = _int(raw.get("size"), 16)
    one["color"] = _color(raw.get("color"), "#18181B")
    one["bold"] = bool(raw.get("bold"))
    one["italic"] = bool(raw.get("italic"))
    one["align"] = raw.get("align") if raw.get("align") in ALIGNS else (
        "center" if kind == "button" else "left")
    if kind == "text":
        line = raw.get("line")
        try:
            line = float(line)
        except (TypeError, ValueError):
            line = 1.4
        one["line"] = min(max(round(line, 2), 1.0), 2.5)
    else:
        one["href"] = str(raw.get("href") or "").strip()[:HREF_MAX + 1]
        one["bg"] = _color(raw.get("bg"), "#31A9E8")
        one["radius"] = min(max(_int(raw.get("radius"), 8), 0), 60)
    return one


def parse(raw: str) -> dict[str, Any] | None:
    """El lienzo que mandó el navegador, rehecho con solo lo que conocemos.

    Devuelve None si ni siquiera es un lienzo. Lo que sí es, sale con los tipos
    en su sitio aunque llegue con números escritos como texto; lo que está fuera
    de rango se queda como llegó, para que `problems()` lo diga.
    """
    try:
        data = json.loads(raw or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("slides"), list):
        return None
    slides = []
    for slide in data["slides"][:MAX_SLIDES + 1]:
        if not isinstance(slide, dict):
            return None
        items = [_item(one) for one in (slide.get("items") or [])[:MAX_ITEMS + 1]
                 if isinstance(one, dict)]
        slides.append({"h": _int(slide.get("h"), 400),
                       "bg": _color(slide.get("bg"), "#FFFFFF"),
                       "items": [one for one in items if one]})
    return {"slides": slides}


def _touch(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Si dos cajas se enciman. Tocarse por el borde no cuenta."""
    return (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
            and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])


def overlaps(slide: dict[str, Any]) -> list[int]:
    """Los textos y botones de una diapositiva que se enciman con otro."""
    front = [(i, one) for i, one in enumerate(slide["items"]) if one["t"] in FRONT]
    bad: set[int] = set()
    for pos, (i, a) in enumerate(front):
        for j, b in front[pos + 1:]:
            if _touch(a, b):
                bad.update((i, j))
    return sorted(bad)


def problems(doc: dict[str, Any] | None, *, owns=lambda name: True) -> list[str]:
    """Qué impide guardar este lienzo. Vacío es que se puede.

    Claves y no frases, como en `html_check`: la pantalla las traduce. `owns`
    dice si una imagen es de esta cuenta; el nombre llega del navegador y el
    navegador lo escribe cualquiera.
    """
    if doc is None:
        return ["broken"]
    found: list[str] = []

    def add(reason: str) -> None:
        if reason not in found:
            found.append(reason)

    if not doc["slides"]:
        add("empty")
    if len(doc["slides"]) > MAX_SLIDES:
        add("too_many_slides")
    for slide in doc["slides"]:
        if not MIN_HEIGHT <= slide["h"] <= MAX_HEIGHT:
            add("height")
        if len(slide["items"]) > MAX_ITEMS:
            add("too_many_items")
        for one in slide["items"]:
            if (one["x"] < 0 or one["y"] < 0 or one["w"] < MIN_BOX or one["h"] < MIN_BOX
                    or one["x"] + one["w"] > WIDTH or one["y"] + one["h"] > slide["h"]):
                add("bounds")
            if one["t"] == "image":
                if not one["name"] or not owns(one["name"]):
                    add("image")
                continue
            if one["font"] not in FONTS:
                add("font")
            if not MIN_SIZE <= one["size"] <= MAX_SIZE:
                add("size")
            if one["t"] == "text" and len(one["text"]) > TEXT_MAX:
                add("text_long")
            if one["t"] == "button":
                if not one["text"].strip() or len(one["text"]) > BUTTON_MAX:
                    add("button_text")
                if not HREF.match(one["href"]):
                    add("href")
        if overlaps(slide):
            add("overlap")
        elif _tangled(slide):
            add("tangled")
    return found


def few_words(slide: dict[str, Any]) -> bool:
    """Una diapositiva con imagen y casi sin texto: de lo que más va a spam."""
    has_image = any(one["t"] == "image" for one in slide["items"])
    words = sum(len(one.get("text", "").split()) for one in slide["items"]
                if one["t"] in FRONT)
    return has_image and words < 5


# -------------------------------------------------------------- el fondo

def backgrounds(doc: dict[str, Any], load) -> list[bytes | None]:
    """Las imágenes de cada diapositiva fundidas en una, en JPEG.

    `load(name)` devuelve los bytes de una imagen de la cuenta, o None. Una
    diapositiva sin imágenes no lleva fondo: le basta su color. Se pintan en el
    orden en que están, así que la última queda encima de las otras.
    """
    from PIL import Image, ImageOps

    out: list[bytes | None] = []
    for slide in doc["slides"]:
        pictures = [one for one in slide["items"] if one["t"] == "image"]
        if not pictures:
            out.append(None)
            continue
        ground = Image.new("RGB", (WIDTH * SCALE, slide["h"] * SCALE), slide["bg"])
        for one in pictures:
            raw = load(one["name"])
            if not raw:
                continue
            box = (max(one["w"] * SCALE, 1), max(one["h"] * SCALE, 1))
            with Image.open(BytesIO(raw)) as opened:
                picture = opened.convert("RGBA")
            if one["fit"] == "cover":
                picture = ImageOps.fit(picture, box, Image.LANCZOS)
                spot = (one["x"] * SCALE, one["y"] * SCALE)
            else:
                picture.thumbnail(box, Image.LANCZOS)
                spot = (one["x"] * SCALE + (box[0] - picture.width) // 2,
                        one["y"] * SCALE + (box[1] - picture.height) // 2)
            ground.paste(picture, spot, picture)
        buffer = BytesIO()
        ground.save(buffer, format="JPEG", quality=78, optimize=True,
                    progressive=True)
        out.append(buffer.getvalue())
    return out


def data_url(raw: bytes) -> str:
    """Un fondo dentro del propio documento, para la vista previa: no se guarda
    nada por mirar cómo queda."""
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")


# --------------------------------------------------------------- la cuadrícula

def _split(items: list[dict[str, Any]], start: str, size: str) -> list[list[dict[str, Any]]]:
    """Repartir en grupos que no comparten nada en un eje.

    Con `y`/`h` salen las franjas, con `x`/`w` las columnas. Dos cajas van en el
    mismo grupo si se solapan en ese eje, y eso se contagia.
    """
    groups: list[list[dict[str, Any]]] = []
    end = None
    for one in sorted(items, key=lambda it: it[start]):
        if groups and one[start] < end:
            groups[-1].append(one)
            end = max(end, one[start] + one[size])
        else:
            groups.append([one])
            end = one[start] + one[size]
    return groups


def _tangled(slide: dict[str, Any]) -> bool:
    """Si los textos y botones no se pueden cortar en guillotina.

    Pasa solo con un molinillo (cuatro cajas que se rodean sin tocarse). No hay
    tabla que lo dibuje, así que se pide moverlas en vez de adivinar.
    """
    def cut(items):
        if len(items) <= 1:
            return True
        for start, size in (("y", "h"), ("x", "w")):
            groups = _split(items, start, size)
            if len(groups) > 1:
                return all(cut(group) for group in groups)
        return False

    return not cut([one for one in slide["items"] if one["t"] in FRONT])


TABLE = ('<table role="presentation" width="{w}" cellpadding="0" cellspacing="0" '
         'border="0" style="width:{w}px;border-collapse:collapse;">')


def _gap_row(height: int, width: int) -> str:
    if height <= 0:
        return ""
    return (f'<tr><td width="{width}" height="{height}" style="width:{width}px;'
            f'height:{height}px;line-height:{height}px;font-size:0;">&nbsp;</td></tr>')


def _gap_cell(width: int, height: int) -> str:
    if width <= 0:
        return ""
    return (f'<td width="{width}" height="{height}" style="width:{width}px;'
            f'height:{height}px;font-size:0;line-height:0;">&nbsp;</td>')


def _text(value: str) -> str:
    """El texto escapado, con sus saltos de línea."""
    return str(escape(value)).replace("\n", "<br>")


def line_px(one: dict[str, Any]) -> int:
    """El interlineado en píxeles: Outlook solo lo respeta así, y el editor
    usa la misma cuenta para que el texto ocupe lo mismo en los dos."""
    return round(one["size"] * one.get("line", 1.4))


def _item_cell(one: dict[str, Any]) -> str:
    font = FONTS.get(one["font"], FONTS["Arial"])
    weight = "bold" if one["bold"] else "normal"
    style = "italic" if one["italic"] else "normal"
    w, h = one["w"], one["h"]
    if one["t"] == "text":
        return (f'<td width="{w}" height="{h}" valign="top" align="{one["align"]}" '
                f'style="width:{w}px;height:{h}px;font-family:{escape(font)};'
                f'font-size:{one["size"]}px;line-height:{line_px(one)}px;'
                f'mso-line-height-rule:exactly;color:{one["color"]};'
                f'font-weight:{weight};font-style:{style};text-align:{one["align"]};'
                f'word-wrap:break-word;">{_text(one["text"])}</td>')
    # Un botón que Outlook respeta: la celda lleva el color, el enlace ocupa la
    # celda entera y la altura de línea lo centra. Outlook no redondea
    # esquinas, así que ahí sale cuadrado; en los demás, como se dibujó.
    return (f'<td width="{w}" height="{h}" align="center" valign="middle" '
            f'bgcolor="{one["bg"]}" style="width:{w}px;height:{h}px;'
            f'background-color:{one["bg"]};border-radius:{one["radius"]}px;">'
            f'<a href="{escape(one["href"])}" target="_blank" style="display:block;'
            f'width:{w}px;line-height:{h}px;font-family:{escape(font)};'
            f'font-size:{one["size"]}px;font-weight:{weight};font-style:{style};'
            f'color:{one["color"]};text-align:center;text-decoration:none;'
            f'border-radius:{one["radius"]}px;">{_text(one["text"])}</a></td>')


def _block(items: list[dict[str, Any]], x0: int, y0: int, w: int, h: int) -> str:
    """Una región del lienzo como tabla. Se llama a sí misma por franjas y por
    columnas hasta que cada caja queda sola."""
    if not items:
        return TABLE.format(w=w) + _gap_row(h, w) + "</table>"

    if len(items) == 1:
        one = items[0]
        top, left = one["y"] - y0, one["x"] - x0
        right, bottom = w - left - one["w"], h - top - one["h"]
        return (TABLE.format(w=w) + _gap_row(top, w)
                + f'<tr><td style="font-size:0;line-height:0;">' + TABLE.format(w=w) + "<tr>"
                + _gap_cell(left, one["h"]) + _item_cell(one)
                + _gap_cell(right, one["h"]) + "</tr></table></td></tr>"
                + _gap_row(bottom, w) + "</table>")

    bands = _split(items, "y", "h")
    if len(bands) > 1:
        rows, cursor = [], y0
        for band in bands:
            top = min(one["y"] for one in band)
            bottom = max(one["y"] + one["h"] for one in band)
            rows.append(_gap_row(top - cursor, w))
            rows.append(f"<tr><td>{_block(band, x0, top, w, bottom - top)}</td></tr>")
            cursor = bottom
        rows.append(_gap_row(y0 + h - cursor, w))
        return TABLE.format(w=w) + "".join(rows) + "</table>"

    columns = _split(items, "x", "w")
    if len(columns) == 1:
        # Un molinillo: `problems()` no deja guardarlo, pero la vista previa
        # puede verlo a medio hacer. Se apilan uno debajo de otro en vez de
        # romper.
        return TABLE.format(w=w) + "".join(
            f"<tr><td>{_block([one], x0, one['y'], w, one['h'])}</td></tr>"
            for one in sorted(items, key=lambda it: it["y"])) + "</table>"
    cells, cursor = [], x0
    for column in columns:
        left = min(one["x"] for one in column)
        right = max(one["x"] + one["w"] for one in column)
        cells.append(_gap_cell(left - cursor, h))
        cells.append(f'<td width="{right - left}" valign="top" style="width:{right - left}px;">'
                     f"{_block(column, left, y0, right - left, h)}</td>")
        cursor = right
    cells.append(_gap_cell(x0 + w - cursor, h))
    return TABLE.format(w=w) + "<tr>" + "".join(cells) + "</tr></table>"


def to_html(doc: dict[str, Any], grounds: list[str | None]) -> str:
    """El lienzo como cuerpo de correo. `grounds` es la dirección del fondo de
    cada diapositiva, o None si no tiene.

    Se supone revisado con `problems()`: aquí no se vuelve a preguntar.
    """
    parts = []
    for index, slide in enumerate(doc["slides"]):
        h, bg = slide["h"], slide["bg"]
        url = grounds[index] if index < len(grounds) else None
        front = [one for one in slide["items"] if one["t"] in FRONT]
        inner = _block(front, 0, 0, WIDTH, h)
        if url:
            safe = escape(url)
            cell = (f'<td width="{WIDTH}" height="{h}" valign="top" bgcolor="{bg}" '
                    f'background="{safe}" style="width:{WIDTH}px;height:{h}px;'
                    f"background-color:{bg};background-image:url('{safe}');"
                    f"background-size:{WIDTH}px {h}px;background-repeat:no-repeat;"
                    f'background-position:0 0;">'
                    # Outlook de escritorio no pinta fondos de celda: los pinta
                    # esto, que solo él lee.
                    f'<!--[if gte mso 9]><v:rect xmlns:v="urn:schemas-microsoft-com:vml" '
                    f'fill="true" stroke="false" style="width:{WIDTH}px;height:{h}px;">'
                    f'<v:fill type="frame" src="{safe}" color="{bg}" />'
                    f'<v:textbox inset="0,0,0,0"><![endif]-->'
                    f"<div>{inner}</div>"
                    f"<!--[if gte mso 9]></v:textbox></v:rect><![endif]--></td>")
        else:
            cell = (f'<td width="{WIDTH}" height="{h}" valign="top" bgcolor="{bg}" '
                    f'style="width:{WIDTH}px;height:{h}px;background-color:{bg};">'
                    f"{inner}</td>")
        parts.append(f'<table role="presentation" width="{WIDTH}" align="center" '
                     f'cellpadding="0" cellspacing="0" border="0" '
                     f'style="width:{WIDTH}px;margin:0 auto;border-collapse:collapse;">'
                     f"<tr>{cell}</tr></table>")
    return "\n".join(parts)


# ------------------------------------------------------ que no vaya a spam

# Lo que se exige para guardar. El contenido es una parte de si un correo llega
# (lo que más pesa es la reputación del dominio y su autenticación), pero es la
# parte que decide quien arma la pieza. Cada regla sale de lo que miran los
# filtros de verdad: un correo que es casi pura imagen es el truco clásico del
# spam para esconder el texto, los enlaces acortados esconden a dónde llevan, y
# las mayúsculas y los signos de más son reglas con puntaje en SpamAssassin.
MIN_TEXT = 300            # caracteres de texto real en todo el correo
MAX_IMAGE_SHARE = 0.5     # la mitad del correo, como mucho, es imagen
MAX_BUTTONS = 8
MAX_CAPS = 0.3            # de las letras, cuántas pueden ir en mayúscula
SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
              "buff.ly", "cutt.ly", "rebrand.ly", "shorturl.at", "rb.gy",
              "tiny.cc", "t.ly", "s.id")
# Palabras que los filtros castigan en cualquier idioma que lean. Sin acentos y
# en minúscula, que es como se compara.
TRIGGERS = ("gratis", "ganaste", "ganador", "dinero facil", "haz clic aqui",
            "compra ya", "sin costo", "urgente", "oferta limitada", "free",
            "winner", "click here", "$$$")


def _fold(text: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in plain if not unicodedata.combining(c)).lower()


def _covered(slide: dict[str, Any], cell: int = 10) -> int:
    """Cuánta superficie de la diapositiva tapan sus imágenes, sin contar dos
    veces la que tapan dos encimadas. Se mide en casillas de 10 px."""
    seen: set[tuple[int, int]] = set()
    for one in slide["items"]:
        if one["t"] != "image":
            continue
        for gx in range(max(one["x"], 0) // cell, min(one["x"] + one["w"], WIDTH) // cell):
            for gy in range(max(one["y"], 0) // cell,
                            min(one["y"] + one["h"], slide["h"]) // cell):
                seen.add((gx, gy))
    return len(seen) * cell * cell


def review(doc: dict[str, Any], size: int, *, limit: int) -> list[dict[str, Any]]:
    """Lo que hace que este correo tenga riesgo de ir a spam. Vacío es que no.

    Cada motivo lleva su clave y, si hace falta, el detalle (qué palabra, cuánto
    pesa). La pantalla lo traduce. Con cualquiera, no se guarda.
    """
    found: list[dict[str, Any]] = []
    front = [one for slide in doc["slides"] for one in slide["items"]
             if one["t"] in FRONT]
    words = " ".join(one.get("text", "") for one in front)
    plain_text = MARK_RE.sub("", words)

    # Caracteres como los cuenta una persona: con los espacios entre palabras.
    letters = len(" ".join(plain_text.split()))
    if letters < MIN_TEXT:
        found.append({"key": "few_text", "n": letters, "min": MIN_TEXT})

    area = sum(WIDTH * slide["h"] for slide in doc["slides"]) or 1
    pictures = sum(_covered(slide) for slide in doc["slides"])
    if pictures / area > MAX_IMAGE_SHARE:
        found.append({"key": "image_heavy", "pct": round(100 * pictures / area)})

    if size > limit:
        found.append({"key": "too_big", "kb": round(size / 1024), "max": limit // 1024})

    buttons = [one for one in front if one["t"] == "button"]
    if len(buttons) > MAX_BUTTONS:
        found.append({"key": "many_links", "n": len(buttons), "max": MAX_BUTTONS})
    for one in buttons:
        host = one["href"].split("://", 1)[-1].split("/", 1)[0].lower()
        if host.startswith("www."):
            host = host[4:]
        if host in SHORTENERS:
            found.append({"key": "shortener", "what": host})
            break

    alpha = [c for c in plain_text if c.isalpha()]
    if len(alpha) >= 20 and sum(c.isupper() for c in alpha) / len(alpha) > MAX_CAPS:
        found.append({"key": "caps"})
    if "!!" in plain_text or "¡¡" in plain_text or plain_text.count("!") > 3:
        found.append({"key": "shouting"})

    folded = _fold(plain_text)
    for word in TRIGGERS:
        if re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", folded):
            found.append({"key": "trigger", "what": word})
            break
    return found


MARK_RE = re.compile(r"\*\|[A-Z0-9_]+\|\*")


def images_of(doc: dict[str, Any] | None) -> list[str]:
    """Las fotos que nombra un lienzo (no los fondos, que van aparte)."""
    if not doc:
        return []
    return [one["name"] for slide in doc.get("slides", [])
            for one in slide.get("items", []) if one.get("t") == "image" and one.get("name")]
