"""A quién sale un envío masivo, además de sus etiquetas (octubre de 2026).

Una campaña ya elegía etiquetas («quien tenga alguna»). Ahora puede llevar
además **condiciones sobre las columnas** de cada contacto, y salir a quien
cumpla **todas** o **alguna**:

  * un número mayor, menor o igual que otro;
  * un texto que es, contiene o empieza con otro (sin importar mayúsculas);
  * una fecha antes o después de otra, o ese mismo día;
  * un sí o un no;
  * y de una lista (las transacciones de un socio): **cuántas filas** tiene,
    si **alguna fila** cumple algo con uno de sus datos, o **la suma** de un
    dato numérico de todas sus filas.

Se guarda en la campaña (`campaigns.filters`) así:

    {"match": "all" | "any",
     "rules": [{"field": "MONTO", "op": "gt", "value": "100"},
               {"field": "TRANSACCIONES", "measure": "rows", "op": "gt", "value": "3"},
               {"field": "TRANSACCIONES", "measure": "any", "item": "FECHA",
                "op": "after", "value": "2026-10-01"},
               {"field": "TRANSACCIONES", "measure": "sum", "item": "MONTO",
                "op": "gte", "value": "500"}]}

Un solo sitio para las tres cosas que se hacen con eso, así el panel, la API, la
cuenta en vivo y el envío por tandas no pueden contar distinto:

  * `parse()`: lo que llegó (de un formulario o de la API), validado contra las
    columnas de la cuenta; la clave existe, el operador es de su tipo y el valor
    pasa por `fields.parse`. Nada de lo que llega se usa sin pasar por aquí.
  * `query()`: la condición de Mongo, que se suma al `$and` de
    `contact._matching()`. **Vuelve a validar al enviar**: si después de
    guardar se borró la columna o cambió su tipo, la campaña no sale
    (`Stale`) en lugar de salir a más gente de la elegida.
  * `describe()`: la frase que se lee («Monto mayor que 100 y Transacciones con
    más de 3 filas»).

Todo se guarda como texto en el contacto, así que cada tipo se compara a su
manera: las fechas como texto `AAAA-MM-DD` (que ordena bien); los números con
`$expr` y `$convert` a decimal (no a double: 0.1 + 0.2 no falla por un pelo);
el texto con una expresión escapada. **Un valor vacío, que falta o mal escrito
no cumple nunca**, ni siquiera «menor que» ni «distinto de»: en Mongo lo que
falta es menor que cualquier número, y `$ne` acepta lo que falta, así que cada
comparación lleva su guarda.
"""

from __future__ import annotations

import re
from decimal import Decimal, localcontext
from typing import Any

from bson.decimal128 import Decimal128
from bson.regex import Regex

from i18n import t
from services import fields

ALL, ANY = "all", "any"
MATCHES = (ALL, ANY)
MAX_RULES = 10
VALUE_MAX = fields.VALUE_MAX

# Los operadores de cada tipo, en el orden en que se ofrecen.
COMPARE = ("eq", "ne", "gt", "gte", "lt", "lte")
OPS = {
    fields.NUMBER: COMPARE,
    fields.TEXT: ("eq", "ne", "contains", "not_contains", "starts"),
    fields.DATE: ("on", "before", "after"),
    fields.YESNO: ("yes", "no"),
}
# De una lista: cuántas filas, alguna fila cumple, o la suma de un dato.
ROWS, SOME, SUM = "rows", "any", "sum"
MEASURES = (ROWS, SOME, SUM)
# Los que no llevan valor: el sí y el no.
NO_VALUE = ("yes", "no")

_MONGO = {"eq": "$eq", "ne": "$ne", "gt": "$gt", "gte": "$gte", "lt": "$lt",
          "lte": "$lte"}


class Stale(Exception):
    """Una condición guardada que ya no vale: su columna se borró, cambió de
    tipo o perdió el dato. Lleva la columna, para decir cuál."""

    def __init__(self, field: str):
        super().__init__(field)
        self.field = field


# --------------------------------------------------------------- validar

def _definition(definitions, key: str) -> dict[str, Any] | None:
    return next((one for one in definitions if one["key"] == key), None)


def _item(definition: dict[str, Any], key: str) -> dict[str, Any] | None:
    return next((one for one in definition.get("items") or [] if one["key"] == key), None)


