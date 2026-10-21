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

import json
import math
import re
import secrets
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

# Una columna de tipo lista (octubre de 2026): varias filas dentro de un mismo
# contacto, como sus transacciones, cada fila con sus datos (de los cuatro tipos
# de arriba). Vive dentro del contacto, así que va con topes.
LIST = "list"
LIST_ITEMS_MAX = 6
LIST_ROWS_MAX = 50
LIST_BYTES_MAX = 3 * 1024
LISTS_MAX = 2
# Cada fila lleva su propio id, para cambiar o borrar esa y no otra aunque entre
# una nueva en ese momento.
ROW_ID = "id"
ROW_ID_SHAPE = re.compile(r"^[0-9a-f]{6}$")

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
        # El símbolo de la moneda delante: «B/.» o «$». Solo eso: un punto
        # suelto es el de los decimales, y «.5» es medio, no cinco.
        plain = re.sub(r"^(?:B/\.?|\$)", "", plain)
        try:
            number = float(plain)
        except ValueError:
            return None
        # «inf» y «nan» los entiende float(), pero no son un monto.
        if not math.isfinite(number):
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


def is_list(one: dict[str, Any] | None) -> bool:
    return (one or {}).get("type") == LIST


def scalars(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las columnas de un solo valor: las que piden el formulario y el CSV."""
    return [one for one in definitions if not is_list(one)]


def new_row_id() -> str:
    return secrets.token_hex(3)


def rows_size(rows: list[dict[str, Any]]) -> int:
    return len(json.dumps(rows, ensure_ascii=False).encode("utf-8"))


def parse_row(raw: Any, items: list[dict[str, Any]], *,
              keep_id: str | None = None) -> tuple[dict[str, str] | None, str]:
    """Una fila de una lista, cada dato por su tipo. Devuelve (fila, por qué
    no): `bad_row`, `empty`, `unknown:<CLAVE>` o `value:<CLAVE>`."""
    if not isinstance(raw, dict):
        return None, "bad_row"
    known = {one["key"]: one for one in items}
    row: dict[str, str] = {}
    for key, value in raw.items():
        if key == ROW_ID:
            continue
        one = known.get(key)
        if one is None:
            return None, f"unknown:{str(key)[:KEY_MAX]}"
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return None, f"value:{key}"
        parsed = parse(str(value), one.get("type", TEXT))
        if parsed is None:
            return None, f"value:{key}"
        if parsed:
            row[key] = parsed
    if not row:
        return None, "empty"
    given = raw.get(ROW_ID)
    row[ROW_ID] = keep_id or (given if isinstance(given, str)
                              and ROW_ID_SHAPE.match(given) else new_row_id())
    return row, ""


def parse_rows(raw: Any, items: list[dict[str, Any]]) -> tuple[list[dict[str, str]] | None, str]:
    """Todas las filas de una lista. Devuelve (filas, por qué no): además de
    los de `parse_row`, `too_many` (más de `LIST_ROWS_MAX`) y `too_big` (más de
    `LIST_BYTES_MAX`)."""
    if not isinstance(raw, list):
        return None, "bad_row"
    if len(raw) > LIST_ROWS_MAX:
        return None, "too_many"
    out: list[dict[str, str]] = []
    ids: set[str] = set()
    for one in raw:
        row, wrong = parse_row(one, items)
        if row is None:
            return None, wrong
        while row[ROW_ID] in ids:
            row[ROW_ID] = new_row_id()
        ids.add(row[ROW_ID])
        out.append(row)
    if rows_size(out) > LIST_BYTES_MAX:
        return None, "too_big"
    return out, ""


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

# Lo que trae todo contacto sin que nadie cree una columna: su nombre y su
# correo. Se escriben igual que las columnas (`*|NOMBRE|*`), y por eso nadie
# puede crear una columna con esas claves (`accounts.add_field`).
BUILT_IN = {"NOMBRE": ("name", "Nombre"), "CORREO": ("email", "Correo")}


def built_in_marks() -> list[dict[str, str]]:
    """Las dos que siempre hay, con su nombre, para los botones de marcas."""
    return [{"key": key, "label": label} for key, (_, label) in BUILT_IN.items()]


def mark(key: str) -> str:
    """La marca que se escribe dentro de la pieza para esa columna."""
    return f"*|{key}|*"


def values_of(contact: dict[str, Any] | None) -> dict[str, Any]:
    """Lo escrito en sus columnas: texto, y las filas de sus listas."""
    return dict((contact or {}).get("fields") or {})


# Una marca suelta, o un bloque: `*|#LISTA|* … *|/LISTA|*` se repite por cada
# fila de la lista, y `*|^LISTA|* … *|/LISTA|*` sale solo cuando está vacía. En
# una sola expresión, para que todo se cambie en una pasada: lo que se pone
# nunca se vuelve a leer, así un dato que diga `*|CORREO|*` sale tal cual.
TOKEN = re.compile(r"\*\|([#^])([A-Z0-9_]{1,%d})\|\*(.*?)\*\|/\2\|\*"
                   r"|\*\|([A-Z0-9_]{1,%d})\|\*" % (KEY_MAX, KEY_MAX), re.S)
BLOCK = re.compile(r"\*\|([#^])([A-Z0-9_]{1,%d})\|\*(.*?)\*\|/\2\|\*" % KEY_MAX, re.S)
# Lo que queda de un bloque dentro de otro, o de uno sin cerrar: no se repite.
LOOSE_BLOCK = re.compile(r"\*\|[#^/][A-Z0-9_]{1,%d}\|\*" % KEY_MAX)

# La tabla de una lista en el correo: en tablas y con estilos en línea, que es
# lo único que entienden todos los lectores de correo.
TABLE = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
         'style="border-collapse:collapse;margin:8px 0;font-size:inherit">')
CELL = "padding:6px 8px;border-bottom:1px solid #E4E4E7;text-align:left;"
HEAD = "padding:6px 8px;border-bottom:2px solid #D4D4D8;text-align:left;font-weight:700;"


def pretty_key(key: str) -> str:
    """El nombre de un dato que llegó por la API sin columna: «PRECIO_UNITARIO»
    se lee «Precio unitario»."""
    return key.replace("_", " ").strip().capitalize()


def table_html(rows: list[dict[str, Any]], items: list[dict[str, Any]],
               cell=None) -> str:
    """Una lista como tabla: los nombres de sus datos arriba y una fila por
    elemento. Cada valor escapado, y los números a la derecha."""
    def align(one) -> str:
        return "text-align:right;" if one.get("type") == NUMBER else ""

    head = "".join(f'<th style="{HEAD}{align(one)}">{escape(one.get("label", one["key"]))}</th>'
                   for one in items)
    body = "".join(
        "<tr>" + "".join(
            f'<td style="{CELL}{align(one)}">'
            + (cell(one) if cell else str(escape(show(str(row.get(one["key"], "")),
                                                      one.get("type", TEXT)))))
            + "</td>" for one in items) + "</tr>"
        for row in rows)
    return f"{TABLE}<tr>{head}</tr>{body}</table>"


def fill(text: str, contact: dict[str, Any] | None,
         definitions: list[dict[str, Any]], *, html: bool = True,
         data: dict[str, Any] | None = None) -> str:
    """Cambiar cada marca por lo que dice ese contacto.

    **El valor se escapa** cuando va dentro de un correo: lo escribió otro y el
    HTML de alrededor es nuestro. En el asunto no, porque ahí `&` es `&` y
    escaparlo lo llenaría de `&amp;`.

    Una marca que nombra una columna que ya no existe se queda en blanco. Es lo
    que pasa cuando se borra una columna que alguna pieza todavía nombra, y
    dejar la marca a la vista sería mandar `*|CIUDAD|*` a mil personas.

    **Las listas** (octubre de 2026): una marca sola arma su tabla, y un bloque
    `*|#LISTA|* … *|/LISTA|*` se repite por cada fila, con las marcas de la fila
    (y las del contacto) dentro; `*|^LISTA|* … *|/LISTA|*` sale cuando está
    vacía. Con una columna de un valor, el mismo bloque sale si tiene algo
    escrito, y `^` si no. En el asunto, una lista no escribe nada.

    `data` son los datos de un correo de la API, que mandan sobre los del
    contacto y pueden traer sus propias listas.
    """
    if not text or "*|" not in text:
        return text
    known = {one["key"]: one for one in definitions}
    values = values_of(contact)
    data = data or {}

    def out(value: str) -> str:
        return str(escape(value)) if html else value

    def rows_of(key: str):
        """Las filas y los datos de esa marca, si es una lista; si no, None."""
        given = data.get(key)
        if isinstance(given, list):
            rows = [one for one in given if isinstance(one, dict)]
            keys: list[str] = []
            for one in rows:
                keys += [name for name in one if name != ROW_ID and name not in keys]
            return rows, [{"key": name, "label": pretty_key(name), "type": TEXT}
                          for name in keys]
        one = known.get(key)
        if is_list(one) and key not in data:
            rows = [row for row in (values.get(key) or []) if isinstance(row, dict)]
            return rows, list(one.get("items") or [])
        return None

    def scalar_of(key: str) -> str | None:
        if key in data:
            return str(data[key])
        one = known.get(key)
        if one is not None:
            return show(values.get(key, ""), one.get("type", TEXT))
        if key in BUILT_IN:
            return str((contact or {}).get(BUILT_IN[key][0]) or "")
        return None

    def single(key: str, row=None, row_items=None) -> str:
        if row is not None and key in row_items:
            return out(show(str(row.get(key, "")), row_items[key].get("type", TEXT)))
        found = rows_of(key)
        if found is not None:
            return table_html(*found) if html else ""
        value = scalar_of(key)
        return out(value) if value is not None else ""

    def inside(inner: str, row=None, row_items=None) -> str:
        return MARK.sub(lambda found: single(found.group(1), row, row_items),
                        LOOSE_BLOCK.sub("", inner))

    def swap(found: re.Match) -> str:
        if found.group(4) is not None:
            return single(found.group(4))
        kind, key, inner = found.group(1), found.group(2), found.group(3)
        listed = rows_of(key)
        if listed is not None:
            rows, items = listed
            if kind == "^":
                return "" if rows else inside(inner)
            by_key = {one["key"]: one for one in items}
            return "".join(inside(inner, row, by_key) for row in rows)
        written = bool(scalar_of(key))
        if kind == "^":
            return "" if written else inside(inner)
        return inside(inner) if written else ""

    return TOKEN.sub(swap, text)


def marks_in(text: str, definitions: list[dict[str, Any]],
             data: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    """Lo que nombra un texto (octubre de 2026): sus marcas sueltas y las
    claves de sus bloques, cada lista en orden y sin repetir. Dentro de un
    bloque, las marcas de la fila son de la lista y no cuentan; las demás sí."""
    known = {one["key"]: one for one in definitions}
    data = data or {}
    marks: list[str] = []
    blocks: list[str] = []

    def add(where: list[str], key: str) -> None:
        if key not in where:
            where.append(key)

    def scan(found: re.Match) -> str:
        if found.group(4) is not None:
            add(marks, found.group(4))
            return ""
        key, inner = found.group(2), found.group(3)
        add(blocks, key)
        given = data.get(key)
        if isinstance(given, list):
            row = {name for one in given if isinstance(one, dict) for name in one}
        else:
            row = {item["key"] for item in (known.get(key) or {}).get("items") or []}
        for inside in MARK.findall(LOOSE_BLOCK.sub("", inner)):
            if inside not in row:
                add(marks, inside)
        return ""

    TOKEN.sub(scan, text or "")
    return marks, blocks


def lacking(text: str, contact: dict[str, Any] | None,
            definitions: list[dict[str, Any]],
            data: dict[str, Any] | None = None) -> list[str]:
    """Las marcas sueltas de un texto que no tienen con qué llenarse: ni en
    `data`, ni en una columna llena del contacto, ni en su nombre. Una lista
    nunca falta, que puede ir vacía; un bloque tampoco, que sin datos no sale."""
    data = data or {}
    known = {one["key"]: one for one in definitions}
    values = values_of(contact)
    out: list[str] = []
    for key in marks_in(text, definitions, data)[0]:
        if key in data or is_list(known.get(key)):
            continue
        if key in known and values.get(key):
            continue
        if key in BUILT_IN and (contact or {}).get(BUILT_IN[key][0]):
            continue
        out.append(key)
    return out


# Cómo se ve una marca en la vista previa: una pastilla con el nombre del dato,
# para que se lea de un vistazo que ahí va algo distinto en cada correo. Solo en
# la vista previa; al enviar va el dato de cada quien, sin adornos.
PILL = ("background:#E0F2FE;color:#075985;border-radius:6px;padding:0 6px;"
        "font-weight:600;")
TAG = re.compile(r"(<[^>]*>)")


def _pill(label: str) -> str:
    return f'<span style="{PILL}">{escape(label)}</span>'


def preview_fill(html: str, definitions: list[dict[str, Any]]) -> str:
    """El correo de la vista previa, con cada marca como pastilla.

    Solo en el texto: una marca dentro de un atributo (el enlace de un botón)
    se llena con el nombre a secas, porque una etiqueta ahí dentro rompería el
    atributo. Una lista sale como su tabla con dos filas de pastillas, y un
    bloque, una vez, con las marcas de la fila en pastillas.
    """
    names = {one["key"]: one.get("label", one["key"]) for one in definitions}
    names.update({key: label for key, (_, label) in BUILT_IN.items()
                  if key not in names})
    lists = {one["key"]: one for one in definitions if is_list(one)}

    def marks(text: str, here: dict[str, str]) -> str:
        def pill(found: re.Match) -> str:
            key = found.group(1)
            if key in lists:
                items = list(lists[key].get("items") or [])
                return table_html([{}, {}], items,
                                  cell=lambda one: _pill(one.get("label", one["key"])))
            label = here.get(key)
            return "" if label is None else _pill(label)

        def plain(found: re.Match) -> str:
            key = found.group(1)
            return "" if key in lists else str(escape(here.get(key, "")))

        return "".join(MARK.sub(plain if part.startswith("<") else pill, part)
                       for part in TAG.split(text))

    def block(found: re.Match) -> str:
        one = lists.get(found.group(2))
        items = {item["key"]: item.get("label", item["key"])
                 for item in (one or {}).get("items") or []}
        return marks(LOOSE_BLOCK.sub("", found.group(3)), {**names, **items})

    return marks(BLOCK.sub(block, html or ""), names)


def sample(definitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Un contacto de mentira para la vista previa.

    Cada marca se dibuja con **el nombre de su columna**, que enseña dónde va
    cada dato sin inventarse un valor que después no se parezca al de nadie.
    Una lista, con una fila con el nombre de cada dato.
    """
    return {"fields": {one["key"]: ([{item["key"]: item.get("label", item["key"])
                                      for item in one.get("items") or []}]
                                    if is_list(one) else one.get("label", one["key"]))
                       for one in definitions}}


def missing(contact: dict[str, Any] | None,
            definitions: list[dict[str, Any]]) -> list[str]:
    """Qué columnas le faltan a ese contacto. Vacío es que está completo.

    Es lo que decide quién recibe un correo y quién no: al que le falte un dato
    no se le manda nada hasta que lo tenga. Una lista puede ir vacía.
    """
    values = values_of(contact)
    return [one["label"] for one in scalars(definitions) if not values.get(one["key"])]
