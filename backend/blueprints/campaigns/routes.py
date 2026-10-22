"""Enviar correos: a quién, con qué pieza, y cuándo.

La pantalla que junta lo que ya había suelto —las listas de `/contacts` y las
piezas de `/templates`— y lo manda. Es la única del panel desde la que sale
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

import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template,
                   request, session, url_for)

from blueprints.auth.routes import (CONFIRM_PER_IP, REGISTER_PER_EMAIL,
                                    clean_email, client_ip, current_account,
                                    current_workspace, needs, not_for_admins,
                                    seconds_left)
from config import Config
from db import get_db
from i18n import t
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from models import design as designs
from models import download as downloads_model
from models import event as events
from models import token as tokens
from models import suppression as suppressions
from services import address_check, attachments, importer, notices, render, sender, ses_identity
from services import audience
from services import clock
from services import fields
from services.security import csrf_ok, rate_limit

bp = Blueprint("campaigns", __name__)

# Cómo viaja la fecha en el formulario: lo que escribe <input type="datetime-local">.
WHEN_FORMAT = "%Y-%m-%dT%H:%M"


@bp.before_request
def keep_out():
    """Un administrador no tiene a quién escribirle, y un usuario entra solo si
    la empresa le dio al menos ver las campañas. Mandar pide su propio permiso,
    y eso se comprueba en las dos rutas que mandan."""
    account = current_account()
    return not_for_admins(account) or needs(account, accounts.CAMPAIGNS)


def signed_in():
    """La cuenta de la empresa: las campañas, los contactos y la cuota son
    suyos, también cuando los mira un usuario que ella creó."""
    return current_workspace()


def may_send():
    """Un redirect si quien mira puede ver las campañas pero no mandarlas."""
    return needs(current_account(), accounts.SEND)


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
    return {
        "account": account,
        "lists": lists_of(db, account),
        "pieces": pieces(db, account["_id"]),
        "named": {one["key"]: one["label"]
                  for one in render.TEMPLATE_LIST.values()},
        "campaigns": campaigns.for_account(db, account["_id"]),
        "tags_of": campaigns.tags_of,
        "everyone": t("send_all_contacts"),
        "times": runs.times_by_campaign(db, account["_id"]),
        # Qué le falta a la cuenta para que un envío salga de verdad. Se enseña
        # siempre, no al final: enterarse de que no se puede después de armarlo
        # todo es la peor forma de enterarse.
        "blocked": sender.blocked(account),
        "default_from": sender.remitente(account),
        "reply": sender.reply_to(account),
        "quota": accounts.quota_left(account),
        # La demostración envía solo a sus direcciones de prueba: se dice
        # arriba, con cuántas tiene y cuántos correos le quedan.
        "demo": ({"addresses": len(accounts.confirmed_test_addresses(account)),
                  "left": accounts.demo_left(account), "total": accounts.DEMO_SENDS}
                 if accounts.in_demo(account) else None),
        "editable": campaigns.editable,
        "due": campaigns.due,
        # Un usuario puede tener solo «ver las campañas»: entonces la pantalla
        # se lee entera y no enseña botones que su cuenta no puede pulsar.
        "can_send": accounts.can(current_account(), accounts.SEND),
        # «Poner mi logo arriba», en lo escrito (octubre de 2026).
        "has_logo": bool(accounts.logo_of(account)),
        "body_max": campaigns.BODY_MAX,
        # Las condiciones (octubre de 2026): qué se puede elegir en cada fila y
        # los operadores de cada tipo.
        "audience_choices": audience.choices(accounts.fields_of(account)),
        "audience_ops": AUDIENCE_OPS,
        "audience_max": audience.MAX_RULES,
        **extra,
    }


# Los operadores de cada tipo, como los ofrece la pantalla: un grupo por tipo.
# «count» son la cantidad de filas y la suma de un dato de una lista.
AUDIENCE_OPS = [
    ("number", audience.OPS[fields.NUMBER]),
    ("text", audience.OPS[fields.TEXT]),
    ("date", audience.OPS[fields.DATE]),
    ("yesno", audience.OPS[fields.YESNO]),
    ("count", audience.COMPARE),
]


def typed_rules() -> list[dict[str, str]]:
    """Las filas de condiciones tal como llegaron del formulario, para leerlas y
    para volver a dibujarlas si algo falló. Una fila sin columna no cuenta."""
    chosen = request.form.getlist("rule_field")
    ops = request.form.getlist("rule_op")
    values = request.form.getlist("rule_value")
    rows = []
    for i, choice in enumerate(chosen[:audience.MAX_RULES + 1]):
        rows.append({"choice": choice.strip()[:80],
                     "op": (ops[i] if i < len(ops) else "").strip()[:20],
                     "value": (values[i] if i < len(values) else "").strip()[:200]})
    return rows


def rules_of(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [audience.from_choice(row["choice"], row["op"], row["value"])
            for row in rows if row["choice"]]


def rule_rows(campaign, form_rows: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Las filas que se dibujan: las que llegaron, o las guardadas; y una vacía
    al final, para agregar sin JavaScript."""
    if form_rows is not None:
        rows = [row for row in form_rows if row["choice"]]
    else:
        saved = campaigns.filters_of(campaign) or {}
        rows = [{"choice": audience.to_choice(rule), "op": rule.get("op", ""),
                 "value": rule.get("value", "")} for rule in saved.get("rules") or []]
    if len(rows) < audience.MAX_RULES:
        rows.append({"choice": "", "op": "", "value": ""})
    return rows


