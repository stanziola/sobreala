"""La pieza del lienzo, dibujada en un PDF.

Se dibuja **desde las coordenadas**, no desde el correo armado: el lienzo ya es
un documento con posiciones, así que un PDF es lo que más se le parece. Por eso
el texto sale como texto y se puede copiar, y por eso no hace falta ningún
dibujante de HTML, que no hay.

Tres cosas que conviene tener presentes:

- **Las fuentes caen a las catorce que todo PDF trae dentro** (`_FACE`), porque
  aquí no se importa ninguna. Miden distinto que las del correo, así que una
  línea puede partirse en otro sitio. Es la única diferencia grande entre este
  archivo y lo que llega a la bandeja.
- **No lleva el pie de la baja ni la dirección postal**: eso se inyecta al
  enviar (reglas 3 y 4) y es del correo, no de la pieza.
- **Las marcas `*|NOMBRE|*` salen tal como están escritas**: el PDF es la
  plantilla, no el correo de nadie en concreto.

`reportlab` se importa dentro de la función, como en `blueprints/analytics`:
arrancar el panel sin él tiene que seguir funcionando.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Callable

from services import canvas

# Lo que se dibuja al doble y se coloca a la mitad: a una resolución, una foto
# de 300 px de ancho saldría a 72 puntos por pulgada y se vería sucia impresa.
SCALE = 2

# De la fuente del lienzo a una de las catorce de PDF. Las que no existen caen
# en la más parecida de medidas, que es el mismo criterio que sigue `FONTS` de
# `services/canvas.py` para los lectores de correo que no las tienen.
_FACE = {
    "Arial": "Helvetica",
    "Helvetica": "Helvetica",
    "Verdana": "Helvetica",
    "Tahoma": "Helvetica",
    "Trebuchet MS": "Helvetica",
    "Lucida Sans": "Helvetica",
    "Century Gothic": "Helvetica",
    "Georgia": "Times",
    "Times New Roman": "Times",
    "Palatino": "Times",
    "Garamond": "Times",
    "Courier New": "Courier",
}
# Cómo se llama cada variante: Times no las nombra como las otras dos.
_VARIANTS = {
    ("Helvetica", False, False): "Helvetica",
    ("Helvetica", True, False): "Helvetica-Bold",
    ("Helvetica", False, True): "Helvetica-Oblique",
    ("Helvetica", True, True): "Helvetica-BoldOblique",
    ("Courier", False, False): "Courier",
    ("Courier", True, False): "Courier-Bold",
    ("Courier", False, True): "Courier-Oblique",
    ("Courier", True, True): "Courier-BoldOblique",
    ("Times", False, False): "Times-Roman",
    ("Times", True, False): "Times-Bold",
    ("Times", False, True): "Times-Italic",
    ("Times", True, True): "Times-BoldItalic",
}


def face_of(one: dict[str, Any]) -> str:
    """El nombre de PDF de la letra de un texto o de un botón."""
    family = _FACE.get(one.get("font", "Arial"), "Helvetica")
    return _VARIANTS[(family, bool(one.get("bold")), bool(one.get("italic")))]


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Las líneas de un texto dentro de su caja, partiendo por palabras.

    Los saltos escritos se respetan; lo demás se parte donde ya no cabe. Una
    palabra sola más ancha que la caja se deja salir, como en el correo: en un
    PDF no hay guionado y cortarla a la mitad se lee peor.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for word in paragraph.split(" "):
            tried = f"{line} {word}".strip() if line else word
            if line and stringWidth(tried, font, size) > width:
                lines.append(line)
                line = word
            else:
                line = tried
        lines.append(line)
    return lines


def _photo(one: dict[str, Any], raw: bytes):
    """La foto de un elemento, recortada y ajustada a su caja.

    Lo mismo que hace `canvas._paint()` para el correo: primero el recorte que
    guardó el cliente y después el ajuste de la caja. Devuelve la imagen y
    dónde va dentro de la caja, que con «contain» no es la esquina.
    """
    from PIL import Image, ImageOps

    box = (max(int(one["w"] * SCALE), 1), max(int(one["h"] * SCALE), 1))
    with Image.open(BytesIO(raw)) as opened:
        picture = opened.convert("RGBA")
    cut = one.get("crop")
    if cut:
        wide, tall = picture.size
        left, top = round(cut[0] * wide), round(cut[1] * tall)
        picture = picture.crop((left, top,
                                min(wide, left + round(cut[2] * wide)),
                                min(tall, top + round(cut[3] * tall))))
    if one.get("fit") == "contain":
        picture.thumbnail(box, Image.LANCZOS)
        spot = ((box[0] - picture.width) / 2 / SCALE,
                (box[1] - picture.height) / 2 / SCALE)
        size = (picture.width / SCALE, picture.height / SCALE)
    else:
        picture = ImageOps.fit(picture, box, Image.LANCZOS)
        spot, size = (0.0, 0.0), (one["w"], one["h"])
    # Sobre blanco: un PDF no tiene transparencia de página, y un PNG con
    # bordes transparentes pegado tal cual sale con el fondo en negro.
    flat = Image.new("RGB", picture.size, "#FFFFFF")
    flat.paste(picture, (0, 0), picture)
    return flat, spot, size


def to_pdf(doc: dict[str, Any], load: Callable[[str], bytes | None],
           title: str = "") -> bytes:
    """El lienzo entero, en un PDF de una página.

    `load` devuelve los bytes de una imagen por su nombre, y **None si no es de
    esa cuenta**: la foto se salta, como en el correo.
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    wide, tall = float(canvas.WIDTH), float(doc["h"])
    buffer = BytesIO()
    sheet = Canvas(buffer, pagesize=(wide, tall))
    if title:
        sheet.setTitle(title)
    sheet.setFillColor(HexColor(doc.get("bg") or "#FFFFFF"))
    sheet.rect(0, 0, wide, tall, fill=1, stroke=0)

    # Las figuras y las fotos atrás y los textos delante, que es el orden del
    # editor y el del correo.
    order = [one for one in doc["items"] if one["t"] in canvas.BACK]
    order += [one for one in doc["items"] if one["t"] in canvas.FRONT]
    for one in order:
        sheet.saveState()
        # El centro de la caja, y desde ahí el giro: un PDF cuenta al revés que
        # CSS, en los dos ejes.
        sheet.translate(one["x"] + one["w"] / 2,
                        tall - (one["y"] + one["h"] / 2))
        if one.get("rot"):
            sheet.rotate(-one["rot"])
        left, top = -one["w"] / 2, one["h"] / 2
        if one["t"] == "shape":
            _shape(sheet, one, left, top, HexColor)
        elif one["t"] == "image":
            raw = load(one["name"])
            if raw:
                flat, spot, size = _photo(one, raw)
                # Con forma o esquinas redondas, recortada a ellas.
                figure = one.get("mask") or "rect"
                shaped = one.get("mask") or one.get("radius")
                if shaped:
                    sheet.saveState()
                    sheet.clipPath(_outline(sheet, figure, left, top, one["w"], one["h"],
                                            one.get("radius") or 0), stroke=0, fill=0)
                sheet.drawImage(ImageReader(flat), left + spot[0],
                                top - spot[1] - size[1], size[0], size[1])
                if shaped:
                    sheet.restoreState()
                _edge(sheet, one, figure, left, top, HexColor)
        elif one["t"] == "button":
            _button(sheet, one, left, top, HexColor)
        else:
            _text(sheet, one, left, top, HexColor)
        sheet.restoreState()

    sheet.showPage()
    sheet.save()
    return buffer.getvalue()


