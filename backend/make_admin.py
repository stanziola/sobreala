#!/usr/bin/env python3
"""Dar o quitar el rol de administrador a una cuenta.

Existe porque el primer administrador no se puede aprobar a sí mismo: alguien
tiene que escribir ese campo una vez desde fuera. Después, todo se hace desde
el panel.

    python backend/make_admin.py tu@correo.com
    python backend/make_admin.py tu@correo.com --quitar
    python backend/make_admin.py --lista

Lee el .env como la aplicación, así que apunta a la misma base de datos que
tengas configurada. Para tocar la de producción, MONGODB_URI tiene que ser la
de producción.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config          # noqa: E402
from db import get_db              # noqa: E402
from models import account as accounts  # noqa: E402


def listar(db) -> int:
    admins = list(db.accounts.find({"role": accounts.ADMIN}))
    if not admins:
        print("No hay ninguna cuenta con rol de administrador.")
        return 0
    print(f"{len(admins)} cuenta(s) con rol de administrador:")
    for cuenta in admins:
        print(f"  {cuenta['email']}  ({cuenta.get('company_name', '')})")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", nargs="?", help="correo de la cuenta")
    parser.add_argument("--quitar", action="store_true",
                        help="quitarle el rol en vez de dárselo")
    parser.add_argument("--lista", action="store_true",
                        help="enseñar quién lo tiene y salir")
    args = parser.parse_args(argv)

    db = get_db()
    print(f"Base de datos: {Config.MONGODB_DB}")

    if args.lista:
        return listar(db)
    if not args.email:
        parser.error("hace falta un correo, o --lista")

    cuenta = accounts.by_email(db, args.email)
    if cuenta is None:
        print(f"No existe ninguna cuenta con {args.email}.")
        print("Regístrala primero desde /registro y confirma el correo.")
        return 1

    # Un administrador que no confirmó su dirección no puede recuperar su
    # propia cuenta, y es la que más falta hace poder recuperar.
    if not accounts.is_confirmed(cuenta):
        print(f"La cuenta {args.email} todavía no confirmó su correo.")
        print("Confírmala antes de darle el rol.")
        return 1

    if args.quitar:
        accounts.set_role(db, cuenta["_id"], None)
        print(f"Listo: {args.email} ya no es administrador.")
        return 0

    if accounts.is_admin(cuenta):
        print(f"{args.email} ya era administrador. No se cambió nada.")
        return 0

    accounts.set_role(db, cuenta["_id"], accounts.ADMIN)
    print(f"Listo: {args.email} es administrador.")
    if not accounts.two_factor_on(cuenta):
        print()
        print("Falta un paso: esa cuenta no tiene verificación en dos pasos, y")
        print("el panel de administración la exige. Actívala desde")
        print("Configuración → Seguridad antes de entrar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
