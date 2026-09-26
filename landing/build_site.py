#!/usr/bin/env python3
"""Generate the public Panamails site into landing/.

Sources of truth, none of them duplicated here:

    brand/colors.css     colors
    brand/fonts/         typefaces (converted to .woff2 on the way out)
    brand/logo/          logo SVG
    brand/favicon/       favicons
    brand/social/        social icons
    docs/pricing.md      plans, limits and add-on prices
    landing/content.py   every line of copy

Everything under landing/ that this script writes is generated: the HTML pages,
assets/fonts/ and assets/img/. Do not edit those by hand, edit the sources and
run this again.

    python landing/build_site.py            # build
    python landing/build_site.py --serve    # build, then serve it locally

Requires jinja2, and fonttools + brotli for the .woff2 conversion (all already
used elsewhere in the project).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from pathlib import Path

LANDING_DIR = Path(__file__).resolve().parent
ROOT = LANDING_DIR.parent
BRAND_DIR = ROOT / "brand"
PRICING_MD = ROOT / "docs" / "pricing.md"

SRC_DIR = LANDING_DIR / "src"
ASSETS_DIR = LANDING_DIR / "assets"
OUT_FONTS = ASSETS_DIR / "fonts"
OUT_IMG = ASSETS_DIR / "img"

sys.path.insert(0, str(LANDING_DIR))
import content  # noqa: E402  (local module, needs the path above)


# --------------------------------------------------------------------------- pricing

# Rows of the plans table that are safe to publish, in display order, with the
# label the visitor reads. Anything not listed here stays internal: cost per
# email, margins, competitors and prospect lists never leave docs/pricing.md.
PUBLIC_ROWS = [
    ("Contactos", "Contactos"),
    ("Correos por mes", "Correos por mes"),
    ("Etiquetas", "Etiquetas"),
    ("Columnas propias del contacto", "Columnas de datos"),
    ("Crear plantillas en el editor", "Crear plantillas en el editor"),
    ("Correos sin marca de agua", "Correos sin marca de agua"),
    ("Analytics completo", "Estadísticas de cada campaña"),
    ("Exportar CSV y PDF", "Exportar a CSV y PDF"),
    ("Usuarios", "Usuarios de la cuenta"),
]

# Filas cuyo número es el del plan pero cuya función todavía se está
# construyendo. Se dibujan con su marca al lado, para que nadie contrate
# esperando algo que hoy no puede usar. Hoy: una cuenta es un solo acceso, sin
# empleados ni permisos.
# Ninguna fila está por venir ahora mismo. La lista se queda: es donde se marca
# lo que se anuncia antes de existir.
SOON_ROWS: set[str] = set()

# Rows shown on the plan cards, above the fold.
CARD_ROWS = ["Contactos", "Correos por mes", "Usuarios"]


def money(cell: str) -> int:
    """«$1,200» → 1200. Lo que la tabla escribe para leerse, como número."""
    digits = "".join(c for c in cell if c.isdigit())
    return int(digits) if digits else 0


def discount(monthly: int, yearly: int) -> int:
    """Cuánto se ahorra al año, en por ciento y redondeado.

    Sale de las dos cifras del documento de precios y no escrito a mano: si un
    día cambian, la etiqueta del sitio cambia con ellas.
    """
    if not monthly or not yearly:
        return 0
    return round((1 - yearly / (monthly * 12)) * 100)


def slug(name: str) -> str:
    """«Básico» → «basico», que es como el panel llama a cada plan.

    Tiene que dar exactamente lo mismo que slug() de
    backend/services/plans.py: es la pieza que enlaza el botón de esta página
    con la pantalla de contratar. No se importa de allí porque este generador
    parsea docs/pricing.md por su cuenta, a propósito: publicar el sitio no
    depende de que el backend se pueda importar.
    """
    plain = unicodedata.normalize("NFKD", name)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return plain.strip().lower()


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_table(lines: list[str], start: int) -> tuple[list[str], dict[str, list[str]], int]:
    """Read one markdown table starting at `start`. Returns header, rows, next index."""
    header = _split_row(lines[start])
    i = start + 2  # skip the |---|---| separator
    rows: dict[str, list[str]] = {}
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        cells = _split_row(lines[i])
        rows[cells[0].replace("*", "").strip()] = cells[1:]
        i += 1
    return header, rows, i


def read_pricing(path: Path = PRICING_MD) -> dict:
    """Extract the plans table from docs/pricing.md.

    Parsed at build time on purpose: the numbers live in exactly one file, so the
    site can never disagree with the document.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    plans_header: list[str] = []
    plans_rows: dict[str, list[str]] = {}

    section = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## ") or line.startswith("### "):
            section = line.lstrip("# ").strip()
        elif line.lstrip().startswith("|") and section == "Planes":
            header, rows, i = _parse_table(lines, i)
            if not plans_rows:
                plans_header, plans_rows = header, rows
            continue
        i += 1

    names = [n for n in plans_header[1:] if n]
    if not names or not plans_rows:
        sys.exit(f"{path}: could not find the plans table")

    def cell(row: str, plan: str) -> str:
        values = plans_rows.get(row)
        if values is None:
            sys.exit(f"{path}: missing row '{row}' in the plans table")
        return values[names.index(plan)]

    plans = []
    for name in names:
        extra = content.PRICING["plans"].get(name, {})
        monthly = cell("Precio mensual", name)
        yearly = cell("Precio anual (20% de descuento)", name)
        plans.append({
            "name": name,
            # Con qué nombre lo conoce el panel, para el botón de contratar.
            "key": slug(name),
            "monthly": monthly,
            "yearly": yearly,
            # Las mismas cifras como números, para el interruptor de mensual y
            # anual: el guion no tiene que interpretar «$1,200». El equivalente
            # mensual del anual es lo que se enseña al elegir año, porque es lo
            # que se compara con el precio de al lado.
            "monthly_value": money(monthly),
            "yearly_value": money(yearly),
            "yearly_monthly": round(money(yearly) / 12),
            # Cuánto se ahorra pagando el año, sacado de las dos cifras de
            # arriba: así la etiqueta no puede decir un descuento que el
            # documento no dé.
            "yearly_off": discount(money(monthly), money(yearly)),
            "highlights": [
                {"label": dict(PUBLIC_ROWS)[r], "value": cell(r, name)} for r in CARD_ROWS
            ],
            **extra,
        })

    table = {
        "plans": names,
        "rows": [
            {"label": label, "soon": key in SOON_ROWS,
             "values": [cell(key, n) for n in names]}
            for key, label in PUBLIC_ROWS
        ],
    }

    # El descuento que se anuncia en la pastilla y en la nota de abajo. Si los
    # tres planes no dieran el mismo, se dice el más chico: es el único que se
    # cumple en todos.
    off = min((one["yearly_off"] for one in plans), default=0)

    return {"plans": plans, "table": table, "yearly_off": f"{off}%"}


