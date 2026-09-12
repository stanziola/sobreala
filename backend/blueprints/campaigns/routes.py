"""Enviar correos: a quién, con qué pieza, y cuándo.

La pantalla que junta lo que ya había suelto —las listas de `/contactos` y las
piezas de `/plantillas`— y lo manda. Es la única del panel desde la que sale
correo a un contacto de un cliente.

**Un administrador no la ve ni entra**: su cuenta no tiene contactos a los que
escribirle, así que la fila no le sale en el menú y la ruta lo devuelve a
`/admin`. Esconder una fila no es un permiso.

El envío de verdad vive en `services/sender.py`. Aquí solo se elige, se agenda,
y se le pide que mande una tanda.

**Una campaña se guarda y se manda las veces que haga falta.** La pantalla
tiene por eso dos listas: las campañas guardadas, que se pueden corregir y
volver a mandar, y los envíos, uno por vez que salió. Y mandar pasa siempre por
una pantalla que pregunta, como exportar contactos: el GET no manda nada y el
POST sí.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, redirect, render_template, request, url_for

from blueprints.auth.routes import current_account, not_for_admins
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from models import design as designs
from services import render, sender
from services.security import csrf_ok

bp = Blueprint("campaigns", __name__)

# Cómo viaja la fecha en el formulario: lo que escribe <input type="datetime-local">.
WHEN_FORMAT = "%Y-%m-%dT%H:%M"


@bp.before_request
def keep_admins_out():
    return not_for_admins(current_account())


def signed_in():
    return current_account()


def as_id(raw):
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def read_when(raw: str) -> datetime | None:
    """La fecha que se escribió, en UTC.

    El navegador manda la hora del reloj de quien la escribió y sin zona. Se
    toma como UTC a propósito: el servidor corre en UTC y hoy no se le pregunta
    a nadie su zona horaria. Está anotado en CLAUDE.md como lo que hay que
    resolver antes de que esto lo use un cliente de verdad.
    """
    try:
        return datetime.strptime(raw, WHEN_FORMAT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def pieces(db, account_id) -> list[dict]:
    """Las piezas guardadas, con el nombre que les puso el cliente."""
    return designs.for_account(db, account_id)


def lists_of(db, account) -> list[dict]:
    """Las listas a las que se le puede escribir, con cuántos hay en cada una.

    La primera es todos los contactos: una cuenta que nunca creó una etiqueta
    tiene igualmente a quién escribirle.
    """
    counted = contacts.count_by_tag(db, account["_id"])
    found = [{"tag": "", "name": t("send_all_contacts"),
              "howmany": contacts.count(db, account["_id"])}]
    for name in accounts.tags_of(account):
        found.append({"tag": name, "name": name,
                      "howmany": counted.get(name, 0)})
    return found


def shared(db, account, **extra):
    return {
        "account": account,
        "lists": lists_of(db, account),
        "pieces": pieces(db, account["_id"]),
        "named": {one["key"]: one["label"]
                  for one in render.TEMPLATE_LIST.values()},
        "campaigns": campaigns.for_account(db, account["_id"]),
        # Una fila por vez que salió algo, que es otra cosa que una fila por
        # campaña: la mandada seis veces son seis envíos.
        "runs": runs.for_account(db, account["_id"]),
        "times": runs.times_by_campaign(db, account["_id"]),
        # Qué le falta a la cuenta para que un envío salga de verdad. Se enseña
        # siempre, no al final: enterarse de que no se puede después de armarlo
        # todo es la peor forma de enterarse.
        "blocked": sender.blocked(account),
        "quota": accounts.quota_left(account),
        # Para escribirlas en el asunto, que es lo primero que se lee.
        "columns": accounts.fields_of(account),
        "editable": campaigns.editable,
        "due": campaigns.due,
        **extra,
    }


@bp.route("/envios", methods=["GET", "POST"])
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}

    if request.method == "POST":
        errors = save(db, account, None)
        if not errors:
            return redirect(url_for("campaigns.index", guardado=1))

    return render_template(
        "campaigns/index.html", section="envios",
        **shared(db, account, errors=errors, form=request.form,
                 saved=bool(request.args.get("guardado")),
                 done=request.args.get("hecho", ""),
                 removed=bool(request.args.get("borrado"))))


def save(db, account, campaign) -> dict[str, str]:
    """Guardar lo que dice el formulario, para una nueva o para una que se edita."""
    errors: dict[str, str] = {}
    subject = campaigns.clean_subject(request.form.get("asunto", ""))
    design_id = as_id(request.form.get("pieza"))
    tag = (request.form.get("lista") or "").strip()
    now_wanted = request.form.get("cuando") == "ahora"
    when = accounts.now() if now_wanted else read_when(
        request.form.get("fecha", ""))

    if not csrf_ok(request.form.get("csrf_token")):
        return {"form": t("error_csrf")}
    if not subject:
        errors["asunto"] = t("error_required")
    if design_id is None or designs.by_id(db, account["_id"], design_id) is None:
        errors["pieza"] = t("send_pick_piece")
    if tag and tag not in accounts.tags_of(account):
        errors["lista"] = t("send_pick_list")
    if when is None:
        errors["fecha"] = t("send_pick_when")
    elif not now_wanted and when <= accounts.now():
        # Programar para una hora que ya pasó es pedir que salga ahora mismo, y
        # eso tiene su propio botón.
        errors["fecha"] = t("send_when_past")
    if errors:
        return errors

    if campaign is None:
        campaigns.create(db, account["_id"], subject=subject,
                         design_id=design_id, tag=tag, scheduled_at=when)
    elif not campaigns.update(db, account["_id"], campaign["_id"],
                              subject=subject, design_id=design_id, tag=tag,
                              scheduled_at=when):
        return {"form": t("send_already_out")}
    return {}


@bp.route("/envios/<raw>", methods=["GET", "POST"])
def edit(raw):
    """Cambiar una campaña que todavía no ha empezado a salir."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    campaign_id = as_id(raw)
    found = (campaigns.by_id(db, account["_id"], campaign_id)
             if campaign_id else None)
    if found is None:
        return redirect(url_for("campaigns.index"))
    if not campaigns.editable(found):
        return redirect(url_for("campaigns.index", hecho="tarde"))

    errors: dict[str, str] = {}
    if request.method == "POST":
        errors = save(db, account, found)
        if not errors:
            return redirect(url_for("campaigns.index", guardado=1))

    return render_template(
        "campaigns/edit.html", section="envios",
        **shared(db, account, errors=errors, form=request.form,
                 campaign=found,
                 when=found["scheduled_at"].strftime(WHEN_FORMAT)))


