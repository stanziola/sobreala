"""Servir las imágenes que los clientes ponen en sus plantillas.

**Es la única dirección del panel que no pide sesión, y tiene que serlo**: quien
la abre no es el cliente, es el lector de correo de cada persona que recibió la
campaña. Lo que protege una imagen no es una sesión sino su nombre, que son
dieciséis bytes al azar.

Va en su propio blueprint y no en `designs/` porque aquel devuelve a los
administradores a `/admin` y exige sesión en todas sus rutas: una imagen que
hiciera eso saldría rota en el correo.

La respuesta se puede guardar un año. El nombre es único e irrepetible —cambiar
una imagen es subir otra, con otro nombre—, así que no hay forma de que lo
guardado quede viejo. Es lo que hace que las aperturas repetidas las conteste
Cloudflare desde su borde y no lleguen ni al servidor ni a la base.
"""

from __future__ import annotations

from flask import Blueprint, Response, abort

from db import get_db
from models import image as images
from services import imaging

bp = Blueprint("media", __name__)

# Un año, que es el máximo que respetan las cachés.
CACHE = "public, max-age=31536000, immutable"


@bp.route("/img/<name>")
def image(name):
    # Se comprueba la forma antes de preguntarle a la base: así una dirección
    # inventada no llega ni a ser una consulta.
    if not imaging.valid_name(name):
        abort(404)
    found = images.by_name(get_db(), name)
    if found is None:
        abort(404)

    answer = Response(bytes(found["data"]), mimetype=found["mime"])
    answer.headers["Cache-Control"] = CACHE
    return answer