def read_audience(account) -> tuple[dict | None, str]:
    """Las condiciones del formulario, validadas, y el problema si hay uno."""
    raw = {"match": request.form.get("cumplan", audience.ALL),
           "rules": rules_of(typed_rules())}
    found, problems = audience.parse(raw, accounts.fields_of(account))
    if problems:
        return None, audience.problem_text(*problems[0])
    return found, ""


def going_count(db, account, campaign) -> int | None:
    """A cuántos saldría, con sus etiquetas, sus columnas llenas y sus
    condiciones. None si una condición ya no vale: entonces no sale."""
    columns = accounts.fields_of(account)
    try:
        chosen = audience.query(campaigns.filters_of(campaign), columns)
    except audience.Stale:
        return None
    return contacts.matching_count(db, account["_id"], tags=campaigns.tags_of(campaign),
                                   complete=columns, audience=chosen)


# Cuántas veces por minuto se puede pedir la cuenta en vivo: una por cambio.
AUDIENCE_PER_MINUTE = (60, 60)


@bp.route("/campaigns/audience", methods=["POST"])
def audience_count():
    """A cuántos saldría lo que está en el formulario, mientras se elige
    (octubre de 2026): las etiquetas marcadas y las condiciones. Pide **el mismo
    permiso que enviar**: si no, un usuario que solo mira podría adivinar los
    valores de los contactos estrechando la cuenta. Con CSRF y un tope."""
    account = signed_in()
    if account is None or may_send():
        return jsonify({"error": t("send_audience_denied")}), 403
    if not csrf_ok(request.form.get("csrf_token")):
        return jsonify({"error": t("error_csrf")}), 400
    db = get_db()
    if not rate_limit(db, f"audience:{account['_id']}", *AUDIENCE_PER_MINUTE):
        return jsonify({"error": t("error_too_many")}), 429
    filters, problem = read_audience(account)
    if problem:
        return jsonify({"error": problem})
    columns = accounts.fields_of(account)
    many = contacts.matching_count(db, account["_id"], tags=lists_chosen(account),
                                   complete=columns,
                                   audience=audience.query(filters, columns))
    response = jsonify({"count": many, "text": t("send_audience_count", n=many) if many != 1
                        else t("send_audience_count_one")})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/campaigns", methods=["GET", "POST"])
def index():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    errors: dict[str, str] = {}

    rows = None
    if request.method == "POST":
        answer = may_send()
        if answer:
            return answer
        rows = typed_rules()
        # «Agregar condición» y «Quitar», sin JavaScript: se vuelve a dibujar
        # con lo escrito, sin guardar nada.
        if not redraw(rows):
            errors = save(db, account, None)
            if not errors:
                return redirect(url_for("campaigns.index", saved=1))

    return render_template(
        "campaigns/index.html", section="envios",
        **shared(db, account, errors=errors, form=request.form,
                 saved=bool(request.args.get("saved")),
                 done=request.args.get("done", ""),
                 removed=bool(request.args.get("deleted")),
                 rule_rows=rule_rows(None, rows)))


def redraw(rows: list[dict[str, str]]) -> bool:
    """Si el formulario pidió agregar o quitar una condición (sin JavaScript).
    Cambia `rows` en su sitio: la vacía del final la agrega `rule_rows()`."""
    action = request.form.get("rule_action", "")
    if action == "add":
        return True
    if action.startswith("remove:"):
        try:
            del rows[int(action.split(":", 1)[1])]
        except (ValueError, IndexError):
            pass
        return True
    return False


# Cómo se arma un correo (octubre de 2026): escrito a mano o con una plantilla
# guardada. Los dos sirven para el individual y para el masivo.
WRITE = "escribir"
TEMPLATE = "plantilla"


def mode_of(default: str) -> str:
    """Lo que eligió el formulario; algo inventado es lo de siempre."""
    chosen = request.form.get("modo", default)
    return chosen if chosen in (WRITE, TEMPLATE) else default


