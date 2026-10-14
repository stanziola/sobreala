"""Tres planes, el pie según el plan y la dirección de cada cliente.

Lo que se fija aquí: que Corporativo ya no existe en ningún lado, que el sitio no
ofrece soporte por plan ni diseño como servicio, que el pie del Básico lleva el
ala de Sobreala y el de los demás no, y que la dirección postal del pie es la
de cada cliente y sin ella no se envía.
"""

from __future__ import annotations

from pathlib import Path

from models import account as accounts
from services import plans, render, sender
from test_campaigns import catch, make, ready, send_it
from test_designs import csrf, inside

ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------ los planes

def test_quedan_tres_planes_y_todos_se_compran():
    assert list(plans.PLANS) == ["basico", "negocio", "empresa"]
    assert not plans.buyable("corporativo")
    assert all(plans.buyable(one) for one in plans.PLANS)
    assert "corporativo" not in accounts.PLAN_CONTACTS


def test_el_sitio_no_ofrece_corporativo_ni_soporte_ni_diseno():
    precios = (ROOT / "docs" / "pricing.md").read_text(encoding="utf-8")
    assert "Corporativo" not in precios
    assert "| Soporte |" not in precios
    assert "Diseño personalizado de tu correo" not in precios

    for pagina in ("", "terms"):
        html = (ROOT / "landing" / pagina / "index.html").read_text(encoding="utf-8")
        assert "Corporativo" not in html, pagina
        assert "Plantillas personalizadas" not in html, pagina
        assert "diseñamos la pieza" not in html.lower(), pagina
        assert "diseño de las piezas de correo" not in html.lower(), pagina
    planes = (ROOT / "landing" / "index.html").read_text(encoding="utf-8")
    assert ">Soporte<" not in planes


def test_el_html_propio_ya_no_se_ofrece_en_ningun_lado():
    """Se quitó en septiembre de 2026: las plantillas se arman en el editor y
    se pasan como el ZIP de un lienzo."""
    precios = (ROOT / "docs" / "pricing.md").read_text(encoding="utf-8")
    assert "Subir tu propio HTML" not in precios
    for pagina in ("index.html", "terms/index.html"):
        html = (ROOT / "landing" / pagina).read_text(encoding="utf-8")
        assert "propio HTML" not in html and "HTML que subas" not in html, pagina


# ------------------------------------------------------------ el pie

def test_el_basico_lleva_el_ala_y_los_demas_nada():
    basico = render.email_from_body("<p>Hola</p>", plan="basico")
    assert "/static/img/email-logo.png" in basico
    assert "Enviado con" in basico
    negocio = render.email_from_body("<p>Hola</p>", plan="negocio")
    assert "email-logo.png" not in negocio and "Enviado con" not in negocio


def test_el_ala_existe_y_es_chica():
    ala = ROOT / "backend" / "static" / "img" / "email-logo.png"
    assert ala.exists() and ala.stat().st_size < 10_000


# ------------------------------------------------------------ la dirección

def test_la_direccion_se_guarda_y_sale_en_el_correo(client, database, outbox,
                                                     monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, postal="", howmany=1)
    assert "postal" in sender.blocked(account)
    assert "Falta la dirección postal" in browser.get("/campaigns").get_data(as_text=True)

    respuesta = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings/account"),
        "address": "  Apartado 0816-00001,   Santiago, Veraguas "})
    assert respuesta.status_code == 302
    cuenta = accounts.by_id(database, account["_id"])
    assert accounts.postal_of(cuenta) == "Apartado 0816-00001, Santiago, Veraguas"
    assert "postal" not in sender.blocked(cuenta)
    assert "Apartado 0816-00001" in browser.get("/settings/account/contact").get_data(as_text=True)

    make(browser, piece)
    send_it(browser, database, account["_id"])
    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "Apartado 0816-00001, Santiago, Veraguas" in cuerpo


