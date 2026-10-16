"""Entrar, registrarse y sus pasos, a dos columnas (octubre de 2026).

Como la imagen de referencia: a la izquierda, en el azul de la barra, el ala
que lleva al sitio y las funciones principales con los dibujos del sitio, que
rotan (`panel.js`); a la derecha, el formulario. Sin la barra de arriba. Lo que
se fija aquí: que estas pantallas no traigan la barra y sí el lado izquierdo
con sus cuatro funciones, que «Recordarme» vaya en la misma fila que
«¿Olvidaste tu contraseña?», que los proveedores vayan después del formulario
al entrar y antes al registrarse, y que dentro de la cuenta siga la barra.
"""

from __future__ import annotations

from pathlib import Path

from conftest import login, register

from config import Config

PANEL_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "panel.js"


def lado(html: str) -> str:
    return html.split('<aside class="auth__side">')[1].split("</aside>")[0]


def test_sin_la_barra_y_con_las_funciones_a_la_izquierda(client, database):
    pantallas = {url: client.get(url).get_data(as_text=True)
                 for url in ("/login", "/signup", "/recover")}
    register(client, email="nueva@ejemplo.com", abierta=False)
    pantallas["/confirm"] = client.get("/confirm").get_data(as_text=True)
    for url, html in pantallas.items():
        assert '<header class="bar' not in html, url
        izquierda = lado(html)
        # El ala lleva al sitio, como el de la barra.
        assert 'class="bar__brand" href="https://sobreala.com/"' in izquierda, url
        # Las cuatro funciones, con su dibujo; sin JavaScript, la primera.
        assert izquierda.count("data-slide") == 4, url
        assert izquierda.count('class="auth__slide is-on"') == 1, url
        for titulo in ("Tu lista, en orden", "Arma tu correo", "Ahora o cuando quieras",
                       "Mira cómo le fue"):
            assert titulo in izquierda, (url, titulo)
        assert 'class="tour__art"' in izquierda, url
        # Los puntitos los enseña el guion.
        assert '<div class="auth__dots" data-dots hidden>' in izquierda, url
    assert "[data-auth-tour]" in PANEL_JS.read_text(encoding="utf-8")


def test_recordarme_va_al_lado_de_olvidaste(client, database):
    html = client.get("/login").get_data(as_text=True)
    assert "<h1>Hola de nuevo</h1>" in html
    assert '¿Todavía no tienes cuenta?\n  <a href="/signup">Regístrate</a>' in html
    fila = html.split('<div class="auth__row">')[1].split("</div>")[0]
    assert 'name="remember"' in fila and "Recordarme 30 días" in fila
    assert '<a href="/recover">¿Olvidaste tu contraseña?</a>' in fila


def test_los_proveedores_van_despues_al_entrar_y_antes_al_registrarse(
        client, database, monkeypatch):
    monkeypatch.setattr(Config, "GOOGLE_CLIENT_ID", "cliente.apps.googleusercontent.com")
    monkeypatch.setattr(Config, "GOOGLE_CLIENT_SECRET", "secreto")
    entrar = client.get("/login").get_data(as_text=True)
    assert entrar.index('<form method="post"') < entrar.index('class="providers"')
    registro = client.get("/signup").get_data(as_text=True)
    assert registro.index('class="providers"') < registro.index('<form method="post"')
    assert "o con tu correo" in registro


def test_dentro_de_la_cuenta_sigue_la_barra(client, database, outbox):
    register(client)
    login(client)
    html = client.get("/settings/account").get_data(as_text=True)
    assert '<header class="bar' in html and 'class="auth__side"' not in html