def save(db, account, campaign) -> dict[str, str]:
    """Guardar lo que dice el formulario, para una nueva o para una que se edita.

    Desde octubre de 2026 una campaña sale de una plantilla o de un texto
    escrito (`modo`), con el logo de la empresa arriba si se pide. Escrita,
    lleva su baja y la marca de agua de su plan como cualquier campaña; el
    archivo es solo del individual."""
    errors: dict[str, str] = {}
    subject = campaigns.clean_subject(request.form.get("asunto", ""))
    mode = mode_of(TEMPLATE)
    design_id = as_id(request.form.get("pieza")) if mode == TEMPLATE else None
    body = request.form.get("mensaje", "").strip() if mode == WRITE else ""
    logo = mode == WRITE and bool(request.form.get("logo")) and bool(accounts.logo_of(account))
    tags = lists_chosen(account)
    filters, filters_problem = read_audience(account)
    now_wanted = request.form.get("cuando") == "ahora"
    when = accounts.now() if now_wanted else read_when(
        request.form.get("fecha", ""))

    if not csrf_ok(request.form.get("csrf_token")):
        return {"form": t("error_csrf")}
    if not subject:
        errors["asunto"] = t("error_required")
    if mode == WRITE:
        if not body:
            errors["mensaje"] = t("error_required")
        elif len(body) > campaigns.BODY_MAX:
            errors["mensaje"] = t("single_body_long", n=campaigns.BODY_MAX)
    elif design_id is None or designs.by_id(db, account["_id"], design_id) is None:
        errors["pieza"] = t("send_pick_piece")
    elif designs.is_draft(designs.by_id(db, account["_id"], design_id)):
        errors["pieza"] = t("send_piece_draft")
    if filters_problem:
        errors["condiciones"] = filters_problem
    if when is None:
        errors["fecha"] = t("send_pick_when")
    elif not now_wanted and when <= accounts.now():
        # Programar para una hora que ya pasó es pedir que salga ahora mismo, y
        # eso tiene su propio botón.
        errors["fecha"] = t("send_when_past")
    if errors:
        return errors

    # Con fecha sale sola a esa hora (octubre de 2026, el proceso en segundo
    # plano); «ahora mismo» sigue pidiendo Enviar y su pantalla que pregunta.
    filters_text = audience.describe(filters, accounts.fields_of(account))
    if campaign is None:
        campaigns.create(db, account["_id"], subject=subject,
                         design_id=design_id, tags=tags, scheduled_at=when,
                         body=body, logo=logo, auto_send=not now_wanted,
                         filters=filters, filters_text=filters_text)
    elif not campaigns.update(db, account["_id"], campaign["_id"],
                              subject=subject, design_id=design_id, tags=tags,
                              scheduled_at=when, body=body, logo=logo,
                              auto_send=not now_wanted, filters=filters,
                              filters_text=filters_text):
        return {"form": t("send_already_out")}
    return {}


