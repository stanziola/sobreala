"""Crear los clientes de Amazon de uno en uno (octubre de 2026).

Desde que gunicorn atiende con hilos, varias peticiones pueden querer hablar
con SES a la vez. Un cliente de boto3 ya creado se puede usar desde varios
hilos, pero **crearlo no**: la sesión por omisión no lo aguanta, y dos hilos
creando a la vez fallan a veces con un error que no se repite. Así que se crean
con candado, de a uno. Se sigue creando uno por llamada, como antes.

Importado aquí y no arriba de cada módulo, para que desarrollar sin boto3
(`MAIL_BACKEND=file`) nunca lo necesite.
"""

from __future__ import annotations

import threading

from config import Config

_lock = threading.Lock()


def client(service: str):
    """Un cliente de ese servicio (`ses`, `sesv2`) en la región de SES."""
    import boto3

    with _lock:
        return boto3.client(service, region_name=Config.AWS_REGION)
