"""Preparar la imagen que un cliente pone en su plantilla.

La imagen no puede viajar dentro del correo: pegada dentro pesa megas, Gmail
recorta a los 102 KB y lo que se pierde es el pie con el botón de la baja. Así
que se guarda fuera y el correo trae su dirección.

**Achicarla es lo que hace que guardarla salga gratis.** Una foto de teléfono
son tres o cuatro megas; a 600 píxeles de ancho —que es a lo que la dibujan las
plantillas— son unos 120 KB. Sin este paso habría que rechazar casi cualquier
foto, que es justo lo que dejaría la pantalla inservible para una cooperativa
que solo tiene la foto que acaba de tomar.

Dos cosas que este archivo no hace:

  * **No decide de quién es la imagen.** Eso lo hace `models/image.py`, que la
    guarda colgada de una cuenta.
  * **No la sirve.** De eso se encarga `blueprints/media/`, que es lo que pide
    el buzón de quien abre el correo.
"""

from __future__ import annotations

import re
import warnings
import zipfile
import zlib
from io import BytesIO

from PIL import Image, ImageOps

from config import Config

# Lo que se acepta que entre. Flask ya corta por encima de esto antes de que la
# petición llegue a ninguna línea nuestra, así que una foto enorme se rechaza
# sin haberla leído.
MAX_UPLOAD = 5 * 1024 * 1024

# El ancho al que las plantillas dibujan la imagen. Guardar más píxeles de los
# que se van a ver es pagar espacio y hacer esperar a quien abre el correo.
WIDTH = 600
# Y un tope de alto, para que una imagen larguísima no se cuele entera solo
# porque es estrecha.
HEIGHT = 2400

# Lo que puede llegar a pesar ya achicada. Es una red de seguridad: si algo se
# sale de aquí, mejor rechazarlo que guardarlo.
STORED_MAX = 400 * 1024
# Un GIF se guarda tal cual, porque achicarlo le mata la animación, que es lo
# único por lo que alguien manda un GIF.
GIF_MAX = 400 * 1024

# Una foto de 40 megapíxeles no la saca ninguna cámara de las que se usan para
# esto. Por encima, es un archivo hecho para reventar el proceso: un PNG de
# 40 KB puede descomprimirse a varios gigabytes en memoria.
Image.MAX_IMAGE_PIXELS = 40_000_000

# El nombre con el que se guarda y con el que se pide. Lo ponemos nosotros
# entero, así que se puede comprobar con una expresión y no hace falta confiar
# en nada de lo que llegue.
NAME = re.compile(r"^[A-Za-z0-9_-]{16,64}\.(jpg|png|gif)$")

# Los formatos que dibuja cualquier lector de correo. Cada uno se reconoce por
# cómo empieza el archivo, no por cómo se llama.
KINDS = (
    ("jpg", "image/jpeg", b"\xff\xd8\xff"),
    ("png", "image/png", b"\x89PNG\r\n\x1a\n"),
    ("gif", "image/gif", b"GIF87a"),
    ("gif", "image/gif", b"GIF89a"),
)

# De qué se sale con cada extensión al servirla.
MIMES = {"jpg": "image/jpeg", "png": "image/png", "gif": "image/gif"}


class ImageError(RuntimeError):
    """La imagen no se puede usar. Quien llama traduce el motivo a una frase."""


def kind(raw: bytes) -> tuple[str, str] | None:
    """Qué imagen es esto, mirando dentro. Devuelve (extensión, tipo) o None.

    WebP va aparte porque no se reconoce por el principio: es un contenedor
    RIFF con la palabra WEBP cuatro bytes más adelante.
    """
    for ext, mime, magic in KINDS:
        if raw.startswith(magic):
            return ext, mime
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def trim(raw: bytes) -> bytes:
    """La imagen sin sus bordes transparentes, en PNG. Si no los tiene, o no se
    puede leer, sale tal cual: `shrink()` es quien decide si sirve.

    Un logo exportado con aire transparente alrededor ocupaba en el lienzo una
    caja más grande que lo que se ve. El GIF no se toca: recortarlo le quitaría
    la animación.
    """
    found = kind(raw)
    if found is None or found[0] == "gif":
        return raw
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as opened:
                clear = (opened.mode in ("RGBA", "LA")
                         or (opened.mode == "P" and "transparency" in opened.info))
                if not clear:
                    return raw
                image = (ImageOps.exif_transpose(opened) or opened).convert("RGBA")
                box = image.getchannel("A").getbbox()
                if not box or box == (0, 0, image.width, image.height):
                    return raw
                out = BytesIO()
                image.crop(box).save(out, format="PNG")
                return out.getvalue()
    except (Image.DecompressionBombWarning, OSError, ValueError):
        return raw


def shrink(raw: bytes, *, width: int = WIDTH) -> tuple[bytes, str, str]:
    """Dejarla lista para un correo. Devuelve (datos, extensión, tipo).

    Sale JPEG, o PNG si la imagen tiene partes transparentes —un logo sobre
    fondo blanco forzado a JPEG queda con un recuadro—. El WebP también sale
    convertido: lo dibujan los navegadores, pero no todos los lectores de
    correo.
    """
    found = kind(raw)
    if found is None:
        raise ImageError("not_image")
    if found[0] == "gif":
        # Tal cual: achicarlo le quitaría la animación.
        if len(raw) > GIF_MAX:
            raise ImageError("gif_too_big")
        return raw, "gif", "image/gif"

    try:
        with warnings.catch_warnings():
            # Pillow avisa antes de reventar; aquí ese aviso tiene que doler.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as opened:
                # Las fotos de teléfono vienen derechas por una etiqueta y no
                # por sus píxeles; sin esto salen acostadas.
                image = ImageOps.exif_transpose(opened) or opened
                clear = (image.mode in ("RGBA", "LA")
                         or (image.mode == "P" and "transparency" in image.info))
                image.thumbnail((width, HEIGHT), Image.LANCZOS)
                out = BytesIO()
                if clear:
                    image.convert("RGBA").save(out, format="PNG", optimize=True)
                    ext = "png"
                else:
                    image.convert("RGB").save(out, format="JPEG", quality=82,
                                              optimize=True, progressive=True)
                    ext = "jpg"
    except Image.DecompressionBombWarning as exc:
        raise ImageError("too_many_pixels") from exc
    except (OSError, ValueError) as exc:
        raise ImageError("unreadable") from exc

    data = out.getvalue()
    if len(data) > STORED_MAX:
        raise ImageError("too_big")
    return data, ext, MIMES[ext]


