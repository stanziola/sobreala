"""Las miniaturas de las plantillas de muestra de la portada.

Cada tarjeta de la tira «¿Aún no sabes por dónde empezar?» enseña su plantilla,
no un dibujo de ella: sale del correo armado que trae su ZIP
(`backend/sample_templates/<slug>.zip`), que es lo mismo que sale al enviar sin
el pie. Se abre en un Chrome sin cabeza a 600 de ancho, que es lo que mide el
correo, y se guarda la parte de arriba en 3:4.

Mismo trato que `tutorials.py`: fuentes de verdad → comando → archivos generados
que no se tocan a mano.

    python landing/samples.py            # rehacer las miniaturas
    python landing/samples.py --check    # decir si falta alguna, sin tocar nada

Hace falta Chrome instalado y Pillow. **Se corre a mano cuando cambie un ZIP o
la lista `SAMPLES` de `content.py`**: si no, la tarjeta enseña otra cosa.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import content
from shots import CHROME

ROOT = Path(__file__).resolve().parent.parent
ZIPS = ROOT / "backend" / "sample_templates"
OUT = ROOT / "landing" / "assets" / "img" / "samples"

# Lo que se ve de cada plantilla: su ancho entero y, de alto, lo que da el 3:4
# desde arriba. Se guarda a este tamaño, el doble de la tarjeta más ancha
# (300 px), para que se lea nítida.
WIDE, TALL = 600, 800


def page_of(pack: zipfile.ZipFile, folder: Path) -> Path:
    """El correo del ZIP en `folder`, con sus imágenes al lado.

    Debajo de un correo más corto que la miniatura asomaría el fondo del sobre;
    se pinta del color de la hoja, así esa parte se lee como hoja.
    """
    page = next(n for n in pack.namelist() if n.endswith(".html") and "/" not in n)
    for name in pack.namelist():
        if name.startswith("imagenes/") and not name.endswith("/"):
            target = folder / "imagenes" / Path(name).name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(pack.read(name))
    sheet = json.loads(pack.read("lienzo.json")).get("bg") or "#FFFFFF"
    html = pack.read(page).decode("utf-8").replace(
        "</head>", f"<style>html,body{{background:{sheet} !important}}</style></head>", 1)
    made = folder / "correo.html"
    made.write_text(html, encoding="utf-8")
    return made


def thumbnail(slug: str) -> bytes:
    """La miniatura de una plantilla, en WEBP."""
    from PIL import Image

    with tempfile.TemporaryDirectory(prefix="sobreala-samples-") as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(ZIPS / f"{slug}.zip") as pack:
            page = page_of(pack, work)
        shot = work / "shot.png"
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
             "--hide-scrollbars", f"--user-data-dir={work / 'chrome'}",
             "--force-device-scale-factor=2", f"--window-size={WIDE},{TALL}",
             f"--screenshot={shot}", page.as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False)
        if not shot.exists():
            raise SystemExit(f"Chrome no fotografió {slug}.")
        # Se corta sobre la medida que devolvió Chrome y no sobre la pedida:
        # así no importa a cuántos píxeles por punto la dibujó.
        with Image.open(shot) as raw:
            wide, tall = raw.size
            cut = raw.crop((0, 0, wide, min(tall, round(wide * TALL / WIDE))))
            cut = cut.resize((WIDE, round(WIDE * cut.height / wide)), Image.LANCZOS)
            buffer = BytesIO()
            cut.convert("RGB").save(buffer, format="WEBP", quality=80, method=6)
            return buffer.getvalue()


def missing() -> list[str]:
    return [one["slug"] for one in content.SAMPLES
            if not (OUT / f"{one['slug']}.webp").exists()]


def main() -> None:
    if "--check" in sys.argv:
        faltan = missing()
        if faltan:
            print("Faltan miniaturas:", ", ".join(faltan))
            print("Correlas con: python landing/samples.py")
            raise SystemExit(1)
        print("Las miniaturas de las plantillas de muestra estan.")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    wanted = {one["slug"] for one in content.SAMPLES}
    for old in OUT.glob("*.webp"):
        if old.stem not in wanted:
            old.unlink()
    for one in content.SAMPLES:
        data = thumbnail(one["slug"])
        target = OUT / f"{one['slug']}.webp"
        target.write_bytes(data)
        print(f"  {target.relative_to(ROOT)}  {len(data) // 1024} KB")


if __name__ == "__main__":
    main()
