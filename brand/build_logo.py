#!/usr/bin/env python3
"""Generate the Sobreala logo assets from one vector geometry + two config files.

The logo is a wing made of four stacked feathers. It is built from a single
closed path (the white wing) drawn twice: once in the shadow color, offset
15.7 units left and 3.85 units up, and once in the logo color on top. The black
separations visible between the feathers, and the thin dark line along the
top edge, are the parts of the offset copy that the white wing does not cover.
This reproduces the reference image (brand/logo/reference/logo-original.png)
with sub-pixel accuracy.

Nothing tweakable is hard-coded here:
  brand/colors.css    colors  (--color-background, --color-logo, --color-shadow)
  brand/layout.json   placement (where the wing sits, favicon and profile framing)

Outputs:
  brand/logo/logo.svg               full composition, colored background (viewBox 0 0 271 254)
  brand/logo/logo-transparent.svg   wing only, transparent background, cropped tight
  brand/logo/logo.png               full composition, 1084 x 1016 px
  brand/favicon/favicon.svg         rounded square
  brand/favicon/favicon-16x16.png, favicon-32x32.png, favicon-180x180.png
  brand/favicon/favicon.ico         16 + 32 + 48 px
  brand/perfil/perfil-1080.png      profile picture for social networks, square and opaque
  brand/preview/colores.html        live color + position editor (open it in a browser)

Usage:
    pip install numpy pillow

    # rebuild every asset from the current config
    python brand/build_logo.py

    # colors: written into colors.css, then everything is rebuilt
    python brand/build_logo.py --background "#2E5F8A"
    python brand/build_logo.py --logo "#FFFFFF" --shadow "#0B1A26"

    # position of the wing, in canvas units from centered (+x right, +y down);
    # the same offset moves it in the logo and in the favicon. Written into layout.json
    python brand/build_logo.py --x 4 --y -2
    python brand/build_logo.py --center          # [0, 0]: centered in both
    python brand/build_logo.py --original        # exactly where the reference image has it

    # favicon framing
    python brand/build_logo.py --favicon-fill 0.84 --favicon-radius 0.20

    # the profile picture for social networks: size of the wing, and its own
    # position (it does not move the logo or the favicon)
    python brand/build_logo.py --avatar-fill 0.6
    python brand/build_logo.py --avatar-x 0 --avatar-y 0

    # print the current config and do nothing else
    python brand/build_logo.py --show

    # open the editor in a browser, with a Save button that writes the
    # config files and rebuilds everything (local development tool)
    python brand/build_logo.py --serve
    python brand/build_logo.py --serve --port 9000

The editor previews the logo over a reference grid, the favicons at real size
and the profile picture as the networks crop it, and re-colors, re-positions and
re-sizes them live. Opened as a plain file it has no
Save button and hands you the equivalent command instead.

NOTE for maintainers: PREVIEW_TEMPLATE is a raw string on purpose. As a normal
string, Python turns the 
 inside its JavaScript literals into real newlines,
which breaks the script with a syntax error and silently kills the whole page.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

BRAND_DIR = Path(__file__).resolve().parent
COLORS_CSS = BRAND_DIR / "colors.css"
LAYOUT_JSON = BRAND_DIR / "layout.json"
LOGO_DIR = BRAND_DIR / "logo"
FAVICON_DIR = BRAND_DIR / "favicon"
PREVIEW_DIR = BRAND_DIR / "preview"
AVATAR_DIR = BRAND_DIR / "perfil"

# --------------------------------------------------------------------------- geometry
# Coordinates are in the reference frame: a 271 x 254 canvas, same as the
# original PNG, so at offset (0, 0) the wing sits exactly where it does in the
# reference image.
CANVAS = (271, 254)

# Closed outline of the white wing, starting at the tip of the main feather
# and going clockwise: straight top edge, rounded top-right corner, right side,
# rounded bottom, then up the left side through the four feather tips and the
# three notches (sharp tails) between them.
START = (39.29, 55.11)
PIECES = [
    ("L", (222.48, 77.8)),                                        # top edge (straight)
    ("C", (227.95, 78.47, 228.95, 83.52, 228.32, 88.98)),         # rounded top-right corner (upper half)
    ("C", (227.15, 99.04, 220.71, 108.08, 219.12, 110.3)),        # corner -> right side, smoothed (G2 both ends)
    ("C", (208.0, 125.84, 184.82, 156.68, 162.18, 170.24)),       # right side + start of bottom curve
    ("C", (158.31, 172.56, 150.91, 174.28, 131.54, 159.81)),      # rounded bottom
    ("C", (124.23, 154.35, 120.22, 148.73, 117.43, 144.88)),      # feather 4 lower edge -> tip 4
    ("C", (118.69, 144.97, 128.31, 145.03, 128.7, 145.32)),       # notch: tip 4 -> tail 3
    ("C", (120.33, 141.45, 111.15, 136.73, 102.43, 128.62)),      # feather 3 lower edge
    ("C", (98.53, 125, 96.9, 122.49, 95.86, 117.99)),             # feather 3 lower edge -> tip 3
    ("C", (102.5, 118.53, 110.4, 119.03, 117.05, 119.06)),        # notch: tip 3 -> tail 2
    ("C", (110.13, 116.32, 100.39, 113.14, 88.88, 105.72)),       # feather 2 lower edge
    ("C", (79.86, 99.91, 76.47, 96.46, 72.08, 89.29)),            # feather 2 lower edge -> tip 2
    ("C", (79.18, 89.53, 94.64, 91.08, 94.93, 91.01)),            # notch: tip 2 -> tail 1
    ("C", (92.19, 88.99, 69.76, 84.96, 51.86, 71.06)),            # feather 1 lower edge
    ("C", (42.96, 64.14, 41.2, 59.1, 39.29, 55.11)),              # feather 1 lower edge -> tip 1
]

# The shadow is the same outline translated by this vector (left and up).
SHADOW_OFFSET = (-15.7, -3.85)

# The thin black line above the wing is the strip of the shadow copy left
# uncovered along the straight top edge. In the reference it is ~1.9 units
# thick; the shadow copy gets its top edge pushed outwards by this much (units,
# perpendicular to the edge) to make that line thicker: 1.34 gives 3.25 units.
# 0 = exact reference.
SHADOW_TOP_LIFT = 1.34

# Bounding box of wing + shadow at offset (0, 0), with the exact reference
# geometry (SHADOW_TOP_LIFT = 0). It is the frame everything is centered in;
# the lifted shadow edge pokes ~0.9 units above it, on purpose.
BBOX = (23.59, 51.26, 228.48, 171.79)  # xmin, ymin, xmax, ymax
BBOX_SIZE = (BBOX[2] - BBOX[0], BBOX[3] - BBOX[1])

# Symbol (transparent) version: cropped tight around the wing with a 1 unit
# margin, so the placement offsets do not apply to it.
SYMBOL_MARGIN = 1.0
SYMBOL_SIZE = (207, 123)

FAVICON_PNG_SIZES = (16, 32, 180)
FAVICON_ICO_SIZES = (16, 32, 48)

# The apple-touch-icon must stay square and opaque: iOS applies its own
# rounded mask, and transparent corners come out black on the home screen.
APPLE_TOUCH_SIZE = 180
APPLE_TOUCH_ROUNDED = False

# Small-size legibility: at 16 px the black separations are only ~0.35 px
# thick and vanish, so for tiny raster sizes the shadow offset is widened just
# enough to keep them visible. The outline itself never changes. favicon.svg is
# rendered by browsers at 16-32 px, so it gets the 32 px treatment.
# Set everything to 1.0 to keep the exact reference geometry at every size.
FAVICON_SHADOW_SCALE = {16: 2.0, 32: 1.5, 48: 1.25}
FAVICON_SVG_SHADOW_SCALE = 1.5

# Profile picture for social networks: 1080 px square, the size Instagram,
# Facebook, WhatsApp, LinkedIn, X, TikTok and YouTube keep without redoing it.
# Almost all of them crop it to a circle, so the wing (and its shadow) has to
# stay within this share of that circle's radius; check_placement() warns past it.
AVATAR_SIZE = 1080
AVATAR_SAFE = 0.8

# --------------------------------------------------------------------------- colors
COLOR_KEYS = ("color-background", "color-logo", "color-shadow")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def read_colors(css_path: Path = COLORS_CSS) -> dict[str, str]:
    """Parse `--name: #RRGGBB;` declarations from colors.css."""
    text = css_path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    found = {m.group(1): m.group(2).upper() for m in re.finditer(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text)}
    missing = [k for k in COLOR_KEYS if k not in found]
    if missing:
        sys.exit(f"{css_path}: missing color variables: {', '.join('--' + m for m in missing)}")
    return {k: found[k] for k in COLOR_KEYS}


def write_colors(updates: dict[str, str], css_path: Path = COLORS_CSS) -> dict[str, str]:
    """Replace color values in colors.css in place, keeping comments and layout."""
    text = css_path.read_text(encoding="utf-8")
    for key, value in updates.items():
        pattern = re.compile(r"(--" + re.escape(key) + r"\s*:\s*)#[0-9a-fA-F]{6}(\s*;)")
        text, count = pattern.subn(lambda m: m.group(1) + value.upper() + m.group(2), text, count=1)
        if not count:
            sys.exit(f"{css_path}: could not find --{key} to update")
    css_path.write_text(text, encoding="utf-8", newline="\n")
    return read_colors(css_path)


def parse_hex(value) -> str | None:
    """Normalize a color to #RRGGBB, or None if it is not one."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v.startswith("#"):
        v = "#" + v
    if len(v) == 4:  # #abc -> #aabbcc
        v = "#" + "".join(c * 2 for c in v[1:])
    return v.upper() if HEX_RE.match(v) else None


