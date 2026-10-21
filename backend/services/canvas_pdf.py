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
                sheet.drawImage(ImageReader(flat), left + spot[0],
                                top - spot[1] - size[1], size[0], size[1])
        elif one["t"] == "button":
            _button(sheet, one, left, top, HexColor)
        else:
            _text(sheet, one, left, top, HexColor)
        sheet.restoreState()

    sheet.showPage()
    sheet.save()
    return buffer.getvalue()


def _shape(sheet, one: dict[str, Any], left: float, top: float, color) -> None:
    """Una figura, con los mismos puntos que pinta el correo."""
    wide, tall = one["w"], one["h"]
    sheet.setFillColor(color(one["bg"]))
    figure = one.get("shape", "rect")
    if figure == "ellipse":
        sheet.ellipse(left, top - tall, left + wide, top, fill=1, stroke=0)
        return
    if figure in canvas.POLYGONS:
        path = sheet.beginPath()
        points = canvas.POLYGONS[figure](wide, tall)
        path.moveTo(left + points[0][0], top - points[0][1])
        for x, y in points[1:]:
            path.lineTo(left + x, top - y)
        path.close()
        sheet.drawPath(path, fill=1, stroke=0)
        return
    radius = min(one.get("radius") or 0, wide / 2, tall / 2)
    if radius:
        sheet.roundRect(left, top - tall, wide, tall, radius, fill=1, stroke=0)
    else:
        sheet.rect(left, top - tall, wide, tall, fill=1, stroke=0)


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
                    sheet.drawCentredString(left + dot / 2, base, "•")
                sheet.drawString(left + dot, base, line)
            n += 1