def _clean_value(kind: str, op: str, raw: Any) -> str | None:
    """El valor de la regla, normalizado como los de los contactos, o None."""
    if op in NO_VALUE:
        return ""
    text = str(raw if raw is not None else "").strip()
    if not text or len(text) > VALUE_MAX:
        return None
    value = fields.parse(text, kind)
    if kind == fields.NUMBER and value and _to_decimal(value) is None:
        return None
    return value or None


def _count(raw: Any) -> str | None:
    """Una cantidad de filas: un entero de 0 al tope de filas."""
    text = str(raw if raw is not None else "").strip()
    if not re.fullmatch(r"\d{1,3}", text) or int(text) > fields.LIST_ROWS_MAX:
        return None
    return str(int(text))


def check_rule(raw: dict[str, Any], definitions) -> tuple[dict[str, str] | None, str]:
    """Una regla limpia, o None y por qué no vale (la clave de su frase)."""
    if not isinstance(raw, dict):
        return None, "audience_bad_rule"
    # Cada parte con su tipo (llega también de la API): un objeto donde va un
    # texto no se convierte en texto, se rechaza.
    if any(name in raw and raw[name] is not None and not isinstance(raw[name], str)
           for name in ("field", "op", "measure", "item")):
        return None, "audience_bad_rule"
    given = raw.get("value")
    if given is not None and (isinstance(given, bool)
                              or not isinstance(given, (str, int, float))):
        return None, "audience_bad_value"
    key = str(raw.get("field") or "")
    definition = _definition(definitions, key)
    if definition is None:
        return None, "audience_bad_field"
    op = str(raw.get("op") or "")
    if fields.is_list(definition):
        measure = str(raw.get("measure") or "")
        if measure not in MEASURES:
            return None, "audience_bad_measure"
        if measure == ROWS:
            if op not in COMPARE:
                return None, "audience_bad_op"
            value = _count(raw.get("value"))
            if value is None:
                return None, "audience_bad_count"
            return {"field": key, "measure": ROWS, "op": op, "value": value}, ""
        item = _item(definition, str(raw.get("item") or ""))
        if item is None:
            return None, "audience_bad_item"
        kind = item.get("type", fields.TEXT)
        if measure == SUM and kind != fields.NUMBER:
            return None, "audience_bad_sum"
        allowed = COMPARE if measure == SUM else OPS.get(kind, OPS[fields.TEXT])
        if op not in allowed:
            return None, "audience_bad_op"
        value = _clean_value(fields.NUMBER if measure == SUM else kind, op, raw.get("value"))
        if value is None:
            return None, "audience_bad_value"
        return {"field": key, "measure": measure, "item": item["key"], "op": op,
                "value": value}, ""
    kind = definition.get("type", fields.TEXT)
    if op not in OPS.get(kind, OPS[fields.TEXT]):
        return None, "audience_bad_op"
    value = _clean_value(kind, op, raw.get("value"))
    if value is None:
        return None, "audience_bad_value"
    return {"field": key, "op": op, "value": value}, ""


def parse(raw: Any, definitions) -> tuple[dict[str, Any] | None, list[tuple[int, str]]]:
    """Las condiciones limpias, o None y qué falló: `[(número de regla, clave)]`
    (con -1 para lo que es de todas). Sin reglas es None y sin problemas: la
    campaña sale a sus etiquetas, como siempre."""
    if raw in (None, "", {}):
        return None, []
    if not isinstance(raw, dict):
        return None, [(-1, "audience_bad_shape")]
    rules = raw.get("rules") or []
    if not isinstance(rules, list):
        return None, [(-1, "audience_bad_shape")]
    match = raw.get("match") or ALL
    if not isinstance(match, str):
        match = ""
    problems: list[tuple[int, str]] = []
    if match not in MATCHES:
        problems.append((-1, "audience_bad_match"))
    if len(rules) > MAX_RULES:
        problems.append((-1, "audience_too_many"))
    clean = []
    for index, one in enumerate(rules[:MAX_RULES]):
        rule, why = check_rule(one, definitions)
        if rule is None:
            problems.append((index, why))
        else:
            clean.append(rule)
    if problems:
        return None, problems
    if not clean:
        return None, []
    return {"match": match, "rules": clean}, []


# --------------------------------------------------------------- consultar

def _to_decimal(value: str) -> Decimal128 | None:
    """El número de una regla como decimal de Mongo, o None si no lo es.

    Redondeado a 34 cifras, que es lo que cabe: un número más largo (un id de 40
    dígitos escrito en una columna de número) no se puede guardar exacto, y
    `Decimal128` se negaría en vez de redondear."""
    try:
        with localcontext() as context:
            context.prec = 34
            number = +Decimal(str(value))
        if not number.is_finite():
            return None
        return Decimal128(number)
    except (ArithmeticError, ValueError):
        return None