def normalize_hex(value: str, flag: str) -> str:
    v = parse_hex(value)
    if v is None:
        sys.exit(f"{flag}: '{value}' is not a #RRGGBB color")
    return v


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


# --------------------------------------------------------------------------- layout
DEFAULT_LAYOUT = {
    "offset": [0.0, 0.0],
    "favicon_fill": 0.84,
    "favicon_corner_radius": 0.20,
    "avatar_fill": 0.6,
    "avatar_offset": [0.0, 0.0],
}

LAYOUT_DOC = {
    "offset": "Where the wing sits, as [x, y] in canvas units from centered (+x right, +y down). "
              "The same offset applies in the logo canvas and in the favicon. [0, 0] = centered in both.",
    "favicon_fill": "Share of the favicon side taken by the wing's width (0-1). The rest is the safe "
                    "area that keeps it clear of the rounded corners.",
    "favicon_corner_radius": "Rounded corners of the favicon, as a fraction of the side. 0 = square.",
    "avatar_fill": "Share of the profile picture's side taken by the wing's width (0-1). The networks "
                   "crop it to a circle, so the wing needs air inside it: past 80% of the radius the build warns.",
    "avatar_offset": "Where the wing sits in the profile picture, as [x, y] in canvas units from centered, "
                     "like offset. Its own: moving it does not touch the logo or the favicon.",
}


def validate_layout(data: dict) -> tuple[dict, list[str]]:
    """Coerce a raw dict into a layout, collecting problems instead of raising.

    Always called before anything is written, so a bad value can never end up
    in layout.json and block later runs.
    """
    layout = dict(DEFAULT_LAYOUT)
    errors: list[str] = []
    data = dict(data)
    if "offset" not in data and isinstance(data.get("logo_offset"), (list, tuple)) and len(data["logo_offset"]) == 2:
        # legacy layout.json: logo_offset was measured from the reference position,
        # and the favicon had its own nudge. Keep the logo where it was; the favicon follows.
        lo, c = data["logo_offset"], centering_shift()
        try:
            data["offset"] = [round(float(lo[0]) - c[0], 2), round(float(lo[1]) - c[1], 2)]
        except (TypeError, ValueError):
            pass
    for key in DEFAULT_LAYOUT:
        if key not in data:
            continue
        value = data[key]
        if key in ("offset", "avatar_offset"):
            if not (isinstance(value, (list, tuple)) and len(value) == 2
                    and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
                errors.append(f"'{key}' must be a list of two numbers, got {value!r}")
                continue
            layout[key] = [float(value[0]), float(value[1])]
        else:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"'{key}' must be a number, got {value!r}")
                continue
            layout[key] = float(value)
    if not 0.05 <= layout["favicon_fill"] <= 1.0:
        errors.append(f"'favicon_fill' must be between 0.05 and 1.0, got {layout['favicon_fill']}")
    if not 0.0 <= layout["favicon_corner_radius"] <= 0.5:
        errors.append(f"'favicon_corner_radius' must be between 0 and 0.5, got {layout['favicon_corner_radius']}")
    if not 0.05 <= layout["avatar_fill"] <= 1.0:
        errors.append(f"'avatar_fill' must be between 0.05 and 1.0, got {layout['avatar_fill']}")
    return layout, errors


def read_layout(path: Path = LAYOUT_JSON) -> dict:
    """Read layout.json, creating it with the defaults if it is missing."""
    if not path.exists():
        write_layout(dict(DEFAULT_LAYOUT), path)
        return dict(DEFAULT_LAYOUT)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{path}: invalid JSON ({exc})")
    if not isinstance(data, dict):
        sys.exit(f"{path}: expected a JSON object")
    layout, errors = validate_layout(data)
    if errors:
        sys.exit("\n".join(f"{path}: {e}" for e in errors)
                 + f"\nDelete {path.name} to regenerate it with the defaults.")
    if "offset" not in data:
        write_layout(layout, path)  # rewrite a legacy file in the current format
    return layout


def write_layout(layout: dict, path: Path = LAYOUT_JSON) -> dict:
    """Write layout.json with an inline `_readme` so the file explains itself."""
    body = {"_readme": LAYOUT_DOC}
    body.update({k: layout[k] for k in DEFAULT_LAYOUT})
    text = json.dumps(body, indent=2, ensure_ascii=False)
    # keep the [x, y] pairs on one line: easier to read and to edit by hand
    text = re.sub(r"\[\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\]", r"[\1, \2]", text)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return layout


def centering_shift() -> tuple[float, float]:
    """Translation that centers wing + shadow in the logo canvas (from the reference position)."""
    cx = (BBOX[0] + BBOX[2]) / 2
    cy = (BBOX[1] + BBOX[3]) / 2
    return (round(CANVAS[0] / 2 - cx, 2), round(CANVAS[1] / 2 - cy, 2))


def original_offset() -> tuple[float, float]:
    """The offset that puts the wing exactly where the reference image has it."""
    c = centering_shift()
    return (-c[0], -c[1])


def logo_shift(layout: dict) -> tuple[float, float]:
    """Where the wing goes in the logo canvas: centered, plus the configured offset."""
    c = centering_shift()
    return (c[0] + layout["offset"][0], c[1] + layout["offset"][1])


def content_bbox(layout: dict) -> tuple[float, float, float, float]:
    dx, dy = logo_shift(layout)
    return (BBOX[0] + dx, BBOX[1] + dy, BBOX[2] + dx, BBOX[3] + dy)


def favicon_canvas(layout: dict) -> float:
    return float(round(BBOX_SIZE[0] / layout["favicon_fill"]))


def favicon_radius(layout: dict, side: float | None = None) -> float:
    return (favicon_canvas(layout) if side is None else side) * layout["favicon_corner_radius"]


def favicon_shift(layout: dict, with_offset: bool = True) -> tuple[float, float]:
    """Where the wing goes in the favicon canvas: centered, plus the same configured offset."""
    c = favicon_canvas(layout)
    sx = -BBOX[0] + (c - BBOX_SIZE[0]) / 2
    sy = -BBOX[1] + (c - BBOX_SIZE[1]) / 2
    if with_offset:
        sx += layout["offset"][0]
        sy += layout["offset"][1]
    return (sx, sy)


def favicon_shadow_scale(px: int) -> float:
    """How much to widen the shadow offset at a given raster size (1.0 = exact geometry)."""
    return FAVICON_SHADOW_SCALE.get(px, 1.0)


def avatar_canvas(layout: dict) -> float:
    return BBOX_SIZE[0] / layout["avatar_fill"]


def avatar_shift(layout: dict) -> tuple[float, float]:
    """Where the wing goes in the profile picture: centered, plus its own offset."""
    c = avatar_canvas(layout)
    return (-BBOX[0] + (c - BBOX_SIZE[0]) / 2 + layout["avatar_offset"][0],
            -BBOX[1] + (c - BBOX_SIZE[1]) / 2 + layout["avatar_offset"][1])


# --------------------------------------------------------------------------- path data
def _fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def outline(top_lift: float = 0.0):
    """(start, pieces) of the wing, with the straight top edge pushed outwards by top_lift units.

    Only the two ends of the top edge and the handle that leaves it move, so the
    rest of the outline (feathers, bottom, right side) stays identical.
    """
    if not top_lift:
        return START, PIECES
    (sx, sy), (lx, ly) = START, PIECES[0][1]
    tx, ty = lx - sx, ly - sy
    length = float(np.hypot(tx, ty))
    dx, dy = ty / length * top_lift, -tx / length * top_lift  # unit normal pointing up
    pieces = list(PIECES)
    pieces[0] = ("L", (lx + dx, ly + dy))
    c = PIECES[1][1]
    pieces[1] = ("C", (c[0] + dx, c[1] + dy) + tuple(c[2:]))
    return (sx + dx, sy + dy), pieces


def path_d(shift=(0.0, 0.0), scale: float = 1.0, top_lift: float = 0.0) -> str:
    """SVG path data of the wing, optionally shifted (before scaling) and scaled."""
    def tr(x, y):
        return _fmt((x + shift[0]) * scale), _fmt((y + shift[1]) * scale)

    start, pieces = outline(top_lift)
    out = ["M%s %s" % tr(*start)]
    for kind, c in pieces:
        if kind == "L":
            out.append("L%s %s" % tr(*c))
        else:
            out.append("C%s %s %s %s %s %s" % (*tr(c[0], c[1]), *tr(c[2], c[3]), *tr(c[4], c[5])))
    out.append("Z")
    return " ".join(out)


def wing_group(logo_fill: str, shadow_fill: str, shift=(0.0, 0.0), scale: float = 1.0,
               shadow_scale: float = 1.0, indent: str = "  ", style: str = "") -> str:
    d = path_d(shift, scale)
    d_shadow = path_d(shift, scale, top_lift=SHADOW_TOP_LIFT * shadow_scale)
    dx, dy = SHADOW_OFFSET[0] * scale * shadow_scale, SHADOW_OFFSET[1] * scale * shadow_scale
    attrs = f" style=\"{style}\"" if style else ""
    return (
        f"{indent}<g class=\"wing\"{attrs}>\n"
        f"{indent}  <!-- shadow: the wing outline with a thicker top edge, offset left and up -->\n"
        f"{indent}  <path class=\"wing-shadow\" fill=\"{shadow_fill}\" transform=\"translate({_fmt(dx)} {_fmt(dy)})\" d=\"{d_shadow}\"/>\n"
        f"{indent}  <path class=\"wing-fill\" fill=\"{logo_fill}\" d=\"{d}\"/>\n"
        f"{indent}</g>\n"
    )