def valid_name(name: str) -> bool:
    return bool(NAME.match(name or ""))


def url_of(name: str) -> str:
    """La dirección completa, que es lo que va en el correo.

    Completa y no relativa porque quien la pide es el buzón de quien recibe el
    correo, desde fuera de aquí. Se arma al dibujar y no se guarda, así que
    cambiar de dominio no rompe ninguna pieza guardada.
    """
    return f"{Config.APP_BASE_URL}/img/{name}" if name else ""


# Una imagen del panel dentro de un HTML: `/img/` y un nombre de los nuestros.
# Sin el dominio, para que la lea aunque el panel haya cambiado de dirección.
IN_HTML = re.compile(r"/img/([A-Za-z0-9_-]{16,64}\.(?:jpg|png|gif))")


# ------------------------------------------------ el ZIP de una plantilla
# Lo que baja el editor para pasarle una plantilla a otra persona. Trae el
# lienzo (`lienzo.json`) con sus fotos originales en `fotos/`, que es lo que se
# vuelve a cargar y se sigue editando; y el HTML con sus imágenes fundidas en
# `imagenes/`, que es para verlo al abrirlo en una computadora o usarlo fuera de
# Sobreala. Al cargarlo, las fotos entran a la cuenta que lo carga.
ZIP_CANVAS = "lienzo.json"
ZIP_PHOTOS = "fotos/"
ZIP_FOLDER = "imagenes/"
# Lo que puede pesar el lienzo: sesenta elementos con su texto caben de sobra.
ZIP_CANVAS_MAX = 512 * 1024
# Lo que se descomprime entre todas. Un ZIP pequeño puede inflarse a gigas, así
# que se cuenta lo que sale y no lo que dice su índice.
ZIP_UNPACKED_MAX = 4 * MAX_UPLOAD
# Lo que el sistema de otro deja dentro y no es de la plantilla.
ZIP_SKIP = ("__MACOSX/",)


class PackError(RuntimeError):
    """El ZIP no se puede usar. Quien llama traduce el motivo a una frase."""


def is_zip(raw: bytes) -> bool:
    return raw.startswith(b"PK\x03\x04")


def unpack(raw: bytes, *, most: int) -> tuple[bytes, dict[str, bytes]]:
    """El lienzo de un ZIP y sus fotos, `{ruta dentro del ZIP: bytes}`, como
    `fotos/1.jpg`, que es como las nombra el lienzo.

    Se lee en memoria, sin escribir nada a disco, y cada archivo con su tope: se
    lee hasta un byte más de lo permitido, así que mentir en el índice no sirve.
    Si todo viene dentro de una carpeta (lo que pasa al comprimir una carpeta),
    se mira dentro de ella. El HTML y `imagenes/` no se leen: el lienzo los
    vuelve a hacer.
    """
    try:
        pack = zipfile.ZipFile(BytesIO(raw))
        entries = [one for one in pack.infolist() if not one.is_dir()
                   and not one.filename.startswith(ZIP_SKIP)]
        tops = {one.filename.split("/", 1)[0] for one in entries}
        root = ""
        if len(tops) == 1 and all("/" in one.filename for one in entries):
            root = tops.pop() + "/"
        inner = {one.filename[len(root):]: one for one in entries
                 if one.filename.startswith(root)}
        if ZIP_CANVAS not in inner:
            raise PackError("zip_no_canvas")
        photos = [name for name in inner if name.startswith(ZIP_PHOTOS)
                  and name[len(ZIP_PHOTOS):] and "/" not in name[len(ZIP_PHOTOS):]]
        if len(photos) > most:
            raise PackError("zip_too_many")
        with pack.open(inner[ZIP_CANVAS]) as opened:
            doc = opened.read(ZIP_CANVAS_MAX + 1)
        if len(doc) > ZIP_CANVAS_MAX:
            raise PackError("zip_heavy")
        found: dict[str, bytes] = {}
        total = 0
        for name in photos:
            with pack.open(inner[name]) as opened:
                data = opened.read(MAX_UPLOAD + 1)
            total += len(data)
            if len(data) > MAX_UPLOAD or total > ZIP_UNPACKED_MAX:
                raise PackError("zip_heavy")
            found[name] = data
        return doc, found
    except PackError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, OSError,
            RuntimeError, NotImplementedError, ValueError) as exc:
        # Roto, con contraseña o comprimido de una forma que no se lee.
        raise PackError("zip_broken") from exc


def names_in(html: str) -> list[str]:
    """Las imágenes del panel que nombra un HTML cargado.

    Es lo que pasa con el HTML bajado de un lienzo y vuelto a cargar: sus
    imágenes fundidas van enlazadas, y no se pueden borrar mientras esa plantilla
    las siga usando. De otra cuenta no borra ni guarda nada: quien borra pregunta
    siempre con la cuenta.
    """
    return sorted(set(IN_HTML.findall(html or "")))