# --------------------------------------------------------------------------- assets

FONT_FILES = [
    # (family name used in CSS, source file, css weight or range)
    ("Changa One", BRAND_DIR / "fonts" / "changa-one" / "ChangaOne-Regular.ttf", "400"),
    ("Sora", BRAND_DIR / "fonts" / "sora" / "Sora-VariableFont_wght.ttf", "100 800"),
]

COPY_IMAGES = [
    (BRAND_DIR / "logo" / "logo-transparent.svg", "logo-wing.svg"),
    # For the emails: the <img> in their header. Clients do not draw SVG.
    (BRAND_DIR / "logo" / "logo-wing.png", "logo-wing.png"),
    (BRAND_DIR / "logo" / "logo.svg", "logo.svg"),
    (BRAND_DIR / "logo" / "logo.png", "logo.png"),
    (BRAND_DIR / "favicon" / "favicon.svg", "favicon.svg"),
    (BRAND_DIR / "favicon" / "favicon.ico", "favicon.ico"),
    (BRAND_DIR / "favicon" / "favicon-32x32.png", "favicon-32x32.png"),
    (BRAND_DIR / "favicon" / "favicon-16x16.png", "favicon-16x16.png"),
    (BRAND_DIR / "favicon" / "favicon-180x180.png", "favicon-180x180.png"),
]