GENERATED_NOTE = "<!-- Generated by brand/build_logo.py from brand/colors.css + brand/layout.json. Edit those, not this. -->\n"


def svg_logo(colors: dict[str, str], layout: dict) -> str:
    w, h = CANVAS
    return (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" height=\"{h}\" role=\"img\" aria-labelledby=\"title\">\n"
        f"  <title id=\"title\">Sobreala</title>\n"
        f"  {GENERATED_NOTE}"
        f"  <rect width=\"{w}\" height=\"{h}\" fill=\"{colors['color-background']}\"/>\n"
        + wing_group(colors["color-logo"], colors["color-shadow"], shift=logo_shift(layout))
        + "</svg>\n"
    )


def symbol_shift() -> tuple[float, float]:
    return (-(BBOX[0] - SYMBOL_MARGIN), -(BBOX[1] - SYMBOL_MARGIN))


def svg_symbol(colors: dict[str, str]) -> str:
    """Wing on transparent background, cropped tight: placement offsets do not apply."""
    w, h = SYMBOL_SIZE
    return (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" height=\"{h}\" role=\"img\" aria-labelledby=\"title\">\n"
        f"  <title id=\"title\">Sobreala</title>\n"
        f"  {GENERATED_NOTE}"
        + wing_group(colors["color-logo"], colors["color-shadow"], shift=symbol_shift())
        + "</svg>\n"
    )


def svg_favicon(colors: dict[str, str], layout: dict, logo_fill: str | None = None,
                shadow_fill: str | None = None, bg_fill: str | None = None,
                shadow_scale: float = FAVICON_SVG_SHADOW_SCALE, clip_id: str = "pmRound",
                note: bool = True, rounded: bool = True, wing_style: str = "",
                with_offset: bool = True) -> str:
    c = _fmt(favicon_canvas(layout))
    r = _fmt(favicon_radius(layout) if rounded else 0.0)
    bg = bg_fill or colors["color-background"]
    return (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {c} {c}\" width=\"{c}\" height=\"{c}\">\n"
        + (f"  {GENERATED_NOTE}" if note else "")
        + f"  <defs><clipPath id=\"{clip_id}\"><rect width=\"{c}\" height=\"{c}\" rx=\"{r}\" ry=\"{r}\"/></clipPath></defs>\n"
        f"  <g clip-path=\"url(#{clip_id})\">\n"
        f"    <rect class=\"bg\" width=\"{c}\" height=\"{c}\" fill=\"{bg}\"/>\n"
        + wing_group(logo_fill or colors["color-logo"], shadow_fill or colors["color-shadow"],
                     shift=favicon_shift(layout, with_offset), shadow_scale=shadow_scale,
                     indent="    ", style=wing_style)
        + "  </g>\n"
        "</svg>\n"
    )


# --------------------------------------------------------------------------- rasterizer
def _bezier(p0, p1, p2, p3, n: int) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n, endpoint=False)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * (t ** 2) * p2 + (t ** 3) * p3


def wing_polygon(shift=(0.0, 0.0), scale: float = 1.0, samples_per_unit: float = 2.0,
                 top_lift: float = 0.0) -> np.ndarray:
    """Flatten the wing outline into a dense polygon (in output pixels)."""
    start, pieces = outline(top_lift)
    pts = []
    cur = np.array(start, float)
    for kind, c in pieces:
        if kind == "L":
            end = np.array(c, float)
            pts.append(cur[None, :])
        else:
            p1, p2, end = np.array(c[0:2]), np.array(c[2:4]), np.array(c[4:6])
            approx_len = np.linalg.norm(p1 - cur) + np.linalg.norm(p2 - p1) + np.linalg.norm(end - p2)
            n = max(8, int(approx_len * samples_per_unit * max(scale, 1.0)))
            pts.append(_bezier(cur, p1, p2, end, n))
        cur = end
    poly = np.concatenate(pts)
    return (poly + np.array(shift)) * scale


def rasterize(size: tuple[int, int], layers, background=None, ss: int = 8) -> Image.Image:
    """Supersampled area-coverage rendering.

    layers: list of (polygon Nx2 in output pixels, (r, g, b)), painted in order.
    background: (r, g, b) or None for a transparent canvas.
    """
    w, h = size
    if background is None:
        rgb = np.zeros((h, w, 3), float)
        alpha = np.zeros((h, w), float)
    else:
        rgb = np.ones((h, w, 3), float) * np.array(background, float)
        alpha = np.ones((h, w), float)
    for poly, color in layers:
        mask = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(mask).polygon([tuple(v) for v in poly * ss], fill=255)
        cov = (np.asarray(mask, dtype=np.float32) / 255.0).reshape(h, ss, w, ss).mean(axis=(1, 3))
        color = np.array(color, float)
        # premultiplied "over" compositing
        rgb = rgb * alpha[..., None] * (1 - cov[..., None]) + color * cov[..., None]
        alpha = alpha * (1 - cov) + cov
        rgb = np.where(alpha[..., None] > 0, rgb / np.maximum(alpha[..., None], 1e-9), 0)
    out = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).round().astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def rounded_mask(px: int, radius_px: float, ss: int = 16) -> np.ndarray:
    """Antialiased coverage mask of a rounded square filling a px x px canvas."""
    img = Image.new("L", (px * ss, px * ss), 0)
    ImageDraw.Draw(img).rounded_rectangle([0, 0, px * ss - 1, px * ss - 1], radius=radius_px * ss, fill=255)
    return (np.asarray(img, dtype=np.float32) / 255.0).reshape(px, ss, px, ss).mean(axis=(1, 3))


def apply_mask(im: Image.Image, mask: np.ndarray) -> Image.Image:
    a = np.asarray(im).astype(np.float32)
    a[..., 3] = a[..., 3] * mask
    return Image.fromarray(a.round().clip(0, 255).astype(np.uint8), "RGBA")


def render_composition(colors: dict[str, str], scale: float, shift=(0.0, 0.0), size=None,
                       background=True, ss: int = 8, shadow_scale: float = 1.0) -> Image.Image:
    if size is None:
        size = (round(CANVAS[0] * scale), round(CANVAS[1] * scale))
    shadow_shift = (shift[0] + SHADOW_OFFSET[0] * shadow_scale, shift[1] + SHADOW_OFFSET[1] * shadow_scale)
    layers = [
        (wing_polygon(shadow_shift, scale, top_lift=SHADOW_TOP_LIFT * shadow_scale), hex_to_rgb(colors["color-shadow"])),
        (wing_polygon(shift, scale), hex_to_rgb(colors["color-logo"])),
    ]
    bg = hex_to_rgb(colors["color-background"]) if background else None
    return rasterize(size, layers, bg, ss)


def render_favicon(colors: dict[str, str], layout: dict, px: int, rounded: bool = True) -> Image.Image:
    c = favicon_canvas(layout)
    scale = px / c
    im = render_composition(colors, scale, shift=favicon_shift(layout), size=(px, px),
                            ss=16 if px <= 64 else 8, shadow_scale=favicon_shadow_scale(px))
    if rounded and layout["favicon_corner_radius"] > 0:
        im = apply_mask(im, rounded_mask(px, favicon_radius(layout, px)))
    return im


def render_avatar(colors: dict[str, str], layout: dict, px: int = AVATAR_SIZE) -> Image.Image:
    """The profile picture: the wing alone on the background, like the favicon.

    Square and opaque on purpose: each network applies its own mask (a circle
    almost everywhere, a square in LinkedIn), and a transparent corner comes out
    black or white depending on the app. Without the word: at the size a profile
    picture is shown, it would not read.
    """
    return render_composition(colors, px / avatar_canvas(layout), shift=avatar_shift(layout),
                              size=(px, px)).convert("RGB")


# --------------------------------------------------------------------------- checks
def check_placement(layout: dict) -> list[str]:
    """Warn when the current offsets push content out of frame or into the corners."""
    warnings = []
    x0, y0, x1, y1 = content_bbox(layout)
    over = []
    if x0 < 0: over.append(f"{-x0:.1f} por la izquierda")
    if y0 < 0: over.append(f"{-y0:.1f} por arriba")
    if x1 > CANVAS[0]: over.append(f"{x1 - CANVAS[0]:.1f} por la derecha")
    if y1 > CANVAS[1]: over.append(f"{y1 - CANVAS[1]:.1f} por abajo")
    if over:
        warnings.append("el logo se sale del lienzo: " + ", ".join(over) + " (unidades)")

    c = favicon_canvas(layout)
    r = favicon_radius(layout)
    sx, sy = favicon_shift(layout)
    pts = np.concatenate([wing_polygon((sx, sy)),
                          wing_polygon((sx + SHADOW_OFFSET[0], sy + SHADOW_OFFSET[1]), top_lift=SHADOW_TOP_LIFT)])
    cx = np.clip(pts[:, 0], r, c - r)
    cy = np.clip(pts[:, 1], r, c - r)
    clipped = int((np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) > r + 1e-9).sum())
    if clipped:
        warnings.append(f"el favicon recorta el ala en {clipped} puntos: baja favicon_fill o favicon_corner_radius")

    c = avatar_canvas(layout)
    sx, sy = avatar_shift(layout)
    pts = np.concatenate([wing_polygon((sx, sy)),
                          wing_polygon((sx + SHADOW_OFFSET[0], sy + SHADOW_OFFSET[1]), top_lift=SHADOW_TOP_LIFT)])
    reach = float(np.hypot(pts[:, 0] - c / 2, pts[:, 1] - c / 2).max()) / (c / 2)
    if reach > AVATAR_SAFE:
        warnings.append(f"en el perfil el ala llega al {reach:.0%} del radio del circulo, mas del "
                        f"{AVATAR_SAFE:.0%}: al recortarla en redondo queda pegada al borde. Baja avatar_fill "
                        "o acerca el ala al centro (avatar_offset)")
    return warnings


