"""Armar el correo que sale de una pieza: lo del cliente más lo que ponemos.

**Este es el único sitio que arma un correo.** La vista previa y, cuando exista,
el envío llaman aquí, para que lo que alguien ve antes de mandar sea de verdad
lo que se manda.

Tres cosas se añaden después de lo que escribió el cliente, y ninguna se guarda
dentro de su pieza:

  * **El botón de anular la suscripción**, en todos los planes y sin excepción.
    Es la regla 3 de CLAUDE.md, y va inyectado justamente para que no se pueda
    quitar editando la plantilla. Su enlace es único por destinatario.
  * **La marca de agua**, solo en los planes que la llevan —hoy el Básico y
    quien no tiene plan—. Es la regla 4. Al subir de plan desaparece sola porque
    nadie la copió a ningún sitio: se pregunta a docs/pricing.md cada vez.
  * **La dirección postal**, que la ley CAN-SPAM exige en todo correo
    publicitario y basta un destinatario con Gmail para caer en su ámbito. Si
    todavía no está configurada no se dibuja, y sigue anotada en CLAUDE.md como
    pendiente antes de la primera campaña real.

Lo que escribió el cliente se escapa. El motor va con autoescape puesto, así que
un `<script>` en el título sale como texto y no como etiqueta.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from config import Config
from services import imaging, plans

TEMPLATES = Path(__file__).resolve().parent.parent / "email_templates"

# El orden en que se ofrecen. Los archivos de la carpeta mandan sobre esto: uno
# que no esté aquí se pone al final, así que agregar la quinta plantilla es
# dejar caer un archivo.
ORDER = ("aviso", "anuncio", "boletin", "convocatoria")

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def _templates() -> dict[str, dict[str, Any]]:
    """Las plantillas de la carpeta, con los campos que declara cada una.

    Cada archivo lleva arriba su `FIELDS` y su `LABEL`, así que la pantalla
    dibuja el formulario sola y no hay una lista de campos escrita aparte que un
    día diga otra cosa que el archivo.
    """
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(TEMPLATES.glob("*.html")):
        # Las que empiezan por guion bajo no se eligen: son el sobre y lo que
        # envuelva a las demás, no plantillas de correo.
        if path.name.startswith("_"):
            continue
        template = _env.get_template(path.name)
        module = template.module
        found[path.stem] = {
            "key": path.stem,
            "label": getattr(module, "LABEL", path.stem.capitalize()),
            "fields": list(getattr(module, "FIELDS", [])),
        }
    return {key: found[key] for key in ORDER if key in found} | {
        key: value for key, value in found.items() if key not in ORDER}


TEMPLATE_LIST = _templates()


def known(key: str) -> bool:
    return key in TEMPLATE_LIST


def fields_of(key: str) -> list[dict[str, Any]]:
    return TEMPLATE_LIST[key]["fields"] if key in TEMPLATE_LIST else []


def clean(key: str, form) -> dict[str, str]:
    """Lo que llegó del formulario, recortado a los campos que la plantilla
    declara y a la longitud que cada uno admite.

    Lo que no esté declarado se descarta: la plantilla manda, no el formulario,
    que se escribe a mano.
    """
    filled: dict[str, str] = {}
    for field in fields_of(key):
        value = (form.get(field["name"]) or "").strip()
        top = field.get("max")
        filled[field["name"]] = value[:top] if top else value
    return filled


def missing(key: str, filled: dict[str, str]) -> list[str]:
    """Los campos obligatorios que quedaron vacíos."""
    return [f["name"] for f in fields_of(key)
            if f.get("required") and not filled.get(f["name"])]


def drawn(key: str, filled: dict[str, str]) -> dict[str, str]:
    """Lo escrito, con las imágenes convertidas en dirección.

    En la pieza se guarda el nombre del archivo y no su dirección: así la pieza
    no se rompe si cambia el dominio, y sobre todo no hay forma de colar una
    imagen de otro sitio escribiendo en el campo escondido del formulario. La
    dirección entera se arma aquí, en el único momento en que hace falta.
    """
    ready = dict(filled)
    for field in fields_of(key):
        if field.get("type") == "image" and ready.get(field["name"]):
            ready[field["name"]] = imaging.url_of(ready[field["name"]])
    return ready


# El ala del pie del plan Básico (la genera build_assets.py). Con la dirección
# entera: el correo se abre lejos del panel.
LOGO_URL = f"{Config.APP_BASE_URL}/static/img/email-logo.png"


def body(key: str, filled: dict[str, str]) -> str:
    """Solo la pieza del cliente, sin lo que se inyecta."""
    return _env.get_template(f"{key}.html").render(**drawn(key, filled))


def email(key: str, filled: dict[str, str], *, plan: str | None,
          unsubscribe: str = "#", preview: bool = False, postal: str = "",
          watermark: bool | None = None, extra: str = "") -> str:
    """El correo entero, tal como saldría.

    `unsubscribe` es el enlace de baja, único por destinatario. En la vista
    previa todavía no hay destinatario, así que va uno de mentira y el pie lo
    dice, para que nadie lo pruebe pensando que se dio de baja.

    `watermark` y `extra` son los del correo individual, que puede salir de
    una plantilla (octubre de 2026): sin marca de agua, y con el botón de su
    archivo justo encima del pie.
    """
    return _env.get_template("_wrap.html").render(
        # Ya viene escapado de su propia plantilla, que también va con
        # autoescape: sin esto el sobre lo escaparía otra vez y el correo
        # llegaría con las etiquetas a la vista.
        cuerpo=Markup(body(key, filled) + extra),
        unsubscribe=unsubscribe,
        preview=preview,
        watermark=plans.has_watermark(plan) if watermark is None else watermark,
        logo=LOGO_URL,
        postal=postal,
    )


def text_to_html(text: str) -> str:
    """El texto de un correo individual como cuerpo de correo: escapado, un
    párrafo por cada línea en blanco y los saltos de línea respetados."""
    blocks = [block.strip("\n") for block in
              str(text or "").replace("\r\n", "\n").split("\n\n")]
    paragraphs = "".join(
        '<p style="margin:0 0 16px">' + str(escape(block)).replace("\n", "<br>") + "</p>"
        for block in blocks if block.strip())
    return ('<div style="padding:28px 24px;font-family:Arial,Helvetica,sans-serif;'
            'font-size:15px;line-height:1.55;color:#1f2933">' + paragraphs + "</div>")


def email_from_body(body: str, *, plan: str | None, unsubscribe: str = "#",
                    preview: bool = False, style: str = "", postal: str = "",
                    bare: bool = False, watermark: bool | None = None) -> str:
    """Un correo a partir de un cuerpo ya armado por nosotros, como el del
    lienzo: el mismo sobre que las prediseñadas, con la baja, la dirección
    postal y la marca de agua por fuera.

    `body` tiene que venir ya escapado: aquí va dentro sin tocarlo. `style`
    son reglas CSS nuestras para la cabecera (las del modo oscuro).

    Con `bare` sale **sin el pie**: es el HTML que se baja para volver a
    cargarlo, y al cargarlo `email_from_html()` le pone el pie al enviar. Con
    el pie dentro saldría dos veces, y uno con una baja que no hace nada.

    El correo individual pasa `unsubscribe=""` y `watermark=False`: sale sin
    baja y sin marca de agua (octubre de 2026). Sin decir nada, la marca la
    decide el plan, como siempre.
    """
    return _env.get_template("_wrap.html").render(
        cuerpo=Markup(body),
        estilo=Markup(style),
        unsubscribe=unsubscribe,
        preview=preview,
        watermark=plans.has_watermark(plan) if watermark is None else watermark,
        logo=LOGO_URL,
        postal=postal,
        sin_pie=bare,
    )


def logo_header(url: str, *, alt: str, width: int, height: int) -> str:
    """El logo de la empresa arriba de un correo escrito (octubre de 2026),
    centrado y a su medida: los lectores de correo no respetan `max-height`,
    así que el ancho y el alto se calculan antes (`sender.logo_block`)."""
    return ('<div style="padding:28px 24px 0;text-align:center">'
            f'<img src="{escape(url)}" width="{int(width)}" height="{int(height)}" '
            f'alt="{escape(alt)}" style="display:inline-block;border:0;'
            f'width:{int(width)}px;height:{int(height)}px"></div>')


def download_button(*, url: str, name: str, size: str) -> str:
    """El botón «Descargar» del archivo de un correo individual, en tablas
    como todo lo demás del correo. Lleva `ses:no-track`: el clic que importa lo
    anota la página de la descarga, no el contador de SES."""
    return _env.get_template("_download.html").render(url=url, name=name, size=size)


def foot(*, plan: str | None, unsubscribe: str = "#",
         preview: bool = False, postal: str = "", watermark: bool | None = None) -> str:
    """Solo lo que ponemos nosotros: la baja, la dirección postal y la marca.

    Existe aparte porque a una pieza subida por el cliente no se le puede poner
    un sobre alrededor: ya es un documento entero, con su `<html>` y su
    `<body>`. Lo que se le hace es meterle esto dentro, antes de que cierre.
    """
    return _env.get_template("_foot.html").render(
        unsubscribe=unsubscribe, preview=preview,
        watermark=plans.has_watermark(plan) if watermark is None else watermark,
        logo=LOGO_URL, postal=postal)


# Dónde termina el documento de un cliente. Se busca sin distinguir mayúsculas
# porque el HTML lo escribió otro.
CLOSING = re.compile(r"</body\s*>", re.IGNORECASE)


def email_from_html(html: str, *, plan: str | None, unsubscribe: str = "#",
                    preview: bool = False, postal: str = "",
                    watermark: bool | None = None, extra: str = "") -> str:
    """Un correo a partir del HTML que subió el cliente.

    Se le inyecta el pie justo antes de que cierre el cuerpo; si no cierra
    —`services/html_check.py` no lo exige—, se le pega al final. De las dos
    formas la baja sale **dentro** del correo y no la puede quitar nadie
    editando su archivo, que es de lo que trata la regla 3.

    `watermark` y `extra` son los del correo individual (ver `email()`): el
    botón de su archivo va justo antes del pie.
    """
    pie = extra + foot(plan=plan, unsubscribe=unsubscribe, preview=preview,
                       postal=postal, watermark=watermark)
    found = list(CLOSING.finditer(html))
    if not found:
        return html + pie
    last = found[-1]
    return html[:last.start()] + pie + html[last.start():]


def as_json(filled: dict[str, str]) -> str:
    """Lo escrito, para guardarlo tal cual y poder reabrirlo."""
    return json.dumps(filled, ensure_ascii=False)
