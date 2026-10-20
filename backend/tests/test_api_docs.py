"""La documentación de la API no puede mentir (octubre de 2026).

`api_spec.py` es la descripción que sirve `/api/v1/openapi.json` y de la que
sale `sobreala.com/api/`. Estas pruebas la comparan con lo que de verdad
responde la API: cada ruta descrita existe con ese método y ese permiso, y cada
ruta que existe está descrita. Cada código de error tiene su frase en
`i18n.py` y su fila en la página, y nada de lo que se lee lleva raya larga.
"""

from __future__ import annotations

import re
from pathlib import Path

import api_spec
from blueprints.api.core import ROUTES
from i18n import TEXTS

ROOT = Path(__file__).resolve().parents[2]


def rutas_de_flask() -> set[tuple[str, str, str]]:
    out = set()
    for meta in ROUTES.values():
        path = re.sub(r"<(?:[a-z]+:)?([a-z_]+)>", r"{\1}", meta["rule"])
        path = path[len("/api/v1"):]
        for method in meta["methods"]:
            out.add((method, path, meta["scope"]))
    return out


def rutas_descritas() -> set[tuple[str, str, str]]:
    return {(one["method"], one["path"], one["scope"]) for one in api_spec.endpoints()}


def test_cada_ruta_esta_descrita_y_cada_descrita_existe(app):
    reales = rutas_de_flask()
    descritas = rutas_descritas()
    assert reales - descritas == set(), f"sin describir: {sorted(reales - descritas)}"
    assert descritas - reales == set(), f"descritas y no existen: {sorted(descritas - reales)}"


def test_cada_permiso_existe():
    from models import api_key as api_keys

    nombres = {code for code, _, _ in api_spec.SCOPES}
    assert nombres == set(api_keys.SCOPES)
    for one in api_spec.endpoints():
        assert one["scope"] in nombres | {api_spec.ANY, api_spec.PUBLIC}, one["path"]


def test_cada_error_tiene_su_frase():
    for code, status, desc in api_spec.ERRORS:
        assert "api_error_" + code in TEXTS, code
        assert 400 <= status < 600 and desc


def test_los_errores_que_se_usan_estan_descritos():
    """Cada `fail("…")` o `error_response("…")` del código de la API está en la
    tabla de errores de la documentación."""
    descritos = {code for code, _, _ in api_spec.ERRORS}
    usados = set()
    for archivo in (ROOT / "backend" / "blueprints" / "api").glob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        usados |= set(re.findall(r'(?:fail|error_response)\(\s*"([a-z_]+)"', texto))
    assert usados - descritos == set(), sorted(usados - descritos)


def test_openapi_tiene_todas_las_rutas():
    paths = api_spec.openapi()["paths"]
    for one in api_spec.endpoints():
        assert one["method"].lower() in paths[one["path"]]


def test_la_pagina_del_sitio_tiene_todas_las_rutas():
    pagina = (ROOT / "landing" / "api" / "index.html").read_text(encoding="utf-8")
    for one in api_spec.endpoints():
        assert f'id="{api_spec.anchor(one)}"' in pagina, one["path"]
    assert 'href="/api/"' in (ROOT / "landing" / "index.html").read_text(encoding="utf-8")


def test_nada_de_lo_que_se_lee_lleva_raya_larga():
    textos = [value for key, value in TEXTS.items()
              if isinstance(value, str) and key.startswith(("api_", "mail_api_", "dash_api"))]
    textos.append((ROOT / "landing" / "api" / "index.html").read_text(encoding="utf-8"))
    textos += [str(one) for one in api_spec.GUIDES]
    textos += [str(one) for one in api_spec.GROUPS]
    textos += [desc for _, _, desc in api_spec.ERRORS]
    for texto in textos:
        assert "—" not in texto, texto[:120]