def _outline(sheet, figure: str, left: float, top: float, wide: float, tall: float,
             radius: float):
    """El contorno de una figura como camino de PDF: para rellenarla, para su
    borde y para recortar una foto con su forma (octubre de 2026)."""
    path = sheet.beginPath()
    if figure == "ellipse":
        path.ellipse(left, top - tall, wide, tall)
    elif figure in canvas.POLYGONS:
        points = canvas.POLYGONS[figure](wide, tall)
        path.moveTo(left + points[0][0], top - points[0][1])
        for x, y in points[1:]:
            path.lineTo(left + x, top - y)
        path.close()
    else:
        radius = min(radius or 0, wide / 2, tall / 2)
        if radius:
            path.roundRect(left, top - tall, wide, tall, radius)
        else:
            path.rect(left, top - tall, wide, tall)
    return path


def _edge(sheet, one: dict[str, Any], figure: str, left: float, top: float, color) -> None:
    """El borde, por dentro de la caja como en el correo: el trazo de un PDF va
    sobre la orilla, así que se dibuja metido la mitad de su grosor."""
    width = one.get("border") or 0
    if not width:
        return
    half = width / 2
    sheet.setStrokeColor(color(one.get("border_color") or "#18181B"))
    sheet.setLineWidth(width)
    sheet.drawPath(_outline(sheet, figure, left + half, top - half, one["w"] - width,
                            one["h"] - width, max((one.get("radius") or 0) - half, 0)),
                   fill=0, stroke=1)