@bp.route("/campaigns/write", methods=["GET", "POST"])
def write():
    """Escribir un correo a una persona, como uno normal: para, asunto, texto y
    un archivo si hace falta. Sale ya, por el mismo camino que una campaña.

    Desde octubre de 2026 va **a cualquier dirección**, esté o no en Contactos,
    y sin guardarla; y **sin baja ni marca de agua**, porque no es una campaña.
    A quien se dio de baja o rebotó en esta cuenta igual no le sale (regla 1).
    El archivo va como enlace de descarga, para saber si lo bajó."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    answer = may_send()
    if answer:
        return answer

    db = get_db()
    errors: dict[str, str] = {}
    form = request.form if request.method == "POST" else {"para": request.args.get("para", "")}
    if request.method == "POST":
        errors = send_single(db, account)
        if isinstance(errors, str):
            # Salió: al detalle de su envío, donde se verá si le llegó y si lo abrió.
            return redirect(errors)
    return render_template(
        "campaigns/write.html", section="envios", account=account, errors=errors,
        form=form, accept=attachments.ACCEPT,
        max_mb=attachments.MAX_BYTES // (1024 * 1024), body_max=campaigns.BODY_MAX,
        keep_days=downloads_model.KEEP_DAYS,
        # Las mismas plantillas que el masivo (octubre de 2026).
        pieces=pieces(db, account["_id"]),
        named={one["key"]: one["label"] for one in render.TEMPLATE_LIST.values()},
        has_logo=bool(accounts.logo_of(account)))


def send_single(db, account):
    """Comprobar el formulario y mandar. Devuelve los errores, o a dónde ir."""
    if not csrf_ok(request.form.get("csrf_token")):
        return {"form": t("error_csrf")}
    errors: dict[str, str] = {}
    # «Usar gmail.com» trae la dirección corregida en su propio botón.
    raw_to = " ".join((request.form.get("corregir") or request.form.get("para", "")).split())[:254]
    to = (importer.clean(raw_to) or "").lower() if raw_to else ""
    subject = campaigns.clean_subject(request.form.get("asunto", ""))
    mode = mode_of(WRITE)
    body = request.form.get("mensaje", "").strip() if mode == WRITE else ""
    design = (designs.by_id(db, account["_id"], as_id(request.form.get("pieza")))
              if mode == TEMPLATE and as_id(request.form.get("pieza")) else None)
    logo = mode == WRITE and bool(request.form.get("logo")) and bool(accounts.logo_of(account))
    found = contacts.by_emails(db, account["_id"], [to]).get(to) if to else None
    if not raw_to:
        errors["para"] = t("error_required")
    elif not to:
        errors["para"] = t("single_bad_address")
    elif suppressions.among(db, account["_id"], [to]):
        errors["para"] = t("single_suppressed")
    elif accounts.in_demo(account) and to not in accounts.confirmed_test_addresses(account):
        # En la demostración, solo a sus direcciones de prueba confirmadas.
        errors["para"] = t("single_demo_only")
    elif (found or {}).get("invalid") or not address_check.domain_receives(
            address_check.domain_of(to)):
        errors["para"] = t("single_undeliverable", domain=address_check.domain_of(to))
    elif (address_check.suggestion(to) and not request.form.get("confirmado")
          and not found):
        # Un error de dedo probable: se pregunta una vez. Si escribe la misma
        # dirección y confirma, sale como la escribió.
        errors["para"] = t("single_typo", better=address_check.suggestion(to))
        errors["typo"] = address_check.suggestion(to)
    if not subject:
        errors["asunto"] = t("error_required")
    if mode == TEMPLATE:
        if design is None:
            errors["pieza"] = t("send_pick_piece")
        elif designs.is_draft(design):
            errors["pieza"] = t("send_piece_draft")
        elif to and "para" not in errors:
            # A quien le falta un dato no le llega nada (octubre de 2026): la
            # plantilla nombra columnas o el nombre, y esa dirección no está en
            # Contactos o no los tiene.
            # El contacto entero: `by_emails` no trae sus columnas.
            person = (contacts.by_id(db, account["_id"], found["_id"]) if found
                      else None) or {"email": to}
            lacking = marks_missing(account, design, subject, person)
            if lacking:
                errors["pieza"] = t("single_template_missing", what=", ".join(lacking))
    elif not body:
        errors["mensaje"] = t("error_required")
    elif len(body) > campaigns.BODY_MAX:
        errors["mensaje"] = t("single_body_long", n=campaigns.BODY_MAX)

    attachment = None
    upload = request.files.get("archivo")
    data = upload.read(attachments.MAX_BYTES + 1) if upload and upload.filename else b""
    if data:
        kind = attachments.kind_of(data)
        if len(data) > attachments.MAX_BYTES:
            errors["archivo"] = t("single_file_big", mb=attachments.MAX_BYTES // (1024 * 1024))
        elif kind is None:
            errors["archivo"] = t("single_file_kind")
        elif not downloads_model.has_room(db, account["_id"], len(data)):
            errors["archivo"] = t("single_file_room",
                                  mb=downloads_model.ACCOUNT_BYTES // (1024 * 1024),
                                  days=downloads_model.KEEP_DAYS)
        else:
            maintype, subtype, ext = kind
            attachment = (attachments.safe_name(upload.filename, ext),
                          f"{maintype}/{subtype}", data)
    if errors:
        return errors

    why = sender.blocked(account)
    if why:
        return {"form": t("single_blocked")}

    campaign_id = campaigns.create_single(
        db, account["_id"], subject=subject, body=body,
        contact_id=found["_id"] if found else None,
        to=found.get("email", to) if found else to,
        design_id=design["_id"] if design else None, logo=logo)
    # El archivo se guarda 30 días y el correo lleva su enlace de descarga: es
    # lo que deja saber si la persona lo bajó (`models/download.py`).
    if attachment:
        name, content_type, data = attachment
        campaigns.attach_download(db, account["_id"], campaign_id, downloads_model.save(
            db, account["_id"], campaign_id, name=name, content_type=content_type,
            data=data))
    result = sender.run(db, account, campaigns.by_id(db, account["_id"], campaign_id))
    done = campaigns.by_id(db, account["_id"], campaign_id) or {}
    if result.get("sent") and done.get("run_id"):
        return url_for("campaigns.run_detail", raw=done["run_id"])
    return url_for("campaigns.index", done="single_failed")


def marks_missing(account, design, subject: str, contact) -> list[str]:
    """Los datos que nombra la plantilla y le faltan a esa persona: los nombres
    de sus columnas (y «Nombre») tal como los ve el cliente.

    Las marcas se buscan en el correo ya armado y en el asunto, así vale para
    las tres clases de pieza. A quien no está en Contactos le falta todo lo
    que se nombre, menos su correo."""
    html = sender.Piece(design, single=True).html(plan=None, unsubscribe_url="")
    used = set(fields.MARK.findall(html + " " + subject))
    if not used:
        return []
    lacking = []
    values = fields.values_of(contact)
    # Una lista puede ir vacía (octubre de 2026): no falta.
    for one in fields.scalars(accounts.fields_of(account)):
        if one["key"] in used and not values.get(one["key"]):
            lacking.append(one["label"])
    for key, (where, label) in fields.BUILT_IN.items():
        if key in used and not (contact or {}).get(where):
            lacking.append(label)
    return lacking


@bp.route("/campaigns/<raw>", methods=["GET", "POST"])
def edit(raw):
    """Cambiar una campaña que todavía no ha empezado a salir."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    db = get_db()
    campaign_id = as_id(raw)
    found = (campaigns.by_id(db, account["_id"], campaign_id)
             if campaign_id else None)
    if found is None or found.get("kind") == campaigns.SINGLE:
        return redirect(url_for("campaigns.index"))
    if not campaigns.editable(found):
        return redirect(url_for("campaigns.index", done="late"))

    errors: dict[str, str] = {}
    rows = None
    if request.method == "POST":
        answer = may_send()
        if answer:
            return answer
        rows = typed_rules()
        if not redraw(rows):
            errors = save(db, account, found)
            if not errors:
                return redirect(url_for("campaigns.index", saved=1))

    return render_template(
        "campaigns/edit.html", section="envios",
        **shared(db, account, errors=errors, form=request.form,
                 campaign=found, rule_rows=rule_rows(found, rows),
                 # Vuelve a salir en la hora de quien la mira.
                 when=clock.local(found["scheduled_at"]).strftime(WHEN_FORMAT)))


