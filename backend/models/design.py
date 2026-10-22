"""Los diseños de correo que sube un cliente.

Se llaman «diseños» y no «templates» por una razón práctica: en este proyecto
`templates/` ya son las plantillas Jinja del panel, y dos cosas distintas con el
mismo nombre se confunden en cada archivo que las toque. Para el cliente la
pantalla dice **Plantillas**, que es la palabra que él usa.

Aquí caben dos cosas, y el campo `source` dice cuál es cada una:

  * **`upload`**, el HTML que sube el cliente. Se guarda entero y tal como
    llegó: es lo que hay que poder volver a mirar cuando alguien pregunte qué
    se envió, y no se puede reconstruir.
  * **`builtin`**, una prediseñada del producto que el cliente llenó. De esta se
    guarda **de qué plantilla salió y qué escribió en cada casilla**, no el HTML
    armado. Guardar el resultado dejaría la pieza imposible de volver a editar,
    y además el archivo de la plantilla puede mejorar: al reabrirla se arma otra
    vez con lo que ella diga hoy.

Los archivos de las prediseñadas no viven en la base de datos: viajan con el
repositorio, en `email_templates/`, iguales para todos y sin nada que aprobar.

**Nadie aprueba una pieza a mano.** Lo que puede hacer daño lo rechaza el
validador al subirla —`services/html_check.py`— y eso es mecánico, no un
juicio. La única puerta con una persona detrás es la demostración que abre la
cuenta, y es sobre la empresa y su lista, no sobre el archivo. Tener las dos
serían dos revisiones manuales para la misma decisión.

Todo queda guardado y visible desde administración, que es lo que permite abrir
una pieza cuando haga falta.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

NAME_MAX = 80

# De dónde salió cada pieza. Va escrito en todos los documentos y no solo en los
# nuevos: un campo que a veces está es fácil de equivocar en una consulta.
UPLOAD = "upload"
BUILT_IN = "builtin"
# Hecha en el lienzo de «Crear plantilla»: se guardan las diapositivas con sus
# coordenadas y los nombres de los fondos ya fundidos, no el HTML. El correo se
# arma al enviar, con `services/canvas.py`.
CANVAS = "canvas"


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_name(raw: str) -> str:
    return " ".join((raw or "").split())[:NAME_MAX]


def save(db, account_id, *, name: str, html: str, uploaded_by=None) -> Any:
    """Guardar una pieza subida. Devuelve su id.

    El HTML se guarda entero y tal como llegó. Es lo que hay que poder volver a
    mirar cuando alguien pregunte qué se envió, y no se puede reconstruir.
    """
    return db.designs.insert_one({
        "account_id": account_id,
        "source": UPLOAD,
        "name": clean_name(name),
        "html": html,
        "bytes": len(html.encode("utf-8")),
        "uploaded_by": uploaded_by,
        "created_at": now(),
    }).inserted_id


def save_filled(db, account_id, *, name: str, template: str,
                filled: dict[str, str]) -> Any:
    """Guardar una prediseñada llena. Devuelve su id.

    Se guarda lo que escribió y no el correo armado, para que reabrirla
    devuelva las casillas como estaban.
    """
    return db.designs.insert_one({
        "account_id": account_id,
        "source": BUILT_IN,
        "template": template,
        "fields": dict(filled),
        "name": clean_name(name),
        "created_at": now(),
        "updated_at": now(),
    }).inserted_id


def update_filled(db, account_id, design_id, *, name: str,
                  filled: dict[str, str]) -> bool:
    """Volver a guardar una prediseñada que se editó.

    La cuenta va en la consulta, así que el id de otra cuenta no encuentra
    nada. `template` no se toca: cambiar de plantilla es empezar otra pieza,
    no editar esta.
    """
    return db.designs.update_one(
        {"_id": design_id, "account_id": account_id, "source": BUILT_IN},
        {"$set": {"name": clean_name(name), "fields": dict(filled),
                  "updated_at": now()}}).matched_count == 1


def is_draft(found: dict[str, Any] | None) -> bool:
    """Si es un borrador (octubre de 2026): se guardó sin cumplir las reglas y
    no se puede enviar hasta que se corrija."""
    return bool((found or {}).get("draft"))


def save_canvas(db, account_id, *, name: str, doc: dict[str, Any],
                backgrounds: list[str | None],
                shades: list[str | None] | None = None, folder_id=None,
                draft_issues: list[str] | None = None) -> Any:
    """Guardar un lienzo nuevo. Devuelve su id.

    `backgrounds` son las imágenes de sus grupos y `shades` su color promedio,
    en el orden de `canvas.groups()` (se llaman así desde que eran los fondos
    de cada diapositiva). `folder_id` es la carpeta elegida en el Lienzo, ya
    comprobada por quien llama. Con `draft_issues` es un borrador: lo que le
    falta para enviarse, y sin imágenes fundidas (se hacen al guardarla
    completa).
    """
    record = {
        "account_id": account_id,
        "source": CANVAS,
        "name": clean_name(name),
        "canvas": doc,
        "backgrounds": list(backgrounds),
        "shades": list(shades or []),
        "created_at": now(),
        "updated_at": now(),
    }
    if folder_id is not None:
        record["folder_id"] = folder_id
    if draft_issues:
        record.update(draft=True, draft_issues=list(draft_issues))
    return db.designs.insert_one(record).inserted_id


# `update_canvas` without a folder leaves it where it was: the sender upgrades
# old canvases and knows nothing about folders.
KEEP = object()


def update_canvas(db, account_id, design_id, *, name: str | None = None,
                  doc: dict[str, Any], backgrounds: list[str | None],
                  shades: list[str | None] | None = None, folder_id=KEEP,
                  draft_issues: list[str] | None = None) -> bool:
    """Volver a guardar un lienzo. La cuenta va en la consulta. Sin
    `draft_issues` deja de ser borrador, si lo era."""
    changes: dict[str, Any] = {"canvas": doc, "backgrounds": list(backgrounds),
                               "shades": list(shades or []), "updated_at": now()}
    if name is not None:
        changes["name"] = clean_name(name)
    update: dict[str, Any] = {"$set": changes}
    unset: dict[str, str] = {}
    if draft_issues:
        changes.update(draft=True, draft_issues=list(draft_issues))
    else:
        unset.update(draft="", draft_issues="")
    if folder_id is None:
        unset["folder_id"] = ""
    elif folder_id is not KEEP:
        changes["folder_id"] = folder_id
    update["$unset"] = unset
    return db.designs.update_one(
        {"_id": design_id, "account_id": account_id, "source": CANVAS},
        update).matched_count == 1


def still_named(db, account_id) -> set[str]:
    """Las imágenes fundidas que alguna pieza de la cuenta todavía nombra."""
    return {name for one in db.designs.find(
        {"account_id": account_id, "source": CANVAS}, {"backgrounds": 1})
        for name in one.get("backgrounds") or [] if name}


def upgrade_canvas(db, account_id, found: dict[str, Any]) -> dict[str, Any]:
    """Un lienzo guardado por diapositivas, pasado a hoja con sus imágenes nuevas.

    Lo llama el envío: una campaña con una pieza vieja tiene que salir bien
    aunque nadie la haya vuelto a abrir. Las imágenes viejas se borran si
    ninguna otra pieza las nombra (una copia hecha antes, por ejemplo).
    """
    from models import image as images
    from services import canvas

    doc = canvas.read(found.get("canvas"))
    if doc is None:
        return found
    names, shades = canvas.store(
        db, account_id, doc, lambda one: images.data_of(db, account_id, one))
    update_canvas(db, account_id, found["_id"], doc=doc, backgrounds=names,
                  shades=shades)
    kept = still_named(db, account_id)
    images.remove(db, account_id, [one for one in found.get("backgrounds") or []
                                   if one and one not in kept])
    return {**found, "canvas": doc, "backgrounds": names, "shades": shades}


def update_html(db, account_id, design_id, *, name: str, html: str) -> bool:
    """Volver a guardar el HTML de una pieza subida, después de editarlo.

    Solo las subidas: una prediseñada llena no tiene HTML propio que cambiar.
    La cuenta va en la consulta, así que el id de otra cuenta no encuentra nada.
    """
    return db.designs.update_one(
        {"_id": design_id, "account_id": account_id, "source": UPLOAD},
        {"$set": {"name": clean_name(name), "html": html,
                  "bytes": len(html.encode("utf-8")),
                  "updated_at": now()}}).matched_count == 1


def duplicate(db, account_id, design_id, *, name: str) -> Any:
    """Una copia de una pieza de esta cuenta, con otro nombre. Devuelve su id.

    Copia lo guardado entero, imágenes incluidas: las dos nombran las mismas, y
    por eso borrar una no borra las que la otra todavía usa (ver `remove` en
    las rutas).
    """
    found = by_id(db, account_id, design_id)
    if found is None:
        return None
    copy = {key: value for key, value in found.items() if key != "_id"}
    copy.update(name=clean_name(name), created_at=now(), updated_at=now())
    return db.designs.insert_one(copy).inserted_id


def for_account(db, account_id, *, limit: int = 50) -> list[dict[str, Any]]:
    return list(db.designs.find({"account_id": account_id})
                .sort("created_at", -1).limit(limit))


def by_id(db, account_id, design_id) -> dict[str, Any] | None:
    """Uno de esta cuenta. El id de otra cuenta no encuentra nada, porque la
    cuenta es parte de la consulta y no algo que se compruebe después."""
    return db.designs.find_one({"_id": design_id, "account_id": account_id})


def count(db, account_id) -> int:
    return db.designs.count_documents({"account_id": account_id})


# Cuántas plantillas caben en una cuenta, por la API y por el panel (octubre de
# 2026): cada lienzo guarda sus imágenes en la base, y sin tope una cuenta
# podía llenar sola el almacenamiento de todos.
LIMIT = 300


def has_room(db, account_id, wanted: int = 1) -> bool:
    return count(db, account_id) + wanted <= LIMIT


def remove(db, account_id, design_id) -> dict[str, Any] | None:
    """El cliente borra la suya, y devuelve lo que borró.

    Devuelve el documento y no un sí o un no porque quien llama tiene que poder
    borrar también las imágenes que colgaban de él. La cuenta va en la consulta,
    siempre.
    """
    return db.designs.find_one_and_delete(
        {"_id": design_id, "account_id": account_id})


# ------------------------------------------------------------- las carpetas
#
# Para agrupar las plantillas (octubre de 2026). Viven en la cuenta de la
# empresa, como sus etiquetas: `design_folders`, una lista de `{id, name,
# color}`. Cada plantilla dice la suya en `folder_id`, y sin él está suelta. Un
# solo nivel: no hay carpetas dentro de carpetas. Eliminar una carpeta nunca
# borra sus plantillas, que quedan sueltas.

FOLDER_NAME_MAX = 40
FOLDER_LIMIT = 50
# The palette, in the order the picker shows it. Gray is the folder of the
# design it came from; white came after, asked for (octubre de 2026).
FOLDER_COLORS = ("gray", "white", "blue", "green", "amber", "red", "purple", "pink",
                 "teal")
# How many templates peek out of a folder when the pointer is on it: three,
# asked for (octubre de 2026), to get into one of them quickly.
PEEK = 3
# What a list of templates needs: neither the HTML nor the canvas of each.
LISTED = {"name": 1, "source": 1, "bytes": 1, "template": 1, "folder_id": 1,
          "created_at": 1, "updated_at": 1, "draft": 1, "draft_issues": 1}


def clean_folder_name(raw: str) -> str:
    return " ".join((raw or "").split())[:FOLDER_NAME_MAX]


def folders_of(account: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Las carpetas de la cuenta, por nombre."""
    found = [dict(one) for one in (account or {}).get("design_folders") or []]
    return sorted(found, key=lambda one: one.get("name", "").casefold())


