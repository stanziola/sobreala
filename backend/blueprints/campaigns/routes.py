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
from flask import Blueprint, abort, redirect, render_template, request, url_for

from blueprints.auth.routes import current_account, not_for_admins
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from models import design as designs
from models import event as events
from services import render, sender
from services import clock
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
    entiende en la zona de su dispositivo (`services/clock.py`) y se guarda en
    UTC: «a las 3 de la tarde» desde Panamá son las 20:00 UTC.
    """
    try:
        return clock.to_utc(datetime.strptime(raw, WHEN_FORMAT))
    except (ValueError, TypeError):
        return None


def pieces(db, account_id) -> list[dict]:
    """Las piezas guardadas, con el nombre que les puso el cliente."""
    return designs.for_account(db, account_id)


def lists_of(db, account) -> list[dict]:
    """Las etiquetas a las que se le puede escribir, con cuántos hay en cada una.

    Marcar varias es escribirle a quien lleve **cualquiera** de ellas, y no
    marcar ninguna es escribirle a toda la lista: una cuenta que nunca creó una
    etiqueta tiene igualmente a quién escribirle.
    """
    # Con las columnas de la cuenta: quien no las tenga llenas no va a recibir
    # nada, así que contarlo aquí sería prometer un número que no sale.
    counted = contacts.count_by_tag(db, account["_id"],
                                    accounts.fields_of(account))
    return [{"tag": name, "name": name, "howmany": counted.get(name, 0)}
            for name in accounts.tags_of(account)]


def lists_chosen(account) -> list[str]:
    """Las etiquetas marcadas, filtradas por las que existen.

    Se recorren las de la cuenta y no lo que llegó: un nombre inventado se
    descarta en vez de filtrar por él, que es lo mismo que hace la pantalla de
    contactos. Vacío es toda la lista.
    """
    marked = set(request.form.getlist("lista"))
    return [name for name in accounts.tags_of(account) if name in marked]


def shared(db, account, **extra):
    sent_runs = runs.for_account(db, account["_id"])
    return {
        "account": account,
        "lists": lists_of(db, account),
        "pieces": pieces(db, account["_id"]),
        "named": {one["key"]: one["label"]
                  for one in render.TEMPLATE_LIST.values()},
        "campaigns": campaigns.for_account(db, account["_id"]),
        "tags_of": campaigns.tags_of,
        "everyone": t("send_all_contacts"),
        # Una fila por vez que salió algo, que es otra cosa que una fila por
        # campaña: la mandada seis veces son seis envíos.
        "runs": sent_runs,
        # Lo que contó SES de cada envío: entregados, rebotes, abiertos, con
        # clic y quejas, en personas. Una consulta para toda la lista.
        "run_counts": events.counts_by_run(
            db, account["_id"], [one["_id"] for one in sent_runs]),
        "times": runs.times_by_campaign(db, account["_id"]),
        # Qué le falta a la cuenta para que un envío salga de verdad. Se enseña
        # siempre, no al final: enterarse de que no se puede después de armarlo
        # todo es la peor forma de enterarse.
        "blocked": sender.blocked(account),
        "quota": accounts.quota_left(account),
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
    tags = lists_chosen(account)
    now_wanted = request.form.get("cuando") == "ahora"
    when = accounts.now() if now_wanted else read_when(
        request.form.get("fecha", ""))

    if not csrf_ok(request.form.get("csrf_token")):
        return {"form": t("error_csrf")}
    if not subject:
        errors["asunto"] = t("error_required")
    if design_id is None or designs.by_id(db, account["_id"], design_id) is None:
        errors["pieza"] = t("send_pick_piece")
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
                         design_id=design_id, tags=tags, scheduled_at=when)
    elif not campaigns.update(db, account["_id"], campaign["_id"],
                              subject=subject, design_id=design_id, tags=tags,
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
                 # Vuelve a salir en la hora de quien la mira.
                 when=clock.local(found["scheduled_at"]).strftime(WHEN_FORMAT)))


# Cuántas personas por página en el detalle de un envío.
PER_PAGE = 50


@bp.route("/envios/enviados/<raw>")
def run_detail(raw):
    """A quién le salió un envío y qué pasó con cada uno: si le llegó, si lo
    abrió, si pulsó. Una fila por persona, con la primera vez de cada cosa.

    El filtro por etiqueta y el buscador se resuelven primero en Contactos: se
    busca quién cumple y solo se miran los eventos de esas personas. Las
    etiquetas y el nombre son los de hoy; quien ya no está en Contactos sale con
    su dirección y lo dice.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    run_id = as_id(raw)
    found = runs.by_id(db, account["_id"], run_id) if run_id else None
    if found is None:
        abort(404)

    known = accounts.tags_of(account)
    tag = request.args.get("etiqueta", "")
    tag = tag if tag in known else ""
    search = " ".join(request.args.get("q", "").split())[:100]
    outcome = request.args.get("estado", "")
    outcome = outcome if outcome in events.OUTCOMES else ""
    try:
        page = max(1, int(request.args.get("pagina", "1")))
    except ValueError:
        page = 1

    emails = None
    if tag or search:
        emails = contacts.emails_matching(db, account["_id"], tag=tag, text=search)
    total, people = events.recipients(db, account["_id"], found["_id"], emails=emails,
                                      outcome=outcome, skip=(page - 1) * PER_PAGE,
                                      limit=PER_PAGE)
    # Nombre y etiquetas de la página, en una consulta (regla 10).
    here = contacts.by_emails(db, account["_id"], [one["email"] for one in people])
    for one in people:
        one["contact"] = here.get(one["email"])

    return render_template(
        "campaigns/run.html", section="envios", account=account, run=found,
        people=people, total=total, page=page,
        pages=max(1, -(-total // PER_PAGE)), tag=tag, tags=known, search=search,
        outcome=outcome, outcomes=list(events.OUTCOMES),
        seen=events.counts_by_run(db, account["_id"], [found["_id"]]).get(found["_id"]),
        everyone=t("send_all_contacts"))


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
                     going=contacts.matching_count(
                         db, account["_id"],
                         tags=campaigns.tags_of(found),
                         complete=accounts.fields_of(account)),
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