# Cuántas personas por página en el detalle de un envío.
PER_PAGE = 50


@bp.route("/campaigns/sent")
def sent_list():
    """Enviados (octubre de 2026): todo lo que salió, campañas e individuales,
    lo último arriba. Una línea por envío y no por campaña: la mandada seis
    veces son seis.

    Sale de `campaign_runs`, con el asunto copiado, así que sigue diciendo la
    verdad aunque después se corrija o se borre la campaña. Las cifras son las
    de `events.counts_by_run()`, en personas y en una sola consulta: de una
    campaña se escriben sobre los que salieron (500/551) y de un individual,
    que es una persona, con una marca.
    """
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    sent_runs = runs.for_account(db, account["_id"])
    # Qué individuales llevaban archivo, para decir si lo bajó. Una consulta.
    singles = [one["campaign_id"] for one in sent_runs if one.get("to")]
    with_file = {doc["_id"] for doc in db.campaigns.find(
        {"account_id": account["_id"], "_id": {"$in": singles},
         "download_id": {"$exists": True}}, {"_id": 1})} if singles else set()
    return render_template(
        "campaigns/sent.html", account=account, runs=sent_runs,
        run_counts=events.counts_by_run(
            db, account["_id"], [one["_id"] for one in sent_runs]),
        with_file=with_file, everyone=t("send_all_contacts"))


@bp.route("/campaigns/sent/<raw>")
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
    tag = request.args.get("tag", "")
    tag = tag if tag in known else ""
    search = " ".join(request.args.get("q", "").split())[:100]
    outcome = request.args.get("status", "")
    outcome = outcome if outcome in events.OUTCOMES else ""
    try:
        page = max(1, int(request.args.get("page", "1")))
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
        everyone=t("send_all_contacts"),
        # El correo individual con archivo: una columna más, si lo bajó.
        has_file=bool((campaigns.by_id(db, account["_id"], found["campaign_id"])
                       or {}).get("download_id")))


@bp.route("/campaigns/<raw>/delete", methods=["POST"])
def remove(raw):
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))

    answer = may_send()
    if answer:
        return answer
    if csrf_ok(request.form.get("csrf_token")):
        campaign_id = as_id(raw)
        if campaign_id:
            campaigns.remove(get_db(), account["_id"], campaign_id)
    return redirect(url_for("campaigns.index", deleted=1))


@bp.route("/campaigns/<raw>/send", methods=["GET", "POST"])
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
    answer = may_send()
    if answer:
        return answer

    db = get_db()
    campaign_id = as_id(raw)
    found = (campaigns.by_id(db, account["_id"], campaign_id)
             if campaign_id else None)
    if found is None or found.get("kind") == campaigns.SINGLE:
        return redirect(url_for("campaigns.index"))

    if request.method == "GET":
        design = (None if campaigns.written(found)
                  else designs.by_id(db, account["_id"], found.get("design_id")))
        context = shared(db, account, campaign=found,
                     # Una escrita no tiene pieza guardada: se dice que es su
                     # texto, y se puede mandar (octubre de 2026).
                     piece=({"name": t("send_written_name")} if campaigns.written(found)
                            else design),
                     # De quién sale y a dónde se responde: lo elige la
                     # plantilla, así que se dice aquí, antes de mandar.
                     sending_from=sender.remitente(account, design),
                     sending_reply=sender.reply_to(account, design),
                     going=going_count(db, account, found),
                     already=runs.times(db, account["_id"], found["_id"]))
        # Una plantilla que volvió a borrador frena la campaña (octubre de
        # 2026): se dice antes de pulsar, y no hay botón.
        if designs.is_draft(design):
            context["blocked"] = context["blocked"] + ["draft"]
        return render_template("campaigns/confirm.html", section="envios", **context)

    if not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("campaigns.index"))

    # Volver a mandar una que ya salió empieza por devolver a cero los
    # contadores de la vuelta. Si otra pestaña se adelantó, la consulta no
    # encuentra nada y aquí no se manda dos veces lo mismo.
    if found["status"] == campaigns.SENT:
        if not campaigns.restart(db, account["_id"], found["_id"],
                                 when=accounts.now()):
            return redirect(url_for("campaigns.index", done="late"))
        found = campaigns.by_id(db, account["_id"], found["_id"])

    # La primera tanda sale aquí, con el turno: si lo tiene el proceso en
    # segundo plano, es que ya está saliendo. El resto lo manda él, solo.
    by = "web:" + secrets.token_hex(6)
    if not campaigns.take(db, account["_id"], found["_id"], by):
        return redirect(url_for("campaigns.index", done="busy"))
    try:
        result = sender.run(db, account, campaigns.by_id(db, account["_id"], found["_id"]),
                            lease_by=by)
        if result["left"] and not result["blocked"]:
            campaigns.set_auto(db, account["_id"], found["_id"], True)
    finally:
        campaigns.release(db, account["_id"], found["_id"], by)
    if result["blocked"] == ["busy"]:
        return redirect(url_for("campaigns.index", done="busy"))
    if result["blocked"] == ["filters"]:
        return redirect(url_for("campaigns.index", done="filters"))
    if result["blocked"] == ["draft"]:
        return redirect(url_for("campaigns.index", done="draft"))
    if result["blocked"]:
        return redirect(url_for("campaigns.index", done="blocked"))
    return redirect(url_for("campaigns.index",
                            done="partial" if result["left"] else "all"))


