"""El lienzo de «Crear plantilla»: de coordenadas libres a un correo.

Quien crea pone cada cosa donde quiere, en **una sola hoja** de 600 px que crece
hacia abajo. Ningún lector de correo entiende «esto va a 120 px de arriba y 40
de la izquierda»: Gmail borra las posiciones y Outlook dibuja con el motor de
Word. Lo que sí respetan todos, al píxel, son **tablas con medidas fijas**. Así
que el lienzo se guarda con sus coordenadas y al armar el correo se traduce a
una cuadrícula:

  * Lo que se toca o se encima se junta en un **grupo** (`groups()`), y cada
    grupo es una caja. Las cajas se reparten en **franjas** (lo que comparte
    altura) y dentro de cada franja en **columnas** (lo que comparte ancho), una
    y otra vez, hasta que cada una queda sola en su celda con los huecos medidos
    alrededor. Es un corte en guillotina: existe mientras nada se enreda en
    molinillo, y eso se comprueba antes de guardar.
  * **Una foto es una imagen de verdad (`<img>`)** en su celda, no un fondo. Si
    el texto de arriba crece en un teléfono, la foto baja con él. Varias fotos o
    rectángulos encimados se funden en una sola imagen del tamaño del grupo.
  * **Solo el texto sobre una foto necesita fondo**, y es el fondo de esa zona:
    una imagen exactamente del tamaño de su celda, para que ningún lector tenga
    que escalarla, con su versión VML para Outlook de escritorio y el color
    promedio de la foto debajo por si no carga.
  * **Un rectángulo sin foto es una celda de color**, sin imagen.
  * Los textos y los botones son **texto de verdad**: el correo no se lee como
    una foto (de lo que más va a spam), las marcas como `*|EDAD|*` funcionan, y
    con las imágenes bloqueadas se sigue leyendo.

Hasta septiembre de 2026 el lienzo iba por **diapositivas**. `parse()` convierte
lo guardado así a una hoja: las apila, y el color de cada una pasa a ser un
rectángulo del ancho entero.

**Nada de lo que llega se usa sin revisar.** El JSON lo escribe el navegador, y
el navegador lo controla quien lo tiene delante: `parse()` lo rehace desde cero
con solo lo que conoce, en los tipos que espera, y `problems()` dice qué no se
puede guardar. El texto se guarda como texto y sale escapado.
"""

from __future__ import annotations

import base64
import json
import math
import re
from io import BytesIO
from typing import Any

from markupsafe import escape

VERSION = 2
WIDTH = 600
# A cuántos píxeles se funde una imagen por cada píxel del lienzo: al doble,
# para que se vea nítida en una pantalla de teléfono. El fondo de una zona con
# texto encima va a uno: tiene que medir lo mismo que su celda.
SCALE = 2

MAX_ITEMS = 60
MIN_HEIGHT = 80
MAX_HEIGHT = 4000
MIN_BOX = 16
# Una línea es un rectángulo tan bajito como su grosor, y es lo único que puede
# medir menos que `MIN_BOX` de alto. Horizontal, vertical o diagonal es girarla.
LINE_MIN = 1
LINE_MAX = 12
TEXT_MAX = 2000
BUTTON_MAX = 60
HREF_MAX = 500
ALT_MAX = 150
MIN_SIZE = 14
MAX_SIZE = 72

KINDS = ("text", "button", "image", "shape")
FRONT = ("text", "button")
BACK = ("image", "shape")

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
    # Las cuatro de abajo no están en Android, y por eso cada una cae en una
    # de las de arriba: quien no la tenga ve una de medidas parecidas, no una
    # cualquiera. No se importan fuentes: Gmail y Outlook ignoran @font-face,
    # así que la letra subida se vería aquí y no allá, y el texto se saldría
    # de su celda.
    "Palatino": "Palatino, 'Palatino Linotype', 'Book Antiqua', Georgia, serif",
    "Garamond": "Garamond, 'Apple Garamond', Baskerville, Georgia, serif",
    "Lucida Sans": "'Lucida Sans Unicode', 'Lucida Grande', Verdana, sans-serif",
    "Century Gothic": "'Century Gothic', 'URW Gothic', 'Trebuchet MS', sans-serif",
}
ALIGNS = ("left", "center", "right")
FITS = ("cover", "contain")
# Las figuras. El rectángulo y la línea (un rectángulo de 1 a 12 px de alto)
# pueden salir como **celda de color**, que es lo más liviano que hay en un
# correo; las demás se pintan en la imagen del grupo, porque Outlook de
# escritorio ignora `border-radius` y no sabe dibujar un polígono.
SHAPES = ("rect", "line", "ellipse", "triangle", "star", "arrow",
          # Las que se sumaron en octubre de 2026: se pintan como las de antes,
          # en la imagen del grupo.
          "diamond", "pentagon", "hexagon", "octagon", "heart", "cross", "bubble",
          "double_arrow")
# La forma que puede tomar una foto (octubre de 2026): cualquiera menos la línea.
MASKS = tuple(one for one in SHAPES if one not in ("rect", "line"))
BORDER_MAX = 20
IMAGE_RADIUS_MAX = 300
# Cuáles siguen siendo una celda de color cuando llenan su grupo.
FLAT = ("rect", "line")

COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Un enlace de botón o de imagen: una página segura o un correo. Ni
# `javascript:`, ni espacios ni comillas, que son como se rompe un atributo.
HREF = re.compile(r"^(https://|mailto:)[^\s\"'<>]+$")


def blank() -> dict[str, Any]:
    """Lo que abre «Crear plantilla»: una hoja blanca y vacía."""
    return {"v": VERSION, "h": 600, "bg": "#FFFFFF", "items": []}


# ------------------------------------------------------------- leer lo que llega

