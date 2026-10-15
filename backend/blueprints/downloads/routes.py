"""Bajar el archivo de un correo individual, sin sesión (octubre de 2026).

La otra punta del enlace que `services/downloads.py` mete en el correo. Como la
baja, se abre **sin sesión**: quien llega es la persona que recibió el correo.

**Abrir no descarga, pero la página baja el archivo sola** (octubre de 2026).
El GET enseña una página propia, sin la barra de Sobreala, con el logo y el
nombre de quien lo manda, el archivo y su tamaño; un guion manda el POST al
cargar, y la página dice que ya se puede cerrar. El POST entrega el archivo y
anota el evento `download`, uno por envío y persona. Los escáneres de correo
abren los enlaces pero no ejecutan guiones (casi ninguno): así «lo descargó»
sigue queriendo decir que alguien lo pidió. Sin JavaScript queda el botón.

Un enlace con la firma mala da 404. Uno bueno de un archivo vencido (más de 30
días) o borrado dice que ya no está, con 410.
"""

from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, Response, abort, render_template, request

from db import get_db
from models import account as accounts
from models import campaign as campaigns
from models import download as downloads_model
from models import event as events
from services import downloads
from services.security import csrf_ok

bp = Blueprint("downloads", __name__)


@bp.route("/d/<token>", methods=["GET", "POST"])
def page(token):
    download_id = downloads.id_of(token)
    if download_id is None:
        abort(404)
    db = get_db()
    found = downloads_model.by_id(db, download_id, with_data=request.method == "POST")
    if found is None:
        return render_template("downloads/gone.html"), 410

    account = accounts.by_id(db, found["account_id"]) or {}
    logo = accounts.logo_of(account)
    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            return render_template(
                "downloads/page.html", file=found, company=account.get("company_name", ""),
                logo=logo, size=downloads.size_label(found["size"]), token=token), 400
        campaign = campaigns.by_id(db, found["account_id"], found["campaign_id"]) or {}
        events.record(db, found["account_id"], kind=events.DOWNLOAD,
                      campaign_id=found["campaign_id"], run_id=campaign.get("run_id"),
                      email=campaign.get("to", ""))
        name = found["name"]
        return Response(bytes(found["data"]), mimetype=found["content_type"], headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
            "Cache-Control": "private, no-store"})

    return render_template(
        "downloads/page.html", file=found, company=account.get("company_name", ""),
        logo=logo, size=downloads.size_label(found["size"]), token=token)