def test_una_direccion_vacia_o_larga_no_se_guarda(client, database, outbox):
    """La que trae del registro se queda: una mala no la pisa."""
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    antes = accounts.postal_of(cuenta)
    assert antes
    for mala in ("", "corta", "x" * 201):
        pantalla = browser.post("/settings/account", data={
            "csrf_token": csrf(browser, "/settings/account"),
            "address": mala}).get_data(as_text=True)
        assert "entre 10 y 200 caracteres" in pantalla
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) == antes


def test_sin_testigo_no_se_guarda(client, database, outbox):
    browser = inside(client)
    cuenta = accounts.by_email(database, "ana@ejemplo.com")
    antes = accounts.postal_of(cuenta)
    browser.post("/settings/account", data={"address": "Calle 50, Panamá"})
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) == antes


# ------------------------------------------------------ mensual y anual

def test_las_tarjetas_traen_los_dos_precios_y_nacen_en_mensual():
    """El interruptor no inventa cifras: las dos salen de docs/pricing.md, y la
    página sirve igual sin JavaScript, en mensual."""
    html = (ROOT / "landing" / "index.html").read_text(encoding="utf-8")

    assert 'data-cycle-set="monthly"' in html and 'data-cycle-set="yearly"' in html
    # El anual entre doce, que es lo que se enseña al elegir año.
    for mensual, anual, equivalente in (("15", "144", "12"), ("25", "240", "20"),
                                        ("55", "528", "44")):
        assert f'data-monthly="{mensual}"' in html
        assert f'data-yearly-monthly="{equivalente}"' in html
        # Lo que se cobra al contratar, en los dos ciclos.
        assert f"Total a pagar ahora: ${mensual}" in html
        assert f"Total a pagar ahora: ${anual}" in html
    # Nace con el mensual dibujado: sin el guion, eso es lo que se lee.
    assert '<span data-price>15</span>' in html
    # Y su guion, que va en la portada desde que los planes son una sección
    # suya, no en las páginas legales.
    assert "/assets/js/plans.js" in html
    assert "plans.js" not in (ROOT / "landing" / "terms" / "index.html").read_text(encoding="utf-8")


def test_el_equivalente_mensual_y_el_descuento_salen_del_documento():
    """Ni el equivalente mensual ni el «-20%» están escritos a mano: los dos
    salen de las dos filas de precio de docs/pricing.md."""
    import sys

    sys.path.insert(0, str(ROOT / "landing"))
    import build_site

    precios = build_site.read_pricing()
    for one in precios["plans"]:
        assert one["yearly_monthly"] == round(one["yearly_value"] / 12)
        assert one["yearly_off"] == 20
        # Las tres cifras dan enteras, que es lo que enseña la tarjeta.
        assert one["yearly_value"] == one["monthly_value"] * 12 * 80 // 100
    assert precios["yearly_off"] == "20%"

    html = (ROOT / "landing" / "index.html").read_text(encoding="utf-8")
    assert '<span class="cycle__save">-20%</span>' in html
    # Y el panel lo saca del mismo documento, para la pantalla de contratar.
    assert plans.discount("basico") == 20


def test_el_ciclo_elegido_en_el_sitio_llega_al_panel(client, database, outbox,
                                                     monkeypatch):
    from test_payments import confirm, fake_paypal, inside

    fake_paypal(monkeypatch)
    browser = inside(client)
    confirm(database)

    def resaltado(url):
        """El ciclo del resumen: el que se eligió en /pricing, y es el que se
        manda al pagar."""
        pantalla = browser.get(url).get_data(as_text=True)
        return [one for one in ("monthly", "yearly")
                if f'name="cycle" value="{one}"' in pantalla]

    assert resaltado("/checkout/basico?cycle=yearly") == ["yearly"]
    assert resaltado("/checkout/basico") == ["monthly"]
    # Un valor inventado se lee como mensual, que es lo de siempre.
    assert resaltado("/checkout/basico?cycle=cualquiera") == ["monthly"]
