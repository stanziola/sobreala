"""Que ningún archivo generado se quede viejo sin que nadie se entere.

El sitio público y el CSS del panel no se escriben a mano: salen de
`landing/src/`, de `backend/static/css/_panel.src.css` y de `brand/`. Editar la
fuente y olvidar regenerar no rompe nada, no falla nada y llega al despliegue en
silencio. Ya pasó: la fila de «Contactos» se agregó a la plantilla del sitio y
las cuatro páginas publicadas se quedaron sin ella.

Estas dos pruebas convierten ese olvido en un error visible. No escriben nada:
los generadores producen todo en un directorio temporal y comparan.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def relativas(rutas):
    return sorted(str(p.relative_to(ROOT)) for p in rutas)


def test_el_sitio_publicado_esta_al_dia():
    sys.path.insert(0, str(ROOT / "landing"))
    import build_site

    viejos = build_site.check()
    assert not viejos, (
        "Estos archivos del sitio se quedaron viejos: "
        f"{relativas(viejos)}. Corre: python landing/build_site.py")


def test_los_archivos_del_panel_estan_al_dia():
    import build_assets

    viejos = build_assets.check()
    assert not viejos, (
        "Estos archivos del panel se quedaron viejos: "
        f"{relativas(viejos)}. Corre: python backend/build_assets.py")


def test_planes_ya_no_vende_complementos():
    """Las recargas y las piezas adicionales se dejaron de vender: ni en el
    documento de precios ni en la página de planes."""
    precios = (ROOT / "docs" / "pricing.md").read_text(encoding="utf-8")
    planes = (ROOT / "landing" / "index.html").read_text(encoding="utf-8")
    for texto in ("Recarga de 1,000 correos", "Diseño de pieza HTML adicional"):
        assert texto not in precios
        assert texto not in planes
    assert "al recargar" not in planes
