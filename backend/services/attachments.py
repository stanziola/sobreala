"""El archivo adjunto del correo individual (octubre de 2026).

Uno por correo, de hasta `MAX_BYTES`, y solo de los tipos que se leen en
cualquier buzón sin riesgo: PDF, JPG, PNG, Word y Excel. **El tipo se reconoce
por el contenido, no por el nombre**: un `.pdf` que por dentro es otra cosa no
entra, como pasa con las imágenes de las plantillas.

Desde octubre de 2026 no va adjunto: se guarda 30 días (`models/download.py`)
y el correo lleva un botón para bajarlo, que es lo que deja saber si la persona
lo bajó.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile

MAX_BYTES = 5 * 1024 * 1024
# Lo que acepta el campo del formulario, para que el selector de archivos ya
# enseñe solo estos.
ACCEPT = ".pdf,.jpg,.jpeg,.png,.docx,.xlsx"


def kind_of(data: bytes) -> tuple[str, str, str] | None:
    """(tipo, subtipo, extensión) por el contenido, o None si no es de los que
    se aceptan."""
    if data.startswith(b"%PDF-"):
        return "application", "pdf", "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "jpeg", "jpg"
    if data.startswith(b"PK\x03\x04"):
        try:
            names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" in names:
            if any(n.startswith("word/") for n in names):
                return ("application",
                        "vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "docx")
            if any(n.startswith("xl/") for n in names):
                return ("application",
                        "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "xlsx")
    return None


SAFE = re.compile(r"[^A-Za-z0-9 ._-]+")


def safe_name(raw: str, ext: str) -> str:
    """El nombre con que llega al buzón: el que tenía, sin lo que rompe una
    cabecera, y con la extensión de lo que de verdad es."""
    base = str(raw or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = base.rsplit(".", 1)[0] if "." in base else base
    clean = SAFE.sub("", unicodedata.normalize("NFKD", base)).strip()[:80]
    return f"{clean or 'archivo'}.{ext}"