# --------------------------------------------------------------- remitente
#
# De quién salen las campañas y a dónde llegan las respuestas (octubre de 2026:
# varios de cada uno, y cada plantilla elige los suyos). La ve quien puede ver
# las campañas, y la cambia solo el dueño, como la dirección postal: es la
# firma de la empresa.

REPLY_ATTEMPTS = "reply_to_attempts"
REPLY_DEADLINE = "reply_to_expires_at"
# Cuántas veces al día se puede pedir un dominio, comprobarlo o quitarlo: cada
# una es una llamada a Amazon.
DOMAIN_PER_ACCOUNT = (20, 86400)
# Por qué no se pudo agregar o cambiar un remitente, en la frase de la pantalla.
FROM_ERRORS = {"full": "sender_from_full", "domain": "sender_from_domain_bad",
               "local": "sender_local_bad", "taken": "sender_from_taken"}


def sender_screen(db, account, **extra):
    """La pantalla de Remitente. `states` es el «Enviado por» de cada dominio,
    que se pregunta a Amazon al abrirla."""
    states = extra.pop("states", {})
    # El remitente que se está editando: el de «Editar» (`?editar=<id>`), o el
    # que volvió con un error.
    editing = extra.pop("editing", None)
    if editing is None and request.args.get("editar"):
        editing = as_id(request.args.get("editar"))
    domains = [{**one,
                "records": ses_identity.records(one["name"], one.get("dkim_tokens") or []),
                "mail_from_records": ses_identity.mail_from_records(one["name"]),
                "mail_from_domain": ses_identity.mail_from_domain(one["name"]),
                "mail_from_state": states.get(one["name"], ""),
                # DMARC (octubre de 2026): se mira en el DNS, y si falta se pide.
                "dmarc": ses_identity.dmarc_state(one["name"]),
                "dmarc_record": ses_identity.dmarc_record(one["name"])}
               for one in accounts.domains_of(account)]
    mine = accounts.sender_of(account)
    return render_template(
        "campaigns/sender.html", section="envios", account=account, mine=mine,
        sending_domain=Config.SENDING_DOMAIN,
        froms=accounts.froms_of(account), default_from=accounts.default_from(account),
        replies=accounts.reply_tos_of(account), default_reply=accounts.default_reply(account),
        domains=domains, verified=accounts.verified_domains(account),
        limits={"domains": accounts.DOMAIN_LIMIT, "froms": accounts.FROM_LIMIT,
                "replies": accounts.REPLY_LIMIT},
        suggestion=mine.get("handle") or accounts.suggest_handle(
            db, account.get("company_name", "")),
        editing=editing, can_edit=not accounts.is_member(current_account()),
        **extra)