def _target(rule: dict[str, str]) -> Decimal128:
    """El número de una regla guardada; si ya no lo es, la regla no vale."""
    number = _to_decimal(rule["value"])
    if number is None:
        raise Stale(rule["field"])
    return number


def _as_number(path: str, otherwise=None) -> dict[str, Any]:
    """Un valor guardado como texto, como número; lo que no lo es, `otherwise`."""
    return {"$convert": {"input": path, "to": "decimal", "onError": otherwise,
                         "onNull": otherwise}}


def _number_test(path: str, op: str, target: Decimal128) -> dict[str, Any]:
    """Comparar un número guardado como texto. Lo vacío o mal escrito no cumple."""
    number = _as_number(path)
    return {"$and": [{"$ne": [number, None]}, {_MONGO[op]: [number, target]}]}


def _pattern(op: str, value: str) -> str:
    plain = re.escape(value)
    return {"eq": f"^{plain}$", "ne": f"^{plain}$", "contains": plain,
            "not_contains": plain, "starts": f"^{plain}"}[op]


def _filled() -> dict[str, Any]:
    return {"$exists": True, "$nin": ["", None]}


def _plain_test(kind: str, op: str, value: str) -> dict[str, Any]:
    """La condición sobre un valor de texto, fecha o sí/no (sin `$expr`), para
    ponerla bajo su ruta: `{ruta: esto}` o dentro de un `$elemMatch`."""
    if kind == fields.DATE:
        shape = {"$regex": r"^\d{4}-\d{2}-\d{2}$"}
        if op == "on":
            return {"$eq": value}
        if op == "before":
            return {**shape, "$lt": value}
        return {**shape, "$gt": value}
    if kind == fields.YESNO:
        return {"$eq": "si" if op == "yes" else "no"}
    if op in ("ne", "not_contains"):
        return {**_filled(), "$not": Regex(_pattern(op, value), "i")}
    return {"$regex": _pattern(op, value), "$options": "i"}


def _array(path: str) -> dict[str, Any]:
    """Las filas de una lista, o ninguna: muchos contactos no tienen la lista, y
    `$size` o `$map` sobre algo que no es lista revientan."""
    return {"$cond": [{"$isArray": path}, path, []]}


def _rule(rule: dict[str, str], definitions) -> dict[str, Any]:
    definition = _definition(definitions, rule["field"])
    path = f"fields.{rule['field']}"
    measure = rule.get("measure")
    if definition is None or bool(measure) != fields.is_list(definition):
        raise Stale(rule["field"])
    if measure == ROWS:
        return {"$expr": {_MONGO[rule["op"]]: [{"$size": _array("$" + path)},
                                              int(rule["value"])]}}
    if measure in (SOME, SUM):
        item = _item(definition, rule.get("item", ""))
        if item is None:
            raise Stale(rule["field"])
        kind = item.get("type", fields.TEXT)
        if measure == SUM:
            if kind != fields.NUMBER:
                raise Stale(rule["field"])
            total = {"$sum": {"$map": {"input": _array("$" + path), "as": "row",
                                       "in": _as_number(f"$$row.{item['key']}",
                                                        Decimal128("0"))}}}
            return {"$expr": {_MONGO[rule["op"]]: [total, _target(rule)]}}
        if rule["op"] not in OPS.get(kind, ()):
            raise Stale(rule["field"])
        if kind == fields.NUMBER:
            # `$expr` no vale dentro de `$elemMatch`: una fila que cumple, mirada
            # desde arriba.
            return {"$expr": {"$anyElementTrue": [{"$map": {
                "input": _array("$" + path), "as": "row",
                "in": _number_test(f"$$row.{item['key']}", rule["op"], _target(rule))}}]}}
        return {path: {"$elemMatch": {item["key"]: _plain_test(kind, rule["op"],
                                                               rule["value"])}}}
    kind = definition.get("type", fields.TEXT)
    if rule["op"] not in OPS.get(kind, ()):
        raise Stale(rule["field"])
    if kind == fields.NUMBER:
        return {"$expr": _number_test("$" + path, rule["op"], _target(rule))}
    return {path: _plain_test(kind, rule["op"], rule["value"])}


def query(filters: dict[str, Any] | None, definitions) -> dict[str, Any] | None:
    """La condición de Mongo de esas reglas, o None si no hay. `Stale` si una ya
    no vale con las columnas de hoy: no se salta, porque saltarla mandaría la
    campaña a más gente de la elegida."""
    if not filters or not filters.get("rules"):
        return None
    parts = [_rule(rule, definitions) for rule in filters["rules"]]
    if len(parts) == 1:
        return parts[0]
    return {"$or" if filters.get("match") == ANY else "$and": parts}