def folder_of(account: dict[str, Any] | None, folder_id) -> dict[str, Any] | None:
    """Una carpeta de esa cuenta, o None. La de otra cuenta no está en su
    lista, así que no se encuentra."""
    if folder_id is None:
        return None
    return next((one for one in folders_of(account) if one.get("id") == folder_id), None)


def _name_taken(account, name: str, but=None) -> bool:
    """Sin mayúsculas, como las etiquetas: «Cobros» y «cobros» serían dos."""
    return any(one.get("name", "").casefold() == name.casefold() and one.get("id") != but
               for one in folders_of(account))


def add_folder(db, account: dict[str, Any], name: str, color: str) -> tuple[Any, str]:
    """Crear una carpeta. Devuelve su id y "", o None y por qué no:
    `required`, `color`, `taken` o `full`."""
    name = clean_folder_name(name)
    if not name:
        return None, "required"
    if color not in FOLDER_COLORS:
        return None, "color"
    if _name_taken(account, name):
        return None, "taken"
    if len(folders_of(account)) >= FOLDER_LIMIT:
        return None, "full"
    folder_id = ObjectId()
    db.accounts.update_one({"_id": account["_id"]}, {
        "$push": {"design_folders": {"id": folder_id, "name": name, "color": color}},
        "$set": {"updated_at": now()}})
    return folder_id, ""