# Third-party marks. The official brand kits live untouched under brand/social/
# and brand/payments/; this is the one place that says which variant the site
# uses. To switch (say, to the color version), change the path here and rebuild.
# A missing file is not an error: the footer falls back to an inline icon or to
# a text line, and the build prints a warning.
SOCIAL_ICONS = {
    "instagram": BRAND_DIR / "social" / "instagram" / "02 White Glyph" / "Instagram_Glyph_White.svg",
    "whatsapp": BRAND_DIR / "social" / "whatsapp" / "01_Glyph" / "01_Digital RGB" / "03_SVG"
                / "Digital_Glyph_White_RGB_2026.svg",
}
# Los dos en blanco, porque la franja del pie es del azul de la marca: el azul
# oscuro de PayPal encima da 2:1 y sus propias normas piden la versión blanca
# sobre fondos oscuros. Yappy solo tiene la "traslucid", que también es blanca.
PAYMENT_LOGOS = {
    "yappy": BRAND_DIR / "payments" / "yappy" / "yappy-color-landscape.svg",
    "paypal": BRAND_DIR / "payments" / "paypal" / "Horizontal Full Color" / "pp_h_rgb.png",
    "visa": (BRAND_DIR / "payments" / "visa" / "Visa Brand Mark DIGITAL 2025"
             / "Visa Brand Mark DIGITAL" / "VBM_digital_2025" / "blue" / "VBM_bluRGB_2025.svg"),
    "mastercard": (BRAND_DIR / "payments" / "mastercard" / "Mastercard Symbol - SVG"
                   / "Artwork" / "ma_symbol.svg"),
}
# Cómo se escribe cada marca, para el texto alternativo.
PAYMENT_LABELS = {"yappy": "Yappy", "paypal": "PayPal", "visa": "Visa",
                  "mastercard": "Mastercard"}
# Raster payment logos are shrunk to this height (4x their 28 px display size).
PAYMENT_LOGO_PX = 112
# El alto al que se dibujan en el pie.
PAYMENT_SHOWN_PX = 28


def build_fonts() -> list[dict]:
    """Convert brand fonts to .woff2 in assets/fonts/. Returns @font-face data."""
    from fontTools.ttLib import TTFont

    OUT_FONTS.mkdir(parents=True, exist_ok=True)
    faces = []
    for family, source, weight in FONT_FILES:
        if not source.exists():
            sys.exit(f"missing font: {source}\nSee brand/fonts/README.md.")
        out = OUT_FONTS / (source.stem + ".woff2")
        if not out.exists() or out.stat().st_mtime < source.stat().st_mtime:
            font = TTFont(str(source))
            font.flavor = "woff2"
            font.save(str(out))
            font.close()
        faces.append({
            "family": family,
            "file": f"/assets/fonts/{out.name}",
            "weight": weight,
        })
    return faces


def write_css(faces: list[dict]) -> Path:
    """assets/css/site.css = brand color variables + @font-face + src/site.css."""
    colors = (BRAND_DIR / "colors.css").read_text(encoding="utf-8")
    header_comment = re.compile(r"/\*.*?\*/\s*", re.S)
    colors = header_comment.sub("", colors, count=1)
    # The dark palette lives in its own file so build_logo.py never sees it:
    # that parser keeps the last value of each variable name.
    dark = BRAND_DIR / "colors-dark.css"
    if dark.exists():
        colors += "\n" + header_comment.sub("", dark.read_text(encoding="utf-8"), count=1)
    face_tpl = (
        "@font-face {{\n"
        "  font-family: \"{family}\";\n"
        "  src: url(\"{file}\") format(\"woff2\");\n"
        "  font-weight: {weight};\n"
        "  font-style: normal;\n"
        "  font-display: swap;\n"
        "}}\n"
    )
    faces_css = "".join(face_tpl.format(**f) for f in faces)
    body = (SRC_DIR / "site.css").read_text(encoding="utf-8")
    out = ASSETS_DIR / "css" / "site.css"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = "/* GENERATED by landing/build_site.py. Edit brand/colors.css and landing/src/site.css instead. */\n"
    out.write_text(
        header + colors.strip() + "\n\n" + faces_css + "\n" + body,
        encoding="utf-8", newline="\n",
    )
    return out