@bp.route("/campaigns/sender", methods=["GET", "POST"])
def sender_page():
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    db = get_db()
    errors: dict[str, str] = {}

    if request.method == "GET":
        # Una cuenta que tiene su usuario y nunca tuvo remitentes los estrena
        # aquí: es la de antes de que hubiera varios.
        if accounts.sender_of(account).get("handle") and "froms" not in accounts.sender_of(account):
            accounts.ensure_base_from(db, account["_id"])
            account = accounts.by_id(db, account["_id"])
        # Un dominio que espera sus registros se mira al abrir la pantalla: no
        # hay quién lo mire a las tres de la mañana. Y el «Enviado por» de
        # cada uno, que a un dominio conectado antes se le pide aquí (octubre de
        # 2026); si Amazon no contesta, la pantalla sale sin decirlo.
        states: dict[str, str] = {}
        changed = False
        for one in accounts.domains_of(account):
            if one.get("status") != accounts.DOMAIN_VERIFIED:
                try:
                    accounts.set_domain_status(db, account["_id"], one["name"],
                                               ses_identity.status(one["name"]))
                    changed = True
                except ses_identity.IdentityError as exc:
                    print(f"  [remitente] {one['name']}: {exc}", flush=True)
            try:
                states[one["name"]] = ses_identity.mail_from(one["name"])
            except ses_identity.IdentityError as exc:
                print(f"  [remitente] MAIL FROM de {one['name']}: {exc}", flush=True)
        if changed:
            # Leída otra vez de la base: la de la sesión es de antes.
            account = accounts.by_id(db, account["_id"])
        return sender_screen(db, account, errors=errors, form={},
                             done=request.args.get("done", ""), states=states)

    if accounts.is_member(current_account()) or not csrf_ok(request.form.get("csrf_token")):
        return redirect(url_for("campaigns.sender_page"))

    action = request.form.get("action", "")
    done = ""
    anchor = ""
    if action == "handle":
        handle = accounts.clean_handle(request.form.get("handle", ""))
        if handle is None:
            errors["handle"] = t("sender_handle_bad", min=accounts.HANDLE_MIN,
                                 max=accounts.HANDLE_MAX)
        elif handle == accounts.sender_of(account).get("handle"):
            return redirect(url_for("campaigns.sender_page", same=1))
        elif not accounts.set_handle(db, account["_id"], handle):
            errors["handle"] = t("sender_handle_taken")
        else:
            done, anchor = "handle", "#handle"

    elif action == "from_add":
        domain = request.form.get("domain", "")
        new_id, wrong = accounts.add_from(db, account, name=request.form.get("name", ""),
                                          local=request.form.get("local", ""),
                                          domain="" if domain == "shared" else domain)
        if new_id is None:
            errors["from"] = t(FROM_ERRORS[wrong], n=accounts.FROM_LIMIT,
                               domain=Config.SENDING_DOMAIN)
        else:
            done, anchor = "from_added", "#remitentes"

    elif action in ("from_edit", "from_remove", "from_default"):
        from_id = as_id(request.form.get("id", ""))
        if action == "from_edit":
            wrong = accounts.update_from(db, account, from_id,
                                         name=request.form.get("name", ""),
                                         local=request.form.get("local", ""))
            if wrong == "same":
                return redirect(url_for("campaigns.sender_page", same=1) + "#remitentes")
            if wrong == "missing":
                return redirect(url_for("campaigns.sender_page"))
            if wrong:
                errors["from_edit"] = t(FROM_ERRORS[wrong], n=accounts.FROM_LIMIT,
                                        domain=Config.SENDING_DOMAIN)
                return sender_screen(db, account, errors=errors, done="",
                                     form=request.form, editing=from_id)
            done, anchor = "from_saved", "#remitentes"
        elif action == "from_remove":
            if accounts.remove_from(db, account, from_id):
                # Las plantillas que salían de él vuelven al predeterminado.
                designs.forget_sending(db, account["_id"], froms=[from_id])
                done, anchor = "from_removed", "#remitentes"
        elif accounts.set_from_default(db, account, from_id):
            done, anchor = "from_default", "#remitentes"
        if not done:
            return redirect(url_for("campaigns.sender_page"))

    elif action == "reply":
        typed = request.form.get("reply_to", "").strip()
        address = clean_email(typed) if typed else None
        replies = accounts.reply_tos_of(account)
        if not address:
            errors["reply"] = t("error_email_invalid")
        elif address.lower() in [one.lower() for one in replies]:
            errors["reply"] = t("sender_reply_same")
        elif len(replies) >= accounts.REPLY_LIMIT:
            errors["reply"] = t("sender_reply_full", n=accounts.REPLY_LIMIT)
        elif address.lower().rsplit("@", 1)[-1] in accounts.verified_domains(account):
            # Una dirección de uno de sus dominios ya está probada: el dominio
            # entero se probó suyo con sus registros DNS.
            accounts.add_reply_to(db, account["_id"], address)
            done, anchor = "reply", "#reply"
        elif not rate_limit(db, f"reply:mail:{accounts.normalize_email(address)}",
                            *REGISTER_PER_EMAIL) \
                or not rate_limit(db, f"reply:account:{account['_id']}",
                                  *REGISTER_PER_EMAIL):
            # Cada intento le manda un correo a una dirección escrita a mano:
            # con tope, nadie llena el buzón de un tercero desde aquí.
            errors["reply"] = t("error_too_many")
        else:
            accounts.start_reply_to(db, account["_id"], address)
            code = tokens.issue(db, account["_id"], tokens.REPLY_TO)
            notices.reply_to_code(account, code=code, to=address,
                                  minutes=Config.CONFIRMATION_CODE_MINUTES)
            session[REPLY_ATTEMPTS] = 0
            session[REPLY_DEADLINE] = (accounts.now() + timedelta(
                minutes=Config.CONFIRMATION_CODE_MINUTES)).isoformat()
            return redirect(url_for("campaigns.reply_code"))

    elif action in ("reply_remove", "reply_default"):
        address = request.form.get("address", "")
        if action == "reply_remove" and accounts.remove_reply_to(db, account, address):
            designs.forget_sending(db, account["_id"], replies=[address])
            done, anchor = "reply_removed", "#reply"
        elif action == "reply_default" and accounts.set_reply_default(db, account, address):
            done, anchor = "reply_default", "#reply"
        else:
            return redirect(url_for("campaigns.sender_page"))

    elif action in ("domain", "check", "remove"):
        name = request.form.get("domain", "")
        found = accounts.domain_of(account, name)
        if action != "domain" and found is None:
            return redirect(url_for("campaigns.sender_page"))
        if not rate_limit(db, f"domain:account:{account['_id']}", *DOMAIN_PER_ACCOUNT):
            errors["domain"] = t("error_too_many")
        elif action == "domain":
            domain = accounts.clean_domain(name)
            if domain is None:
                errors["domain"] = t("sender_domain_bad")
            elif accounts.domain_of(account, domain) is not None:
                errors["domain"] = t("sender_domain_mine")
            elif len(accounts.domains_of(account)) >= accounts.DOMAIN_LIMIT:
                errors["domain"] = t("sender_domain_full", n=accounts.DOMAIN_LIMIT)
            elif db.accounts.find_one({"sender.domains.name": domain}, {"_id": 1}):
                # Antes de hablar con Amazon: el dominio de otra cuenta no se
                # crea ni se toca desde aquí.
                errors["domain"] = t("sender_domain_taken")
            else:
                try:
                    created = ses_identity.create(domain)
                except ses_identity.IdentityError as exc:
                    print(f"  [remitente] {domain}: {exc}", flush=True)
                    errors["domain"] = t("sender_domain_failed")
                else:
                    if accounts.add_domain(db, account["_id"], domain, created):
                        done, anchor = "domain", "#domain"
                    else:
                        errors["domain"] = t("sender_domain_taken")
        elif action == "check":
            try:
                accounts.set_domain_status(db, account["_id"], name,
                                           ses_identity.status(name))
                done, anchor = "check", "#domain"
            except ses_identity.IdentityError as exc:
                print(f"  [remitente] {name}: {exc}", flush=True)
                errors["domain"] = t("sender_domain_failed")
        else:
            try:
                ses_identity.delete(name)
            except ses_identity.IdentityError as exc:
                print(f"  [remitente] {name}: {exc}", flush=True)
                errors["domain"] = t("sender_domain_failed")
            else:
                # Con el dominio se van sus remitentes y los «Responder a» que
                # solo él probaba; las plantillas que los usaban vuelven al
                # predeterminado.
                gone = accounts.remove_domain(db, account, name)
                designs.forget_sending(db, account["_id"], froms=gone["froms"],
                                       replies=gone["replies"])
                done, anchor = "removed", "#domain"

    if done:
        return redirect(url_for("campaigns.sender_page", done=done) + anchor)
    return sender_screen(db, account, errors=errors, done="", form=request.form)