def _shape(sheet, one: dict[str, Any], left: float, top: float, color) -> None:
    """Una figura, con los mismos puntos que pinta el correo, y su borde."""
    sheet.setFillColor(color(one["bg"]))
    figure = one.get("shape", "rect")
    if figure == "line":
        figure = "rect"
    sheet.drawPath(_outline(sheet, figure, left, top, one["w"], one["h"],
                            one.get("radius") or 0), fill=1, stroke=0)
    _edge(sheet, one, figure, left, top, color)


def _button(sheet, one: dict[str, Any], left: float, top: float, color) -> None:
    """Un botón: su fondo redondeado y el texto centrado dentro."""
    wide, tall = one["w"], one["h"]
    radius = min(one.get("radius") or 0, wide / 2, tall / 2)
    sheet.setFillColor(color(one["bg"]))
    if radius:
        sheet.roundRect(left, top - tall, wide, tall, radius, fill=1, stroke=0)
    else:
        sheet.rect(left, top - tall, wide, tall, fill=1, stroke=0)
    font, size = face_of(one), one["size"]
    sheet.setFont(font, size)
    sheet.setFillColor(color(one["color"]))
    # Centrado a ojo de letra: la mayúscula ocupa unos siete décimos del cuerpo.
    sheet.drawCentredString(left + wide / 2, top - tall / 2 - size * 0.35,
                            one["text"])


def _text(sheet, one: dict[str, Any], left: float, top: float, color) -> None:
    """Un texto, línea a línea y con su alineación.

    **Se recorta a su caja** (octubre de 2026), como el correo: lo que no cabe
    no sale. Antes no se recortaba, porque en el correo un texto que no cabía
    salía entero y empujaba lo de abajo. Con variables no se recorta, igual que
    en el correo (`canvas.has_variables`).
    """
    if not canvas.has_variables(one):
        sheet.saveState()
        box = sheet.beginPath()
        box.rect(left, top - one["h"], one["w"], one["h"])
        sheet.clipPath(box, stroke=0, fill=0)
        try:
            _lines(sheet, one, left, top, color)
        finally:
            sheet.restoreState()
        return
    _lines(sheet, one, left, top, color)


def _lines(sheet, one: dict[str, Any], left: float, top: float, color) -> None:
    font, size = face_of(one), one["size"]
    leading = round(size * (one.get("line") or 1.4))
    if one.get("runs"):
        _rich(sheet, one, left, top, color, size, leading)
        return
    sheet.setFont(font, size)
    sheet.setFillColor(color(one["color"]))
    if one.get("list"):
        _bullets(sheet, one, left, top, font, size, leading)
        return
    align = one.get("align", "left")
    for n, line in enumerate(wrap(one["text"], font, size, one["w"])):
        if not line:
            continue
        # La línea de base, dentro del renglón: el navegador centra ahí la caja
        # de la letra, así que se deja el mismo aire arriba y abajo.
        base = top - n * leading - (leading + size * 0.72) / 2
        if align == "center":
            sheet.drawCentredString(left + one["w"] / 2, base, line)
        elif align == "right":
            sheet.drawRightString(left + one["w"], base, line)
        else:
            sheet.drawString(left, base, line)


def _bullets(sheet, one: dict[str, Any], left: float, top: float, font: str,
             size: float, leading: float) -> None:
    """Un texto con viñetas: la viñeta en la primera línea de cada renglón y el
    texto con sangría francesa, en la misma columna que en el correo
    (`canvas.dot_px()`). Un renglón vacío es un hueco."""
    dot = canvas.dot_px(one)
    n = 0
    for paragraph in one["text"].split("\n"):
        lines = wrap(paragraph, font, size, one["w"] - dot) if paragraph.strip() else [""]
        for first, line in zip([True] + [False] * len(lines), lines):
            base = top - n * leading - (leading + size * 0.72) / 2
            if line:
                if first:
                    _bullet(sheet, one, left + dot / 2, base, size)
                sheet.drawString(left + dot, base, line)
            n += 1


