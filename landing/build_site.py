#!/usr/bin/env python3
"""Generate the public Sobreala site into landing/.

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
import json
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
    ("Correos sin marca de agua", "Correos sin marca de agua"),
    ("Usuarios", "Usuarios de la cuenta"),
]
# Las filas de docs/pricing.md que el sitio ya no publica (octubre de 2026):
# «Crear plantillas en el editor», «Analytics completo» y «Exportar CSV y
# PDF». Siguen en ese documento, que es la fuente de verdad de los planes.

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
    ("Outfit", BRAND_DIR / "fonts" / "outfit" / "Outfit-VariableFont_wght.ttf", "100 900"),
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

# Third-party marks. The official brand kits live untouched under brand/social/;
# this is the one place that says which variant the site uses. To switch (say,
# to the color version), change the path here and rebuild. A missing file is not
# an error: the footer falls back to an inline icon, and the build prints a
# warning.
#
# Los logos de pago (brand/payments/) ya no salen en el sitio: iban en una
# franja del pie que se quitó en octubre de 2026. El panel tiene su propia copia
# para el checkout (backend/build_assets.py).
SOCIAL_ICONS = {
    "instagram": BRAND_DIR / "social" / "instagram" / "02 White Glyph" / "Instagram_Glyph_White.svg",
    "whatsapp": BRAND_DIR / "social" / "whatsapp" / "01_Glyph" / "01_Digital RGB" / "03_SVG"
                / "Digital_Glyph_White_RGB_2026.svg",
}


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


def prepare_png(source: Path, target: Path, square: bool) -> None:
    """Copy a PNG trimmed to its visible content, optionally squared.

    Icon files often come on a wide canvas with the glyph centered; rendered in a
    square box that squashes the glyph, so social icons are squared here.
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
        str(BRAND_DIR / "fonts" / "outfit" / "Outfit-VariableFont_wght.ttf"), 58)
    titulo = ImageFont.truetype(
        str(BRAND_DIR / "fonts" / "sora" / "Sora-VariableFont_wght.ttf"), 66)
    pie = ImageFont.truetype(
        str(BRAND_DIR / "fonts" / "sora" / "Sora-VariableFont_wght.ttf"), 28)
    for font, peso in ((titulo, 700), (pie, 500), (wordmark, 500)):
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
                  "sobreala", font=wordmark, fill=marca, anchor="lm")

        lineas = wrap_text(draw, card_title(page), titulo, OG_SIZE[0] - margen * 2)
        alto = 86
        y = OG_SIZE[1] - margen - 52 - alto * len(lineas)
        for linea in lineas:
            draw.text((margen, y), linea, font=titulo, fill="#FFFFFF")
            y += alto

        draw.text((margen, OG_SIZE[1] - margen), "sobreala.com",
                  font=pie, fill=claro, anchor="ls")

        target = OG_DIR / f"{slug}.png"
        lienzo.save(target, optimize=True)
        written.append(target)
    return written


def copy_icon_set(sources: dict[str, Path], out_dir: Path, url_prefix: str,
                  square: bool = False) -> dict:
    """Copy the chosen kit file of each icon as <name>.<ext>. Returns name -> URL."""
    out_dir.mkdir(parents=True, exist_ok=True)
    available = {}
    for name, source in sources.items():
        if not source.exists():
            print(f"aviso: falta {source.relative_to(ROOT)}; el sitio usa el respaldo", file=sys.stderr)
            continue
        target = out_dir / f"{name}{source.suffix.lower()}"
        if source.suffix.lower() == ".png":
            prepare_png(source, target, square=square)
        else:
            shutil.copy2(source, target)
        available[name] = f"{url_prefix}/{target.name}"
    return available


# Where each tutorial step's dot goes, written by tutorials.py.
TUTORIAL_DATA = LANDING_DIR / "tutorials.json"


def tutorial_tours() -> list[dict]:
    """The tutorials of /how-it-works: the words from content.py and, for each
    step, its screenshot and its dot from tutorials.json.

    A step without its words stops the build: a tutorial that silently skipped
    one would leave its reader pressing a dot nobody explained.
    """
    spots = json.loads(TUTORIAL_DATA.read_text(encoding="utf-8"))
    tours = []
    for tour in content.TUTORIALS["tours"]:
        steps = []
        for one in spots[tour["id"]]:
            words = tour["steps"].get(one["id"])
            if words is None:
                raise SystemExit(f"Falta el texto del paso {tour['id']}/{one['id']} "
                                 "en content.py (TUTORIALS).")
            steps.append({**words, "id": one["id"], "image": one["image"],
                          "spot": one["spot"]})
        tours.append({**tour, "steps": steps})
    return tours


# The pictures of the home page samples, written by samples.py. Fixed here and
# not built from LANDING_DIR at build time: check() points that to a scratch
# folder, and the build does not make these.
SAMPLE_IMG = LANDING_DIR / "assets" / "img" / "samples"


def sample_cards() -> list[dict]:
    """The home page samples from content.py, each with its picture and the
    size the <img> reserves before it loads.

    A sample without its picture stops the build: its card would be empty.
    """
    from PIL import Image

    cards = []
    for one in content.SAMPLES:
        made = SAMPLE_IMG / f"{one['slug']}.webp"
        if not made.exists():
            raise SystemExit(f"Falta la miniatura de la muestra {one['slug']}. "
                             "Corre: python landing/samples.py")
        with Image.open(made) as opened:
            size = opened.size
        cards.append({**one, "image": f"/assets/img/samples/{made.name}", "size": size})
    return cards