# --------------------------------------------------------------------------- color + position editor
PREVIEW_TEMPLATE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sobreala · colores y posición</title>
<!-- resolves to brand/favicon/ when opened as a file, and to /favicon/ when served -->
<link rel="icon" href="../favicon/favicon.svg" type="image/svg+xml">
<link rel="icon" href="../favicon/favicon.ico" sizes="32x32">
<!-- Generated by brand/build_logo.py. Nothing here is a source of truth: it is a
     scratchpad. The chosen values go into brand/colors.css and brand/layout.json. -->
<style>
  :root {
    --color-background: __BG__;
    --color-logo: __LOGO__;
    --color-shadow: __SHADOW__;
    --logo-x: __LX__px; --logo-y: __LY__px;
    --ui-bg: #12151a; --ui-panel: #1b2027; --ui-line: #2c333d;
    --ui-text: #e7eaee; --ui-dim: #98a2b0; --ui-accent: #6aa9e0;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 28px 20px 56px;
    background: var(--ui-bg); color: var(--ui-text);
    font: 15px/1.55 ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--ui-dim); margin: 0 0 26px; font-size: 14px; }
  .grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(300px, 1fr); gap: 22px; align-items: start; }
  @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
  .panel { background: var(--ui-panel); border: 1px solid var(--ui-line); border-radius: 12px; padding: 18px; }
  .panel + .panel { margin-top: 18px; }
  .panel h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ui-dim); margin: 0 0 14px; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
  .stage { position: relative; border-radius: 8px; overflow: hidden; }
  .stage svg { display: block; width: 100%; height: auto; }
  .stage .ovl { position: absolute; inset: 0; pointer-events: none; opacity: 0; transition: opacity .12s; }
  .stage.show-grid .ovl { opacity: 1; }
  .wing { transform: translate(var(--logo-x), var(--logo-y)); }
  /* CSS rules beat presentation attributes, so the colors update live even in
     browsers that do not resolve var() inside a fill="" attribute. */
  .bg { fill: var(--color-background); }
  .wing-fill { fill: var(--color-logo); }
  .wing-shadow { fill: var(--color-shadow); }
  .icons { display: flex; align-items: flex-end; gap: 26px; flex-wrap: wrap; }
  .icon b { display: block; font-size: 11px; color: var(--ui-dim); font-weight: 500; margin-top: 8px; text-align: center; }
  .icon svg { display: block; }
  /* The profile picture: one big circle to adjust it, dragging the wing, and
     the small circles it is seen at. Its wing moves with its own variables. */
  .avatar-stage {
    width: 300px; max-width: 100%; margin: 0 auto; border-radius: 50%;
    cursor: grab; touch-action: none;
  }
  .avatar-stage.dragging { cursor: grabbing; }
  .avatar-stage:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
  .avatar-stage svg { width: 100%; height: auto; }
  .avatar { display: block; }
  .avatar.round { border-radius: 50%; }
  .avatar .wing { transform: translate(var(--av-x), var(--av-y)); }
  .avatar .safe { display: none; }
  .show-safe .avatar .safe { display: inline; }
  .tab {
    display: inline-flex; align-items: center; gap: 8px; margin-top: 18px;
    background: #2b3038; border-radius: 9px 9px 0 0; padding: 8px 34px 8px 11px;
    font-size: 12.5px; color: #dfe4ea; border: 1px solid var(--ui-line); border-bottom: none;
  }
  .field { margin-bottom: 16px; }
  .field:last-child { margin-bottom: 0; }
  .field label { display: block; font-size: 12.5px; color: var(--ui-dim); margin-bottom: 6px; }
  .row { display: flex; gap: 8px; align-items: center; }
  input[type=color] {
    width: 46px; height: 36px; padding: 0; border: 1px solid var(--ui-line);
    border-radius: 8px; background: none; cursor: pointer; flex: none;
  }
  input[type=text], input[type=number] {
    flex: 1; min-width: 0; height: 36px; padding: 0 10px; border-radius: 8px;
    border: 1px solid var(--ui-line); background: #10141a; color: var(--ui-text);
    font: 13px ui-monospace, SFMono-Regular, Consolas, monospace;
  }
  input[type=text] { text-transform: uppercase; }
  input[type=number] { width: 78px; flex: none; }
  input:focus { outline: 2px solid var(--ui-accent); outline-offset: -1px; }
  input[type=range] { flex: 1; min-width: 0; accent-color: var(--ui-accent); }
  .axis-tag { display: inline-block; width: 14px; color: var(--ui-dim); font: 12px ui-monospace, Consolas, monospace; }
  .swatches { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
  .swatches button { width: 30px; height: 30px; border-radius: 7px; border: 1px solid rgba(255,255,255,.18); cursor: pointer; padding: 0; }
  .swatches button[aria-pressed="true"] { outline: 2px solid #e7eaee; outline-offset: 2px; }
  pre {
    background: #10141a; border: 1px solid var(--ui-line); border-radius: 8px;
    padding: 12px; overflow-x: auto; margin: 0; white-space: pre-wrap; word-break: break-all;
    font: 12.5px/1.6 ui-monospace, SFMono-Regular, Consolas, monospace; color: #cfd6de;
  }
  .actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .btn { border: 1px solid var(--ui-line); background: #232932; color: var(--ui-text); border-radius: 8px; padding: 8px 12px; font-size: 13px; cursor: pointer; }
  .btn:hover { background: #2b323c; }
  .btn.sm { padding: 5px 9px; font-size: 12px; }
  .btn.primary { background: #2f6ea8; border-color: #3d80bd; }
  .btn.primary:hover { background: #377cbb; }
  .btn[disabled] { opacity: .55; cursor: default; }
  .status { font-size: 12.5px; margin: 10px 0 0; min-height: 1em; }
  .status.ok { color: #7fd18f; }
  .status.err { color: #f08a7a; }
  .status.busy { color: var(--ui-dim); }
  .note { color: var(--ui-dim); font-size: 12.5px; margin: 12px 0 0; }
  .readout { color: var(--ui-dim); font: 12px ui-monospace, Consolas, monospace; margin-top: 10px; }
  .readout b { color: var(--ui-text); font-weight: 600; }
  .warn { color: #f0b46a; font-size: 12.5px; margin-top: 10px; min-height: 1px; }
  code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: #cfd6de; }
  .switch { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ui-dim); text-transform: none; letter-spacing: 0; font-weight: 400; cursor: pointer; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Colores y posición · Sobreala</h1>
  <p class="sub" id="sub"></p>

  <div class="grid">
    <div>
      <div class="panel">
        <h2>Logo
          <label class="switch"><input type="checkbox" id="toggle-grid" checked> eje de referencia</label>
        </h2>
        <div class="stage show-grid" id="stage">
          __LOGO_SVG__
          <div class="ovl">__GRID_SVG__</div>
        </div>
        <p class="readout" id="readout"></p>
        <p class="warn" id="warn"></p>
      </div>

      <div class="panel">
        <h2>Favicon</h2>
        <div class="icons">
          <div class="icon">__FAV_16__<b>16 px</b></div>
          <div class="icon">__FAV_32__<b>32 px</b></div>
          <div class="icon">__FAV_48__<b>48 px</b></div>
          <div class="icon">__FAV_180__<b>180 px · apple&#8209;touch</b></div>
        </div>
        <div class="tab">__FAV_TAB__ <span>Sobreala</span></div>
        <p class="note">El de 180 px va cuadrado a propósito: iOS le aplica su propio redondeo y las esquinas transparentes saldrían negras.</p>
      </div>

      <div class="panel show-safe" id="avatar-panel">
        <h2>Foto de perfil para redes
          <label class="switch"><input type="checkbox" id="toggle-safe" checked> zona segura</label>
        </h2>
        <div class="avatar-stage" id="avatar-stage" tabindex="0" role="group"
             aria-label="Foto de perfil: arrastra el ala para moverla">__AV_STAGE__</div>
        <p class="note" style="text-align:center">Arrastra el ala para moverla. Con el círculo seleccionado, las flechas también la mueven (Mayús: pasos de 5).</p>
        <div class="icons" style="margin-top:18px">
          <div class="icon">__AV_110__<b>110 px · perfil</b></div>
          <div class="icon">__AV_56__<b>56 px · publicaciones</b></div>
          <div class="icon">__AV_32__<b>32 px · comentarios</b></div>
        </div>
        <div class="field" style="margin-top:18px">
          <label for="num-af">Tamaño del ala <span style="opacity:.7">(% del ancho de la foto)</span></label>
          <div class="row">
            <input type="number" id="num-af" min="30" max="95" step="1" data-av>
            <input type="range" id="rng-af" min="30" max="95" step="1" data-av>
          </div>
        </div>
        <div class="field">
          <label for="num-ax">Horizontal · X <span style="opacity:.7">(+ derecha)</span></label>
          <div class="row">
            <input type="number" id="num-ax" step="0.5" data-avpos="ax">
            <input type="range" id="rng-ax" min="-120" max="120" step="0.5" data-avpos="ax">
          </div>
        </div>
        <div class="field">
          <label for="num-ay">Vertical · Y <span style="opacity:.7">(+ abajo)</span></label>
          <div class="row">
            <input type="number" id="num-ay" step="0.5" data-avpos="ay">
            <input type="range" id="rng-ay" min="-120" max="120" step="0.5" data-avpos="ay">
          </div>
        </div>
        <div class="actions"><button class="btn sm" id="btn-av-center" type="button">Centrar en el círculo</button></div>
        <p class="readout" id="av-readout"></p>
        <p class="warn" id="av-warn"></p>
        <p class="note">Se guarda en <code>brand/perfil/perfil-1080.png</code>: cuadrada, de 1080 px y la misma para todas las redes. Las redes la recortan en círculo. La línea punteada es el __AV_SAFE__ % del radio: con el ala dentro, ninguna red la corta. Su posición es solo suya: no mueve el logo ni el favicon.</p>
      </div>
    </div>

    <div>
      <div class="panel">
        <h2>Posición</h2>
        <p class="note" style="margin-top:0">Mueve el ala igual en el logo y en el favicon. <b>0, 0</b> es centrada en los dos.</p>
        <div class="field">
          <label for="num-lx">Horizontal · X <span style="opacity:.7">(+ derecha)</span></label>
          <div class="row">
            <input type="number" id="num-lx" step="0.5" data-pos="lx">
            <input type="range" id="rng-lx" min="-140" max="140" step="0.5" data-pos="lx">
          </div>
        </div>
        <div class="field">
          <label for="num-ly">Vertical · Y <span style="opacity:.7">(+ abajo)</span></label>
          <div class="row">
            <input type="number" id="num-ly" step="0.5" data-pos="ly">
            <input type="range" id="rng-ly" min="-140" max="140" step="0.5" data-pos="ly">
          </div>
        </div>
        <div class="actions">
          <button class="btn sm" id="btn-center" type="button">Centrar</button>
          <button class="btn sm" id="btn-origin" type="button">Como el original</button>
        </div>
      </div>

      <div class="panel">
        <h2>Colores</h2>
        <div class="field">
          <label for="pick-background">Fondo</label>
          <div class="row">
            <input type="color" id="pick-background" data-var="color-background">
            <input type="text" id="hex-background" data-var="color-background" spellcheck="false" maxlength="7">
          </div>
          <div class="swatches" id="swatches"></div>
        </div>
        <div class="field">
          <label for="pick-logo">Logo</label>
          <div class="row">
            <input type="color" id="pick-logo" data-var="color-logo">
            <input type="text" id="hex-logo" data-var="color-logo" spellcheck="false" maxlength="7">
          </div>
        </div>
        <div class="field">
          <label for="pick-shadow">Sombras</label>
          <div class="row">
            <input type="color" id="pick-shadow" data-var="color-shadow">
            <input type="text" id="hex-shadow" data-var="color-shadow" spellcheck="false" maxlength="7">
          </div>
        </div>
      </div>

      <div class="panel">
        <h2>Aplicar</h2>
        <div id="save-box" hidden>
          <div class="actions" style="margin-top:0">
            <button class="btn primary" id="btn-save" type="button">Guardar y regenerar</button>
            <button class="btn" id="reset" type="button">Descartar cambios</button>
          </div>
          <p class="status" id="save-status"></p>
          <p class="note">Escribe los valores en <code>colors.css</code> y <code>layout.json</code> y regenera SVG, PNG e ICO al momento.</p>
        </div>
        <div id="cmd-box">
          <pre id="cmd"></pre>
          <div class="actions">
            <button class="btn" id="copy-cmd" type="button">Copiar comando</button>
            <button class="btn" id="reset-2" type="button">Restablecer todo</button>
          </div>
          <p class="note">Para guardar desde aquí con un botón, cierra esta pestaña y abre la página con
            <code>python brand/build_logo.py --serve</code>.</p>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
  const DEFAULTS = {
    "color-background": "__BG__", "color-logo": "__LOGO__", "color-shadow": "__SHADOW__",
    lx: __LX__, ly: __LY__, af: __AF__, ax: __AX__, ay: __AY__
  };
  const PRESETS = __PRESETS__;
  const CANVAS = __CANVAS__;             // [w, h] of the logo canvas
  const BBOX = __BBOX__;                 // wing + shadow bbox at offset (0, 0)
  const CENTER = __CENTER__;             // translation that centers it in the logo canvas
  const ORIGINAL = __ORIGINAL__;         // offset that matches the reference image
  // The profile picture: the centre of the wing's frame, its width, the safe
  // share of the circle's radius, and the outline of wing + shadow at offset 0.
  const AVATAR = __AVATAR__;
  const COLOR_KEYS = ["color-background", "color-logo", "color-shadow"];
  const POS_KEYS = ["lx", "ly"];
  const root = document.documentElement;
  const state = Object.assign({}, DEFAULTS);

  function normalize(v) {
    v = (v || "").trim();
    if (v && v[0] !== "#") v = "#" + v;
    if (/^#[0-9a-fA-F]{3}$/.test(v)) v = "#" + v.slice(1).split("").map(c => c + c).join("");
    return /^#[0-9a-fA-F]{6}$/.test(v) ? v.toUpperCase() : null;
  }
  const round2 = n => Math.round(n * 100) / 100;
  const fmt = n => String(round2(n));

  function render() {
    COLOR_KEYS.forEach(key => {
      root.style.setProperty("--" + key, state[key]);
      const short = key.replace("color-", "");
      const p = document.getElementById("pick-" + short);
      const h = document.getElementById("hex-" + short);
      if (p) p.value = state[key].toLowerCase();
      if (h && normalize(h.value) !== state[key]) h.value = state[key];
    });
    root.style.setProperty("--logo-x", state.lx + "px");
    root.style.setProperty("--logo-y", state.ly + "px");
    POS_KEYS.forEach(k => {
      const n = document.getElementById("num-" + k), r = document.getElementById("rng-" + k);
      if (n && document.activeElement !== n) n.value = fmt(state[k]);
      if (r) r.value = state[k];
    });
    document.querySelectorAll("#swatches button").forEach(b => {
      b.setAttribute("aria-pressed", String(b.dataset.hex === state["color-background"]));
    });

    const dx = CENTER[0] + state.lx, dy = CENTER[1] + state.ly;
    const x0 = BBOX[0] + dx, y0 = BBOX[1] + dy;
    const x1 = BBOX[2] + dx, y1 = BBOX[3] + dy;
    document.getElementById("readout").innerHTML =
      "borde: izq <b>" + fmt(x0) + "</b> · der <b>" + fmt(CANVAS[0] - x1) +
      "</b> · arriba <b>" + fmt(y0) + "</b> · abajo <b>" + fmt(CANVAS[1] - y1) +
      "</b> &nbsp;|&nbsp; centro <b>" + fmt((x0 + x1) / 2) + ", " + fmt((y0 + y1) / 2) + "</b>";
    const out = [];
    if (x0 < 0) out.push(fmt(-x0) + " por la izquierda");
    if (y0 < 0) out.push(fmt(-y0) + " por arriba");
    if (x1 > CANVAS[0]) out.push(fmt(x1 - CANVAS[0]) + " por la derecha");
    if (y1 > CANVAS[1]) out.push(fmt(y1 - CANVAS[1]) + " por abajo");
    document.getElementById("warn").textContent = out.length ? "Se sale del lienzo: " + out.join(", ") : "";

    // The profile picture: the viewBox frames the wing at the chosen size, the
    // way render_avatar() does, and its own offset (--av-x, --av-y) moves it.
    root.style.setProperty("--av-x", state.ax + "px");
    root.style.setProperty("--av-y", state.ay + "px");
    ["ax", "ay"].forEach(k => {
      const n = document.getElementById("num-" + k), r = document.getElementById("rng-" + k);
      if (n && document.activeElement !== n) n.value = fmt(state[k]);
      if (r) r.value = state[k];
    });
    const side = AVATAR.width / state.af;
    const acx = AVATAR.center[0], acy = AVATAR.center[1];
    const box = [acx - side / 2, acy - side / 2, side, side].map(fmt).join(" ");
    document.querySelectorAll("svg[data-avatar]").forEach(el => el.setAttribute("viewBox", box));
    document.querySelectorAll("svg[data-avatar] .safe").forEach(el => el.setAttribute("r", fmt(AVATAR.safe * side / 2)));
    let reach = 0;
    AVATAR.points.forEach(pt => {
      reach = Math.max(reach, Math.hypot(pt[0] + state.ax - acx, pt[1] + state.ay - acy));
    });
    reach = reach / (side / 2);
    const pct = Math.round(state.af * 100);
    const nAf = document.getElementById("num-af"), rAf = document.getElementById("rng-af");
    if (nAf && document.activeElement !== nAf) nAf.value = pct;
    if (rAf) rAf.value = pct;
    document.getElementById("av-readout").innerHTML =
      "el ala ocupa el <b>" + pct + " %</b> del ancho y llega al <b>" + Math.round(reach * 100) +
      " %</b> del radio del círculo";
    document.getElementById("av-warn").textContent = reach > AVATAR.safe
      ? "Pasa del " + Math.round(AVATAR.safe * 100) + " %: al recortarla en redondo queda pegada al borde."
      : "";

    const flags = [];
    COLOR_KEYS.forEach(key => {
      if (state[key] !== DEFAULTS[key]) flags.push("--" + key.replace("color-", "") + ' "' + state[key] + '"');
    });
    if (state.lx !== DEFAULTS.lx) flags.push("--x " + fmt(state.lx));
    if (state.ly !== DEFAULTS.ly) flags.push("--y " + fmt(state.ly));
    if (state.af !== DEFAULTS.af) flags.push("--avatar-fill " + state.af);
    if (state.ax !== DEFAULTS.ax) flags.push("--avatar-x " + fmt(state.ax));
    if (state.ay !== DEFAULTS.ay) flags.push("--avatar-y " + fmt(state.ay));
    document.getElementById("cmd").textContent = flags.length
      ? "python brand/build_logo.py " + flags.join(" ")
      : "python brand/build_logo.py\n\n# (sin cambios respecto a la configuración actual)";
  }

  function setColor(key, value) { const v = normalize(value); if (v) { state[key] = v; render(); } }
  function setPos(key, value) {
    const n = parseFloat(value);
    if (!isNaN(n)) { state[key] = round2(n); render(); }
  }

  document.querySelectorAll("input[data-var]").forEach(el => {
    el.addEventListener("input", () => setColor(el.dataset.var, el.value));
    el.addEventListener("change", () => { el.value = state[el.dataset.var]; render(); });
  });
  document.querySelectorAll("input[data-pos]").forEach(el => {
    el.addEventListener("input", () => setPos(el.dataset.pos, el.value));
    el.addEventListener("blur", () => render());
  });
  document.querySelectorAll("input[data-av]").forEach(el => {
    el.addEventListener("input", () => {
      const n = parseFloat(el.value);
      if (!isNaN(n) && n >= 5 && n <= 100) { state.af = Math.round(n * 100) / 10000; render(); }
    });
    el.addEventListener("blur", () => render());
  });
  document.getElementById("toggle-safe").addEventListener("change", e => {
    document.getElementById("avatar-panel").classList.toggle("show-safe", e.target.checked);
  });
  document.querySelectorAll("input[data-avpos]").forEach(el => {
    el.addEventListener("input", () => setPos(el.dataset.avpos, el.value));
    el.addEventListener("blur", () => render());
  });
  document.getElementById("btn-av-center").addEventListener("click", () => {
    state.ax = 0; state.ay = 0; render();
  });

  // Dragging the wing inside the circle: the pointer's travel in screen
  // pixels, turned into canvas units by the size the circle is drawn at.
  const stageEl = document.getElementById("avatar-stage");
  let drag = null;
  stageEl.addEventListener("pointerdown", e => {
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY, ax: state.ax, ay: state.ay };
    stageEl.setPointerCapture(e.pointerId);
    stageEl.classList.add("dragging");
    stageEl.focus();
    e.preventDefault();
  });
  stageEl.addEventListener("pointermove", e => {
    if (!drag || e.pointerId !== drag.id) return;
    const k = (AVATAR.width / state.af) / stageEl.getBoundingClientRect().width;
    state.ax = round2(drag.ax + (e.clientX - drag.x) * k);
    state.ay = round2(drag.ay + (e.clientY - drag.y) * k);
    render();
  });
  ["pointerup", "pointercancel"].forEach(type => stageEl.addEventListener(type, () => {
    drag = null;
    stageEl.classList.remove("dragging");
  }));

  const sw = document.getElementById("swatches");
  PRESETS.forEach(hex => {
    const b = document.createElement("button");
    b.type = "button"; b.dataset.hex = hex; b.style.background = hex; b.title = hex;
    b.setAttribute("aria-label", "Fondo " + hex);
    b.addEventListener("click", () => setColor("color-background", hex));
    sw.appendChild(b);
  });

  document.getElementById("toggle-grid").addEventListener("change", e => {
    document.getElementById("stage").classList.toggle("show-grid", e.target.checked);
  });
  document.getElementById("btn-center").addEventListener("click", () => { state.lx = 0; state.ly = 0; render(); });
  document.getElementById("btn-origin").addEventListener("click", () => {
    state.lx = ORIGINAL[0]; state.ly = ORIGINAL[1]; render();
  });
  ["reset", "reset-2"].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.addEventListener("click", () => { Object.assign(state, DEFAULTS); setStatus("", ""); render(); });
  });
  document.getElementById("copy-cmd").addEventListener("click", e => {
    navigator.clipboard.writeText(document.getElementById("cmd").textContent).then(() => {
      const b = e.target, old = b.textContent; b.textContent = "Copiado";
      setTimeout(() => { b.textContent = old; }, 1200);
    });
  });

  // --- saving straight to the config files, only when served by --serve
  // Injected by build_logo.py --serve; the file on disk always says false, so a
  // generic static server (VS Code Live Server, etc.) shows the command instead.
  const SERVED = __SERVED__;
  document.getElementById("save-box").hidden = !SERVED;
  document.getElementById("cmd-box").hidden = SERVED;
  document.getElementById("sub").innerHTML = SERVED
    ? 'Mueve, colorea, ajusta la foto de perfil en su círculo y cuando te guste dale a <b>Guardar y regenerar</b>: escribe los valores en <code>brand/colors.css</code> y <code>brand/layout.json</code> y vuelve a generar el SVG, el PNG, los favicons y la foto de perfil. Nada se guarda hasta que pulses el botón.'
    : 'Prueba aquí. No se guarda nada: cuando te decidas, copia el comando de abajo y ejecútalo. Para guardar con un botón desde esta misma página, ábrela con <code>python brand/build_logo.py --serve</code>.';

  function setStatus(text, kind) {
    const el = document.getElementById("save-status");
    el.textContent = text;
    el.className = "status" + (kind ? " " + kind : "");
  }

  if (SERVED) {
    const btn = document.getElementById("btn-save");
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      setStatus("Guardando y regenerando...", "busy");
      try {
        const res = await fetch("apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            colors: {
              "color-background": state["color-background"],
              "color-logo": state["color-logo"],
              "color-shadow": state["color-shadow"]
            },
            layout: { offset: [state.lx, state.ly], avatar_fill: state.af,
                      avatar_offset: [state.ax, state.ay] }
          })
        });
        const text = await res.text();
        let data = null;
        try { data = JSON.parse(text); } catch (e) {
          throw new Error("HTTP " + res.status + " sin JSON. Esta pagina no la esta sirviendo build_logo.py --serve.");
        }
        if (!res.ok || !data.ok) throw new Error((data && data.error) || ("HTTP " + res.status));
        Object.assign(DEFAULTS, state);
        const warn = (data.warnings || []).length ? " · aviso: " + data.warnings.join("; ") : "";
        setStatus("Guardado. " + data.written + " archivos regenerados." + warn, warn ? "err" : "ok");
        render();
      } catch (err) {
        setStatus("No se pudo guardar: " + err.message, "err");
      } finally {
        btn.disabled = false;
      }
    });
  }

  window.addEventListener("keydown", e => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    const t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
    const step = e.shiftKey ? 5 : 0.5;
    // With the circle selected the arrows move the profile picture's wing;
    // anywhere else, the logo's and the favicon's, as always.
    const kx = t === stageEl ? "ax" : "lx", ky = t === stageEl ? "ay" : "ly";
    if (e.key === "ArrowLeft") state[kx] = round2(state[kx] - step);
    if (e.key === "ArrowRight") state[kx] = round2(state[kx] + step);
    if (e.key === "ArrowUp") state[ky] = round2(state[ky] - step);
    if (e.key === "ArrowDown") state[ky] = round2(state[ky] + step);
    e.preventDefault(); render();
  });

  render();