@bp.route("/envios/<raw>/borrar", methods=["POST"])
def remove(raw):
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    if csrf_ok(request.form.get("csrf_token")):
        campaign_id = as_id(raw)
        if campaign_id:
            campaigns.remove(get_db(), account["_id"], campaign_id)
    return redirect(url_for("campaigns.index", borrado=1))


@bp.route("/envios/<raw>/mandar", methods=["GET", "POST"])
def send(raw):
    """Preguntar primero, y después mandar una tanda de esta campaña.

    **El GET no manda nada**: dibuja a quién le va a salir y cuántos son, y
    pregunta. Es el mismo reparto que exportar contactos, y aquí importa más,
    porque lo que hace el POST no se puede deshacer: un correo que salió, salió.

    Una tanda y no la campaña entera: esto corre dentro de la petición y una
    lista larga la cortaría el servidor a la mitad. La pantalla dice cuántos
    van y ofrece seguir, que es lo que hará el proceso en segundo plano el día
    que exista, sin que nada de esto cambie.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    campaign_id = as_id(raw)
    found = (campaigns.by_id(db, account["_id"], campaign_id)
             if campaign_id else None)
    if found is None:
        return redirect(url_for("campaigns.index"))

    if request.method == "GET":
        return render_template(
            "campaigns/confirm.html", section="envios",
            **shared(db, account, campaign=found,
                     piece=designs.by_id(db, account["_id"],
                                         found.get("design_id")),
                     going=contacts.matching_count(db, account["_id"],
                                                   tag=found.get("tag", "")),
                     already=runs.times(db, account["_id"], found["_id"])))

    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("campaigns.index"))

    # Volver a mandar una que ya salió empieza por devolver a cero los
    # contadores de la vuelta. Si otra pestaña se adelantó, la consulta no
    # encuentra nada y aquí no se manda dos veces lo mismo.
    if found["status"] == campaigns.SENT:
        if not campaigns.restart(db, account["_id"], found["_id"],
                                 when=accounts.now()):
            return redirect(url_for("campaigns.index", hecho="tarde"))
        found = campaigns.by_id(db, account["_id"], found["_id"])

    result = sender.run(db, account, found)
    if result["blocked"]:
        return redirect(url_for("campaigns.index", hecho="falta"))
    return redirect(url_for("campaigns.index",
                            hecho="parte" if result["left"] else "todo"))
