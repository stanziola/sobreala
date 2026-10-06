"""Los tutoriales de /como-funciona: cada paso de landing/tutorials.py tiene su
texto en content.py, sus dos capturas y un punto dentro de la imagen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LANDING = ROOT / "landing"
sys.path.insert(0, str(LANDING))

import content  # noqa: E402
import tutorials  # noqa: E402

DATA = json.loads((LANDING / "tutorials.json").read_text(encoding="utf-8"))
WORDS = {tour["id"]: tour for tour in content.TUTORIALS["tours"]}


def test_cada_recorrido_tiene_sus_textos_y_al_reves():
    assert [tour for tour, _ in tutorials.TOURS] == list(WORDS)
    for tour, steps in tutorials.TOURS:
        assert [s["id"] for s in steps] == list(WORDS[tour]["steps"]), tour


def test_lo_generado_es_de_estos_recorridos():
    """Si alguien cambia un recorrido y no vuelve a correr tutorials.py."""
    assert tutorials.missing() == []
    for tour, steps in tutorials.TOURS:
        assert [s["id"] for s in DATA[tour]] == [s["id"] for s in steps]


def test_cada_punto_cae_dentro_de_su_captura():
    for tour, steps in DATA.items():
        for step in steps:
            if step["spot"] is None:
                continue
            x, y, w, h = step["spot"]
            assert 0 <= x and 0 <= y and w > 0 and h > 0, (tour, step["id"])
            assert x + w <= 100.01 and y + h <= 100.01, (tour, step["id"])


def test_solo_el_ultimo_paso_va_sin_punto():
    for tour, steps in DATA.items():
        assert all(s["spot"] for s in steps[:-1]), tour
        assert steps[-1]["spot"] is None, tour


def test_los_textos_no_llevan_guiones_largos():
    for tour in content.TUTORIALS["tours"]:
        for words in tour["steps"].values():
            assert "—" not in words["do"] + words["why"]
        assert "—" not in tour["done"] + tour["lead"]


def test_la_pagina_trae_todos_los_pasos_sin_guion():
    """Sin JavaScript se leen enteros: cada paso con su captura y su texto."""
    html = (LANDING / "como-funciona" / "index.html").read_text(encoding="utf-8")
    total = sum(len(steps) for steps in DATA.values())
    assert html.count('class="guide-step" data-step') == total
    assert "{n}" not in html and "{total}" not in html
    for tour in WORDS:
        assert f'href="#{tour}"' in html and f'id="{tour}"' in html