def rename_folder(db, account: dict[str, Any], folder_id, name: str) -> str:
    """Vacío si se cambió. Si no: `missing`, `required`, `same` o `taken`."""
    found = folder_of(account, folder_id)
    if found is None:
        return "missing"
    name = clean_folder_name(name)
    if not name:
        return "required"
    if name == found.get("name"):
        return "same"
    if _name_taken(account, name, but=folder_id):
        return "taken"
    db.accounts.update_one({"_id": account["_id"], "design_folders.id": folder_id},
                           {"$set": {"design_folders.$.name": name, "updated_at": now()}})
    return ""


def recolor_folder(db, account: dict[str, Any], folder_id, color: str) -> str:
    """Vacío si se cambió. Si no: `missing`, `color` o `same`."""
    found = folder_of(account, folder_id)
    if found is None:
        return "missing"
    if color not in FOLDER_COLORS:
        return "color"
    if color == found.get("color"):
        return "same"
    db.accounts.update_one({"_id": account["_id"], "design_folders.id": folder_id},
                           {"$set": {"design_folders.$.color": color, "updated_at": now()}})
    return ""


def remove_folder(db, account: dict[str, Any], folder_id) -> bool:
    """Eliminar la carpeta. Sus plantillas no se borran: quedan sueltas."""
    if folder_of(account, folder_id) is None:
        return False
    db.accounts.update_one({"_id": account["_id"]},
                           {"$pull": {"design_folders": {"id": folder_id}},
                            "$set": {"updated_at": now()}})
    db.designs.update_many({"account_id": account["_id"], "folder_id": folder_id},
                           {"$unset": {"folder_id": ""}})
    return True