# ------------------------------------------------- el formato por palabras

# La viñeta de cada tipo en el PDF: el punto con la letra del texto, y las
# demás con ZapfDingbats, que es de las catorce que todo PDF trae y sí las tiene.
_BULLETS = {"check": "\u2713", "star": "\u2605", "circle": "\u274d"}


def _bullet(sheet, one: dict[str, Any], x: float, base: float, size: float) -> None:
    glyph = _BULLETS.get(one.get("list"))
    if glyph:
        sheet.setFont("ZapfDingbats", size * 0.8)
        sheet.drawCentredString(x, base, glyph)
        sheet.setFont(face_of(one), size)
    else:
        sheet.drawCentredString(x, base, "•")


def _run_face(one: dict[str, Any], run: dict[str, Any]) -> str:
    """La letra de un tramo: la de la caja, con su negrita y su cursiva."""
    family = _FACE.get(one.get("font", "Arial"), "Helvetica")
    return _VARIANTS[(family, bool(run.get("b", one.get("bold"))),
                      bool(run.get("i", one.get("italic"))))]


def _wrap_runs(one: dict[str, Any], runs: list[dict[str, Any]], size: float,
               width: float) -> list[list[tuple[str, dict[str, Any], str, float]]]:
    """Los renglones de un párrafo con formato, partiendo por palabras como
    `wrap()`: cada pedazo con su tramo, su letra y su ancho."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines: list[list[tuple[str, dict[str, Any], str, float]]] = []
    line: list[tuple[str, dict[str, Any], str, float]] = []
    used = 0.0
    for run in runs:
        face = _run_face(one, run)
        for token in re.findall(r"\S+|\s+", run["text"]):
            wide = stringWidth(token, face, size)
            if token.isspace():
                if line:
                    line.append((token, run, face, wide))
                    used += wide
                continue
            if line and used + wide > width:
                while line and line[-1][0].isspace():
                    used -= line.pop()[3]
                lines.append(line)
                line, used = [], 0.0
            line.append((token, run, face, wide))
            used += wide
    while line and line[-1][0].isspace():
        line.pop()
    lines.append(line)
    return lines


def _draw_line(sheet, one: dict[str, Any], pieces, x: float, base: float, size: float,
               color) -> None:
    """Un renglón con formato: cada pedazo con su letra y su color, el subrayado
    como una raya debajo, y el enlace como un vínculo que se puede pulsar."""
    for token, run, face, wide in pieces:
        tone = color(run.get("color") or one["color"])
        sheet.setFont(face, size)
        sheet.setFillColor(tone)
        sheet.drawString(x, base, token)
        if run.get("u") and not token.isspace():
            sheet.setStrokeColor(tone)
            sheet.setLineWidth(max(size / 16, 0.6))
            sheet.line(x, base - size * 0.12, x + wide, base - size * 0.12)
        if run.get("href"):
            sheet.linkURL(run["href"], (x, base - size * 0.25, x + wide, base + size * 0.8),
                          relative=1)
        x += wide


def _rich(sheet, one: dict[str, Any], left: float, top: float, color, size: float,
          leading: float) -> None:
    """Un texto con formato por palabras (octubre de 2026), con su alineación,
    o con viñetas: la misma columna y la misma sangría que el correo."""
    listed = bool(one.get("list"))
    dot = canvas.dot_px(one) if listed else 0
    align = "left" if listed else one.get("align", "left")
    n = 0
    for runs in canvas.text_lines(one):
        if not "".join(run["text"] for run in runs).strip():
            n += 1
            continue
        for at, pieces in enumerate(_wrap_runs(one, runs, size, one["w"] - dot)):
            base = top - n * leading - (leading + size * 0.72) / 2
            wide = sum(piece[3] for piece in pieces)
            if listed and at == 0:
                sheet.setFont(face_of(one), size)
                sheet.setFillColor(color(one["color"]))
                _bullet(sheet, one, left + dot / 2, base, size)
            if align == "center":
                x = left + (one["w"] - wide) / 2
            elif align == "right":
                x = left + one["w"] - wide
            else:
                x = left + dot
            _draw_line(sheet, one, pieces, x, base, size, color)
            n += 1
