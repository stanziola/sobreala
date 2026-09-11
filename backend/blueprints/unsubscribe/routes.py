"""Darse de baja de las campañas de un cliente.

La otra punta del enlace que `services/unsubscribe.py` mete en cada correo. Es,
con `/img`, lo único del panel que se abre **sin sesión**: quien llega aquí no
es el cliente, es una de las personas a las que le escribió, y no tiene cuenta
ni tiene por qué tenerla.

Dos decisiones que sostienen esta pantalla:

  * **Abrirla no da de baja a nadie.** Los antivirus y los escáneres de correo
    abren los enlaces de los mensajes que revisan; si el GET diera de baja, la
    lista de un cliente se vaciaría sola. Lo que da de baja es el POST.
  * **El POST no lleva testigo, a propósito.** El «cancelar suscripción» que
    enseña Gmail manda un POST directo desde su servidor, sin pasar por la
    página, y no puede traer un testigo nuestro. Lo que autoriza aquí es la
    firma del enlace, que es lo que prueba que ese correo llegó a ese buzón.

La baja queda en `suppressions` con motivo `unsubscribe`, que es el que el
cliente **no puede levantar** desde su panel: solo vuelve quien se vuelva a
suscribir por su cuenta.
"""

from __future__ import annotations

from flask import Blueprint, abort, render_template, request

from db import get_db
from models import account as accounts
from models import suppression as suppressions
from services import unsubscribe

bp = Blueprint("unsubscribe", __name__)


@bp.route("/baja/<token>", methods=["GET", "POST"])
def page(token):
    contact_id = unsubscribe.contact_of(token)
    if contact_id is None:
        abort(404)

    db = get_db()
    contact = db.contacts.find_one({"_id": contact_id})
    if contact is None:
        # El cliente borró el contacto. Que no reciba más es justo lo que se
        # venía a pedir, así que se dice que ya está.
        return render_template("unsubscribe/done.html", email="", company="")

    account = accounts.by_id(db, contact["account_id"])
    company = (account or {}).get("company_name", "")

    if request.method == "POST":
        suppressions.add(db, contact["account_id"], contact["email"],
                         reason=suppressions.UNSUBSCRIBE,
                         source="enlace del correo")
        return render_template("unsubscribe/done.html",
                               email=contact["email"], company=company)

    return render_template(
        "unsubscribe/ask.html", email=contact["email"], company=company,
        token=token,
        already=suppressions.has(db, contact["account_id"], contact["email"]))