def _finite(value) -> float:
    """Un número de verdad: NaN e infinito no lo son, aunque `float()` los lea
    (un JSON con 1e999 da infinito, y `int()` de eso era un error 500)."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(value)
    return number


def _int(value, default=0) -> int:
    try:
        return int(round(_finite(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def _not_json(constant: str):
    """NaN e Infinity no son JSON, aunque Python los lea."""
    raise ValueError(constant)


def _color(value, default: str) -> str:
    value = str(value or "")
    return value.upper() if COLOR.match(value) else default


def _clean(text: Any, limit: int) -> str:
    """Solo texto: los saltos de línea se quedan, el resto de controles no."""
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return "".join(c for c in text if c == "\n" or c >= " ")[:limit + 1]


MIN_CROP = 0.05


def _crop(raw: Any) -> list[float] | None:
    """Qué parte de la foto se ve: x, y, ancho y alto, de 0 a 1.

    Sin recorte se ve entera, que es lo de siempre. Lo que no sea cuatro
    números dentro de la foto, o un pedazo más chico que un veinteavo, se
    descarta: el recuadro lo escribe el navegador.
    """
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        x, y, w, h = (round(_finite(one), 4) for one in raw)
    except (TypeError, ValueError):
        return None
    if min(x, y) < 0 or min(w, h) < MIN_CROP or x + w > 1.0001 or y + h > 1.0001:
        return None
    if (x, y, w, h) == (0, 0, 1, 1):
        return None
    return [x, y, min(w, 1 - x), min(h, 1 - y)]


# El formato por palabras (octubre de 2026): un texto puede llevar `runs`,
# tramos con su negrita, cursiva, subrayado, color y enlace. El estilo de la caja
# (`bold`, `italic`, `color`) es el de base, y cada tramo dice solo en qué cambia.
# `text` sigue siendo el texto entero, armado aquí con los tramos: así no cambian
# las variables, el conteo de la revisión ni la API de antes.
RUNS_MAX = 200
# Los tipos de viñeta (octubre de 2026): punto, gancho, estrella y círculo, con
# la entidad que va en el correo. Un `list: true` de antes es el punto.
BULLETS = {"dot": "&#8226;", "check": "&#10003;", "star": "&#9733;", "circle": "&#9675;"}
RUN_FLAGS = ("b", "i", "u")


def _run_style(run: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in run.items() if key != "text"}


def _runs(raw: Any, one: dict[str, Any]) -> list[dict[str, Any]]:
    """Los tramos de un texto, limpios y unidos los seguidos que se ven igual.
    Lo que dice lo mismo que la caja se quita."""
    if not isinstance(raw, list):
        return []
    base = {"b": one["bold"], "i": one["italic"], "u": False, "color": one["color"]}
    out: list[dict[str, Any]] = []
    for piece in raw[:RUNS_MAX]:
        if not isinstance(piece, dict):
            continue
        text = _clean(piece.get("text"), TEXT_MAX)
        if not text:
            continue
        run: dict[str, Any] = {"text": text}
        for key in RUN_FLAGS:
            if isinstance(piece.get(key), bool) and piece[key] != base[key]:
                run[key] = piece[key]
        tone = str(piece.get("color") or "")
        if COLOR.match(tone) and tone.upper() != base["color"].upper():
            run["color"] = tone.upper()
        href = str(piece.get("href") or "").strip()[:HREF_MAX + 1]
        if href:
            run["href"] = href
        if out and _run_style(out[-1]) == _run_style(run):
            out[-1]["text"] += text
        else:
            out.append(run)
    return out


def _border(one: dict[str, Any], raw: dict[str, Any]) -> None:
    """El borde de una foto o una figura: su grosor (hasta 20 px) y su color.
    Sin grosor no se escribe nada."""
    width = min(max(_int(raw.get("border"), 0), 0), BORDER_MAX)
    if width:
        one["border"] = width
        one["border_color"] = _color(raw.get("border_color"), "#18181B")


def links_of(one: dict[str, Any]) -> list[str]:
    """Los enlaces de un elemento: el de un botón (aunque esté vacío, que es lo
    que lo hace botón), el de una foto si lo tiene, y los de los tramos de un
    texto."""
    if one["t"] == "button":
        return [one["href"]]
    if one["t"] == "image":
        return [one["href"]] if one["href"] else []
    if one["t"] == "text":
        return [run["href"] for run in one.get("runs") or [] if run.get("href")]
    return []


def _item(raw: dict[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("t")
    if kind not in KINDS:
        return None
    one: dict[str, Any] = {"t": kind, "x": _int(raw.get("x")), "y": _int(raw.get("y")),
                           "w": _int(raw.get("w"), 100), "h": _int(raw.get("h"), 40)}
    # El grupo del editor: lo que se mueve junto. No cambia cómo se arma el
    # correo, que lo siguen decidiendo las cajas que se enciman, así que
    # `groups()` y `to_html()` lo ignoran. Se guarda para que sobreviva a
    # cerrar la pieza.
    tie = _int(raw.get("g"), 0)
    if 1 <= tie <= 999:
        one["g"] = tie
    if kind == "image":
        one["name"] = str(raw.get("name") or "")[:80]
        one["fit"] = raw.get("fit") if raw.get("fit") in FITS else "cover"
        try:
            ratio = _finite(raw.get("r") or 0)
        except (TypeError, ValueError):
            ratio = 0
        # La proporción de la foto, ancho entre alto. Solo la usa el editor.
        one["r"] = round(ratio, 4) if 0.05 <= ratio <= 20 else 0
        one["href"] = str(raw.get("href") or "").strip()[:HREF_MAX + 1]
        one["alt"] = " ".join(_clean(raw.get("alt"), ALT_MAX).split())[:ALT_MAX]
        cut = _crop(raw.get("crop"))
        if cut:
            one["crop"] = cut
        # Grados, como en CSS: hacia la derecha. El texto y el botón no giran,
        # que girarlos sería convertirlos en imagen.
        one["rot"] = _int(raw.get("rot")) % 360
        # Su forma, sus esquinas y su borde (octubre de 2026). Solo se escriben
        # puestos, así las fotos de antes se leen igual.
        if raw.get("mask") in MASKS:
            one["mask"] = raw["mask"]
        radius = min(max(_int(raw.get("radius"), 0), 0), IMAGE_RADIUS_MAX)
        if radius:
            one["radius"] = radius
        _border(one, raw)
        return one
    if kind == "shape":
        one["bg"] = _color(raw.get("bg"), "#E0F2FE")
        one["radius"] = min(max(_int(raw.get("radius"), 0), 0), 60)
        one["shape"] = raw.get("shape") if raw.get("shape") in SHAPES else "rect"
        # Antes una «línea» podía medir lo que fuera de alto y se dibujaba igual
        # que un rectángulo. La que pasa del grosor de una línea se lee como lo
        # que siempre pareció: así ninguna pieza guardada cambia.
        if one["shape"] == "line" and one["h"] > LINE_MAX:
            one["shape"] = "rect"
        one["rot"] = _int(raw.get("rot")) % 360
        _border(one, raw)
        return one
    one["text"] = _clean(raw.get("text"), TEXT_MAX if kind == "text" else BUTTON_MAX)
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
            line = _finite(line)
        except (TypeError, ValueError):
            line = 1.4
        one["line"] = min(max(round(line, 2), 1.0), 2.5)
        # Con viñetas, cada renglón es un punto de la lista. Solo se escribe
        # cuando está puesto, así los textos de siempre se leen igual que antes.
        bullet = raw.get("list")
        if bullet:
            one["list"] = bullet if bullet in BULLETS else "dot"
        # Con tramos, el texto son ellos; y si ninguno cambia nada, es un texto
        # de siempre y no se guardan.
        runs = _runs(raw.get("runs"), one)
        if runs:
            one["text"] = "".join(run["text"] for run in runs)[:TEXT_MAX + 1]
            if any(_run_style(run) for run in runs):
                one["runs"] = runs
    else:
        one["href"] = str(raw.get("href") or "").strip()[:HREF_MAX + 1]
        one["bg"] = _color(raw.get("bg"), "#31A9E8")
        one["radius"] = min(max(_int(raw.get("radius"), 8), 0), 60)
    return one


def _from_slides(slides: list) -> dict[str, Any] | None:
    """Lo guardado cuando el lienzo iba por diapositivas, como una hoja.

    Se apilan en su orden. La hoja es blanca, y cada diapositiva de otro color
    se vuelve un rectángulo del ancho entero, detrás de lo suyo.
    """
    items: list[dict[str, Any]] = []
    top = 0
    for slide in slides[:20]:
        if not isinstance(slide, dict):
            return None
        h = _int(slide.get("h"), 400)
        bg = _color(slide.get("bg"), "#FFFFFF")
        if bg != "#FFFFFF":
            items.append({"t": "shape", "x": 0, "y": top, "w": WIDTH, "h": h,
                          "bg": bg, "radius": 0})
        for raw in (slide.get("items") or [])[:MAX_ITEMS + 1]:
            if isinstance(raw, dict):
                one = _item(raw)
                if one:
                    one["y"] += top
                    items.append(one)
        top += h
    return {"v": VERSION, "h": top, "bg": "#FFFFFF", "items": items}


def parse(raw: str) -> dict[str, Any] | None:
    """El lienzo que mandó el navegador, rehecho con solo lo que conocemos.

    Devuelve None si ni siquiera es un lienzo. Lo que sí es, sale con los tipos
    en su sitio aunque llegue con números escritos como texto; lo que está fuera
    de rango se queda como llegó, para que `problems()` lo diga.
    """
    try:
        data = (json.loads(raw or "", parse_constant=_not_json)
                if isinstance(raw, str) else raw)
    except (TypeError, ValueError, RecursionError):
        return None
    return read(data)


def read(data: Any) -> dict[str, Any] | None:
    """Lo mismo que `parse()`, desde un diccionario: lo guardado en la base."""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("slides"), list):
        return _from_slides(data["slides"])
    if not isinstance(data.get("items"), list):
        return None
    items = [_item(one) for one in data["items"][:MAX_ITEMS + 1] if isinstance(one, dict)]
    return {"v": VERSION, "h": _int(data.get("h"), 600),
            "bg": _color(data.get("bg"), "#FFFFFF"),
            "items": [one for one in items if one]}


# ---------------------------------------------------------------- los grupos

def bounds(one: dict[str, Any]) -> dict[str, int]:
    """Lo que ocupa de verdad: su caja, o la que abarca su giro.

    La caja que se arrastra en el editor (`x/y/w/h`) no cambia al girar: lo que
    cambia es la huella, y es la huella la que decide qué se encima con qué, qué
    se sale de la hoja y cuánta superficie es imagen. Un texto o un botón nunca
    giran, así que devuelven la suya.
    """
    angle = one.get("rot") or 0
    if not angle:
        return one
    import math

    rad = math.radians(angle)
    cos, sin = abs(math.cos(rad)), abs(math.sin(rad))
    wide = round(one["w"] * cos + one["h"] * sin)
    tall = round(one["w"] * sin + one["h"] * cos)
    return {"x": round(one["x"] + (one["w"] - wide) / 2),
            "y": round(one["y"] + (one["h"] - tall) / 2),
            "w": wide, "h": tall}


def _touch(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Si dos cajas se enciman. Tocarse por el borde no cuenta."""
    a, b = bounds(a), bounds(b)
    return (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
            and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])


