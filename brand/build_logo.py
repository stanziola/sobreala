#!/usr/bin/env python3
"""Generate the Panamails logo assets from one vector geometry + brand/colors.css.

The logo is a wing made of four stacked feathers. It is built from a single
closed path (the white wing) drawn twice: once in the shadow color, offset
15.7 units left and 3.85 units up, and once in the logo color on top. The black
separations visible between the feathers, and the thin dark line along the
top edge, are the parts of the offset copy that the white wing does not cover.
This reproduces the reference image (brand/logo/reference/logo-original.png)
with sub-pixel accuracy.

Colors are never written here: they are read from brand/colors.css
(--color-background, --color-logo, --color-shadow).

Outputs:
  brand/logo/logo.svg               full composition, blue background (viewBox 0 0 271 254)
  brand/logo/logo-transparent.svg   wing only, transparent background
  brand/logo/logo.png               full composition, 1084 x 1016 px
  brand/favicon/favicon.svg         square, blue background
  brand/favicon/favicon-16x16.png, favicon-32x32.png, favicon-180x180.png
  brand/favicon/favicon.ico         16 + 32 + 48 px

Usage:
    pip install numpy pillow
    python brand/build_logo.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

BRAND_DIR = Path(__file__).resolve().parent
COLORS_CSS = BRAND_DIR / "colors.css"
LOGO_DIR = BRAND_DIR / "logo"
FAVICON_DIR = BRAND_DIR / "favicon"

# --------------------------------------------------------------------------- geometry
# Coordinates are in the reference frame: a 271 x 254 canvas, same as the
# original PNG, so the wing sits exactly where it does in the reference.
CANVAS = (271, 254)

# Closed outline of the white wing, starting at the tip of the main feather
# and going clockwise: straight top edge, rounded top-right corner, right side,
# rounded bottom, then up the left side through the four feather tips and the
# three notches (sharp tails) between them.
START = (39.29, 55.11)
PIECES = [
    ("L", (222.48, 77.8)),                                        # top edge (straight)
    ("C", (234.63, 79.3, 224.74, 102.37, 223.81, 103.68)),        # rounded top-right corner
    ("C", (216.2, 114.41, 188.81, 154.29, 162.18, 170.24)),       # right side + start of bottom curve
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

# Bounding box of wing + shadow in the reference frame.
BBOX = (23.59, 51.26, 228.48, 171.79)  # xmin, ymin, xmax, ymax

# Symbol (transparent) version: tight box with a 1 unit margin.
SYMBOL_MARGIN = 1.0
SYMBOL_SIZE = (207, 123)

# Favicon: square canvas with the wing centered, ~6% side margins.
FAVICON_CANVAS = 232.0
FAVICON_PNG_SIZES = (16, 32, 180)
FAVICON_ICO_SIZES = (16, 32, 48)

# Small-size legibility: at 16 px the black separations are only ~0.35 px
# thick and vanish, so for tiny raster sizes the shadow offset is widened just
# enough to keep them visible. The outline itself never changes. favicon.svg is
# rendered by browsers at 16-32 px, so it gets the 32 px treatment.
# Set everything to 1.0 to keep the exact reference geometry at every size.
FAVICON_SHADOW_SCALE = {16: 2.0, 32: 1.5, 48: 1.25}
FAVICON_SVG_SHADOW_SCALE = 1.5

# --------------------------------------------------------------------------- colors
REQUIRED_COLORS = ("color-background", "color-logo", "color-shadow")


def read_colors(css_path: Path = COLORS_CSS) -> dict[str, str]:
    """Parse `--name: #RRGGBB;` declarations from colors.css."""
    text = css_path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    found = {m.group(1): m.group(2).upper() for m in re.finditer(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text)}
    missing = [k for k in REQUIRED_COLORS if k not in found]
    if missing:
        sys.exit(f"{css_path}: missing color variables: {', '.join('--' + m for m in missing)}")
    return {k: found[k] for k in REQUIRED_COLORS}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


# --------------------------------------------------------------------------- path data
def _fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def path_d(shift=(0.0, 0.0), scale: float = 1.0) -> str:
    """SVG path data of the wing, optionally shifted (before scaling) and scaled."""
    def tr(x, y):
        return _fmt((x + shift[0]) * scale), _fmt((y + shift[1]) * scale)

    out = ["M%s %s" % tr(*START)]
    for kind, c in PIECES:
        if kind == "L":
            out.append("L%s %s" % tr(*c))
        else:
            out.append("C%s %s %s %s %s %s" % (*tr(c[0], c[1]), *tr(c[2], c[3]), *tr(c[4], c[5])))
    out.append("Z")
    return " ".join(out)


def wing_group(colors: dict[str, str], shift=(0.0, 0.0), scale: float = 1.0, shadow_scale: float = 1.0, indent: str = "  ") -> str:
    d = path_d(shift, scale)
    dx, dy = SHADOW_OFFSET[0] * scale * shadow_scale, SHADOW_OFFSET[1] * scale * shadow_scale
    return (
        f"{indent}<g id=\"wing\">\n"
        f"{indent}  <!-- shadow: the same wing outline, offset left and up -->\n"
        f"{indent}  <path id=\"wing-shadow\" fill=\"{colors['color-shadow']}\" transform=\"translate({_fmt(dx)} {_fmt(dy)})\" d=\"{d}\"/>\n"
        f"{indent}  <path id=\"wing-fill\" fill=\"{colors['color-logo']}\" d=\"{d}\"/>\n"
        f"{indent}</g>\n"
    )


GENERATED_NOTE = "<!-- Generated by brand/build_logo.py from brand/colors.css. Edit colors there, not here. -->\n"


def svg_logo(colors: dict[str, str]) -> str:
    w, h = CANVAS
    return (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" height=\"{h}\" role=\"img\" aria-labelledby=\"title\">\n"
        f"  <title id=\"title\">Panamails</title>\n"
        f"  {GENERATED_NOTE}"
        f"  <rect width=\"{w}\" height=\"{h}\" fill=\"{colors['color-background']}\"/>\n"
        + wing_group(colors)
        + "</svg>\n"
    )


def symbol_shift() -> tuple[float, float]:
    return (-(BBOX[0] - SYMBOL_MARGIN), -(BBOX[1] - SYMBOL_MARGIN))


def svg_symbol(colors: dict[str, str]) -> str:
    w, h = SYMBOL_SIZE
    return (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" height=\"{h}\" role=\"img\" aria-labelledby=\"title\">\n"
        f"  <title id=\"title\">Panamails</title>\n"
        f"  {GENERATED_NOTE}"
        + wing_group(colors, shift=symbol_shift())
        + "</svg>\n"
    )


def favicon_shift() -> tuple[float, float]:
    bw, bh = BBOX[2] - BBOX[0], BBOX[3] - BBOX[1]
    return (-BBOX[0] + (FAVICON_CANVAS - bw) / 2, -BBOX[1] + (FAVICON_CANVAS - bh) / 2)


def svg_favicon(colors: dict[str, str]) -> str:
    c = _fmt(FAVICON_CANVAS)
    return (
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {c} {c}\" width=\"{c}\" height=\"{c}\">\n"
        f"  {GENERATED_NOTE}"
        f"  <rect width=\"{c}\" height=\"{c}\" fill=\"{colors['color-background']}\"/>\n"
        + wing_group(colors, shift=favicon_shift(), shadow_scale=FAVICON_SVG_SHADOW_SCALE)
        + "</svg>\n"
    )


# --------------------------------------------------------------------------- rasterizer
def _bezier(p0, p1, p2, p3, n: int) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n, endpoint=False)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * (t ** 2) * p2 + (t ** 3) * p3


def wing_polygon(shift=(0.0, 0.0), scale: float = 1.0, samples_per_unit: float = 2.0) -> np.ndarray:
    """Flatten the wing outline into a dense polygon (in output pixels)."""
    pts = []
    cur = np.array(START, float)
    for kind, c in PIECES:
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


def render_composition(colors: dict[str, str], scale: float, shift=(0.0, 0.0), size=None, background=True, ss: int = 8, shadow_scale: float = 1.0) -> Image.Image:
    if size is None:
        size = (round(CANVAS[0] * scale), round(CANVAS[1] * scale))
    shadow_shift = (shift[0] + SHADOW_OFFSET[0] * shadow_scale, shift[1] + SHADOW_OFFSET[1] * shadow_scale)
    layers = [
        (wing_polygon(shadow_shift, scale), hex_to_rgb(colors["color-shadow"])),
        (wing_polygon(shift, scale), hex_to_rgb(colors["color-logo"])),
    ]
    bg = hex_to_rgb(colors["color-background"]) if background else None
    return rasterize(size, layers, bg, ss)


def render_favicon(colors: dict[str, str], px: int) -> Image.Image:
    scale = px / FAVICON_CANVAS
    return render_composition(colors, scale, shift=favicon_shift(), size=(px, px), ss=16 if px <= 64 else 8,
                              shadow_scale=FAVICON_SHADOW_SCALE.get(px, 1.0))


# --------------------------------------------------------------------------- build
def build() -> list[Path]:
    colors = read_colors()
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    FAVICON_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def write_text(path: Path, text: str):
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)

    write_text(LOGO_DIR / "logo.svg", svg_logo(colors))
    write_text(LOGO_DIR / "logo-transparent.svg", svg_symbol(colors))
    write_text(FAVICON_DIR / "favicon.svg", svg_favicon(colors))

    png = LOGO_DIR / "logo.png"
    render_composition(colors, scale=4.0).convert("RGB").save(png, optimize=True)
    written.append(png)

    for px in FAVICON_PNG_SIZES:
        p = FAVICON_DIR / f"favicon-{px}x{px}.png"
        render_favicon(colors, px).save(p, optimize=True)
        written.append(p)

    # Pillow drops any size larger than the base image, so the largest render goes first.
    ico_images = [render_favicon(colors, px) for px in sorted(FAVICON_ICO_SIZES, reverse=True)]
    ico = FAVICON_DIR / "favicon.ico"
    ico_images[0].save(ico, format="ICO", sizes=[(px, px) for px in FAVICON_ICO_SIZES], append_images=ico_images[1:])
    written.append(ico)
    return written


if __name__ == "__main__":
    for p in build():
        print("wrote", p.relative_to(BRAND_DIR.parent))
