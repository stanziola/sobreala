"""Revisar el HTML que sube un cliente antes de guardarlo.

Lo que se rechaza está en CLAUDE.md y no es una lista de gustos: cada regla
existe porque el correo se envía en nombre de Panamails y todos los clientes
comparten la reputación del dominio.

  * `<script>`, `<iframe>`, `<object>` y los atributos de evento no los ejecuta
    ningún lector de correo serio, y un correo que los trae parece un ataque
    aunque no lo sea.
  * Nada de CSS ni JavaScript traído de fuera: un archivo remoto puede cambiar
    después de aprobada la pieza, así que aprobarla no significaría nada.
  * Los formularios dentro del correo son el patrón exacto del phishing.
  * Y **102 KB**: pasado eso Gmail recorta el correo, y lo que se pierde es el
    final, que es justo donde van el botón de baja y la marca de agua. Un
    correo recortado es un correo sin baja, y eso sí puede cerrar el negocio.

Se revisa con un parser, no con expresiones regulares: `< script >` y
`&lt;script&gt;` no son lo mismo, y una expresión regular acaba tratándolos
igual.
"""

from __future__ import annotations

from html.parser import HTMLParser

from config import Config

# Pasado esto Gmail recorta. Es un tope duro, no una recomendación.
MAX_BYTES = 102 * 1024

# Etiquetas que no pueden aparecer, pase lo que pase.
FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "applet", "form",
                  "base", "frame", "frameset"}

# Un atributo que empieza por «on» es un manejador de eventos: onclick, onload,
# onerror. No hace falta enumerarlos, y enumerarlos dejaría fuera el próximo.
EVENT_PREFIX = "on"

# De dónde puede venir una imagen. Nada de http: en un correo que se ve por
# HTTPS, y `javascript:` no es un origen, es código.
SAFE_SCHEMES = ("https://", "data:", "cid:", "/")


class Reader(HTMLParser):
    """Recorre el documento y anota lo que no puede quedarse."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.problems: list[str] = []
        self.seen_tags: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        self.seen_tags.add(tag)
        if tag in FORBIDDEN_TAGS:
            self.problems.append(f"tag:{tag}")
            return
        for name, value in attrs:
            name = (name or "").lower()
            value = (value or "").strip()
            if name.startswith(EVENT_PREFIX) and name != "on":
                self.problems.append(f"event:{name}")
            elif name == "href" and value.lower().startswith("javascript:"):
                self.problems.append("href:javascript")
            elif tag == "link" and name == "href" and value:
                # Una hoja de estilos de fuera: puede cambiar después de que la
                # pieza quede aprobada.
                self.problems.append("external:css")
            elif tag == "img" and name == "src" and value:
                # Las del propio panel entran aunque vayan por http, que es
                # como corre en desarrollo: en producción ya son https.
                own = value.startswith(f"{Config.APP_BASE_URL}/img/")
                if not (own or value.lower().startswith(SAFE_SCHEMES)):
                    self.problems.append("external:img")

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)


def check(raw: bytes) -> list[str]:
    """Devuelve los motivos por los que no se puede guardar. Vacío es que sí.

    Los motivos son claves, no frases: la pantalla las traduce, y así el mismo
    motivo se lee igual en el panel del cliente y en el del administrador.
    """
    problems: list[str] = []

    if not raw.strip():
        return ["empty"]
    if len(raw) > MAX_BYTES:
        problems.append("too_big")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return problems + ["not_utf8"]

    reader = Reader()
    try:
        reader.feed(text)
        reader.close()
    except Exception:  # noqa: BLE001 - un documento que ni se puede leer
        return problems + ["broken"]

    if not reader.seen_tags:
        # Ni una etiqueta: es texto suelto, no una pieza de correo.
        problems.append("broken")

    # Sin repetir: que haya tres <script> es el mismo problema una vez.
    for reason in reader.problems:
        if reason not in problems:
            problems.append(reason)
    return problems