# --------------------------------------------------------------- decir

def _shown(kind: str, value: str) -> str:
    return fields.show(value, kind) if kind != fields.TEXT else f"«{value}»"


def problem_text(index: int, why: str) -> str:
    """La frase de un problema de `parse()`: «Condición 2: ese operador no va
    con esa columna.» La usan el panel y la API."""
    message = t(why, n=MAX_RULES, rows=fields.LIST_ROWS_MAX)
    return t("audience_row_problem", n=index + 1, why=message) if index >= 0 else message


def describe_rule(rule: dict[str, str], definitions) -> str:
    definition = _definition(definitions, rule["field"]) or {"label": rule["field"]}
    label = definition.get("label", rule["field"])
    measure = rule.get("measure")
    if measure == ROWS:
        return t(f"audience_rows_{rule['op']}", field=label, n=rule["value"])
    if measure in (SOME, SUM):
        item = _item(definition, rule.get("item", "")) or {"label": rule.get("item", ""),
                                                           "type": fields.TEXT}
        kind = fields.NUMBER if measure == SUM else item.get("type", fields.TEXT)
        test = t(f"audience_op_{rule['op']}", field=item.get("label", ""),
                 value=_shown(kind, rule.get("value", "")))
        return t(f"audience_{measure}", field=label, item=item.get("label", ""),
                 test=test)
    kind = definition.get("type", fields.TEXT)
    return t(f"audience_op_{rule['op']}", field=label,
             value=_shown(kind, rule.get("value", "")))


def describe(filters: dict[str, Any] | None, definitions) -> str:
    """La frase que se lee: «Monto mayor que 100 y Transacciones con más de 3
    filas». Vacío sin reglas."""
    if not filters or not filters.get("rules"):
        return ""
    joiner = t("audience_join_any" if filters.get("match") == ANY else "audience_join_all")
    return joiner.join(describe_rule(rule, definitions) for rule in filters["rules"])


def choices(definitions) -> list[dict[str, str]]:
    """Lo que se puede elegir en la pantalla, una opción por cosa: cada columna,
    y de cada lista sus filas, alguno de sus datos y la suma de los numéricos.
    `value` es lo que manda el formulario («MONTO», «TRANSACCIONES:rows»,
    «TRANSACCIONES:any:FECHA», «TRANSACCIONES:sum:MONTO») y `kind` qué
    operadores le tocan."""
    out = []
    for one in definitions:
        if not fields.is_list(one):
            out.append({"value": one["key"], "label": one.get("label", one["key"]),
                        "kind": one.get("type", fields.TEXT)})
            continue
        label = one.get("label", one["key"])
        out.append({"value": f"{one['key']}:{ROWS}",
                    "label": t("audience_choice_rows", field=label), "kind": "count"})
        for item in one.get("items") or []:
            out.append({"value": f"{one['key']}:{SOME}:{item['key']}",
                        "label": t("audience_choice_any", field=label,
                                   item=item.get("label", item["key"])),
                        "kind": item.get("type", fields.TEXT)})
        for item in one.get("items") or []:
            if item.get("type") == fields.NUMBER:
                out.append({"value": f"{one['key']}:{SUM}:{item['key']}",
                            "label": t("audience_choice_sum", field=label,
                                       item=item.get("label", item["key"])),
                            "kind": "count_number"})
    return out


def from_choice(value: str, op: str, raw: str) -> dict[str, str]:
    """Una regla a partir de lo que manda una fila del formulario."""
    parts = (value or "").split(":")
    if len(parts) == 2 and parts[1] == ROWS:
        return {"field": parts[0], "measure": ROWS, "op": op, "value": raw}
    if len(parts) == 3 and parts[1] in (SOME, SUM):
        return {"field": parts[0], "measure": parts[1], "item": parts[2], "op": op,
                "value": raw}
    return {"field": parts[0] if parts else "", "op": op, "value": raw}


def to_choice(rule: dict[str, str]) -> str:
    """Lo contrario: la opción del formulario de una regla guardada."""
    if rule.get("measure") == ROWS:
        return f"{rule['field']}:{ROWS}"
    if rule.get("measure") in (SOME, SUM):
        return f"{rule['field']}:{rule['measure']}:{rule.get('item', '')}"
    return rule.get("field", "")
