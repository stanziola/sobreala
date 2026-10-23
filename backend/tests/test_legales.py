"""Lo que dicen los textos legales es lo que hace el producto (octubre de 2026).

Antes de pedir la producción de Amazon SES se revisaron los términos, la
privacidad y la ayuda: los umbrales de la pausa decían una cosa en un sitio y
otra en otro, había un tope de 48 horas que no existía y una copia de 30 días
al cerrar la cuenta que tampoco. Estas pruebas fijan que digan lo mismo que el
código, y que esté la dirección para reportar abusos.
"""

from __future__ import annotations

from pathlib import Path

from services import reputation

LANDING = Path(__file__).resolve().parent.parent.parent / "landing"


def pagina(nombre: str) -> str:
    return (LANDING / nombre / "index.html").read_text(encoding="utf-8")


def test_los_umbrales_de_la_pausa_son_los_del_codigo():
    rebotes = f"{reputation.BOUNCE_LIMIT * 100:g} %"
    quejas = f"{reputation.COMPLAINT_LIMIT * 100:g} %"
    terminos, ayuda = pagina("terms"), pagina("ayuda")
    for texto in (terminos, ayuda):
        assert rebotes in texto and quejas in texto
    assert f"{reputation.WINDOW_DAYS} días" in terminos
    # El 0.05 % de antes no queda (el número suelto sale en el dibujo del ala).
    assert "0.05%" not in terminos and "0.05 %" not in terminos


def test_no_promete_lo_que_no_existe():
    terminos, privacidad = pagina("terms"), pagina("privacy")
    assert "48 horas" not in terminos
    assert "en construcción" not in terminos
    assert "durante 30 días" not in terminos
    assert "vuelve a suscribirse" not in privacidad
    assert "anotamos si lo bajó" not in privacidad
    assert "almacenamiento de las imágenes" not in privacidad
    assert "Inglés (pronto)" not in pagina("")


def test_esta_la_direccion_para_reportar_abusos_y_la_politica_de_uso():
    terminos, privacidad = pagina("terms"), pagina("privacy")
    assert "abuse@sobreala.com" in terminos and "abuse@sobreala.com" in privacidad
    for frase in ("CAN-SPAM", "phishing", "demuestres ese", "Amazon SES"):
        assert frase in terminos, frase
