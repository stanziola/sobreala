#!/usr/bin/env python3
"""Generate backend/static/css/panel.css, templates/_wing.svg, the favicon
and the small wing for the footer of Básico campaigns.

Same idea as write_css() in landing/build_site.py: the brand colour variables
are prepended to the stylesheet, so the panel has no hex codes of its own and
both themes come from brand/colors.css and brand/colors-dark.css. The wing is
inlined into a template for the same reason — as an <img> it could not follow
the theme.

Also four of the public site's «Funciones» drawings, for the side of the sign
in and sign up pages (templates/_art-*.svg), rendered from landing/src/partials
with their words from landing/content.py, and the .art-* colour rules they
need, copied from landing/src/site.css. Only this build reads landing/; what
it writes is committed, so the panel never needs it to run.

    python backend/build_assets.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BRAND_DIR = BASE_DIR.parent / "brand"
LANDING_DIR = BASE_DIR.parent / "landing"
OUT_CSS = BASE_DIR / "static" / "css" / "panel.css"
OUT_WING = BASE_DIR / "templates" / "_wing.svg"
OUT_FONTS = BASE_DIR / "static" / "fonts"
OUT_IMG = BASE_DIR / "static" / "img"

# Lo que se compara en --check. Solo texto: dos versiones de Pillow pueden
# escribir el mismo PNG con bytes distintos, y una prueba que falla al
# actualizar una dependencia deja de creerse. La deriva que importa es esta.
CHECKED = (".html", ".css", ".svg", ".txt", ".xml")


# The same two the public site converts, for the same reason: the wordmark next
# to the wing has to be the wordmark, not whatever the system offers.
FONT_FILES = [
    ("Outfit", BRAND_DIR / "fonts" / "outfit" / "Outfit-VariableFont_wght.ttf", "100 900"),
    ("Sora", BRAND_DIR / "fonts" / "sora" / "Sora-VariableFont_wght.ttf", "100 800"),
]

HEADER_COMMENT = re.compile(r"/\*.*?\*/\s*", re.S)


def palette(name: str, fallback: str) -> str:
    """One colour from brand/colors.css, the single source of truth."""
    text = (BRAND_DIR / "colors.css").read_text(encoding="utf-8")
    found = re.search(rf"--{name}:\s*(#[0-9A-Fa-f]{{3,8}})\s*;", text)
    return found.group(1) if found else fallback


def wing_svg() -> str:
    """The logo wing, ready to be dropped inside a template.

    Same treatment as read_wing_svg() in landing/build_site.py, with one
    difference that matters: the fills are not removed, they are rewritten with
    the value from the palette. A path with no fill at all paints black, so a
    stylesheet that arrives late — or a cached one from before these rules
    existed — turned the whole mark into a black blob. The CSS still wins when
    it loads, because a class selector beats a presentation attribute.
    """
    svg = (BRAND_DIR / "logo" / "logo-transparent.svg").read_text(encoding="utf-8")
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg, count=2)
    for part, name, fallback in (("fill", "color-logo", "#EFEEEC"),
                                 ("shadow", "color-shadow", "#000000")):
        svg = re.sub(rf'(class="wing-{part}") fill="#[0-9A-Fa-f]{{6}}"',
                     rf'\1 fill="{palette(name, fallback)}"', svg)
    svg = svg.replace('role="img"', 'aria-hidden="true" focusable="false"')
    svg = re.sub(r"<title[^>]*>.*?</title>\s*", "", svg, flags=re.S)
    svg = re.sub(r'\saria-labelledby="[^"]*"', "", svg)
    return svg.strip()


# Las funciones que rotan al lado de entrar y registrarse (octubre de 2026), en
# este orden. Cada una es un dibujo de «Funciones» del sitio, el mismo archivo.
# El de envío programado salió de Funciones ese mismo mes, y entró quién lo vio.
# La lista de templates/_auth.html dice las mismas cuatro.
AUTH_ART = ("contacts", "editor", "results", "opens")
ART_RULE = re.compile(r"^\.art-[\w-]+ \{[^}\n]*\}$", re.M)


def auth_art() -> dict[str, str]:
    """The drawings, rendered the way landing/build_site.py renders them."""
    import importlib.util

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    spec = importlib.util.spec_from_file_location("landing_content",
                                                  LANDING_DIR / "content.py")
    content = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(content)
    items = {one["art"]: one for one in content.HOME["features"]["items"]}
    env = Environment(loader=FileSystemLoader(str(LANDING_DIR / "src")), autoescape=True,
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    return {name: env.get_template(f"partials/feature-{name}.svg.j2")
            .render(item=items[name]).strip() for name in AUTH_ART}


def art_rules() -> str:
    """The colours of the drawings: classes, because an SVG attribute cannot
    read a CSS variable. The variables themselves are brand ones, already at
    the top of panel.css."""
    site = (LANDING_DIR / "src" / "site.css").read_text(encoding="utf-8")
    return "\n".join(ART_RULE.findall(site))


def build_fonts() -> list[dict]:
    """Convert the brand fonts to .woff2 under static/fonts. Returns the faces.

    Same conversion as build_fonts() in landing/build_site.py, kept here rather
    than imported because the two builds deploy to different places and neither
    may depend on the other being present.
    """
    from fontTools.ttLib import TTFont

    OUT_FONTS.mkdir(parents=True, exist_ok=True)
    faces = []
    for family, source, weight in FONT_FILES:
        if not source.exists():
            raise SystemExit(f"missing font: {source}\nSee brand/fonts/README.md.")
        out = OUT_FONTS / (source.stem + ".woff2")
        if not out.exists() or out.stat().st_mtime < source.stat().st_mtime:
            font = TTFont(str(source))
            font.flavor = "woff2"
            font.save(str(out))
            font.close()
        faces.append({"family": family, "file": f"/static/fonts/{out.name}",
                      "weight": weight})
    return faces


FACE_TEMPLATE = (
    '@font-face {{\n'
    '  font-family: "{family}";\n'
    '  src: url("{file}") format("woff2");\n'
    '  font-weight: {weight};\n'
    '  font-style: normal;\n'
    '  font-display: swap;\n'
    '}}\n'
)


def build() -> list[Path]:
    colors = HEADER_COMMENT.sub("", (BRAND_DIR / "colors.css").read_text(encoding="utf-8"), count=1)
    dark = BRAND_DIR / "colors-dark.css"
    if dark.exists():
        colors += "\n" + HEADER_COMMENT.sub("", dark.read_text(encoding="utf-8"), count=1)

    faces = build_fonts()
    faces_css = "".join(FACE_TEMPLATE.format(**f) for f in faces)

    body = (BASE_DIR / "static" / "css" / "_panel.src.css").read_text(encoding="utf-8")
    OUT_CSS.parent.mkdir(parents=True, exist_ok=True)
    OUT_CSS.write_text(
        "/* GENERATED by backend/build_assets.py. Edit brand/colors.css and "
        "backend/static/css/_panel.src.css instead. */\n"
        + colors.strip() + "\n\n" + faces_css + "\n" + body
        + "\n/* GENERATED from landing/src/site.css: the colours of the «Funciones»\n"
          "   drawings, which also turn beside the sign in and sign up pages. */\n"
        + art_rules() + "\n",
        encoding="utf-8", newline="\n",
    )

    OUT_WING.parent.mkdir(parents=True, exist_ok=True)
    OUT_WING.write_text(
        "{# GENERATED by backend/build_assets.py from "
        "brand/logo/logo-transparent.svg. #}\n" + wing_svg() + "\n",
        encoding="utf-8", newline="\n",
    )

    written = [OUT_CSS, OUT_WING] + [OUT_FONTS / Path(f["file"]).name for f in faces]
    for name, svg in auth_art().items():
        out = OUT_WING.parent / f"_art-{name}.svg"
        out.write_text(
            f"{{# GENERATED by backend/build_assets.py from "
            f"landing/src/partials/feature-{name}.svg.j2 and landing/content.py. #}}\n"
            + svg + "\n",
            encoding="utf-8", newline="\n",
        )
        written.append(out)
    img = OUT_IMG
    img.mkdir(parents=True, exist_ok=True)
    for name in ("favicon.svg", "favicon.ico"):
        source = BRAND_DIR / "favicon" / name
        if source.exists():
            shutil.copy2(source, img / name)
            written.append(img / name)
    written.append(email_logo(img))
    written.append(mail_header(img))
    written += mail_social(img)
    written += payment_logos(img)
    return written


# Los logos de los métodos de pago, para la pantalla de contratar: los archivos a
# color de brand/payments/ (ver su README). Los SVG van tal cual; el PNG de
# PayPal se recorta a lo que se ve y se achica a este alto, cuatro veces el que
# se dibuja.
PAYMENTS = BRAND_DIR / "payments"
PAYMENT_LOGOS = {
    "paypal": PAYMENTS / "paypal" / "Horizontal Full Color" / "pp_h_rgb.png",
    "visa": (PAYMENTS / "visa" / "Visa Brand Mark DIGITAL 2025" / "Visa Brand Mark DIGITAL"
             / "VBM_digital_2025" / "blue" / "VBM_bluRGB_2025.svg"),
    "mastercard": PAYMENTS / "mastercard" / "Mastercard Symbol - SVG" / "Artwork" / "ma_symbol.svg",
    "yappy": PAYMENTS / "yappy" / "yappy-color-landscape.svg",
}
PAYMENT_LOGO_HEIGHT = 88


def payment_logos(img: Path) -> list[Path]:
    from PIL import Image

    out_dir = img / "payments"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, source in PAYMENT_LOGOS.items():
        if not source.exists():
            continue
        target = out_dir / f"{name}{source.suffix.lower()}"
        if source.suffix.lower() == ".png":
            with Image.open(source) as opened:
                logo = opened.convert("RGBA")
                box = logo.getchannel("A").getbbox()
                if box:
                    logo = logo.crop(box)
                width = round(logo.width * PAYMENT_LOGO_HEIGHT / logo.height)
                logo.resize((width, PAYMENT_LOGO_HEIGHT), Image.LANCZOS).save(
                    target, format="PNG", optimize=True)
        else:
            shutil.copy2(source, target)
        written.append(target)
    crop_logos(out_dir)
    return written


def crop_logos(out_dir: Path) -> None:
    """El recorte de brand/payments/viewbox.json en las copias SVG: Visa y
    Mastercard traen su margen de respeto dentro del archivo, y a 22 px de alto
    el dibujo quedaba diminuto. El kit no se toca."""
    import json

    crops = json.loads((PAYMENTS / "viewbox.json").read_text(encoding="utf-8"))
    for name, box in crops.items():
        made = out_dir / f"{name}.svg"
        if name.startswith("_") or not made.exists():
            continue
        text = made.read_text(encoding="utf-8")
        made.write_text(re.sub(r'viewBox="[^"]*"', f'viewBox="{box}"', text, count=1),
                        encoding="utf-8", newline="")


# El ala que va al pie de las campañas del plan Básico, junto a «Enviado con
# Sobreala». En PNG y no en SVG, que Outlook y Gmail no dibujan, y al doble del
# tamaño al que se ve (32 px) para que salga nítida en un teléfono. Es el PNG de
# la marca tal cual, solo achicado.
EMAIL_LOGO = "email-logo.png"
EMAIL_LOGO_HEIGHT = 64


def email_logo(img: Path) -> Path:
    from PIL import Image

    out = img / EMAIL_LOGO
    with Image.open(BRAND_DIR / "logo" / "logo.png") as source:
        width = round(source.width * EMAIL_LOGO_HEIGHT / source.height)
        source.convert("RGB").resize((width, EMAIL_LOGO_HEIGHT), Image.LANCZOS).save(
            out, format="PNG", optimize=True)
    return out


# Los íconos de redes del pie de los correos del sistema (octubre de 2026). En
# PNG, por lo mismo que el ala, y en gris: el pie va callado, como el del resto
# del correo. Salen del glifo negro de cada kit oficial (brand/social/, que no se
# edita): su forma, recortada a lo que se ve, cuadrada y pintada de este gris,
# al doble de los 18 px a los que se dibuja.
MAIL_SOCIAL = {
    "instagram": BRAND_DIR / "social" / "instagram" / "03 Black Glyph" / "Instagram_Glyph_Black.png",
    "whatsapp": (BRAND_DIR / "social" / "whatsapp" / "01_Glyph" / "01_Digital RGB" / "02_PNG"
                 / "Digital_Glyph_Black_RGB_2026.png"),
}
MAIL_SOCIAL_SIZE = 36
MAIL_SOCIAL_GRAY = (113, 113, 122)  # #71717A, el gris del pie


# La cabecera de los correos del sistema (octubre de 2026): el ala y «sobreala»
# en Outfit Medium y en minúsculas, la marca escrita, en el color del logo y **sin
# fondo**, porque va sobre la franja azul que pinta la plantilla. Sin fondo a
# propósito: en modo oscuro el lector repinta el fondo de la celda y no toca
# las imágenes, y un PNG con su propio azul se vería como un recuadro flotando.
# La palabra va dentro de la imagen porque los lectores de correo no cargan
# fuentes propias: en texto saldría en Arial. Medida fija, al doble de la que se
# dibuja (`mailer.HEADER_SIZE`), para que la plantilla no la achate nunca.
MAIL_HEADER = "header.png"
# El grosor de la marca escrita: Outfit Medium, el mismo que pone el CSS.
BRAND_WEIGHT = 500
MAIL_HEADER_SIZE = (400, 88)


def mail_header(img: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    width, height = MAIL_HEADER_SIZE
    canvas = Image.new("RGBA", MAIL_HEADER_SIZE, (0, 0, 0, 0))
    wing = Image.open(BRAND_DIR / "logo" / "logo-wing.png").convert("RGBA")
    wing.thumbnail((10_000, round(height * .62)), Image.LANCZOS)
    font = ImageFont.truetype(
        str(BRAND_DIR / "fonts" / "outfit" / "Outfit-VariableFont_wght.ttf"), round(height * .56))
    font.set_variation_by_axes([BRAND_WEIGHT])
    draw = ImageDraw.Draw(canvas)
    word = "sobreala"
    box = draw.textbbox((0, 0), word, font=font, anchor="ls")
    gap = round(height * .2)
    total = wing.width + gap + (box[2] - box[0])
    left = (width - total) // 2
    canvas.paste(wing, (left, (height - wing.height) // 2), wing)
    draw.text((left + wing.width + gap, height // 2), word, font=font,
              fill=palette("color-logo", "#EFEEEC"), anchor="lm")
    out = img / "mail" / MAIL_HEADER
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="PNG", optimize=True)
    return out


def mail_social(img: Path) -> list[Path]:
    from PIL import Image

    out_dir = img / "mail"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, source in MAIL_SOCIAL.items():
        if not source.exists():
            continue
        with Image.open(source) as opened:
            shape = opened.convert("RGBA")
        # La forma es lo opaco y oscuro: el glifo negro sobre transparente.
        alpha = shape.getchannel("A")
        dark = shape.convert("L").point(lambda v: 255 - v)
        mask = Image.composite(dark, Image.new("L", shape.size, 0), alpha)
        box = mask.getbbox()
        if box:
            mask = mask.crop(box)
        side = max(mask.size)
        square = Image.new("L", (side, side), 0)
        square.paste(mask, ((side - mask.width) // 2, (side - mask.height) // 2))
        square = square.resize((MAIL_SOCIAL_SIZE, MAIL_SOCIAL_SIZE), Image.LANCZOS)
        icon = Image.new("RGBA", square.size, MAIL_SOCIAL_GRAY + (0,))
        icon.putalpha(square)
        target = out_dir / f"{name}.png"
        icon.save(target, format="PNG", optimize=True)
        written.append(target)
    return written


def check() -> list[Path]:
    """Los archivos generados que ya no coinciden con sus fuentes.

    Misma idea que en landing/build_site.py: panel.css y _wing.svg se generan
    desde brand/ y desde _panel.src.css, y editarlos sin regenerar no rompe
    nada hasta que alguien mira la página. Genera en un directorio temporal y
    compara; no escribe nada en el repositorio.
    """
    import tempfile

    global OUT_CSS, OUT_WING, OUT_FONTS, OUT_IMG
    saved = (OUT_CSS, OUT_WING, OUT_FONTS, OUT_IMG)
    stale: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="sobreala-check-") as tmp:
        fake = Path(tmp)
        OUT_CSS = fake / "static" / "css" / "panel.css"
        OUT_WING = fake / "templates" / "_wing.svg"
        OUT_FONTS = fake / "static" / "fonts"
        OUT_IMG = fake / "static" / "img"
        try:
            produced = build()
        finally:
            OUT_CSS, OUT_WING, OUT_FONTS, OUT_IMG = saved

        for made in produced:
            if made.suffix.lower() not in CHECKED:
                continue
            published = BASE_DIR / made.relative_to(fake)
            if (not published.exists()
                    or published.read_bytes() != made.read_bytes()):
                stale.append(published)
    return stale


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="no escribir: solo decir si lo generado quedo viejo")
    args = ap.parse_args(argv)

    if args.check:
        stale = check()
        if not stale:
            print("Los archivos generados del panel estan al dia.")
            return 0
        print("Estos archivos se quedaron viejos:")
        for path in stale:
            print("  ", path.relative_to(BASE_DIR.parent))
        print()
        print("Corre:  python backend/build_assets.py")
        return 1

    for path in build():
        print("wrote", path.relative_to(BASE_DIR.parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