def copy_assets() -> dict:
    """Copy logo, favicons and social icons. Returns the social icons that exist."""
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    for source, name in COPY_IMAGES:
        if source.exists():
            shutil.copy2(source, OUT_IMG / name)

    return copy_icon_set(SOCIAL_ICONS, OUT_IMG / "social", "/assets/img/social", square=True)


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
    ("privacy/index.html", "legal.html.j2", "/privacy/", content.PRIVACY),
    ("terms/index.html", "legal.html.j2", "/terms/", content.TERMS),
    # La documentación de la API (octubre de 2026), de backend/api_spec.py.
    ("api/index.html", "api.html.j2", "/api/", content.API_PAGE),
]

# La descripción de la API: la misma que la API sirve en /api/v1/openapi.json.
API_SPEC = ROOT / "backend" / "api_spec.py"


def load_api_spec():
    """backend/api_spec.py, cargado por su ruta: son solo datos, sin Flask."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("sobreala_api_spec", API_SPEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def curl_of(base: str, one: dict) -> str:
    """El ejemplo de `curl` de una ruta: el método, la llave y su cuerpo."""
    import json

    url = base + one["path"] + (("?" + one["query_example"]) if one.get("query_example") else "")
    first = f"curl -X {one['method']} {url}" if one["method"] != "GET" else f"curl {url}"
    lines = [first]
    if one["scope"] != "public":
        lines.append('-H "Authorization: Bearer sa_live_tu_llave"')
    if one.get("upload"):
        lines.append(f'-F "{one["upload"]}"')
    elif one.get("request") is not None:
        lines.append('-H "Content-Type: application/json"')
        body = json.dumps(one["request"], ensure_ascii=False, indent=2)
        lines.append("-d '" + body.replace("'", "'\\''") + "'")
    return " \\\n  ".join(lines)


def api_page_data() -> dict:
    """Lo que dibuja /api/: las guías y cada ruta con su ancla y su `curl`."""
    api = load_api_spec()
    # Lo que una guía o una ruta puede no traer, con su valor vacío: la
    # plantilla va con StrictUndefined.
    guide_defaults = {"code": "", "scopes": False, "errors": False}
    endpoint_defaults = {"test": "", "query": [], "fields": [], "response": None}
    return {
        "guides": [{**guide_defaults, **one} for one in api.GUIDES],
        "scopes": api.SCOPES,
        "errors": api.ERRORS,
        "openapi_url": api.BASE_URL + "/openapi.json",
        "groups": [{**group, "endpoints": [
            {**endpoint_defaults, **one, "anchor": api.anchor(one),
             "curl": curl_of(api.BASE_URL, one), "status": one.get("status", 200)}
            for one in group["endpoints"]]} for group in api.GROUPS],
    }


def rich(text: str) -> "Markup":
    """Lo de `strong`, y además `código` entre acentos graves. Escapa primero,
    así que el texto sigue sin poder meter HTML."""
    from markupsafe import Markup, escape

    done = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(text)))
    return Markup(re.sub(r"`([^`]+)`", r"<code>\1</code>", done))


def pretty_json(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2)

# The pages that became sections of the home page, and the anchor each one
# lands on. They still answer, because the panel, saved links and search
# engines know them: each is a page that only sends the visitor on.
REDIRECTS = [
    ("pricing/index.html", "/pricing/", "planes", content.PRICING),
    ("how-it-works/index.html", "/how-it-works/", "como-funciona", content.HOW),
    # Nosotros se quitó (octubre de 2026): la dirección vieja lleva al inicio.
    ("about/index.html", "/about/", "inicio", content.ABOUT),
    ("contact/index.html", "/contact/", "contacto", content.CONTACT_PAGE),
]


# Solo las páginas que alguien comparte. Las dos legales se quedan con el logo:
# nadie pega los términos en un chat.
SOCIAL_CARDS = [
    ("home", content.HOME),
]

# Qué tarjeta le toca a cada página. Lo que no esté aquí usa el logo.
OG_IMAGES = {
    "/": "home",
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
    social = copy_assets()
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
    env.filters["rich"] = rich
    env.filters["pretty_json"] = pretty_json

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
        "cta_states": content.CTA_STATES,
        "footer": content.FOOTER,
        "tutorials": content.TUTORIALS,
        "tutorial_tours": tutorial_tours(),
        "samples": sample_cards(),
        # The other sections of the home page, each with its own words.
        "pricing": content.PRICING,
        "how": content.HOW,
        "font_faces": faces,
        "social_icons": social,
        "wing_svg": Markup(read_wing_svg()),  # trusted: our own generated SVG
        "pricing_data": pricing,
        "api": api_page_data(),
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

    for out_name, url, anchor, page in REDIRECTS:
        html = env.get_template("redirect.html.j2").render(
            page=page, current_url=url, anchor=anchor, **shared)
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
    with tempfile.TemporaryDirectory(prefix="sobreala-check-") as tmp:
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
    ap = argparse.ArgumentParser(description="Generate the public Sobreala site.")
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