def prepare_png(source: Path, target: Path, square: bool, max_height: int | None) -> None:
    """Copy a PNG trimmed to its visible content, optionally squared and shrunk.

    Icon files often come on a wide canvas with the glyph centered; rendered in a
    square box that squashes the glyph, so social icons are squared here. Logos
    keep their proportions and are only shrunk: the kits ship at print size.
    """
    from PIL import Image

    im = Image.open(source).convert("RGBA")
    box = im.getchannel("A").getbbox()
    if box:
        im = im.crop(box)
    if square:
        side = max(im.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
        im = canvas
    if max_height and im.height > max_height:
        im = im.resize((round(im.width * max_height / im.height), max_height), Image.LANCZOS)
    im.save(target, optimize=True)


# La tarjeta que enseñan WhatsApp, Facebook e Instagram al pegar un enlace.
# 1200 x 630 es lo que llena esa tarjeta; el logo, que es casi cuadrado, se
# recortaba. Van en su propia carpeta: assets/img/social/ ya es la de los
# iconos de redes y mezclarlas confunde las dos cosas.
OG_DIR = OUT_IMG / "og"
OG_SIZE = (1200, 630)


def brand_color(name: str, fallback: str) -> str:
    """Un color de brand/colors.css, que es la fuente de verdad."""
    text = (BRAND_DIR / "colors.css").read_text(encoding="utf-8")
    found = re.search(rf"--{name}:\s*(#[0-9A-Fa-f]{{3,8}})\s*;", text)
    return found.group(1) if found else fallback


def card_title(page: dict) -> str:
    """El título de la página, tal como lo escribe content.py.

    La portada lo tiene partido en dos porque la segunda mitad va en otro color;
    aquí se vuelven a juntar. Ninguna frase se escribe en este archivo: el
    español sigue viviendo en un solo sitio.
    """
    hero = page.get("hero", {})
    if hero.get("title"):
        return hero["title"]
    return " ".join(x for x in (hero.get("title_lead"), hero.get("title_accent")) if x)


def wrap_text(draw, text: str, font, width: int) -> list[str]:
    """Partir el título en líneas que quepan, sin cortar palabras."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]


def build_social_cards() -> list[Path]:
    """Una tarjeta por página, con el ala, la marca y su propio título."""
    from PIL import Image, ImageDraw, ImageFont

    fondo = brand_color("color-background", "#3166A7")
    marca = brand_color("color-logo", "#EFEEEC")
    claro = brand_color("color-accent-light", "#CFEBFA")

    ala = Image.open(BRAND_DIR / "logo" / "logo-wing.png").convert("RGBA")
    ala.thumbnail((300, 300), Image.LANCZOS)

    wordmark = ImageFont.truetype(
        str(BRAND_DIR / "fonts" / "changa-one" / "ChangaOne-Regular.ttf"), 58)
    titulo = ImageFont.truetype(
        str(BRAND_DIR / "fonts" / "sora" / "Sora-VariableFont_wght.ttf"), 66)
    pie = ImageFont.truetype(
        str(BRAND_DIR / "fonts" / "sora" / "Sora-VariableFont_wght.ttf"), 28)
    for font, peso in ((titulo, 700), (pie, 500)):
        try:
            font.set_variation_by_axes([peso])
        except Exception:  # noqa: BLE001 - sin ejes variables se usa el normal
            pass

    OG_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    margen = 76
    for slug, page in SOCIAL_CARDS:
        lienzo = Image.new("RGB", OG_SIZE, fondo)
        draw = ImageDraw.Draw(lienzo)

        lienzo.paste(ala, (margen, margen - 18), ala)
        draw.text((margen + ala.width + 20, margen + ala.height // 2),
                  "Panamails", font=wordmark, fill=marca, anchor="lm")

        lineas = wrap_text(draw, card_title(page), titulo, OG_SIZE[0] - margen * 2)
        alto = 86
        y = OG_SIZE[1] - margen - 52 - alto * len(lineas)
        for linea in lineas:
            draw.text((margen, y), linea, font=titulo, fill="#FFFFFF")
            y += alto

        draw.text((margen, OG_SIZE[1] - margen), "panamails.com",
                  font=pie, fill=claro, anchor="ls")

        target = OG_DIR / f"{slug}.png"
        lienzo.save(target, optimize=True)
        written.append(target)
    return written


def copy_icon_set(sources: dict[str, Path], out_dir: Path, url_prefix: str,
                  square: bool = False, max_height: int | None = None) -> dict:
    """Copy the chosen kit file of each icon as <name>.<ext>. Returns name -> URL."""
    out_dir.mkdir(parents=True, exist_ok=True)
    available = {}
    for name, source in sources.items():
        if not source.exists():
            print(f"aviso: falta {source.relative_to(ROOT)}; el sitio usa el respaldo", file=sys.stderr)
            continue
        target = out_dir / f"{name}{source.suffix.lower()}"
        if source.suffix.lower() == ".png":
            prepare_png(source, target, square=square, max_height=max_height)
        else:
            shutil.copy2(source, target)
        available[name] = f"{url_prefix}/{target.name}"
    return available


def icon_size(url: str, height: int) -> tuple[int, int]:
    """Las medidas con las que se dibuja un logo, a este alto.

    Van en el `<img>` para que el navegador le guarde el sitio antes de bajarlo:
    sin eso, la franja del pie salta al cargar. Se sacan del archivo generado,
    así que cambiar de variante no deja las medidas viejas escritas.
    """
    made = LANDING_DIR / url.lstrip("/")
    if made.suffix.lower() == ".svg":
        box = re.search(r'viewBox="[\d.\s]*?([\d.]+)\s+([\d.]+)"',
                        made.read_text(encoding="utf-8"))
        wide, tall = (float(box.group(1)), float(box.group(2))) if box else (1.0, 1.0)
    else:
        from PIL import Image

        with Image.open(made) as opened:
            wide, tall = opened.size
    return round(height * wide / max(tall, 1)), height


def crop_logos(out_dir: Path) -> None:
    """El recorte de brand/payments/viewbox.json en las copias SVG: Visa y
    Mastercard traen su margen de respeto dentro del archivo, y a 28 px de alto
    el dibujo quedaba diminuto. El kit no se toca."""
    import json

    crops = json.loads((BRAND_DIR / "payments" / "viewbox.json").read_text(encoding="utf-8"))
    for name, box in crops.items():
        made = out_dir / f"{name}.svg"
        if name.startswith("_") or not made.exists():
            continue
        text = made.read_text(encoding="utf-8")
        made.write_text(re.sub(r'viewBox="[^"]*"', f'viewBox="{box}"', text, count=1),
                        encoding="utf-8", newline="")


def copy_assets() -> tuple[dict, dict]:
    """Copy logo, favicons, social icons and payment logos. Returns what exists."""
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    for source, name in COPY_IMAGES:
        if source.exists():
            shutil.copy2(source, OUT_IMG / name)

    social = copy_icon_set(SOCIAL_ICONS, OUT_IMG / "social", "/assets/img/social", square=True)
    payments = copy_icon_set(PAYMENT_LOGOS, OUT_IMG / "payments", "/assets/img/payments",
                             max_height=PAYMENT_LOGO_PX)
    crop_logos(OUT_IMG / "payments")
    return social, payments


def read_wing_svg() -> str:
    """Inline the wing so it inherits colors from CSS and needs no extra request."""
    svg = (BRAND_DIR / "logo" / "logo-transparent.svg").read_text(encoding="utf-8")
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg, count=2)
    svg = re.sub(r'fill="#[0-9A-Fa-f]{6}"', "", svg)
    svg = svg.replace('role="img"', 'aria-hidden="true" focusable="false"')
    svg = re.sub(r"<title[^>]*>.*?</title>\s*", "", svg, flags=re.S)
    svg = re.sub(r'\saria-labelledby="[^"]*"', "", svg)
    return svg.strip()


# --------------------------------------------------------------------------- render

PAGES = [
    ("index.html", "index.html.j2", "/", content.HOME),
    ("como-funciona/index.html", "como-funciona.html.j2", "/como-funciona/", content.HOW),
    ("planes/index.html", "precios.html.j2", "/planes/", content.PRICING),
    ("nosotros/index.html", "nosotros.html.j2", "/nosotros/", content.ABOUT),
    ("contacto/index.html", "contacto.html.j2", "/contacto/", content.CONTACT_PAGE),
    ("privacidad/index.html", "legal.html.j2", "/privacidad/", content.PRIVACY),
    ("terminos/index.html", "legal.html.j2", "/terminos/", content.TERMS),
]


# Solo las páginas que alguien comparte. Las dos legales se quedan con el logo:
# nadie pega los términos en un chat.
SOCIAL_CARDS = [
    ("inicio", content.HOME),
    ("como-funciona", content.HOW),
    ("precios", content.PRICING),
    ("nosotros", content.ABOUT),
    ("contacto", content.CONTACT_PAGE),
]

# Qué tarjeta le toca a cada página. Lo que no esté aquí usa el logo.
OG_IMAGES = {
    "/": "inicio",
    "/como-funciona/": "como-funciona",
    "/planes/": "precios",
    "/nosotros/": "nosotros",
    "/contacto/": "contacto",
}


def strong(text: str) -> "Markup":
    """Pone en negrita lo que va entre ** en un texto de content.py.

    Escapa primero y marca después, así que el contenido sigue sin poder
    inyectar HTML: lo único que sobrevive es el <strong>. Lo usan las páginas
    legales, donde cada punto de una lista empieza nombrando de qué habla.
    """
    from markupsafe import Markup, escape

    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(text))))


def whatsapp_url() -> str:
    from urllib.parse import quote

    c = content.CONTACT
    return f"https://wa.me/{c['whatsapp_number']}?text={quote(c['whatsapp_message'])}"


def mailto_url() -> str:
    """mailto with subject and body prefilled, so the draft opens ready to send."""
    from urllib.parse import quote

    c = content.CONTACT
    return (f"mailto:{c['email']}"
            f"?subject={quote(c['email_subject'])}&body={quote(c['email_body'])}")


def build() -> list[Path]:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from markupsafe import Markup

    faces = build_fonts()
    css = write_css(faces)
    social, payments = copy_assets()
    build_social_cards()
    pricing = read_pricing()

    env = Environment(
        loader=FileSystemLoader([str(SRC_DIR), str(SRC_DIR / "pages")]),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["strong"] = strong

    shared = {
        "site": content.SITE,
        "nav": content.NAV,
        "contact": content.CONTACT,
        "whatsapp_url": whatsapp_url(),
        "mailto_url": mailto_url(),
        "cta_primary": content.CTA_PRIMARY,
        "panel": content.PANEL,
        "plan_buttons": content.PLAN_BUTTONS,
        "cta_secondary": content.CTA_SECONDARY,
        "footer": content.FOOTER,
        "steps": content.STEPS,
        "font_faces": faces,
        "social_icons": social,
        # Ordered as PAYMENT_LOGOS, so the footer keeps a stable order.
        "payment_logos": [
            {"name": n, "label": PAYMENT_LABELS.get(n, n.capitalize()), "url": payments[n],
             "size": icon_size(payments[n], PAYMENT_SHOWN_PX)}
            for n in PAYMENT_LOGOS if n in payments],
        "wing_svg": Markup(read_wing_svg()),  # trusted: our own generated SVG
        "pricing_data": pricing,
    }

    written = [css]
    for out_name, template, url, page in PAGES:
        html = env.get_template(template).render(
            page=page, current_url=url,
            # La tarjeta que se ve al compartir. Lo que no tenga la suya cae en
            # el logo, que es lo que hacían las cuatro hasta ahora.
            og_image=(f"/assets/img/og/{OG_IMAGES[url]}.png"
                      if url in OG_IMAGES else "/assets/img/logo.png"),
            **shared)
        target = LANDING_DIR / out_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html.rstrip() + "\n", encoding="utf-8", newline="\n")
        written.append(target)

    # Cloudflare Pages serves these from the site root.
    for name in ("favicon.ico", "favicon.svg"):
        source = OUT_IMG / name
        if source.exists():
            shutil.copy2(source, LANDING_DIR / name)
            written.append(LANDING_DIR / name)

    written.append(write_robots())
    written.append(write_sitemap())
    return written


def write_robots() -> Path:
    target = LANDING_DIR / "robots.txt"
    target.write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {content.SITE['base_url']}/sitemap.xml\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def write_sitemap() -> Path:
    base = content.SITE["base_url"]
    urls = "".join(f"  <url><loc>{base}{u}</loc></url>\n" for _, _, u, _ in PAGES)
    target = LANDING_DIR / "sitemap.xml"
    target.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def serve(port: int = 8080) -> int:
    """Serve landing/ locally so the /rutas/ resolve like on Cloudflare Pages."""
    import functools
    import webbrowser
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(LANDING_DIR))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Sitio en {url}  (Ctrl+C para parar)")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nservidor detenido")
    finally:
        httpd.server_close()
    return 0



# Lo que se compara en --check. Solo texto: dos versiones de Pillow pueden
# escribir el mismo PNG con bytes distintos, y una prueba que falla al
# actualizar una dependencia deja de creerse. La deriva que importa es esta.
CHECKED = (".html", ".css", ".svg", ".txt", ".xml")


def check() -> list[Path]:
    """Los archivos publicados que ya no coinciden con sus fuentes.

    Un archivo generado que se queda viejo no rompe nada, no falla ninguna
    prueba y llega al despliegue sin decir palabra: pasó con la fila de
    Contactos, que se agregó a la plantilla y nunca se regeneró. Esto lo
    convierte en un error visible.

    Genera todo en un directorio temporal y compara. No escribe nada en el
    repositorio, así que se puede llamar desde las pruebas.
    """
    import tempfile

    global LANDING_DIR, ASSETS_DIR, OUT_IMG, OG_DIR
    saved = (LANDING_DIR, ASSETS_DIR, OUT_IMG, OG_DIR)
    stale: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="panamails-check-") as tmp:
        fake = Path(tmp)
        LANDING_DIR = fake
        ASSETS_DIR = fake / "assets"
        OUT_IMG = ASSETS_DIR / "img"
        OG_DIR = OUT_IMG / "og"
        try:
            produced = build()
        finally:
            LANDING_DIR, ASSETS_DIR, OUT_IMG, OG_DIR = saved

        for made in produced:
            if made.suffix.lower() not in CHECKED:
                continue
            published = LANDING_DIR / made.relative_to(fake)
            if (not published.exists()
                    or published.read_bytes() != made.read_bytes()):
                stale.append(published)
    return stale


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the public Panamails site.")
    ap.add_argument("--serve", action="store_true", help="serve the built site locally")
    ap.add_argument("--port", type=int, default=8080, metavar="N", help="port for --serve")
    ap.add_argument("--check", action="store_true",
                    help="no escribir: solo decir si lo publicado quedo viejo")
    args = ap.parse_args(argv)

    if args.check:
        stale = check()
        if not stale:
            print("El sitio publicado esta al dia.")
            return 0
        print("Estos archivos se quedaron viejos:")
        for path in stale:
            print("  ", path.relative_to(ROOT))
        print("\nCorre:  python landing/build_site.py")
        return 1

    for path in build():
        print("wrote", path.relative_to(ROOT))
    if args.serve:
        return serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