def move_many(db, account: dict[str, Any], design_ids, folder_id) -> int:
    """Pasar plantillas a una carpeta de la misma cuenta, o sacarlas con None:
    una desde «Mover a…», o varias arrastradas juntas (octubre de 2026).
    Devuelve cuántas eran de la cuenta; las de otra no se tocan, y nada se
    mueve a la carpeta de otra. No cuenta como un cambio: no las vuelve de las
    más recientes."""
    if folder_id is not None and folder_of(account, folder_id) is None:
        return 0
    ids = [one for one in design_ids if one is not None]
    if not ids:
        return 0
    update = ({"$unset": {"folder_id": ""}} if folder_id is None
              else {"$set": {"folder_id": folder_id}})
    return db.designs.update_many({"_id": {"$in": ids}, "account_id": account["_id"]},
                                  update).matched_count


def changed_at(one: dict[str, Any]):
    """Su último cambio. Las cargadas que nunca se editaron no tienen
    `updated_at`."""
    return one.get("updated_at") or one.get("created_at")


def shelf(db, account: dict[str, Any], *, limit: int = 50) -> dict[str, Any]:
    """Mis plantillas, ordenada: las sueltas (las más nuevas primero, hasta
    `limit`, como antes de las carpetas) y, por carpeta, cuántas tiene y las
    `PEEK` de cambio más reciente, que son las que asoman. Van de la más vieja a
    la más nueva, que es la que queda delante, pegada al cristal.

    Una plantilla que nombra una carpeta que ya no existe cuenta como suelta.
    """
    folders = folders_of(account)
    inside: dict[Any, list[dict[str, Any]]] = {one["id"]: [] for one in folders}
    loose: list[dict[str, Any]] = []
    for one in db.designs.find({"account_id": account["_id"]}, LISTED).sort("created_at", -1):
        if one.get("folder_id") in inside:
            inside[one["folder_id"]].append(one)
        else:
            loose.append(one)
    return {
        "loose": loose[:limit],
        "counts": {key: len(items) for key, items in inside.items()},
        "peek": {key: sorted(items, key=changed_at, reverse=True)[:PEEK][::-1]
                 for key, items in inside.items()},
    }


def set_sending(db, account_id, design_id, *, send_from, reply_to) -> None:
    """De quién sale y a dónde se responde esta plantilla (octubre de 2026):
    el id de un remitente de la cuenta y una dirección de sus «Responder a»,
    ya comprobados por quien llama. None es el predeterminado de la cuenta."""
    sets: dict[str, Any] = {}
    gone: dict[str, str] = {}
    for field, value in (("send_from", send_from), ("reply_to", reply_to)):
        if value is None:
            gone[field] = ""
        else:
            sets[field] = value
    update: dict[str, Any] = {}
    if sets:
        update["$set"] = sets
    if gone:
        update["$unset"] = gone
    db.designs.update_one({"_id": design_id, "account_id": account_id}, update)


def forget_sending(db, account_id, *, froms=(), replies=()) -> None:
    """Lo que se quitó de Remitente sale también de las plantillas que lo
    usaban, que vuelven al predeterminado."""
    if froms:
        db.designs.update_many({"account_id": account_id, "send_from": {"$in": list(froms)}},
                               {"$unset": {"send_from": ""}})
    if replies:
        db.designs.update_many({"account_id": account_id, "reply_to": {"$in": list(replies)}},
                               {"$unset": {"reply_to": ""}})


def in_folder(db, account_id, folder_id, *, limit: int = 50) -> list[dict[str, Any]]:
    """Las plantillas de una carpeta, las más nuevas primero."""
    return list(db.designs.find({"account_id": account_id, "folder_id": folder_id}, LISTED)
                .sort("created_at", -1).limit(limit))