@bp.route("/campaigns/sender/records/<domain>.txt")
def sender_records(domain):
    """Los registros de un dominio propio como archivo de zona, para importarlos
    de una vez en el proveedor de DNS que lo permita (Cloudflare, Route 53 y
    otros) en lugar de copiarlos uno por uno. Los ve quien ve la
    pantalla del remitente; un dominio que no es de la cuenta no tiene
    archivo."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    found = accounts.domain_of(account, domain)
    if found is None or not found.get("dkim_tokens"):
        abort(404)
    text = ses_identity.zone_file(
        found["name"], found["dkim_tokens"],
        dmarc=ses_identity.dmarc_state(found["name"]) == ses_identity.DMARC_MISSING)
    name = f"registros-dns-{found['name']}.txt"
    return Response(text, mimetype="text/plain", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "no-store"})


@bp.route("/campaigns/sender/code", methods=["GET", "POST"])
def reply_code():
    """El código que llegó al «Responder a» nuevo. Hasta que entra, las
    respuestas siguen llegando a donde iban."""
    account = signed_in()
    if account is None:
        return redirect(url_for("auth.login"))
    waiting = accounts.sender_of(account).get("reply_to_pending")
    if accounts.is_member(current_account()) or not waiting:
        return redirect(url_for("campaigns.sender_page"))

    db = get_db()
    errors: dict[str, str] = {}
    if request.method == "POST":
        typed = "".join(request.form.getlist("code"))
        if not csrf_ok(request.form.get("csrf_token")):
            errors["form"] = t("error_csrf")
        elif not rate_limit(db, f"reply:ip:{client_ip()}", *CONFIRM_PER_IP):
            errors["form"] = t("error_too_many")
        else:
            attempts = session.get(REPLY_ATTEMPTS, 0) + 1
            session[REPLY_ATTEMPTS] = attempts
            reason, doc = tokens.check(db, account["_id"], typed, tokens.REPLY_TO)
            if reason in (tokens.UNKNOWN, tokens.INVALID) \
                    and attempts >= tokens.MAX_ATTEMPTS:
                reason = tokens.TOO_MANY
            if reason == tokens.VALID and not tokens.spend(db, doc):
                reason = tokens.USED
            if reason == tokens.VALID:
                accounts.add_reply_to(db, account["_id"], waiting)
                return redirect(url_for("campaigns.sender_page", done="reply") + "#reply")
            errors["form"] = t({tokens.USED: "error_code_used",
                                tokens.TOO_MANY: "error_code_too_many"}.get(
                                    reason, "error_code_invalid"))

    return render_template("campaigns/sender-code.html", section="envios",
                           errors=errors, waiting=waiting,
                           minutes=Config.CONFIRMATION_CODE_MINUTES,
                           left=seconds_left(REPLY_DEADLINE))
