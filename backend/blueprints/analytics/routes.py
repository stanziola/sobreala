"""Bajarse lo que enseña Estadísticas: en CSV para la hoja de cálculo y en PDF
para mandarlo a una junta directiva.

`docs/pricing.md` los promete en los tres planes, y esta carpeta llevaba vacía
desde el primer día.

**Lo que se baja es exactamente lo que se está viendo**: las dos rutas llaman al
mismo `services/stats.screen()` que dibuja la pantalla, con los mismos filtros
de la dirección. Así no hay dos cuentas distintas que puedan separarse, que es
la misma razón por la que la pantalla del cliente y la del administrador son una
sola plantilla.

Solo el cliente. El administrador mira las cifras de quien elija con un selector,
y bajarse el archivo de un cliente es otra decisión, no un efecto secundario de
poder mirarlas.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, Response, redirect, request, url_for

from blueprints.auth.routes import (current_account, current_workspace, needs,
                                    not_for_admins)
from db import get_db
from i18n import at_moment, t
from models import account as accounts
from models import image as images
from services import stats

bp = Blueprint("analytics", __name__)


def _screen():
    """La misma pantalla que /dashboard, o la respuesta que dice que no.

    Devuelve `(cuenta, datos)` o `(None, respuesta)`: las dos rutas hacen la
    misma comprobación y sería fácil que una se quedara sin ella.
    """
    account = current_account()
    if account is None:
        return None, redirect(url_for("auth.login"))
    answer = not_for_admins(account) or needs(account, accounts.STATS)
    if answer:
        return None, answer
    company = current_workspace()
    return company, stats.screen(
        get_db(), company,
        period=request.args.get("period", ""),
        tag=request.args.get("tag", ""),
        campaign=request.args.get("campaign", ""))


def _change(one) -> str:
    """El cambio de una cifra, como se lee en la pastilla."""
    change = one.get("change")
    if not change:
        return ""
    return f"{'+' if change['up'] else '-'}{change['pct']} %"


def _value(one) -> str:
    return f"{one['pct']} %" if one["pct"] is not None else str(one["n"])


def _blocks(company, data) -> list[tuple[str, list[list[str]], str]]:
    """Las tablas del archivo, en el mismo orden que la pantalla.

    Cada una con su título y con la frase que se escribe **en su lugar** cuando
    no hay filas: una tabla con solo la cabecera no dice nada. Un solo sitio
    para las dos rutas: el CSV y el PDF no pueden traer cosas distintas.
    """
    where = [
        [t("export_account"), company.get("company_name", "")],
        [t("stats_period"), t("stats_period_" + data["period"])],
        [t("export_compared"), data["before"]],
        [t("stats_tag"), data["tag"] or t("stats_all_tags")],
        [t("stats_campaign"), _campaign_name(data) or t("stats_all_campaigns")],
        [t("export_made"), at_moment(stats.events.now())],
    ]

    rates = [[t("export_figure"), t("export_value"), t("export_of"),
              t("export_change")]]
    for one in data["rates"]:
        rates.append([t("stats_" + one["key"]), _value(one),
                      f"{one['n']} / {one['of']}" if one["of"] else "",
                      _change(one)])

    series = [[t("export_slot"), t("stats_sent"), t("stats_bounce"),
               t("stats_open"), t("stats_click")]]
    for sending, engaging in zip(data["sending"]["rows"], data["engaging"]["rows"]):
        series.append([sending["tip"],
                       str(sending["values"]["sent"]),
                       str(sending["values"]["bounce"]),
                       str(engaging["values"]["open"]),
                       str(engaging["values"]["click"])])

    best = [[t("stats_best_subject"), t("stats_best_when"), t("stats_best_sent"),
             t("stats_best_open"), t("stats_best_click")]]
    for one in data["best"]:
        best.append([one["subject"], at_moment(one["at"]) if one["at"] else "",
                     str(one["sent"]),
                     "" if one["open"] is None else f"{one['open']} %",
                     "" if one["click"] is None else f"{one['click']} %"])

    links = [[t("stats_links_title"), t("stats_links_who")]]
    for one in data["links"]:
        links.append([one["link"], str(one["n"])])

    return [
        (t("export_title"), where, ""),
        (t("stats_rates_title"), rates, ""),
        (t("stats_sending_title"), series, ""),
        (t("stats_best_title"), best, t("stats_best_none")),
        (t("stats_links_title"), links, t("stats_links_none")),
    ]


def _campaign_name(data) -> str:
    for one in data["campaigns"]:
        if one["_id"] == data["campaign"]:
            return one["subject"]
    return ""


@bp.route("/dashboard/export.csv")
def as_csv():
    company, data = _screen()
    if company is None:
        return data

    buffer = io.StringIO()
    # Punto y coma y BOM, como el de contactos: es lo que hace que Excel en
    # español abra el archivo en columnas y sin partir los acentos.
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    buffer.write("﻿")
    for title, rows, nothing in _blocks(company, data):
        writer.writerow([title])
        if len(rows) > 1 or not nothing:
            writer.writerows(rows)
        else:
            writer.writerow([nothing])
        writer.writerow([])

    name = f"estadisticas-{date.today().isoformat()}.csv"
    return Response(buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="{name}"'})


def _logo_flowable(company, mm):
    """El logo como imagen del PDF, a 14 mm de alto y con su proporción; None
    si no tiene o no se puede leer."""
    name = accounts.logo_of(company)
    if not name:
        return None
    raw = images.data_of(get_db(), company["_id"], name)
    if not raw:
        return None
    try:
        from PIL import Image as Picture
        from reportlab.platypus import Image as PdfImage

        with Picture.open(io.BytesIO(raw)) as opened:
            width, height = opened.size
        tall = 14 * mm
        wide = min(tall * width / max(height, 1), 60 * mm)
        return PdfImage(io.BytesIO(raw), width=wide, height=wide * height / max(width, 1),
                        hAlign="LEFT")
    except Exception:  # noqa: BLE001 - sin logo es mejor que sin PDF
        return None


@bp.route("/dashboard/export.pdf")
def as_pdf():
    company, data = _screen()
    if company is None:
        return data

    # Perezoso a propósito: reportlab solo hace falta aquí, y arrancar el panel
    # sin él tiene que seguir funcionando.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    buffer = io.BytesIO()
    paper = SimpleDocTemplate(buffer, pagesize=letter,
                              leftMargin=18 * mm, rightMargin=18 * mm,
                              topMargin=16 * mm, bottomMargin=16 * mm,
                              title=t("export_title"))
    styles = getSampleStyleSheet()
    small = styles["BodyText"]
    small.fontSize = 8.5
    small.leading = 11

    story = []
    # El logo de la empresa arriba, si tiene (octubre de 2026): el PDF es para
    # pasárselo a una junta, y así se ve de quién es. Nunca rompe el archivo.
    logo = _logo_flowable(company, mm)
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 5 * mm))
    for title, rows, nothing in _blocks(company, data):
        story.append(Paragraph(f"<b>{title}</b>", styles["Heading3"]))
        if len(rows) == 1 and nothing:
            story.append(Paragraph(nothing, small))
            story.append(Spacer(1, 7 * mm))
            continue
        table = Table([[Paragraph(cell, small) for cell in row] for row in rows],
                      hAlign="LEFT")
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFCFD4")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F4F5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(t("stats_rates_note"), small))
    paper.build(story)

    name = f"estadisticas-{date.today().isoformat()}.pdf"
    return Response(buffer.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition":
                             f'attachment; filename="{name}"'})