def overlaps(doc: dict[str, Any]) -> list[int]:
    """Los textos y botones que se enciman con otro texto o botón."""
    front = [(i, one) for i, one in enumerate(doc["items"]) if one["t"] in FRONT]
    bad: set[int] = set()
    for pos, (i, a) in enumerate(front):
        for j, b in front[pos + 1:]:
            if _touch(a, b):
                bad.update((i, j))
    return sorted(bad)


def _box(members: list[dict[str, Any]]) -> dict[str, int]:
    """La caja que abarca a todos, contando lo que crece al girar."""
    boxes = [bounds(one) for one in members]
    x = min(one["x"] for one in boxes)
    y = min(one["y"] for one in boxes)
    return {"x": x, "y": y,
            "w": max(one["x"] + one["w"] for one in boxes) - x,
            "h": max(one["y"] + one["h"] for one in boxes) - y}


def groups(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Lo que va junto en una celda, en orden de arriba abajo.

    Dos cosas que se enciman van en el mismo grupo, y también lo que se enciman
    con la caja del grupo: una tabla no puede partir una caja por la mitad. Cada
    grupo dice qué es (`kind`):

      * `front`: un texto o un botón solo.
      * `color`: un solo rectángulo, con o sin texto encima, que llena su caja.
        Es una celda de color, sin imagen.
      * `picture`: fotos o rectángulos sin nada encima. Una imagen.
      * `backdrop`: fotos con texto o botones encima. Un fondo del tamaño de la
        celda, y el texto dentro.

    Los elementos de cada grupo van en el orden de la lista, que es el orden en
    que se pintan: el último queda encima.
    """
    items = doc["items"]
    found = [[i] for i in range(len(items))]
    changed = True
    while changed:
        changed = False
        boxes = [_box([items[i] for i in one]) for one in found]
        for a in range(len(found)):
            for b in range(a + 1, len(found)):
                if _touch(boxes[a], boxes[b]):
                    found[a] = sorted(found[a] + found[b])
                    del found[b]
                    changed = True
                    break
            if changed:
                break

    out = []
    for members in found:
        parts = [items[i] for i in members]
        box = _box(parts)
        backs = [one for one in parts if one["t"] in BACK]
        fronts = [one for one in parts if one["t"] in FRONT]
        if not backs:
            kind = "front"
        elif (len(backs) == 1 and backs[0]["t"] == "shape"
              and backs[0].get("shape", "rect") in FLAT
              and not backs[0].get("rot")
              # Con borde se pinta: Outlook no dibuja bien un borde con esquinas.
              and not backs[0].get("border")
              and _box(backs) == box):
            kind = "color"
        elif fronts:
            kind = "backdrop"
        else:
            kind = "picture"
        out.append({**box, "kind": kind, "items": parts, "backs": backs,
                    "fronts": fronts})
    out.sort(key=lambda one: (one["y"], one["x"]))
    return out


def _needs_image(group: dict[str, Any]) -> bool:
    return group["kind"] in ("picture", "backdrop")


def _linked(group: dict[str, Any]) -> str:
    """El enlace de una foto sola, que es la única que puede llevarlo."""
    if group["kind"] == "picture" and len(group["items"]) == 1:
        return group["items"][0].get("href", "")
    return ""


# ------------------------------------------------------------ qué no se guarda

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

    if not doc["items"]:
        add("empty")
    if not MIN_HEIGHT <= doc["h"] <= MAX_HEIGHT:
        add("height")
    if len(doc["items"]) > MAX_ITEMS:
        add("too_many_items")
    for one in doc["items"]:
        # La caja es la que se arrastra; la huella es lo que ocupa girada, y es
        # la que no puede salirse de la hoja.
        seat = bounds(one)
        # A una línea no se le piden los 16 px de alto: su alto es su grosor.
        thin = one["t"] == "shape" and one.get("shape") == "line"
        if (seat["x"] < 0 or seat["y"] < 0 or one["w"] < MIN_BOX
                or (not thin and one["h"] < MIN_BOX)
                or seat["x"] + seat["w"] > WIDTH or seat["y"] + seat["h"] > doc["h"]):
            add("bounds")
        if thin and not LINE_MIN <= one["h"] <= LINE_MAX:
            add("line")
        if one["t"] == "shape":
            continue
        if one["t"] == "image":
            if not one["name"] or not owns(one["name"]):
                add("image")
            if one["href"] and not HREF.match(one["href"]):
                add("href")
            # Sin descripción no se guarda: es lo que se lee cuando el buzón
            # bloquea las imágenes, que pasa en la mitad de los casos.
            if not one["alt"].strip():
                add("alt")
            continue
        if one["font"] not in FONTS:
            add("font")
        if not MIN_SIZE <= one["size"] <= MAX_SIZE:
            add("size")
        if one["t"] == "text" and len(one["text"]) > TEXT_MAX:
            add("text_long")
        if one["t"] == "text" and any(not HREF.match(href) for href in links_of(one)):
            add("href")
        if one["t"] == "button":
            if not one["text"].strip() or len(one["text"]) > BUTTON_MAX:
                add("button_text")
            if not HREF.match(one["href"]):
                add("href")
    if overlaps(doc):
        add("overlap")
    elif _tangled(doc):
        add("tangled")
    # Una foto con enlace va sola: un fondo o una imagen fundida no pueden
    # llevar el enlace de una sola de sus partes.
    for group in groups(doc):
        if len(group["items"]) > 1 and any(one["t"] == "image" and one["href"]
                                           for one in group["items"]):
            add("link_overlap")
    return found


# Lo que ni un borrador puede guardar (octubre de 2026). Un borrador se guarda
# aunque no cumpla las reglas de forma ni la revisión antispam, porque no se
# puede enviar; pero lo de aquí es seguridad o recursos: una imagen de otra
# cuenta, un enlace que no es https ni mailto, una hoja o una lista de
# elementos que no caben, y una fuente o un tamaño que no se sabe dibujar.
def hard_problems(doc: dict[str, Any] | None, *, owns=lambda name: True) -> list[str]:
    if doc is None:
        return ["broken"]
    found: list[str] = []

    def add(reason: str) -> None:
        if reason not in found:
            found.append(reason)

    if not MIN_HEIGHT <= doc["h"] <= MAX_HEIGHT:
        add("height")
    if len(doc["items"]) > MAX_ITEMS:
        add("too_many_items")
    for one in doc["items"]:
        if one["t"] == "image" and (not one["name"] or not owns(one["name"])):
            add("image")
        if any(href and not HREF.match(href) for href in links_of(one)):
            add("href")
        if one["t"] in FRONT:
            if one["font"] not in FONTS:
                add("font")
            if not MIN_SIZE <= one["size"] <= MAX_SIZE:
                add("size")
    return found


def linked_alone(doc: dict[str, Any]) -> list[int]:
    """Las fotos con enlace que tienen algo encima, para marcarlas en el editor."""
    bad: list[int] = []
    for group in groups(doc):
        if len(group["items"]) > 1:
            bad.extend(doc["items"].index(one) for one in group["items"]
                       if one["t"] == "image" and one["href"])
    return sorted(bad)


# --------------------------------------------------------- las imágenes fundidas

def _triangle(w: int, h: int) -> list[tuple[float, float]]:
    return [(w / 2, 0), (w, h), (0, h)]


def _star(w: int, h: int) -> list[tuple[float, float]]:
    """Una estrella de cinco puntas dentro de su caja."""
    import math

    points = []
    for n in range(10):
        # Empezando arriba, y alternando punta y valle.
        angle = math.pi / 2 + n * math.pi / 5
        far = 1.0 if n % 2 == 0 else 0.4
        points.append((w / 2 + math.cos(angle) * w / 2 * far,
                       h / 2 - math.sin(angle) * h / 2 * far))
    return points


def _arrow(w: int, h: int) -> list[tuple[float, float]]:
    """Una flecha hacia la derecha. Para que apunte a otro lado se gira."""
    return [(0, h * 0.3), (w * 0.6, h * 0.3), (w * 0.6, 0), (w, h / 2),
            (w * 0.6, h), (w * 0.6, h * 0.7), (0, h * 0.7)]


def _regular(sides: int, turn: float = 0.0):
    """Un polígono regular dentro de su caja, con una punta arriba."""
    import math

    def points(w: int, h: int) -> list[tuple[float, float]]:
        return [(w / 2 + math.cos(-math.pi / 2 + turn + k * 2 * math.pi / sides) * w / 2,
                 h / 2 + math.sin(-math.pi / 2 + turn + k * 2 * math.pi / sides) * h / 2)
                for k in range(sides)]
    return points


def _diamond(w: int, h: int) -> list[tuple[float, float]]:
    return [(w / 2, 0), (w, h / 2), (w / 2, h), (0, h / 2)]


def _heart(w: int, h: int) -> list[tuple[float, float]]:
    """Un corazón, con la curva de siempre, ajustado a su caja."""
    import math

    raw = []
    for n in range(48):
        t = n * 2 * math.pi / 48
        raw.append((16 * math.sin(t) ** 3,
                    -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t)
                      - math.cos(4 * t))))
    xs, ys = [p[0] for p in raw], [p[1] for p in raw]
    return [((x - min(xs)) / (max(xs) - min(xs)) * w, (y - min(ys)) / (max(ys) - min(ys)) * h)
            for x, y in raw]


def _cross(w: int, h: int) -> list[tuple[float, float]]:
    a, b = 0.35, 0.65
    return [(w * a, 0), (w * b, 0), (w * b, h * a), (w, h * a), (w, h * b), (w * b, h * b),
            (w * b, h), (w * a, h), (w * a, h * b), (0, h * b), (0, h * a), (w * a, h * a)]


def _bubble(w: int, h: int) -> list[tuple[float, float]]:
    """Un globo de diálogo, con su pico abajo a la izquierda."""
    return [(0, 0), (w, 0), (w, h * 0.75), (w * 0.45, h * 0.75), (w * 0.22, h),
            (w * 0.27, h * 0.75), (0, h * 0.75)]


def _double_arrow(w: int, h: int) -> list[tuple[float, float]]:
    return [(0, h / 2), (w * 0.25, 0), (w * 0.25, h * 0.3), (w * 0.75, h * 0.3),
            (w * 0.75, 0), (w, h / 2), (w * 0.75, h), (w * 0.75, h * 0.7),
            (w * 0.25, h * 0.7), (w * 0.25, h)]


POLYGONS = {"triangle": _triangle, "star": _star, "arrow": _arrow,
            "diamond": _diamond, "pentagon": _regular(5), "hexagon": _regular(6),
            "octagon": _regular(8, 3.141592653589793 / 8), "heart": _heart,
            "cross": _cross, "bubble": _bubble, "double_arrow": _double_arrow}


def shape_points() -> dict[str, list[list[float]]]:
    """Los puntos de cada figura, en fracciones de su caja: el editor los usa
    para dibujar lo mismo que el correo (octubre de 2026)."""
    return {name: [[round(x, 4), round(y, 4)] for x, y in make(1, 1)]
            for name, make in POLYGONS.items()}


def _figure(pen, figure: str, box, radius: float, *, fill=None, border: float = 0,
            edge=None) -> None:
    """Una figura en su caja, rellena, con borde o las dos cosas."""
    corners = (0, 0, box[0] - 1, box[1] - 1)
    outline = edge if border else None
    width = max(int(round(border)), 0) if border else 0
    if figure == "ellipse":
        pen.ellipse(corners, fill=fill, outline=outline, width=width or 1)
    elif figure in POLYGONS:
        pen.polygon(POLYGONS[figure](box[0] - 1, box[1] - 1), fill=fill, outline=outline,
                    width=width or 1)
    else:
        pen.rounded_rectangle(corners, radius=min(radius, min(box) / 2), fill=fill,
                              outline=outline, width=width or 1)


def _shaped(picture, figure: str, radius: float, border: float, edge):
    """Una foto con forma (la máscara), esquinas redondas y borde: se dibuja al
    cuádruple y se achica, para que la orilla no salga dentada."""
    from PIL import Image, ImageChops, ImageDraw

    big = (picture.width * 4, picture.height * 4)
    mask = Image.new("L", big, 0)
    _figure(ImageDraw.Draw(mask), figure, big, radius * 4, fill=255)
    mask = mask.resize(picture.size, Image.LANCZOS)
    picture.putalpha(ImageChops.multiply(picture.getchannel("A"), mask))
    if border:
        layer = Image.new("RGBA", big, (0, 0, 0, 0))
        _figure(ImageDraw.Draw(layer), figure, big, radius * 4, border=border * 4, edge=edge)
        picture = Image.alpha_composite(picture, layer.resize(picture.size, Image.LANCZOS))
    return picture


def _paint(group: dict[str, Any], page: str, load, scale: int):
    """Las fotos y los rectángulos de un grupo, pintados en su caja."""
    from PIL import Image, ImageDraw, ImageOps

    size = (max(group["w"] * scale, 1), max(group["h"] * scale, 1))
    ground = Image.new("RGB", size, page)
    for one in group["backs"]:
        spot = ((one["x"] - group["x"]) * scale, (one["y"] - group["y"]) * scale)
        box = (max(one["w"] * scale, 1), max(one["h"] * scale, 1))
        if one["t"] == "shape":
            # En su propia hoja transparente, para poder girarla. Sin giro se
            # pega igual: lo que se ve es lo mismo.
            piece = Image.new("RGBA", box, (0, 0, 0, 0))
            figure = one.get("shape", "rect")
            _figure(ImageDraw.Draw(piece), figure, box, one["radius"] * scale,
                    fill=one["bg"])
            if one.get("border"):
                # El borde, por dentro de la figura, con su orilla suave.
                piece = _shaped(piece, figure if figure != "line" else "rect",
                                one["radius"] * scale, one["border"] * scale,
                                one["border_color"])
            _drop(ground, piece, one, spot, box)
            continue
        raw = load(one["name"])
        if not raw:
            continue
        with Image.open(BytesIO(raw)) as opened:
            picture = opened.convert("RGBA")
        cut = one.get("crop")
        if cut:
            # Lo que el cliente dejó dentro del recuadro. La foto guardada no
            # se toca: el recorte vive en la pieza y se puede cambiar mañana.
            wide, tall = picture.size
            left, top = round(cut[0] * wide), round(cut[1] * tall)
            picture = picture.crop((left, top,
                                    min(wide, left + round(cut[2] * wide)),
                                    min(tall, top + round(cut[3] * tall))))
        if one.get("fit") == "contain":
            picture.thumbnail(box, Image.LANCZOS)
            spot = (spot[0] + (box[0] - picture.width) // 2,
                    spot[1] + (box[1] - picture.height) // 2)
        else:
            picture = ImageOps.fit(picture, box, Image.LANCZOS)
        if one.get("mask") or one.get("radius") or one.get("border"):
            picture = _shaped(picture, one.get("mask") or "rect",
                              (one.get("radius") or 0) * scale,
                              (one.get("border") or 0) * scale, one.get("border_color"))
        _drop(ground, picture, one, spot, box)
    return ground


def _drop(ground, piece, one: dict[str, Any], spot, box) -> None:
    """Pegar una pieza en su sitio, girada sobre su centro si lo lleva.

    Se gira al revés que en PIL, que cuenta al contrario que CSS, y se pega
    centrada en la caja de siempre: lo que crece al girar son las esquinas, que
    es justo lo que `bounds()` ya le reservó al grupo.
    """
    from PIL import Image

    angle = one.get("rot") or 0
    if angle:
        middle = (spot[0] + box[0] / 2, spot[1] + box[1] / 2)
        piece = piece.rotate(-angle, resample=Image.BICUBIC, expand=True)
        spot = (round(middle[0] - piece.width / 2), round(middle[1] - piece.height / 2))
    ground.paste(piece, (int(spot[0]), int(spot[1])), piece)


def parts(doc: dict[str, Any], load) -> list[bytes | None]:
    """La imagen de cada grupo que la necesita, en JPEG; None en los demás.

    `load(name)` devuelve los bytes de una imagen de la cuenta, o None. Va en el
    mismo orden que `groups()`, y así se guarda: `to_html()` la lee por
    posición.
    """
    out: list[bytes | None] = []
    for group in groups(doc):
        if not _needs_image(group):
            out.append(None)
            continue
        scale = SCALE if group["kind"] == "picture" else 1
        ground = _paint(group, doc["bg"], load, scale)
        buffer = BytesIO()
        ground.save(buffer, format="JPEG", quality=80, optimize=True, progressive=True)
        out.append(buffer.getvalue())
    return out


def average(raw: bytes | None, default: str) -> str:
    """El color promedio de una imagen: lo que se ve si la imagen no carga."""
    if not raw:
        return default
    from PIL import Image

    with Image.open(BytesIO(raw)) as opened:
        r, g, b = opened.convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0))
    return f"#{r:02X}{g:02X}{b:02X}"


def store(db, account_id, doc: dict[str, Any], load) -> tuple[list, list]:
    """Guardar la imagen de cada grupo que la lleva. Devuelve sus nombres y sus
    colores promedio, en el orden de `groups()`.

    Son del sistema (`kind: background`): no cuentan contra el tope de 20.
    """
    from models import image as images

    names, shades = [], []
    for raw in parts(doc, load):
        names.append(images.save(db, account_id, data=raw, ext="jpg",
                                 mime="image/jpeg", kind=images.BACKGROUND)
                     if raw else None)
        shades.append(average(raw, doc["bg"]) if raw else None)
    return names, shades


def data_url(raw: bytes) -> str:
    """Una imagen dentro del propio documento, para la vista previa: no se
    guarda nada por mirar cómo queda."""
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")


# --------------------------------------------------------------- la cuadrícula

def _split(items: list[dict[str, Any]], start: str, size: str) -> list[list[dict[str, Any]]]:
    """Repartir en grupos que no comparten nada en un eje.

    Con `y`/`h` salen las franjas, con `x`/`w` las columnas. Dos cajas van en el
    mismo grupo si se solapan en ese eje, y eso se contagia.
    """
    found: list[list[dict[str, Any]]] = []
    end = None
    for one in sorted(items, key=lambda it: it[start]):
        if found and one[start] < end:
            found[-1].append(one)
            end = max(end, one[start] + one[size])
        else:
            found.append([one])
            end = one[start] + one[size]
    return found


def _cuttable(items: list[dict[str, Any]]) -> bool:
    if len(items) <= 1:
        return True
    for start, size in (("y", "h"), ("x", "w")):
        parts_ = _split(items, start, size)
        if len(parts_) > 1:
            return all(_cuttable(one) for one in parts_)
    return False


def _tangled(doc: dict[str, Any]) -> bool:
    """Si las cajas no se pueden cortar en guillotina.

    Pasa solo con un molinillo (cuatro cajas que se rodean sin tocarse). No hay
    tabla que lo dibuje, así que se pide moverlas en vez de adivinar. Se mira
    entre grupos y, dentro de cada grupo con texto encima, entre sus textos.
    """
    found = groups(doc)
    if not _cuttable(found):
        return True
    return any(not _cuttable(one["fronts"]) for one in found if one["kind"] != "front")


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
            f'height:{height}px;{_thin(height) or "font-size:0;line-height:0;"}">&nbsp;</td>')


def _thin(height: int) -> str:
    """Lo que necesita una celda más baja que un renglón, que solo pasa al lado
    de una línea: Outlook de escritorio no baja de lo que mide una letra si no
    se le fija el interlineado al alto exacto."""
    if height >= MIN_BOX:
        return ""
    return f"font-size:1px;line-height:{height}px;mso-line-height-rule:exactly;"


def _text(value: str) -> str:
    """El texto escapado, con sus saltos de línea."""
    return str(escape(value)).replace("\n", "<br>")


def _run_html(run: dict[str, Any], one: dict[str, Any]) -> str:
    """Un tramo con su formato. Un enlace lleva su color y su subrayado
    escritos: sin ellos Gmail lo pinta de azul y lo subraya a su gusto."""
    text = _text(run["text"])
    style = ""
    if "b" in run:
        style += f"font-weight:{'bold' if run['b'] else 'normal'};"
    if "i" in run:
        style += f"font-style:{'italic' if run['i'] else 'normal'};"
    tone = run.get("color") or one["color"]
    if run.get("href"):
        decoration = "underline" if run.get("u") else "none"
        return (f'<a href="{escape(run["href"])}" target="_blank" class="{ink(tone)}" '
                f'style="color:{tone};text-decoration:{decoration};{style}">{text}</a>')
    if run.get("u"):
        style += "text-decoration:underline;"
    if "color" in run:
        style += f"color:{tone};"
    if not style:
        return text
    marked = f' class="{ink(tone)}"' if "color" in run else ""
    return f'<span{marked} style="{style}">{text}</span>'


def _rich(one: dict[str, Any]) -> str:
    """Lo escrito de un texto: con su formato por palabras, si lo tiene."""
    if not one.get("runs"):
        return _text(one["text"])
    return "".join(_run_html(run, one) for run in one["runs"])


def text_lines(one: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Los renglones de un texto, cada uno con sus tramos. Los usan las viñetas
    del correo y el PDF."""
    lines: list[list[dict[str, Any]]] = [[]]
    for run in one.get("runs") or [{"text": one["text"]}]:
        for at, part in enumerate(run["text"].split("\n")):
            if at:
                lines.append([])
            if part:
                lines[-1].append({**run, "text": part})
    return lines


def line_px(one: dict[str, Any]) -> int:
    """El interlineado en píxeles: Outlook solo lo respeta así, y el editor
    usa la misma cuenta para que el texto ocupe lo mismo en los dos."""
    return round(one["size"] * one.get("line", 1.4))


def ink(color: str) -> str:
    """La clase que protege un color de letra del modo oscuro (`dark_css()`)."""
    return "sac-" + color[1:].upper()


def paint(color: str) -> str:
    """La clase que protege un color de fondo del modo oscuro."""
    return "sab-" + color[1:].upper()


def _font_style(one: dict[str, Any]) -> str:
    font = FONTS.get(one["font"], FONTS["Arial"])
    return (f"font-family:{escape(font)};font-size:{one['size']}px;"
            f"font-weight:{'bold' if one['bold'] else 'normal'};"
            f"font-style:{'italic' if one['italic'] else 'normal'};"
            f"color:{one['color']};")


def dot_px(one: dict[str, Any]) -> int:
    """El ancho de la columna de la viñeta. El editor hace la misma cuenta, para
    que el texto se parta en el mismo sitio en los dos."""
    return round(one["size"] * 1.2)


def _bullets(one: dict[str, Any], style: str) -> str:
    """Un texto con viñetas: una fila por renglón, la viñeta en su columna y el
    texto en la otra, con sangría francesa. Una tabla y no `<ul>`, que Outlook
    de escritorio dibuja con márgenes propios. Un renglón vacío es un hueco."""
    w, lh, dot = one["w"], line_px(one), dot_px(one)
    cell = f"{style}line-height:{lh}px;mso-line-height-rule:exactly;"
    rows = []
    for runs in text_lines(one):
        line = "".join(run["text"] for run in runs)
        if not line.strip():
            rows.append(f'<tr><td colspan="2" height="{lh}" style="height:{lh}px;'
                        f'line-height:{lh}px;font-size:0;">&nbsp;</td></tr>')
            continue
        rows.append(f'<tr><td width="{dot}" valign="top" align="center" '
                    f'class="{ink(one["color"])}" style="width:{dot}px;{cell}'
                    f'text-align:center;">{BULLETS.get(one["list"], BULLETS["dot"])}</td>'
                    f'<td width="{w - dot}" valign="top" class="{ink(one["color"])}" '
                    f'style="width:{w - dot}px;{cell}word-wrap:break-word;">'
                    f'<span class="{ink(one["color"])}" style="{style}'
                    f'line-height:{lh}px;">'
                    + "".join(_run_html(run, one) for run in runs)
                    + '</span></td></tr>')
    return TABLE.format(w=w) + "".join(rows) + "</table>"


# Una variable o un bloque de una lista dentro de un texto (`*|NOMBRE|*`,
# `*|#TRANSACCIONES|*`): lo que pone se sabe solo al enviar.
VARIABLE = re.compile(r"\*\|[#^/]?[A-Z0-9_]+\|\*")


def has_variables(one: dict[str, Any]) -> bool:
    return bool(VARIABLE.search(one.get("text", "")))


def _clipped(one: dict[str, Any], inner: str) -> str:
    """El texto dentro de su caja (octubre de 2026): lo que no cabe no sale, y
    el correo mide lo mismo que el lienzo. Antes la celda crecía con el texto y
    empujaba todo lo de abajo.

    **Una caja con variables no se recorta**: el largo de cada valor se sabe
    solo al enviar (un nombre de 120 caracteres, una tabla de diez filas), y
    recortarla cortaría datos de la persona. Crece, como antes.

    Lo respetan Gmail, Apple Mail, Outlook.com, el Outlook nuevo y Yahoo
    (`overflow` y `max-height` en un `div`, según caniemail.com). **Outlook de
    escritorio para Windows no**: ahí el texto que no cabe sigue empujando."""
    if has_variables(one):
        return inner
    h = one["h"]
    return f'<div style="height:{h}px;max-height:{h}px;overflow:hidden;">{inner}</div>'


def _front_cell(one: dict[str, Any], *, inside_vml: bool) -> str:
    w, h = one["w"], one["h"]
    style = _font_style(one)
    if one["t"] == "text" and one.get("list"):
        # Con viñetas va siempre a la izquierda: centrada, la viñeta de cada
        # renglón quedaría en otro sitio.
        return (f'<td width="{w}" height="{h}" valign="top" align="left" '
                f'class="{ink(one["color"])}" '
                f'style="width:{w}px;height:{h}px;{style}'
                f'line-height:{line_px(one)}px;mso-line-height-rule:exactly;'
                f'text-align:left;">{_clipped(one, _bullets(one, style))}</td>')
    if one["t"] == "text":
        # La letra va en la celda y otra vez en un <span>: dentro de un fondo
        # VML, Outlook de escritorio ignora lo que dice la celda.
        return (f'<td width="{w}" height="{h}" valign="top" align="{one["align"]}" '
                f'class="{ink(one["color"])}" '
                f'style="width:{w}px;height:{h}px;{style}'
                f'line-height:{line_px(one)}px;mso-line-height-rule:exactly;'
                f'text-align:{one["align"]};word-wrap:break-word;">'
                + _clipped(one, f'<span class="{ink(one["color"])}" style="{style}'
                                f'line-height:{line_px(one)}px;">{_rich(one)}</span>')
                + '</td>')
    href = escape(one["href"])
    link = (f'<a href="{href}" target="_blank" class="{ink(one["color"])}" '
            f'style="display:block;width:{w}px;line-height:{h}px;{style}'
            f'text-align:center;text-decoration:none;border-radius:{one["radius"]}px;">'
            f'{_text(one["text"])}</a>')
    if not inside_vml:
        # Outlook de escritorio no redondea ni respeta el alto de un enlace: el
        # mismo botón en VML, que es lo único que dibuja con sus esquinas, su
        # color y su letra. Los demás leen el enlace de siempre. Dentro de un
        # fondo VML no: un VML dentro de otro Outlook lo dibuja mal.
        arc = min(50, round(one["radius"] * 100 / max(min(w, h), 1)))
        font = FONTS.get(one["font"], FONTS["Arial"])
        link = (f'<!--[if mso]><v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" '
                f'xmlns:w="urn:schemas-microsoft-com:office:word" href="{href}" '
                f'style="height:{h}px;v-text-anchor:middle;width:{w}px;" '
                f'arcsize="{arc}%" stroke="f" fillcolor="{one["bg"]}"><w:anchorlock/>'
                f'<center style="color:{one["color"]};font-family:{escape(font)};'
                f'font-size:{one["size"]}px;'
                f'font-weight:{"bold" if one["bold"] else "normal"};">'
                f'{_text(one["text"])}</center></v:roundrect><![endif]-->'
                f'<!--[if !mso]><!-->{link}<!--<![endif]-->')
    return (f'<td width="{w}" height="{h}" align="center" valign="middle" '
            f'bgcolor="{one["bg"]}" class="{paint(one["bg"])}" '
            f'style="width:{w}px;height:{h}px;background-color:{one["bg"]};'
            f'border-radius:{one["radius"]}px;">{link}</td>')


def _grid(boxes: list[dict[str, Any]], x0: int, y0: int, w: int, h: int, cell) -> str:
    """Una región como tabla. Se llama a sí misma por franjas y por columnas
    hasta que cada caja queda sola; `cell(box)` dibuja esa caja."""
    if not boxes:
        return TABLE.format(w=w) + _gap_row(h, w) + "</table>"

    if len(boxes) == 1:
        one = boxes[0]
        top, left = one["y"] - y0, one["x"] - x0
        right, bottom = w - left - one["w"], h - top - one["h"]
        return (TABLE.format(w=w) + _gap_row(top, w)
                + '<tr><td style="font-size:0;line-height:0;">' + TABLE.format(w=w) + "<tr>"
                + _gap_cell(left, one["h"]) + cell(one)
                + _gap_cell(right, one["h"]) + "</tr></table></td></tr>"
                + _gap_row(bottom, w) + "</table>")

    bands = _split(boxes, "y", "h")
    if len(bands) > 1:
        rows, cursor = [], y0
        for band in bands:
            top = min(one["y"] for one in band)
            bottom = max(one["y"] + one["h"] for one in band)
            rows.append(_gap_row(top - cursor, w))
            rows.append(f"<tr><td>{_grid(band, x0, top, w, bottom - top, cell)}</td></tr>")
            cursor = bottom
        rows.append(_gap_row(y0 + h - cursor, w))
        return TABLE.format(w=w) + "".join(rows) + "</table>"

    columns = _split(boxes, "x", "w")
    if len(columns) == 1:
        # Un molinillo: `problems()` no deja guardarlo, pero la vista previa
        # puede verlo a medio hacer. Se apilan uno debajo de otro en vez de
        # romper.
        return TABLE.format(w=w) + "".join(
            f"<tr><td>{_grid([one], x0, one['y'], w, one['h'], cell)}</td></tr>"
            for one in sorted(boxes, key=lambda it: it["y"])) + "</table>"
    cells, cursor = [], x0
    for column in columns:
        left = min(one["x"] for one in column)
        right = max(one["x"] + one["w"] for one in column)
        cells.append(_gap_cell(left - cursor, h))
        cells.append(f'<td width="{right - left}" valign="top" style="width:{right - left}px;">'
                     f"{_grid(column, left, y0, right - left, h, cell)}</td>")
        cursor = right
    cells.append(_gap_cell(x0 + w - cursor, h))
    return TABLE.format(w=w) + "<tr>" + "".join(cells) + "</tr></table>"


def _inner(group: dict[str, Any], *, inside_vml: bool) -> str:
    """Los textos y botones de un grupo, en su propia cuadrícula."""
    return _grid(group["fronts"], group["x"], group["y"], group["w"], group["h"],
                 lambda one: _front_cell(one, inside_vml=inside_vml))


def _group_cell(group: dict[str, Any], url: str | None, shade: str) -> str:
    w, h, kind = group["w"], group["h"], group["kind"]
    if kind == "front":
        if len(group["items"]) == 1:
            return _front_cell(group["items"][0], inside_vml=False)
        # Dos textos encimados: no se guarda, pero la vista previa lo dibuja.
        return (f'<td width="{w}" height="{h}" valign="top" style="width:{w}px;">'
                f"{_inner(group, inside_vml=False)}</td>")

    if kind == "color":
        shape = group["backs"][0]
        inner = _inner(group, inside_vml=False) if group["fronts"] else "&nbsp;"
        return (f'<td width="{w}" height="{h}" valign="top" bgcolor="{shape["bg"]}" '
                f'class="{paint(shape["bg"])}" style="width:{w}px;height:{h}px;'
                f'background-color:{shape["bg"]};border-radius:{shape["radius"]}px;'
                f'{_thin(h) or "font-size:0;line-height:0;"}">{inner}</td>')

    if kind == "picture":
        alt = " ".join(one["alt"] for one in group["backs"]
                       if one["t"] == "image" and one["alt"])
        image = (f'<img src="{escape(url or "")}" width="{w}" height="{h}" '
                 f'alt="{escape(alt)}" style="display:block;width:{w}px;height:{h}px;'
                 f'border:0;outline:none;text-decoration:none;">')
        href = _linked(group)
        if href:
            image = f'<a href="{escape(href)}" target="_blank">{image}</a>'
        return (f'<td width="{w}" height="{h}" valign="top" style="width:{w}px;'
                f'height:{h}px;font-size:0;line-height:0;">{image}</td>')

    # Texto sobre foto: el fondo mide lo mismo que la celda, así que ningún
    # lector tiene que escalarlo. Debajo, el color promedio de la foto: si no
    # carga, el texto blanco se sigue leyendo.
    safe = escape(url or "")
    return (f'<td width="{w}" height="{h}" valign="top" bgcolor="{shade}" '
            f'background="{safe}" class="{paint(shade)}" style="width:{w}px;height:{h}px;'
            f"background-color:{shade};background-image:url('{safe}');"
            f"background-size:{w}px {h}px;background-repeat:no-repeat;"
            f'background-position:0 0;">'
            # Outlook de escritorio no pinta fondos de celda: los pinta esto,
            # que solo él lee.
            f'<!--[if gte mso 9]><v:rect xmlns:v="urn:schemas-microsoft-com:vml" '
            f'fill="true" stroke="false" style="width:{w}px;height:{h}px;">'
            f'<v:fill type="frame" src="{safe}" color="{shade}" />'
            f'<v:textbox inset="0,0,0,0"><![endif]-->'
            f"<div>{_inner(group, inside_vml=True)}</div>"
            f"<!--[if gte mso 9]></v:textbox></v:rect><![endif]--></td>")


def to_html(doc: dict[str, Any], urls: list[str | None],
            shades: list[str | None] | None = None) -> str:
    """El lienzo como cuerpo de correo.

    `urls` es la dirección de la imagen de cada grupo, en el orden de
    `groups()`, o None si no la lleva. `shades`, el color promedio de cada una,
    que es el fondo de una zona con texto encima mientras la foto no carga.

    Se supone revisado con `problems()`: aquí no se vuelve a preguntar.
    """
    found = groups(doc)
    for index, group in enumerate(found):
        group["url"] = urls[index] if index < len(urls) else None
        group["shade"] = ((shades or [])[index] if index < len(shades or []) else None) \
            or doc["bg"]
    inner = _grid(found, 0, 0, WIDTH, doc["h"],
                  lambda group: _group_cell(group, group["url"], group["shade"]))
    bg = doc["bg"]
    return (f'<table role="presentation" width="{WIDTH}" align="center" '
            f'cellpadding="0" cellspacing="0" border="0" '
            f'style="width:{WIDTH}px;margin:0 auto;border-collapse:collapse;">'
            f'<tr><td width="{WIDTH}" valign="top" bgcolor="{bg}" class="{paint(bg)}" '
            f'style="width:{WIDTH}px;background-color:{bg};">{inner}</td></tr></table>')


def dark_css(doc: dict[str, Any], shades: list[str | None] | None = None) -> str:
    """Las reglas que le piden a Outlook que no cambie los colores en modo oscuro.

    Outlook en el teléfono y en la web «corrige» los colores cuando el
    teléfono está en oscuro: el texto blanco sobre una foto sale gris oscuro y
    un botón negro se queda sin fondo. Marca lo que cambió con `data-ogsc` (letra)
    y `data-ogsb` (fondo), y respeta reglas que lo nombran. Una por color usado.
    """
    inks: set[str] = set()
    paints = {doc["bg"]}
    for one in doc["items"]:
        if one["t"] in FRONT:
            inks.add(one["color"])
            inks.update(run["color"] for run in one.get("runs") or [] if run.get("color"))
        if one["t"] in ("button", "shape"):
            paints.add(one["bg"])
    paints.update(one for one in (shades or []) if one)
    rules = [f"[data-ogsc] .{ink(c)}{{color:{c} !important;}}" for c in sorted(inks)]
    rules += [f"[data-ogsb] .{paint(c)}{{background-color:{c} !important;}}"
              for c in sorted(paints)]
    return "".join(rules)


# ------------------------------------------------------ que no vaya a spam

# Lo que se exige para guardar. El contenido es una parte de si un correo llega
# (lo que más pesa es la reputación del dominio y su autenticación), pero es la
# parte que decide quien arma la pieza. Cada regla sale de lo que miran los
# filtros de verdad: un correo que es casi pura imagen es el truco clásico del
# spam para esconder el texto, los enlaces acortados esconden a dónde llevan, y
# las mayúsculas y los signos de más son reglas con puntaje en SpamAssassin.
#
# El texto y la imagen se aflojaron en septiembre de 2026 (eran 300 caracteres y
# la mitad del correo): 200 son un titular y un par de frases, y el 60 % de
# imagen es la proporción 60/40 de siempre, del lado permisivo. Sigue sin pasar
# lo que de verdad castigan los filtros, que es el correo casi todo imagen.
MIN_TEXT = 200            # caracteres de texto real en todo el correo
MAX_IMAGE_SHARE = 0.6     # la parte del correo que puede ser imagen
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


def _covered(doc: dict[str, Any], cell: int = 10) -> int:
    """Cuánta superficie del correo es imagen, sin contar dos veces lo encimado.

    Cuentan las fotos, y una imagen fundida entera (también lo que en ella son
    rectángulos, porque llega como imagen). Un rectángulo que es una celda de
    color no cuenta. Se mide en casillas de 10 px.
    """
    seen: set[tuple[int, int]] = set()
    boxes = [bounds(one) for one in doc["items"] if one["t"] == "image"]
    boxes += [group for group in groups(doc) if group["kind"] == "picture"]
    for one in boxes:
        for gx in range(max(one["x"], 0) // cell, min(one["x"] + one["w"], WIDTH) // cell):
            for gy in range(max(one["y"], 0) // cell,
                            min(one["y"] + one["h"], doc["h"]) // cell):
                seen.add((gx, gy))
    return len(seen) * cell * cell


def _measure(doc: dict[str, Any]) -> dict[str, Any]:
    """Lo que se cuenta del correo para saber si parece spam, en un solo sitio:
    lo usan la revisión que no deja guardar y la lista de requisitos, y así las
    dos no pueden contar distinto."""
    front = [one for one in doc["items"] if one["t"] in FRONT]
    words = " ".join(one.get("text", "") for one in front)
    plain_text = MARK_RE.sub("", words)
    alpha = [c for c in plain_text if c.isalpha()]
    return {
        "text": plain_text,
        # Caracteres como los cuenta una persona: con los espacios entre palabras.
        "letters": len(" ".join(plain_text.split())),
        "share": _covered(doc) / (WIDTH * doc["h"] or 1),
        # Los de los botones, las fotos y, desde octubre de 2026, las palabras
        # con enlace de un texto.
        "links": [href for one in doc["items"] for href in links_of(one)],
        "alpha": len(alpha),
        "caps": sum(c.isupper() for c in alpha) / len(alpha) if alpha else 0.0,
    }


def review(doc: dict[str, Any], size: int, *, limit: int) -> list[dict[str, Any]]:
    """Lo que hace que este correo tenga riesgo de ir a spam. Vacío es que no.

    Cada motivo lleva su clave y, si hace falta, el detalle (qué palabra, cuánto
    pesa). La pantalla lo traduce. Con cualquiera, no se guarda.
    """
    found: list[dict[str, Any]] = []
    seen = _measure(doc)
    plain_text = seen["text"]

    if seen["letters"] < MIN_TEXT:
        found.append({"key": "few_text", "n": seen["letters"], "min": MIN_TEXT})

    if seen["share"] > MAX_IMAGE_SHARE:
        found.append({"key": "image_heavy", "pct": round(100 * seen["share"]),
                      "max": round(100 * MAX_IMAGE_SHARE)})

    if size > limit:
        found.append({"key": "too_big", "kb": round(size / 1024), "max": limit // 1024})

    links = seen["links"]
    if len(links) > MAX_BUTTONS:
        found.append({"key": "many_links", "n": len(links), "max": MAX_BUTTONS})
    for href in links:
        host = href.split("://", 1)[-1].split("/", 1)[0].lower()
        if host.startswith("www."):
            host = host[4:]
        if host in SHORTENERS:
            found.append({"key": "shortener", "what": host})
            break

    if seen["alpha"] >= 20 and seen["caps"] > MAX_CAPS:
        found.append({"key": "caps"})
    if "!!" in plain_text or "¡¡" in plain_text or plain_text.count("!") > 3:
        found.append({"key": "shouting"})

    folded = _fold(plain_text)
    for word in TRIGGERS:
        if re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", folded):
            found.append({"key": "trigger", "what": word})
            break
    return found


# ------------------------------------------------------ la lista de requisitos

# Todo lo que decide si un lienzo se guarda, en el orden en que lo enseña la
# ventana de requisitos: primero si el correo se puede armar (`problems()`) y
# después si tiene pinta de llegar a la bandeja (`review()`). Una regla nueva
# en cualquiera de las dos tiene que estar también aquí, o esa ventana diría
# que todo se cumple mientras Guardar sigue apagado.
BUILD_RULES = ("empty", "height", "too_many_items", "bounds", "image", "alt", "href",
               "font", "size", "text_long", "button_text", "line", "overlap",
               "tangled", "link_overlap")
SPAM_RULES = ("few_text", "image_heavy", "too_big", "many_links", "shortener",
              "caps", "shouting", "trigger")


def checklist(doc: dict[str, Any], size: int, *, limit: int, failed: list[str],
              found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cada regla con si se cumple y sus cifras, para enseñarlas todas.

    `failed` es lo que dijo `problems()` y `found` lo que dijo `review()`: se
    reciben hechos para no preguntar dos veces, que `problems()` mira en la base
    si cada imagen es de la cuenta. El molinillo se pregunta aparte, porque
    `problems()` no lo dice mientras haya algo encimado.
    """
    bad = set(failed)
    if _tangled(doc):
        bad.add("tangled")
    spam = {one["key"]: {k: v for k, v in one.items() if k != "key"} for one in found}
    seen = _measure(doc)
    figures: dict[str, dict[str, Any]] = {
        "height": {"h": doc["h"], "min": MIN_HEIGHT, "max": MAX_HEIGHT},
        "too_many_items": {"n": len(doc["items"]), "max": MAX_ITEMS},
        "size": {"min": MIN_SIZE, "max": MAX_SIZE},
        "text_long": {"max": TEXT_MAX},
        "button_text": {"max": BUTTON_MAX},
        "line": {"min": LINE_MIN, "max": LINE_MAX},
        "few_text": {"n": seen["letters"], "min": MIN_TEXT},
        "image_heavy": {"pct": round(100 * seen["share"]),
                        "max": round(100 * MAX_IMAGE_SHARE)},
        # Redondeado hacia arriba, como la barra de peso que está al lado.
        "too_big": {"kb": -(-size // 1024), "max": limit // 1024},
        "many_links": {"n": len(seen["links"]), "max": MAX_BUTTONS},
        "caps": {"pct": round(100 * seen["caps"]), "max": round(100 * MAX_CAPS)},
    }
    out = [{"key": key, "group": "build", "ok": key not in bad, **figures.get(key, {})}
           for key in BUILD_RULES]
    out += [{"key": key, "group": "spam", "ok": key not in spam,
             **spam.get(key, {}), **figures.get(key, {})}
            for key in SPAM_RULES]
    return out


MARK_RE = re.compile(r"\*\|[A-Z0-9_]+\|\*")


def images_of(doc: dict[str, Any] | None) -> list[str]:
    """Las fotos que nombra un lienzo (no las fundidas, que van aparte).

    Lee también lo guardado por diapositivas."""
    doc = read(doc) if doc else None
    if not doc:
        return []
    return [one["name"] for one in doc["items"] if one["t"] == "image" and one["name"]]