</script>
</body>
</html>
"""

# Background candidates offered as swatches in the picker. The first one is
# always the color currently in colors.css.
PRESET_BACKGROUNDS = ["#2E5F8A", "#1F4E79", "#14395C", "#0F2C47", "#4A82B8", "#5B93C7", "#2B6CB0", "#26566E", "#3F6B8E"]


def grid_svg(minor: int = 10, major: int = 50) -> str:
    """Reference grid + axes drawn over the logo canvas, in canvas coordinates."""
    w, h = CANVAS
    out = [f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"100%\" height=\"100%\" aria-hidden=\"true\">"]
    lines = []
    for x in range(minor, w, minor):
        strong = x % major == 0
        lines.append(f"<line x1=\"{x}\" y1=\"0\" x2=\"{x}\" y2=\"{h}\" stroke=\"#000\" stroke-opacity=\"{0.28 if strong else 0.13}\" stroke-width=\"{0.6 if strong else 0.4}\"/>")
    for y in range(minor, h, minor):
        strong = y % major == 0
        lines.append(f"<line x1=\"0\" y1=\"{y}\" x2=\"{w}\" y2=\"{y}\" stroke=\"#000\" stroke-opacity=\"{0.28 if strong else 0.13}\" stroke-width=\"{0.6 if strong else 0.4}\"/>")
    out.append("<g>" + "".join(lines) + "</g>")
    # center axes
    cx, cy = w / 2, h / 2
    out.append(f"<line x1=\"{cx}\" y1=\"0\" x2=\"{cx}\" y2=\"{h}\" stroke=\"#FF5A36\" stroke-opacity=\"0.85\" stroke-width=\"0.9\"/>")
    out.append(f"<line x1=\"0\" y1=\"{cy}\" x2=\"{w}\" y2=\"{cy}\" stroke=\"#FF5A36\" stroke-opacity=\"0.85\" stroke-width=\"0.9\"/>")
    # tick labels along the top and left edges
    labels = []
    for x in range(major, w, major):
        labels.append(f"<text x=\"{x + 2}\" y=\"9\" font-size=\"7\" fill=\"#000\" fill-opacity=\"0.55\" font-family=\"monospace\">{x}</text>")
    for y in range(major, h, major):
        labels.append(f"<text x=\"2\" y=\"{y - 2}\" font-size=\"7\" fill=\"#000\" fill-opacity=\"0.55\" font-family=\"monospace\">{y}</text>")
    out.append("<g>" + "".join(labels) + "</g>")
    out.append(f"<rect x=\"0.5\" y=\"0.5\" width=\"{w - 1}\" height=\"{h - 1}\" fill=\"none\" stroke=\"#000\" stroke-opacity=\"0.35\" stroke-width=\"1\"/>")
    out.append("</svg>")
    return "".join(out)


def preview_html(colors: dict[str, str], layout: dict, served: bool = False) -> str:
    """A self-contained page that re-colors and re-positions the real geometry live.

    served=True enables the Save button; only the --serve handler passes it, so
    the copy written to disk never offers a button that has no server behind it.
    """
    logo_svg = (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {CANVAS[0]} {CANVAS[1]}\" role=\"img\" aria-label=\"Sobreala\">\n"
        f"  <rect class=\"bg\" width=\"{CANVAS[0]}\" height=\"{CANVAS[1]}\" fill=\"var(--color-background)\"/>\n"
        # centered position baked in; the live offset comes from CSS variables on .wing
        + wing_group("var(--color-logo)", "var(--color-shadow)", shift=centering_shift())
        + "</svg>"
    )

    def fav(px: int, clip_id: str, rounded: bool = True) -> str:
        """Preview of one favicon size, matching exactly what the build writes."""
        svg = svg_favicon(colors, layout, logo_fill="var(--color-logo)", shadow_fill="var(--color-shadow)",
                          bg_fill="var(--color-background)", clip_id=clip_id, note=False,
                          shadow_scale=favicon_shadow_scale(px), rounded=rounded, with_offset=False)
        c = _fmt(favicon_canvas(layout))
        svg = svg.replace(f"width=\"{c}\" height=\"{c}\"", f"width=\"{px}\" height=\"{px}\"", 1)
        return svg.replace("<svg ", "<svg class=\"fav\" ", 1)

    centre = ((BBOX[0] + BBOX[2]) / 2, (BBOX[1] + BBOX[3]) / 2)

    def avatar(px: int, round_: bool = True, guide: bool = False) -> str:
        """Preview of the profile picture at one size, as a network crops it.

        The wing stays at its reference coordinates and the viewBox frames it,
        centred on the wing's frame like render_avatar(); the page changes the
        viewBox when the size changes, and the offset arrives through .wing.
        """
        side = avatar_canvas(layout)
        box = " ".join(_fmt(v) for v in (centre[0] - side / 2, centre[1] - side / 2, side, side))
        safe = (f"  <circle class=\"safe\" cx=\"{_fmt(centre[0])}\" cy=\"{_fmt(centre[1])}\" "
                f"r=\"{_fmt(AVATAR_SAFE * side / 2)}\" fill=\"none\" stroke=\"#fff\" "
                "stroke-opacity=\".8\" stroke-width=\"1.2\" stroke-dasharray=\"4 4\" "
                "vector-effect=\"non-scaling-stroke\"/>\n") if guide else ""
        return (
            f"<svg class=\"avatar{' round' if round_ else ''}\" xmlns=\"http://www.w3.org/2000/svg\" "
            f"viewBox=\"{box}\" width=\"{px}\" height=\"{px}\" role=\"img\" aria-label=\"Sobreala\" data-avatar>\n"
            "  <rect class=\"bg\" x=\"-1000\" y=\"-1000\" width=\"2500\" height=\"2500\" "
            "fill=\"var(--color-background)\"/>\n"
            + wing_group("var(--color-logo)", "var(--color-shadow)")
            + safe
            + "</svg>"
        )

    # The outline the page measures the reach with: the same wing + shadow that
    # check_placement() measures, thinner, since it travels inside the page.
    outline_pts = np.concatenate([
        wing_polygon(samples_per_unit=1.0),
        wing_polygon(SHADOW_OFFSET, samples_per_unit=1.0, top_lift=SHADOW_TOP_LIFT)])
    avatar_data = json.dumps({
        "center": [round(centre[0], 2), round(centre[1], 2)],
        "width": round(BBOX_SIZE[0], 2),
        "safe": AVATAR_SAFE,
        "points": [[round(float(x), 2), round(float(y), 2)] for x, y in outline_pts],
    }, separators=(",", ":"))

    presets = [colors["color-background"]] + [p for p in PRESET_BACKGROUNDS if p != colors["color-background"]]
    lx, ly = layout["offset"]
    html = PREVIEW_TEMPLATE
    for token, value in [
        ("__LOGO_SVG__", logo_svg),
        ("__GRID_SVG__", grid_svg()),
        ("__FAV_16__", fav(16, "pmR16")),
        ("__FAV_32__", fav(32, "pmR32")),
        ("__FAV_48__", fav(48, "pmR48")),
        ("__FAV_180__", fav(APPLE_TOUCH_SIZE, "pmR180", rounded=APPLE_TOUCH_ROUNDED)),
        ("__FAV_TAB__", fav(16, "pmRtab")),
        ("__PRESETS__", "[" + ", ".join(f'"{p}"' for p in presets) + "]"),
        ("__CANVAS__", f"[{CANVAS[0]}, {CANVAS[1]}]"),
        ("__BBOX__", "[" + ", ".join(_fmt(v) for v in BBOX) + "]"),
        ("__CENTER__", "[" + ", ".join(_fmt(v) for v in centering_shift()) + "]"),
        ("__ORIGINAL__", "[" + ", ".join(_fmt(v) for v in original_offset()) + "]"),
        ("__AV_STAGE__", avatar(300, guide=True)),
        ("__AV_110__", avatar(110)),
        ("__AV_56__", avatar(56)),
        ("__AV_32__", avatar(32)),
        ("__AVATAR__", avatar_data),
        ("__AV_SAFE__", str(round(AVATAR_SAFE * 100))),
        ("__AF__", repr(float(layout["avatar_fill"]))),
        ("__AX__", _fmt(layout["avatar_offset"][0])),
        ("__AY__", _fmt(layout["avatar_offset"][1])),
        ("__SERVED__", "true" if served else "false"),
        ("__LX__", _fmt(lx)), ("__LY__", _fmt(ly)),
        ("__BG__", colors["color-background"]),
        ("__LOGO__", colors["color-logo"]),
        ("__SHADOW__", colors["color-shadow"]),
    ]:
        html = html.replace(token, value)
    left = re.findall(r"__[A-Z0-9_]+__", html)
    if left:
        raise AssertionError(f"preview template: unreplaced placeholders {sorted(set(left))}")
    return html


# --------------------------------------------------------------------------- build
def build(colors: dict[str, str] | None = None, layout: dict | None = None) -> list[Path]:
    colors = colors or read_colors()
    layout = layout or read_layout()
    for d in (LOGO_DIR, FAVICON_DIR, PREVIEW_DIR, AVATAR_DIR):
        d.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def write_text(path: Path, text: str):
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)

    write_text(LOGO_DIR / "logo.svg", svg_logo(colors, layout))
    write_text(LOGO_DIR / "logo-transparent.svg", svg_symbol(colors))
    write_text(FAVICON_DIR / "favicon.svg", svg_favicon(colors, layout))

    png = LOGO_DIR / "logo.png"
    # shift is in canvas units: wing_polygon applies it before scaling
    render_composition(colors, scale=4.0, shift=logo_shift(layout)).convert("RGB").save(png, optimize=True)
    written.append(png)

    # The wing with no background, cropped to what it draws. Email clients in
    # dark mode repaint the backgrounds declared in the HTML and leave images
    # alone, so a logo with its own background shows up as a box floating on a
    # bar of a different colour. This one has nothing to repaint.
    wing = LOGO_DIR / "logo-wing.png"
    transparent = render_composition(colors, scale=4.0, shift=logo_shift(layout),
                                     background=False)
    transparent.crop(transparent.getbbox()).save(wing, optimize=True)
    written.append(wing)

    for px in FAVICON_PNG_SIZES:
        p = FAVICON_DIR / f"favicon-{px}x{px}.png"
        rounded = APPLE_TOUCH_ROUNDED if px == APPLE_TOUCH_SIZE else True
        im = render_favicon(colors, layout, px, rounded=rounded)
        if px == APPLE_TOUCH_SIZE and not rounded:
            im = im.convert("RGB")  # opaque: iOS turns transparency into black
        im.save(p, optimize=True)
        written.append(p)

    # Pillow drops any size larger than the base image, so the largest render goes first.
    ico_images = [render_favicon(colors, layout, px) for px in sorted(FAVICON_ICO_SIZES, reverse=True)]
    ico = FAVICON_DIR / "favicon.ico"
    ico_images[0].save(ico, format="ICO", sizes=[(px, px) for px in FAVICON_ICO_SIZES], append_images=ico_images[1:])
    written.append(ico)

    avatar = AVATAR_DIR / f"perfil-{AVATAR_SIZE}.png"
    render_avatar(colors, layout).save(avatar, optimize=True)
    written.append(avatar)

    write_text(PREVIEW_DIR / "colores.html", preview_html(colors, layout))
    return written


def describe(colors: dict[str, str], layout: dict) -> str:
    x0, y0, x1, y1 = content_bbox(layout)
    return "\n".join([
        *(f"--{k}: {v}" for k, v in colors.items()),
        f"offset:                [{_fmt(layout['offset'][0])}, {_fmt(layout['offset'][1])}]"
        f"   (0, 0 = centrado; como el original seria [{_fmt(original_offset()[0])}, {_fmt(original_offset()[1])}])",
        f"favicon_fill:          {layout['favicon_fill']}",
        f"favicon_corner_radius: {layout['favicon_corner_radius']}",
        f"avatar_fill:           {layout['avatar_fill']}",
        f"avatar_offset:         [{_fmt(layout['avatar_offset'][0])}, {_fmt(layout['avatar_offset'][1])}]",
        f"logo en el lienzo {CANVAS[0]}x{CANVAS[1]}: x {_fmt(x0)}..{_fmt(x1)}  y {_fmt(y0)}..{_fmt(y1)}",
    ])


# --------------------------------------------------------------------------- local server
APPLY_LIMIT = 64 * 1024  # a config payload is a few hundred bytes

# The only files the server hands out, by fixed name: no path comes from the request.
FAVICON_ROUTES = {
    "/favicon.ico": ("favicon.ico", "image/x-icon"),          # the browser's implicit request
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/favicon/favicon.ico": ("favicon.ico", "image/x-icon"),  # what the page's <link> resolves to
    "/favicon/favicon.svg": ("favicon.svg", "image/svg+xml"),
}


def apply_payload(payload: dict) -> dict:
    """Validate a {colors, layout} payload, write both config files, rebuild.

    Returns a result dict. Nothing is written unless everything validates, so a
    bad request can never leave the config in a broken state.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "error": "se esperaba un objeto JSON"}

    colors = read_colors()
    raw_colors = payload.get("colors") or {}
    if not isinstance(raw_colors, dict):
        return {"ok": False, "error": "'colors' debe ser un objeto"}
    new_colors = dict(colors)
    for key in COLOR_KEYS:
        if key not in raw_colors:
            continue
        parsed = parse_hex(raw_colors[key])
        if parsed is None:
            return {"ok": False, "error": f"'{key}' no es un color #RRGGBB: {raw_colors[key]!r}"}
        new_colors[key] = parsed

    layout = read_layout()
    raw_layout = payload.get("layout") or {}
    if not isinstance(raw_layout, dict):
        return {"ok": False, "error": "'layout' debe ser un objeto"}
    merged = {k: (list(v) if isinstance(v, list) else v) for k, v in layout.items()}
    merged.update({k: v for k, v in raw_layout.items() if k in DEFAULT_LAYOUT})
    new_layout, errors = validate_layout(merged)
    if errors:
        return {"ok": False, "error": "; ".join(errors)}

    changed = {k: v for k, v in new_colors.items() if v != colors[k]}
    if changed:
        write_colors(changed, COLORS_CSS)
    if new_layout != layout:
        write_layout(new_layout, LAYOUT_JSON)

    written = build(new_colors, new_layout)
    return {"ok": True, "written": len(written), "warnings": check_placement(new_layout),
            "colors": new_colors, "layout": new_layout}


