"""Las columnas propias de un contacto: definirlas, leerlas y escribirlas.

Además del correo y el nombre, cada cuenta define **sus** columnas —ciudad,
número de socio, monto, fecha de vencimiento— y las nombra dentro del correo
para que a cada persona le llegue su propio texto. Cuántas caben lo dice
`docs/pricing.md`, como las etiquetas y como los precios.

Tres decisiones que se notan en todo el archivo:

  * **El valor se guarda ya normalizado y siempre como texto.** Una fecha se
    guarda como `2026-03-15` y se escribe como «15 de marzo de 2026»; un número
    escrito «1,234.50» se guarda `1234.5`. Así el archivo de cada cliente puede
    venir como venga y el correo sale parejo.
  * **La marca es `*|CLAVE|*` y no `{{clave}}`.** El HTML de un cliente **no**
    puede pasar nunca por Jinja, que es el motor de plantillas del panel: sería
    dejar que un archivo subido ejecute código en el servidor. Lo que se hace
    aquí es una sustitución nuestra, con el valor escapado. Y esa forma tampoco
    choca con las llaves que ya usan el CSS y el HTML de nadie.
  * **Las columnas son obligatorias.** Un contacto solo entra en la base con
    todas llenas, y al que le falte una no le llega ningún correo. Por eso no
    hay texto de respaldo: tapar el hueco es lo contrario de enseñarlo.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from markupsafe import escape

from i18n import on_date

# Los tipos. Son pocos a propósito: cada uno tiene que ganarse el sitio
# haciendo algo distinto al leer el archivo y al escribir el correo.
TEXT = "text"
NUMBER = "number"
DATE = "date"
YESNO = "yesno"
TYPES = (TEXT, NUMBER, DATE, YESNO)

LABEL_MAX = 40
KEY_MAX = 24
# Lo que cabe en un valor. Un correo personalizado escribe un dato, no un
# párrafo, y esto es lo que impide que una celda con media hoja de cálculo
# dentro llegue a un buzón.
VALUE_MAX = 120

# Cómo se nombra una columna dentro de una pieza.
MARK = re.compile(r"\*\|([A-Z0-9_]{1,%d})\|\*" % KEY_MAX)

_SI = ("si", "sí", "s", "yes", "y", "1", "true", "verdadero", "x")
_NO = ("no", "n", "0", "false", "falso", "")

# Cómo puede venir escrita una fecha en el archivo de un cliente.
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d",
                 "%d.%m.%Y")


def fold(text: str) -> str:
    """Sin acentos y en minúsculas, para comparar dos títulos."""
    plain = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in plain if not unicodedata.combining(c)).strip().lower()


def clean_label(raw: str) -> str:
    """El nombre visible de una columna, sin espacios de más."""
    return " ".join((raw or "").split())[:LABEL_MAX]


def key_from(label: str) -> str:
    """«Número de socio» → `NUMERO_DE_SOCIO`, que es lo que se escribe dentro
    de la pieza.

    En mayúsculas y sin acentos porque va a la vista dentro de un correo a
    medio escribir, y ahí tiene que distinguirse del texto de alrededor.
    """
    plain = fold(label).upper()
    key = re.sub(r"[^A-Z0-9]+", "_", plain).strip("_")
    return key[:KEY_MAX].strip("_")


def clean_kind(raw: str) -> str:
    """El tipo que llegó del formulario, o texto si no es ninguno de los
    nuestros. Texto acepta cualquier cosa, así que es el que no puede perder
    datos."""
    return raw if raw in TYPES else TEXT


# --------------------------------------------------------------- los valores

def parse(raw: str, kind: str) -> str | None:
    """El valor tal como se guarda, o None si no es de ese tipo.

    None no es «vacío»: es «esto no es un número». Quien llama decide, y el
    importador lo deja sin escribir en vez de guardar basura.
    """
    value = " ".join((raw or "").split())[:VALUE_MAX]
    if not value:
        return ""
    if kind == NUMBER:
        plain = value.replace(",", "").replace(" ", "")
        plain = re.sub(r"^[$B/.]+", "", plain)
        try:
            number = float(plain)
        except ValueError:
            return None
        # Sin decimales cuando no los tiene: «3» y no «3.0».
        return str(int(number)) if number == int(number) else str(number)
    if kind == DATE:
        for shape in _DATE_FORMATS:
            try:
                return datetime.strptime(value, shape).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    if kind == YESNO:
        low = fold(value)
        if low in _SI:
            return "si"
        if low in _NO:
            return "no"
        return None
    return value


def show(value: str, kind: str) -> str:
    """Cómo se escribe ese valor dentro del correo."""
    if not value:
        return ""
    if kind == DATE:
        try:
            return on_date(datetime.strptime(value, "%Y-%m-%d"))
        except ValueError:
            return value
    if kind == YESNO:
        return "sí" if value == "si" else "no"
    return value


# ------------------------------------------------------- ponerlas en el texto

def mark(key: str) -> str:
    """La marca que se escribe dentro de la pieza para esa columna."""
    return f"*|{key}|*"


def values_of(contact: dict[str, Any] | None) -> dict[str, str]:
    return dict((contact or {}).get("fields") or {})


def fill(text: str, contact: dict[str, Any] | None,
         definitions: list[dict[str, Any]], *, html: bool = True) -> str:
    """Cambiar cada marca por lo que dice ese contacto.

    **El valor se escapa** cuando va dentro de un correo: lo escribió otro y el
    HTML de alrededor es nuestro. En el asunto no, porque ahí `&` es `&` y
    escaparlo lo llenaría de `&amp;`.

    Una marca que nombra una columna que ya no existe se queda en blanco. Es lo
    que pasa cuando se borra una columna que alguna pieza todavía nombra, y
    dejar la marca a la vista sería mandar `*|CIUDAD|*` a mil personas.
    """
    if not text or "*|" not in text:
        return text
    known = {one["key"]: one for one in definitions}
    values = values_of(contact)

    def swap(found: re.Match) -> str:
        key = found.group(1)
        one = known.get(key)
        if one is None:
            return ""
        written = show(values.get(key, ""), one.get("type", TEXT))
        return str(escape(written)) if html else written

    return MARK.sub(swap, text)


def sample(definitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Un contacto de mentira para la vista previa.

    Cada marca se dibuja con **el nombre de su columna**, que enseña dónde va
    cada dato sin inventarse un valor que después no se parezca al de nadie.
    """
    return {"fields": {one["key"]: one.get("label", one["key"])
                       for one in definitions}}


def missing(contact: dict[str, Any] | None,
            definitions: list[dict[str, Any]]) -> list[str]:
    """Qué columnas le faltan a ese contacto. Vacío es que está completo.

    Es lo que decide quién recibe un correo y quién no: al que le falte un dato
    no se le manda nada hasta que lo tenga.
    """
    values = values_of(contact)
    return [one["label"] for one in definitions if not values.get(one["key"])]