def serve(port: int = 8765, host: str = "127.0.0.1", open_browser: bool = True) -> int:
    """Serve the editor locally so its Save button can write the config files.

    Development tool only: it binds to the loopback interface and is never part
    of anything that gets deployed.
    """
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        server_version = "SobrealaBrand"

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: dict):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html", "/colores.html"):
                # regenerate from the config on every load, so the page always
                # opens showing what is actually saved
                html = preview_html(read_colors(), read_layout(), served=True)
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/state":
                self._json(200, {"colors": read_colors(), "layout": read_layout()})
            elif path in FAVICON_ROUTES:
                # the editor gets the brand's own tab icon, and the browser's
                # automatic /favicon.ico request stops 404-ing
                name, ctype = FAVICON_ROUTES[path]
                target = FAVICON_DIR / name
                if target.is_file():
                    self._send(200, target.read_bytes(), ctype)
                else:
                    self._json(404, {"ok": False, "error": "no encontrado"})
            else:
                self._json(404, {"ok": False, "error": "no encontrado"})

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/apply":
                self._json(404, {"ok": False, "error": "no encontrado"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > APPLY_LIMIT:
                self._json(413, {"ok": False, "error": "cuerpo de la peticion invalido"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._json(400, {"ok": False, "error": f"JSON invalido: {exc}"})
                return
            try:
                result = apply_payload(payload)
            except Exception as exc:  # never take the server down on one bad request
                self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
                return
            self._json(200 if result["ok"] else 400, result)
            try:
                if result["ok"]:
                    print(f"  guardado: {result['written']} archivos regenerados")
                    for w in result["warnings"]:
                        print(f"  aviso: {w}")
                else:
                    print(f"  rechazado: {result['error']}")
            except OSError:
                pass

        def log_message(self, fmt, *args):  # quieter than the default access log
            if self.command == "POST":
                try:
                    print(f"  {self.command} {self.path}")
                except OSError:
                    pass

    last_error = None
    for candidate in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer((host, candidate), Handler)
            break
        except OSError as exc:
            last_error = exc
    else:
        sys.exit(f"no se pudo abrir ningun puerto entre {port} y {port + 9}: {last_error}")

    url = f"http://{host}:{httpd.server_port}/"
    print(f"Editor de marca en {url}")
    print("El boton Guardar escribe colors.css y layout.json y regenera todo.")
    print("Ctrl+C para parar.")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nservidor detenido")
    finally:
        httpd.server_close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate the Sobreala logo and favicons from brand/colors.css + brand/layout.json.",
        epilog="Any value passed here is written into its config file and then everything is rebuilt, "
               "so the config files stay the single source of truth. "
               "To try colors and positions without applying them, open brand/preview/colores.html.",
    )
    ap.add_argument("--background", metavar="HEX", help="background color (#RRGGBB)")
    ap.add_argument("--logo", metavar="HEX", help="wing color (#RRGGBB)")
    ap.add_argument("--shadow", metavar="HEX", help="separations/shadow color (#RRGGBB)")
    ap.add_argument("--x", type=float, metavar="N", help="horizontal offset of the wing from centered (+ right), logo and favicon alike")
    ap.add_argument("--y", type=float, metavar="N", help="vertical offset of the wing from centered (+ down), logo and favicon alike")
    ap.add_argument("--center", action="store_true", help="offset [0, 0]: centered in the logo and in the favicon")
    ap.add_argument("--original", action="store_true", help="put the wing exactly where the reference image has it")
    ap.add_argument("--favicon-fill", type=float, metavar="F", help="share of the favicon side taken by the wing (0-1)")
    ap.add_argument("--favicon-radius", type=float, metavar="F", help="corner radius as a fraction of the side (0-0.5)")
    ap.add_argument("--avatar-fill", type=float, metavar="F",
                    help="share of the profile picture's side taken by the wing (0-1)")
    ap.add_argument("--avatar-x", type=float, metavar="N",
                    help="horizontal offset of the wing in the profile picture (+ right), its own")
    ap.add_argument("--avatar-y", type=float, metavar="N",
                    help="vertical offset of the wing in the profile picture (+ down), its own")
    ap.add_argument("--show", action="store_true", help="print the current config and exit")
    ap.add_argument("--serve", action="store_true",
                    help="open the editor in a browser with a Save button that writes the config (local only)")
    ap.add_argument("--port", type=int, default=8765, metavar="N", help="port for --serve (default 8765)")
    ap.add_argument("--no-open", action="store_true", help="with --serve, do not open the browser")
    args = ap.parse_args(argv)

    colors = read_colors()
    layout = read_layout()

    if args.show:
        print(describe(colors, layout))
        return 0

    if args.center and (args.x is not None or args.y is not None):
        sys.exit("--center cannot be combined with --x/--y")

    color_updates = {}
    for flag, key in (("background", "color-background"), ("logo", "color-logo"), ("shadow", "color-shadow")):
        value = getattr(args, flag)
        if value:
            color_updates[key] = normalize_hex(value, "--" + flag)
    if color_updates:
        for key, value in color_updates.items():
            print(f"colors.css: --{key} {colors[key]} -> {value}")
        colors = write_colors(color_updates, COLORS_CSS)

    new_layout = {k: (list(v) if isinstance(v, list) else v) for k, v in layout.items()}
    if args.center:
        new_layout["offset"] = [0.0, 0.0]
    if args.original:
        new_layout["offset"] = list(original_offset())
    if args.x is not None:
        new_layout["offset"][0] = round(args.x, 2)
    if args.y is not None:
        new_layout["offset"][1] = round(args.y, 2)
    if args.favicon_fill is not None:
        new_layout["favicon_fill"] = round(args.favicon_fill, 4)
    if args.favicon_radius is not None:
        new_layout["favicon_corner_radius"] = round(args.favicon_radius, 4)
    if args.avatar_fill is not None:
        new_layout["avatar_fill"] = round(args.avatar_fill, 4)
    if args.avatar_x is not None:
        new_layout["avatar_offset"][0] = round(args.avatar_x, 2)
    if args.avatar_y is not None:
        new_layout["avatar_offset"][1] = round(args.avatar_y, 2)

    new_layout, errors = validate_layout(new_layout)
    if errors:
        # nothing has been written yet, so layout.json is left untouched
        sys.exit("\n".join(f"error: {e}" for e in errors))
    if new_layout != layout:
        for key in DEFAULT_LAYOUT:
            if new_layout[key] != layout[key]:
                print(f"layout.json: {key} {layout[key]} -> {new_layout[key]}")
        write_layout(new_layout, LAYOUT_JSON)
        layout = read_layout(LAYOUT_JSON)

    for warning in check_placement(layout):
        print(f"aviso: {warning}", file=sys.stderr)

    for p in build(colors, layout):
        print("wrote", p.relative_to(BRAND_DIR.parent))

    if args.serve:
        return serve(args.port, open_browser=not args.no_open)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
